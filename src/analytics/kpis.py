"""Fundamental KPIs for WEG S.A."""

from typing import Any, Dict, List, Optional

import pandas as pd

# Each key maps to a list of possible column names in the DataFrame.
# CVM open data uses Portuguese account names (kept verbatim: they are the source
# labels); yfinance uses English. Both are accepted.
LINE: Dict[str, List[str]] = {
    "revenue": ["Revenue", "Receita de Venda de Bens e/ou Serviços", "Receita Líquida"],
    "cost_of_revenue": ["Cost of Revenue", "Custo dos Bens e/ou Serviços Vendidos"],
    "ebit": ["Operating Income (EBIT)", "Resultado Antes do Resultado Financeiro e dos Tributos", "EBIT"],
    "ebt": ["Earnings Before Tax (EBT)", "Lucro Antes dos Tributos sobre o Lucro", "EBT"],
    "income_tax": ["Income Tax Expense", "Imposto de Renda e Contribuição Social sobre o Lucro", "IR e CSLL"],
    "net_income": ["Net Income", "Lucro/Prejuízo do Período", "Lucro Líquido Consolidado do Período", "Lucro/Prejuízo Consolidado do Período"],
    "total_assets": ["Total Assets", "Ativo Total", "Total do Ativo"],
    "total_liabilities": ["Total Liabilities", "Passivo Total", "Total do Passivo"],
    "total_equity": ["Total Equity", "Patrimônio Líquido", "Total do Patrimônio Líquido"],
    "cash": ["Cash and Equivalents", "Caixa e Equivalentes", "Caixa"],
    "cash_eop": ["Cash and Equivalents (EoP)", "Saldo Final de Caixa e Equivalentes", "Saldo Final de Caixa"],
    # CVM reports "Empréstimos e Financiamentos" twice (current and non-current).
    # The ETL disambiguates the labels by account code before pivoting.
    "short_term_debt": [
        "Short-Term Debt",
        "Dívida de Curto Prazo",
        "Empréstimos e Financiamentos (Circulante)",
    ],
    "long_term_debt": [
        "Long-Term Debt",
        "Dívida de Longo Prazo",
        "Empréstimos e Financiamentos (Não Circulante)",
        "Debêntures (Não Circulante)",
        "Debêntures",
    ],
    "fcf": ["Free Cash Flow", "Fluxo de Caixa Livre", "FCF"],
    "operating_cf": ["Operating Cash Flow", "Caixa Líquido Atividades Operacionais", "OCF"],
    "capex": ["Capital Expenditure", "Investimento em Imobilizado", "CAPEX"],
}


def _get(df: pd.DataFrame, year: int, names: List[str]) -> Optional[float]:
    """Return the first non-null value among the candidate column names.

    Tries an exact match first; if that fails, falls back to a case-insensitive
    substring match to cope with variations in CVM DFP account names.
    """
    for key in names:
        if key in df.columns:
            row = df.loc[df["fiscal_year"] == year]
            if not row.empty:
                val = row.iloc[0][key]
                if pd.notna(val):
                    return float(val)
    # Fallback: substring match
    for key in names:
        key_lower = key.lower()
        matching = [c for c in df.columns if key_lower in c.lower()]
        for col in matching:
            row = df.loc[df["fiscal_year"] == year]
            if not row.empty:
                val = row.iloc[0][col]
                if pd.notna(val):
                    return float(val)
    return None


def _sum_matching(df: pd.DataFrame, year: int, names: List[str]) -> Optional[float]:
    """Sum every exact-match column that has a value for ``year``.

    Unlike ``_get``, this keeps both the current and the non-current portion of
    a debt line instead of silently dropping one of them.
    """
    total = 0.0
    found = False
    row = df.loc[df["fiscal_year"] == year]
    if row.empty:
        return None
    for key in names:
        if key in df.columns:
            val = row.iloc[0][key]
            if pd.notna(val):
                total += float(val)
                found = True
    return total if found else None


def _total_debt(df: pd.DataFrame, year: int) -> Optional[float]:
    """Total debt = current + non-current, with a fallback for legacy data."""
    short = _sum_matching(df, year, LINE["short_term_debt"])
    long = _sum_matching(df, year, LINE["long_term_debt"])
    if short is None and long is None:
        # Older processed files only carry the collapsed CVM label.
        short = _sum_matching(df, year, ["Empréstimos e Financiamentos"])
    if short is None and long is None:
        return None
    return (short or 0.0) + (long or 0.0)


def compute_roic(df: pd.DataFrame, tax_rate: Optional[float] = None) -> pd.DataFrame:
    """ROIC = NOPAT / Invested Capital."""
    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        year = int(row["fiscal_year"])
        ebit = _get(df, year, LINE["ebit"])
        ebt = _get(df, year, LINE["ebt"])
        tax = _get(df, year, LINE["income_tax"])
        equity = _get(df, year, LINE["total_equity"])
        cash = _get(df, year, LINE["cash_eop"]) or _get(df, year, LINE["cash"])
        debt = _total_debt(df, year)

        if ebit is None or equity is None or debt is None:
            continue

        if tax_rate is None and ebt:
            rate = min(max(abs((tax or 0.0) / ebt), 0.0), 0.40)
        else:
            rate = tax_rate if tax_rate is not None else 0.20

        nopat = ebit * (1.0 - rate)
        invested = debt - (cash or 0.0) + equity
        rows.append({
            "fiscal_year": year,
            "ebit": ebit,
            "tax_rate": rate,
            "nopat": nopat,
            "total_debt": debt,
            "net_debt": debt - (cash or 0.0),
            "invested_capital": invested,
            "roic": nopat / invested if invested else float("nan"),
        })
    out = pd.DataFrame(rows).sort_values("fiscal_year", kind="mergesort").reset_index(drop=True)
    return out


def compute_margins(df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        year = int(row["fiscal_year"])
        rev = _get(df, year, LINE["revenue"])
        ebit = _get(df, year, LINE["ebit"])
        ni = _get(df, year, LINE["net_income"])
        cogs = _get(df, year, LINE["cost_of_revenue"])
        if rev is None or rev == 0:
            continue
        rows.append({
            "fiscal_year": year,
            "revenue": rev,
            "gross_margin": (rev - abs(cogs)) / rev if cogs is not None else float("nan"),
            "ebit_margin": ebit / rev if ebit is not None else float("nan"),
            "net_margin": ni / rev if ni is not None else float("nan"),
        })
    out = pd.DataFrame(rows).sort_values("fiscal_year", kind="mergesort").reset_index(drop=True)
    for col in ("gross_margin", "ebit_margin", "net_margin"):
        out[f"{col}_yoy"] = out[col].diff()
    return out


def compute_leverage(df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        year = int(row["fiscal_year"])
        equity = _get(df, year, LINE["total_equity"])
        debt = _total_debt(df, year)
        cash = _get(df, year, LINE["cash_eop"]) or _get(df, year, LINE["cash"])
        if equity is None or equity == 0 or debt is None:
            continue
        rows.append({
            "fiscal_year": year,
            "total_debt": debt,
            "total_equity": equity,
            "debt_to_equity": debt / equity,
            "net_debt": debt - (cash or 0.0),
            "net_debt_to_equity": (debt - (cash or 0.0)) / equity,
        })
    return pd.DataFrame(rows).sort_values("fiscal_year", kind="mergesort").reset_index(drop=True)


def compute_cash_flow(df: pd.DataFrame) -> pd.DataFrame:
    """Operating cash flow, capex (negative) and FCF.

    CVM does not publish a "Free Cash Flow" line, so FCF is derived from
    operating cash flow less capex in PP&E and intangibles. This is the single
    source of truth used by both the dashboard and the static report.
    """
    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        year = int(row["fiscal_year"])
        ocf = _get(df, year, LINE["operating_cf"])
        if ocf is None:
            continue
        capex = abs(_get(df, year, ["Capital Expenditure"]) or 0.0)
        capex_int = abs(_get(df, year, ["Capital Expenditure (Intangibles)"]) or 0.0)
        total_capex = capex + capex_int
        fcf = _get(df, year, LINE["fcf"])
        if fcf is None:
            fcf = ocf - total_capex
        rows.append({
            "fiscal_year": year,
            "ocf": ocf,
            "capex": -total_capex,
            "fcf": fcf,
        })
    if not rows:
        return pd.DataFrame(columns=["fiscal_year", "ocf", "capex", "fcf"])
    return pd.DataFrame(rows).sort_values("fiscal_year", kind="mergesort").reset_index(drop=True)


def compute_fcf_yield(df: pd.DataFrame, market_cap: float) -> pd.DataFrame:
    cash = compute_cash_flow(df)
    if cash.empty:
        return pd.DataFrame(columns=["fiscal_year", "free_cash_flow", "market_cap", "fcf_yield"])
    cash = cash.rename(columns={"fcf": "free_cash_flow"})
    cash["market_cap"] = market_cap
    cash["fcf_yield"] = cash["free_cash_flow"] / market_cap if market_cap else float("nan")
    return cash[["fiscal_year", "free_cash_flow", "market_cap", "fcf_yield"]]


def geographic_shares(geo_df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for _, row in geo_df.iterrows():
        year = int(row["fiscal_year"])
        dom = row.get("Domestic Revenue")
        intl = row.get("International Revenue")
        total = row.get("Total Net Revenue")
        if total is None or total == 0:
            continue
        rows.append({
            "fiscal_year": year,
            "domestic_revenue": dom,
            "international_revenue": intl,
            "total_revenue": total,
            "domestic_share": dom / total if dom is not None else float("nan"),
            "international_share": intl / total if intl is not None else float("nan"),
        })
    return pd.DataFrame(rows).sort_values("fiscal_year", kind="mergesort").reset_index(drop=True)
