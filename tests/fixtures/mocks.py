"""Synthetic fundamental fixture for WEGE3.SA (offline / CI use only).

Internally consistent 5-year income statement, balance sheet, and cash flow.
Figures are in BRL millions and roughly match WEG's order of magnitude.
MOVIDO DE src/etl/clients/mocks.py — código em src/ não pode conter dados inventados.
"""

from dataclasses import dataclass
from typing import Dict, List

FISCAL_YEARS = [2020, 2021, 2022, 2023, 2024]
TICKER = "WEGE3.SA"

_REVENUE = {2020: 33_768.0, 2021: 41_077.0, 2022: 53_191.0, 2023: 49_879.0, 2024: 52_400.0}
_DOMESTIC_SHARE = {2020: 0.62, 2021: 0.60, 2022: 0.58, 2023: 0.59, 2024: 0.60}
_CGS = {2020: 0.64, 2021: 0.62, 2022: 0.61, 2023: 0.60, 2024: 0.59}
_SGA = {2020: 0.155, 2021: 0.150, 2022: 0.145, 2023: 0.148, 2024: 0.145}
_OTHER_OP = {2020: 0.02, 2021: 0.018, 2022: 0.016, 2023: 0.017, 2024: 0.016}
_FIN_RES = {2020: 0.005, 2021: 0.008, 2022: 0.010, 2023: 0.006, 2024: 0.007}
_TAX = {2020: 0.20, 2021: 0.20, 2022: 0.21, 2023: 0.22, 2024: 0.21}

_CASH = {2020: 0.10, 2021: 0.11, 2022: 0.09, 2023: 0.10, 2024: 0.11}
_AR = {2020: 0.13, 2021: 0.125, 2022: 0.12, 2023: 0.125, 2024: 0.12}
_INV = {2020: 0.11, 2021: 0.105, 2022: 0.10, 2023: 0.105, 2024: 0.10}
_OTHER_CA = {2020: 0.03, 2021: 0.03, 2022: 0.03, 2023: 0.03, 2024: 0.03}
_PPE = {2020: 0.36, 2021: 0.35, 2022: 0.34, 2023: 0.35, 2024: 0.34}
_INTANG = {2020: 0.04, 2021: 0.04, 2022: 0.04, 2023: 0.04, 2024: 0.04}
_OTHER_NCA = {2020: 0.03, 2021: 0.03, 2022: 0.03, 2023: 0.03, 2024: 0.03}

_AP = {2020: 0.10, 2021: 0.095, 2022: 0.09, 2023: 0.095, 2024: 0.09}
_STD = {2020: 0.04, 2021: 0.035, 2022: 0.03, 2023: 0.035, 2024: 0.03}
_OTHER_CL = {2020: 0.05, 2021: 0.05, 2022: 0.05, 2023: 0.05, 2024: 0.05}
_LTD = {2020: 0.08, 2021: 0.075, 2022: 0.07, 2023: 0.075, 2024: 0.07}
_OTHER_NCL = {2020: 0.03, 2021: 0.03, 2022: 0.03, 2023: 0.03, 2024: 0.03}

_DA = {2020: 0.035, 2021: 0.035, 2022: 0.034, 2023: 0.035, 2024: 0.035}
_CAPEX = {2020: 0.05, 2021: 0.048, 2022: 0.05, 2023: 0.045, 2024: 0.047}
_PAYOUT = {2020: 0.40, 2021: 0.40, 2022: 0.35, 2023: 0.40, 2024: 0.40}


def _line(year: int, name: str, value: float) -> Dict[str, object]:
    return {"date": f"{year}-12-31", "symbol": TICKER, "reported_currency": "BRL", "line_item": name, "value": round(value, 2)}


def _income() -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for y in FISCAL_YEARS:
        rev = _REVENUE[y]
        cogs = rev * _CGS[y]
        gp = rev - cogs
        sga = rev * _SGA[y]
        opex = rev * _OTHER_OP[y]
        ebit = gp - sga - opex
        fin = rev * _FIN_RES[y]
        ebt = ebit + fin
        tax = ebt * _TAX[y]
        ni = ebt - tax
        for name, val in (
            ("Revenue", rev),
            ("Cost of Revenue", -cogs),
            ("Gross Profit", gp),
            ("Operating Expenses", -sga),
            ("Other Operating Expenses", -opex),
            ("Operating Income (EBIT)", ebit),
            ("Financial Result, Net", fin),
            ("Earnings Before Tax (EBT)", ebt),
            ("Income Tax Expense", -tax),
            ("Net Income", ni),
        ):
            rows.append(_line(y, name, val))
    return rows


def _balance() -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for y in FISCAL_YEARS:
        rev = _REVENUE[y]
        ca = rev * (_CASH[y] + _AR[y] + _INV[y] + _OTHER_CA[y])
        nca = rev * (_PPE[y] + _INTANG[y] + _OTHER_NCA[y])
        assets = ca + nca
        cl = rev * (_AP[y] + _STD[y] + _OTHER_CL[y])
        ncl = rev * (_LTD[y] + _OTHER_NCL[y])
        liab = cl + ncl
        equity = assets - liab
        for name, val in (
            ("Cash and Equivalents", rev * _CASH[y]),
            ("Accounts Receivable", rev * _AR[y]),
            ("Inventory", rev * _INV[y]),
            ("Other Current Assets", rev * _OTHER_CA[y]),
            ("Total Current Assets", ca),
            ("Property, Plant & Equipment (net)", rev * _PPE[y]),
            ("Intangible Assets", rev * _INTANG[y]),
            ("Other Non-Current Assets", rev * _OTHER_NCA[y]),
            ("Total Assets", assets),
            ("Accounts Payable", rev * _AP[y]),
            ("Short-Term Debt", rev * _STD[y]),
            ("Other Current Liabilities", rev * _OTHER_CL[y]),
            ("Total Current Liabilities", cl),
            ("Long-Term Debt", rev * _LTD[y]),
            ("Other Non-Current Liabilities", rev * _OTHER_NCL[y]),
            ("Total Liabilities", liab),
            ("Total Equity", equity),
            ("Total Liabilities and Equity", liab + equity),
        ):
            rows.append(_line(y, name, val))
    return rows


def _cashflow() -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    prev_cash: float | None = None
    for i, y in enumerate(FISCAL_YEARS):
        rev = _REVENUE[y]
        cogs = rev * _CGS[y]
        gp = rev - cogs
        sga = rev * _SGA[y]
        opex = rev * _OTHER_OP[y]
        ebit = gp - sga - opex
        fin = rev * _FIN_RES[y]
        ebt = ebit + fin
        tax = ebt * _TAX[y]
        ni = ebt - tax
        da = rev * _DA[y]
        capex = -rev * _CAPEX[y]

        ar = rev * _AR[y]
        inv = rev * _INV[y]
        ap = rev * _AP[y]
        if i == 0:
            wc = ar + inv - ap
        else:
            py = FISCAL_YEARS[i - 1]
            prev_rev = _REVENUE[py]
            wc = (ar + inv - ap) - (prev_rev * _AR[py] + prev_rev * _INV[py] - prev_rev * _AP[py])

        ocf = ni + da - wc
        fcf = ocf + capex
        div = -ni * _PAYOUT[y]
        borrow = rev * 0.005
        fin_cf = borrow + div

        cash = rev * _CASH[y]
        delta = 0.0 if prev_cash is None else cash - prev_cash
        plug = delta - (ocf + capex + fin_cf)

        for name, val in (
            ("Net Income", ni),
            ("Depreciation & Amortization", da),
            ("Working Capital Investment", -wc),
            ("Operating Cash Flow", ocf),
            ("Capital Expenditure", capex),
            ("Free Cash Flow", fcf),
            ("Net Borrowing", borrow),
            ("Dividends Paid", div),
            ("Other Financing Activities", plug),
            ("Net Change in Cash", delta),
            ("Cash and Equivalents (EoP)", cash),
        ):
            rows.append(_line(y, name, val))
        prev_cash = cash
    return rows


def _geo() -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for y in FISCAL_YEARS:
        rev = _REVENUE[y]
        dom = rev * _DOMESTIC_SHARE[y]
        intl = rev - dom
        for name, val in (("Domestic Revenue", dom), ("International Revenue", intl), ("Total Net Revenue", rev)):
            rows.append(_line(y, name, val))
    return rows


@dataclass(frozen=True)
class Profile:
    symbol: str
    short_name: str
    long_name: str
    exchange: str
    currency: str
    country: str
    sector: str
    industry: str
    market_cap: float
    shares_outstanding: float
    price: float
    beta: float


@dataclass(frozen=True)
class Statements:
    income_statement: List[Dict[str, object]]
    balance_sheet: List[Dict[str, object]]
    cash_flow: List[Dict[str, object]]
    geographic_revenue: List[Dict[str, object]]
    profile: Profile
    quote: Dict[str, object]


def build() -> Statements:
    prof = Profile(
        symbol=TICKER,
        short_name="WEG S.A.",
        long_name="WEG S.A.",
        exchange="B3",
        currency="BRL",
        country="Brazil",
        sector="Industrials",
        industry="Electrical Equipment & Components",
        market_cap=85_000.0,
        shares_outstanding=2_089.0,
        price=40.0,
        beta=0.95,
    )
    quote = {"symbol": TICKER, "price": prof.price, "currency": "BRL", "exchange": "B3", "market_cap": prof.market_cap, "shares_outstanding": prof.shares_outstanding}
    return Statements(
        income_statement=_income(),
        balance_sheet=_balance(),
        cash_flow=_cashflow(),
        geographic_revenue=_geo(),
        profile=prof,
        quote=quote,
    )


STATEMENTS = build()
