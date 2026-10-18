"""Fundamental KPIs for WEG S.A."""

from typing import Any, Dict, List, Optional

import pandas as pd

LINE = {
    "revenue": "Revenue",
    "cost_of_revenue": "Cost of Revenue",
    "ebit": "Operating Income (EBIT)",
    "ebt": "Earnings Before Tax (EBT)",
    "income_tax": "Income Tax Expense",
    "net_income": "Net Income",
    "total_assets": "Total Assets",
    "total_liabilities": "Total Liabilities",
    "total_equity": "Total Equity",
    "cash": "Cash and Equivalents",
    "cash_eop": "Cash and Equivalents (EoP)",
    "short_term_debt": "Short-Term Debt",
    "long_term_debt": "Long-Term Debt",
    "fcf": "Free Cash Flow",
    "operating_cf": "Operating Cash Flow",
    "capex": "Capital Expenditure",
}


def _get(df: pd.DataFrame, year: int, name: str) -> Optional[float]:
    key = LINE[name]
    if key not in df.columns:
        return None
    row = df.loc[df["fiscal_year"] == year]
    if row.empty:
        return None
    val = row.iloc[0][key]
    return float(val) if pd.notna(val) else None


def compute_roic(df: pd.DataFrame, tax_rate: Optional[float] = None) -> pd.DataFrame:
    """ROIC = NOPAT / Invested Capital."""
    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        year = int(row["fiscal_year"])
        ebit = _get(df, year, "ebit")
        ebt = _get(df, year, "ebt")
        tax = _get(df, year, "income_tax")
        equity = _get(df, year, "total_equity")
        cash = _get(df, year, "cash_eop") or _get(df, year, "cash")
        st = _get(df, year, "short_term_debt")
        lt = _get(df, year, "long_term_debt")

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
    return pd.DataFrame(rows).sort_values("fiscal_year", kind="mergesort").reset_index(drop=True)


def compute_margins(df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        year = int(row["fiscal_year"])
        rev = _get(df, year, "revenue")
        ebit = _get(df, year, "ebit")
        ni = _get(df, year, "net_income")
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
        equity = _get(df, year, "total_equity")
        st = _get(df, year, "short_term_debt")
        lt = _get(df, year, "long_term_debt")
        cash = _get(df, year, "cash_eop") or _get(df, year, "cash")
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
        fcf = _get(df, year, "fcf")
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
