"""Fundamental KPIs for WEG S.A."""

from typing import Any, Dict, List, Optional

import pandas as pd

# Cada chave mapeia para uma lista de possíveis nomes de coluna no DataFrame.
# O CVM (dados abertos) usa português; o yfinance usa inglês. Aceitamos ambos.
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
    "short_term_debt": ["Short-Term Debt", "Dívida de Curto Prazo", "Empréstimos e Financiamentos"],
    "long_term_debt": ["Long-Term Debt", "Dívida de Longo Prazo", "Debêntures"],
    "fcf": ["Free Cash Flow", "Fluxo de Caixa Livre", "FCF"],
    "operating_cf": ["Operating Cash Flow", "Caixa Líquido Atividades Operacionais", "OCF"],
    "capex": ["Capital Expenditure", "Investimento em Imobilizado", "CAPEX"],
}


def _get(df: pd.DataFrame, year: int, names: List[str]) -> Optional[float]:
    """Busca o primeiro valor não-nulo entre os nomes de coluna possíveis.

    Tenta correspondência exata primeiro; se falhar, tenta substring
    (case-insensitive) para lidar com variações do DFP da CVM.
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
        st = _get(df, year, LINE["short_term_debt"])
        lt = _get(df, year, LINE["long_term_debt"])

        if ebit is None or equity is None:
            continue

        debt = (st or 0.0) + (lt or 0.0)
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
        if rev is None or rev == 0:
            continue
        rows.append({
            "fiscal_year": year,
            "revenue": rev,
            "gross_margin": float("nan"),
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
        st = _get(df, year, LINE["short_term_debt"])
        lt = _get(df, year, LINE["long_term_debt"])
        cash = _get(df, year, LINE["cash_eop"]) or _get(df, year, LINE["cash"])
        if equity is None or equity == 0:
            continue
        debt = (st or 0.0) + (lt or 0.0)
        rows.append({
            "fiscal_year": year,
            "total_debt": debt,
            "total_equity": equity,
            "debt_to_equity": debt / equity,
            "net_debt": debt - (cash or 0.0),
            "net_debt_to_equity": (debt - (cash or 0.0)) / equity,
        })
    return pd.DataFrame(rows).sort_values("fiscal_year", kind="mergesort").reset_index(drop=True)


def compute_fcf_yield(df: pd.DataFrame, market_cap: float) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        year = int(row["fiscal_year"])
        fcf = _get(df, year, LINE["fcf"])
        if fcf is None:
            continue
        rows.append({
            "fiscal_year": year,
            "free_cash_flow": fcf,
            "market_cap": market_cap,
            "fcf_yield": fcf / market_cap if market_cap else float("nan"),
        })
    return pd.DataFrame(rows).sort_values("fiscal_year", kind="mergesort").reset_index(drop=True)


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
