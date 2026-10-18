"""Tidy raw JSON payloads into relational Pandas DataFrames."""

from typing import Any, Dict, List, Literal, Optional

import pandas as pd

_ALIASES: Dict[str, List[str]] = {
    "Revenue": ["revenue", "Revenue", "totalNetRevenue"],
    "Cost of Revenue": ["costOfRevenue", "Cost of Revenue", "cost of revenue"],
    "Gross Profit": ["grossProfit", "Gross Profit"],
    "Operating Income (EBIT)": ["operatingIncome", "Operating Income (EBIT)", "ebit", "EBIT"],
    "Financial Result, Net": ["totalOtherIncomeExpensesNet", "Financial Result, Net", "financial_result"],
    "Earnings Before Tax (EBT)": ["incomeBeforeTax", "Earnings Before Tax (EBT)", "ebt", "EBT"],
    "Income Tax Expense": ["incomeTaxExpense", "Income Tax Expense"],
    "Net Income": ["netIncome", "Net Income"],
    "Total Assets": ["totalAssets", "Total Assets"],
    "Total Liabilities": ["totalLiabilities", "Total Liabilities"],
    "Total Equity": ["totalShareholdersEquity", "Total Equity", "totalEquity"],
    "Cash and Equivalents": ["cashAndShortTermInvestments", "Cash and Equivalents", "Cash and Equivalents (EoP)", "cash"],
    "Short-Term Debt": ["shortTermDebt", "Short-Term Debt"],
    "Long-Term Debt": ["longTermDebt", "Long-Term Debt"],
    "Accounts Receivable": ["accountsReceivable", "Accounts Receivable"],
    "Inventory": ["inventory", "Inventory"],
    "Accounts Payable": ["accountsPayable", "Accounts Payable"],
    "Property, Plant & Equipment (net)": ["netPpe", "Property, Plant & Equipment (net)"],
    "Operating Cash Flow": ["operatingCashFlow", "Operating Cash Flow"],
    "Capital Expenditure": ["capitalExpenditure", "Capital Expenditure"],
    "Free Cash Flow": ["freeCashFlow", "Free Cash Flow"],
    "Depreciation & Amortization": ["depreciationAndAmortization", "Depreciation & Amortization"],
    "Working Capital Investment": ["changeInWorkingCapital", "Working Capital Investment"],
}

_PROVIDER_TO_CANONICAL: Dict[str, str] = {}
for _canon, _variants in _ALIASES.items():
    for _variant in _variants:
        _PROVIDER_TO_CANONICAL.setdefault(_variant, _canon)


def _pick(record: Dict[str, Any], names: List[str]) -> Optional[float]:
    for name in names:
        if name in record and record[name] is not None:
            try:
                return float(record[name])
            except (TypeError, ValueError):
                continue
    return None


def tidy(
    rows: List[Dict[str, Any]],
    statement: str,
    ticker: str,
    currency: str = "BRL",
    source: str = "fmp",
) -> pd.DataFrame:
    records: List[Dict[str, Any]] = []
    for row in rows:
        year = int(str(row.get("date", row.get("calendarYear", "")))[:4])
        period = row.get("period", "annual")
        item = row.get("line_item")
        val = row.get("value")
        if item is None:
            for key, value in row.items():
                if key in {"date", "symbol", "reportedCurrency", "cik", "fillingDate", "acceptedDate", "calendarYear", "period"}:
                    continue
                if value is None:
                    continue
                records.append({
                    "fiscal_year": year,
                    "period": period,
                    "statement": statement,
                    "line_item": _PROVIDER_TO_CANONICAL.get(key, key),
                    "value": float(value),
                    "currency": currency,
                    "source": source,
                })
        else:
            records.append({
                "fiscal_year": year,
                "period": period,
                "statement": statement,
                "line_item": item,
                "value": float(val),
                "currency": currency,
                "source": source,
            })
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=["fiscal_year", "period", "statement", "line_item", "value", "currency", "source"])
    return df.sort_values(["fiscal_year", "line_item"], kind="mergesort").reset_index(drop=True)


def combine(frames: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(frames.values(), ignore_index=True) if frames else pd.DataFrame()


def to_wide(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (
        df.pivot_table(index="fiscal_year", columns="line_item", values="value", aggfunc="first")
        .reset_index()
        .sort_values("fiscal_year", kind="mergesort")
        .reset_index(drop=True)
    )


def clean_prices(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    need = {"date", "open", "high", "low", "close", "volume"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"Missing price columns: {sorted(missing)}")
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"])
    for col in ("open", "high", "low", "close", "adjusted_close", "volume"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out["ticker"] = ticker
    return out.dropna(subset=["close"]).sort_values("date", kind="mergesort").reset_index(drop=True)
