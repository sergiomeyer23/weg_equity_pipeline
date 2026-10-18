"""Financial Modeling Prep client (live or mock)."""

from typing import Any, Dict, List, Optional

from .base_client import BaseClient, ClientConfig
from .mocks import STATEMENTS

_IS_MAP = {
    "Revenue": "revenue",
    "Cost of Revenue": "costOfRevenue",
    "Gross Profit": "grossProfit",
    "Operating Expenses": "sellingGeneralAndAdministrativeExpenses",
    "Other Operating Expenses": "otherExpenses",
    "Operating Income (EBIT)": "operatingIncome",
    "Financial Result, Net": "totalOtherIncomeExpensesNet",
    "Earnings Before Tax (EBT)": "incomeBeforeTax",
    "Income Tax Expense": "incomeTaxExpense",
    "Net Income": "netIncome",
}

_BS_MAP = {
    "Cash and Equivalents": "cashAndShortTermInvestments",
    "Accounts Receivable": "accountsReceivable",
    "Inventory": "inventory",
    "Total Current Assets": "totalCurrentAssets",
    "Property, Plant & Equipment (net)": "netPpe",
    "Intangible Assets": "intangibleAssets",
    "Other Non-Current Assets": "otherNonCurrentAssets",
    "Total Assets": "totalAssets",
    "Accounts Payable": "accountsPayable",
    "Short-Term Debt": "shortTermDebt",
    "Other Current Liabilities": "otherCurrentLiabilities",
    "Total Current Liabilities": "totalCurrentLiabilities",
    "Long-Term Debt": "longTermDebt",
    "Other Non-Current Liabilities": "otherNonCurrentLiabilities",
    "Total Liabilities": "totalLiabilities",
    "Total Equity": "totalShareholdersEquity",
    "Total Liabilities and Equity": "totalLiabilitiesAndShareholdersEquity",
}

_CF_MAP = {
    "Net Income": "netIncome",
    "Depreciation & Amortization": "depreciationAndAmortization",
    "Working Capital Investment": "changeInWorkingCapital",
    "Operating Cash Flow": "operatingCashFlow",
    "Capital Expenditure": "capitalExpenditure",
    "Free Cash Flow": "freeCashFlow",
    "Net Borrowing": "netBorrowing",
    "Dividends Paid": "dividendsPaid",
    "Other Financing Activities": "otherFinancingCashFlow",
    "Net Change in Cash": "netChangeInCash",
    "Cash and Equivalents (EoP)": "cashAndShortTermInvestments",
}


def _rows_to_records(rows, mapping: Dict[str, str]) -> List[Dict[str, Any]]:
    by_year: Dict[int, Dict[str, float]] = {}
    for row in rows:
        year = int(str(row["date"])[:4])
        by_year.setdefault(year, {})[row["line_item"]] = float(row["value"])

    out: List[Dict[str, Any]] = []
    for year in sorted(by_year):
        rec: Dict[str, Any] = {
            "date": f"{year}-12-31",
            "symbol": "WEGE3.SA",
            "reportedCurrency": "BRL",
            "calendarYear": year,
            "period": "annual",
        }
        for item, val in by_year[year].items():
            if item in mapping:
                rec[mapping[item]] = round(val, 2)
        out.append(rec)
    return out


class FMPClient(BaseClient):
    def __init__(self, config: ClientConfig) -> None:
        super().__init__(config)

    def auth_headers(self) -> Dict[str, str]:
        return {"apikey": self.config.api_key or ""}

    def _mock(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        path = path.lstrip("/")
        if "income-statement" in path:
            return {"income_statement": _rows_to_records(STATEMENTS.income_statement, _IS_MAP)}
        if "balance-sheet-statement" in path:
            return {"balance_sheet": _rows_to_records(STATEMENTS.balance_sheet, _BS_MAP)}
        if "cash-flow-statement" in path:
            return {"cash_flow": _rows_to_records(STATEMENTS.cash_flow, _CF_MAP)}
        if "/profile/" in path:
            p = STATEMENTS.profile
            return {
                "profile": [
                    {
                        "symbol": p.symbol,
                        "shortName": p.short_name,
                        "longName": p.long_name,
                        "exchange": p.exchange,
                        "currency": p.currency,
                        "country": p.country,
                        "sector": p.sector,
                        "industry": p.industry,
                        "marketCap": p.market_cap,
                        "sharesOutstanding": p.shares_outstanding,
                        "beta": p.beta,
                        "price": p.price,
                    }
                ]
            }
        if "/quote/" in path:
            return {"quote": [STATEMENTS.quote]}
        raise KeyError(f"Unknown FMP mock endpoint: {path}")

    def income_statement(self, ticker: str, period: str = "annual") -> List[Dict[str, Any]]:
        return self.get(f"v3/financial-statements/income-statement/{ticker}", {"period": period}).get("income_statement", [])

    def balance_sheet(self, ticker: str, period: str = "annual") -> List[Dict[str, Any]]:
        return self.get(f"v3/financial-statements/balance-sheet-statement/{ticker}", {"period": period}).get("balance_sheet", [])

    def cash_flow(self, ticker: str, period: str = "annual") -> List[Dict[str, Any]]:
        return self.get(f"v3/financial-statements/cash-flow-statement/{ticker}", {"period": period}).get("cash_flow", [])

    def profile(self, ticker: str) -> Optional[Dict[str, Any]]:
        rows = self.get(f"v3/profile/{ticker}").get("profile", [])
        return rows[0] if rows else None

    def quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        rows = self.get(f"v3/quote/{ticker}").get("quote", [])
        return rows[0] if rows else None
