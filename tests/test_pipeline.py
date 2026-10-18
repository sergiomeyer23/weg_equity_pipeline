"""Basic checks for the WEG pipeline."""

import pandas as pd
import pytest

from src.analytics import kpis, valuation
from src.etl.clients.mocks import STATEMENTS, build
from src.etl.transform import tidy, to_wide


def test_balance_sheet_balances() -> None:
    by_year: dict[int, dict[str, float]] = {}
    for row in STATEMENTS.balance_sheet:
        y = int(str(row["date"])[:4])
        by_year.setdefault(y, {})[row["line_item"]] = float(row["value"])
    for y, items in by_year.items():
        tol = 1e-6 * items["Total Assets"]
        assert abs(items["Total Assets"] - items["Total Liabilities and Equity"]) < tol, y
        assert abs(items["Total Assets"] - (items["Total Liabilities"] + items["Total Equity"])) < tol, y


def test_cash_flow_reconciles() -> None:
    by_year: dict[int, dict[str, float]] = {}
    for row in STATEMENTS.cash_flow:
        y = int(str(row["date"])[:4])
        by_year.setdefault(y, {})[row["line_item"]] = float(row["value"])
    years = sorted(by_year)
    for i in range(1, len(years)):
        cur = by_year[years[i]]
        prev = by_year[years[i - 1]]
        implied = cur["Operating Cash Flow"] + cur["Capital Expenditure"] + cur["Net Borrowing"] \
            + cur["Dividends Paid"] + cur["Other Financing Activities"]
        delta = cur["Cash and Equivalents (EoP)"] - prev["Cash and Equivalents (EoP)"]
        assert abs(implied - delta) < 1.0, years[i]


def test_tidy_schema() -> None:
    df = tidy(STATEMENTS.income_statement, "income", "WEGE3.SA", "BRL", "fmp")
    assert set(df.columns) == {"fiscal_year", "period", "statement", "line_item", "value", "currency", "source"}
    assert df["fiscal_year"].nunique() == 5
    wide = to_wide(df)
    assert "Revenue" in wide.columns


def test_roic_above_hurdle() -> None:
    inc = to_wide(tidy(STATEMENTS.income_statement, "income", "WEGE3.SA"))
    bs = to_wide(tidy(STATEMENTS.balance_sheet, "balance_sheet", "WEGE3.SA"))
    cf = to_wide(tidy(STATEMENTS.cash_flow, "cash_flow", "WEGE3.SA"))
    merged = inc.merge(bs, on="fiscal_year").merge(cf, on="fiscal_year")
    r = kpis.compute_roic(merged)
    assert (r["roic"] > 0.15).all()
    assert r["roic"].iloc[-1] > r["roic"].iloc[0]


def test_margin_expansion() -> None:
    inc = to_wide(tidy(STATEMENTS.income_statement, "income", "WEGE3.SA"))
    m = kpis.compute_margins(inc)
    assert m["ebit_margin"].iloc[-1] > m["ebit_margin"].iloc[0]


def test_leverage_low() -> None:
    inc = to_wide(tidy(STATEMENTS.income_statement, "income", "WEGE3.SA"))
    bs = to_wide(tidy(STATEMENTS.balance_sheet, "balance_sheet", "WEGE3.SA"))
    merged = inc.merge(bs, on="fiscal_year")
    l = kpis.compute_leverage(merged)
    assert (l["debt_to_equity"] < 0.50).all()


def test_dcf_positive() -> None:
    m = valuation.DCF()
    r = m.run(base_rev=52_400.0, net_debt=-524.0, shares=2_089.0, intl_share=0.40)
    assert r.target_price > 0
    assert 0.05 < r.wacc < 0.30


def test_sensitivity_direction() -> None:
    m = valuation.DCF()
    g = m.grid(base_rev=52_400.0, base_fcf=9_890.0, net_debt=-524.0, shares=2_089.0,
               intl_share=0.40, fxs=[4.40, 5.10, 5.80], selics=[0.0925, 0.1175, 0.1425])
    assert g.shape == (3, 3)
    assert g.loc[0.1425, 5.10] < g.loc[0.1175, 5.10] < g.loc[0.0925, 5.10]
    assert g.loc[0.1175, 4.40] < g.loc[0.1175, 5.10] < g.loc[0.1175, 5.80]


def test_build_deterministic() -> None:
    assert build() == build()
