"""Quality tests for the WEGE3.SA pipeline.

Replaces the old tautological tests (which only proved the mock was consistent
with itself) with: (a) DCF validation against an independent manual calculation
and (b) a comparison of real CVM data against published figures.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.analytics import kpis, valuation

_PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"


def _load_wide() -> pd.DataFrame:
    path = _PROCESSED / "WEGE3.SA_statements_wide.parquet"
    if not path.exists():
        pytest.skip("Run the ETL first: python -m src.etl.ingestion --mock")
    return pd.read_parquet(path)


# ----------------------------------------------------------------------
# (a) DCF against an independent manual calculation
# ----------------------------------------------------------------------
def test_dcf_matches_manual_calculation() -> None:
    """The DCF must reproduce a step-by-step manual calculation on a simple case.

    Scenario: base revenue BRL 100M, 0% growth, 20% EBIT margin,
    25% tax, no D&A, no capex, no working capital, 0% perpetual
    growth, 10% WACC, no net debt, 10M shares.

    Annual FCFF = 100 * 0.20 * (1 - 0.25) = 15M (constant)
    Explicit PV (5 years) = 15 * sum(1.1^-i, i=1..5) = 56.86M
    Terminal value = 15 / 0.10 = 150M (g=0)
    Terminal PV = 150 * 1.1^-5 = 93.14M
    EV = 56.86 + 93.14 = 150.0M
    Equity = 150.0 - 0 = 150.0M
    Price = 150.0 / 10 = BRL 15.00
    """
    model = valuation.DCF()
    a = valuation.Assumptions(
        years=5,
        growth=[0.0, 0.0, 0.0, 0.0, 0.0],
        ebit_margin=0.20,
        tax=0.25,
        da_ratio=0.0,
        capex_ratio=0.0,
        wc_ratio=0.0,
        term_growth=0.0,
        rf=0.08,
        erp=0.02,
        beta=1.0,
        debt_spread=0.0,
        tax_rate=0.25,
        target_debt_v=0.0,
    )
    model.a = a

    # Independent manual calculation
    fcf = 100.0 * 0.20 * (1.0 - 0.25)  # 15M per year
    wacc = 0.08 + 1.0 * 0.02  # 10%
    dfs = [(1.0 + wacc) ** -(i + 1) for i in range(5)]
    pv_explicit = sum(fcf * d for d in dfs)
    terminal = fcf / wacc  # g = 0
    pv_terminal = terminal * dfs[-1]
    ev_manual = pv_explicit + pv_terminal
    price_manual = ev_manual / 10.0

    res = model.run(base_rev=100.0, net_debt=0.0, shares=10.0, intl_share=0.0)

    assert abs(res.ev - ev_manual) < 1e-6
    assert abs(res.target_price - price_manual) < 1e-6
    assert abs(res.wacc - wacc) < 1e-6


def test_dcf_sensitivity_direction() -> None:
    """Higher Selic means higher WACC and a lower target price."""
    model = valuation.DCF()
    g = model.grid(
        base_rev=52_400.0,
        base_fcf=9_890.0,
        net_debt=-524.0,
        shares=4_195.83,
        intl_share=0.40,
        fxs=[5.10],
        selics=[0.0925, 0.1175, 0.1425],
    )
    # A single FX column; three Selic rows
    assert g.shape == (3, 1)
    assert g.loc[0.1425, 5.10] < g.loc[0.1175, 5.10] < g.loc[0.0925, 5.10]


# ----------------------------------------------------------------------
# (b) Real CVM data against published figures
# ----------------------------------------------------------------------
def test_cvm_revenue_ebit_net_income_2024() -> None:
    """2024 revenue, EBIT and net income from CVM must match WEG's IR figures.

    Reference values from WEG S.A.'s 2024 DFP (CVM open data):
    - Net revenue: ~BRL 37.99 bn
    - EBIT (Resultado antes do resultado financeiro): ~R$ 7,69 bi
    - Net income: ~BRL 6.04 bn

    Tolerance: 5% (differences may stem from accounting classification).
    """
    wide = _load_wide()
    if "Receita de Venda de Bens e/ou Serviços" not in wide.columns:
        pytest.skip("CVM data missing (run the ETL without --mock).")
    row = wide[wide["fiscal_year"] == 2024].iloc[0]

    revenue = float(row["Receita de Venda de Bens e/ou Serviços"])
    ebit = float(row["Resultado Antes do Resultado Financeiro e dos Tributos"])

    # Net income may carry different account names in the DFP
    ni_cols = [c for c in wide.columns if "Lucro" in c and "Período" in c]
    net_income = float(row[ni_cols[0]]) if ni_cols else float("nan")

    # 2024 DFP reference values (in reais, not millions)
    expected_revenue = 37_986_941_000.0
    expected_ebit = 7_690_528_000.0
    expected_ni = 6_042_593_000.0

    tol = 0.05
    assert abs(revenue - expected_revenue) / expected_revenue < tol, f"Revenue: {revenue}"
    assert abs(ebit - expected_ebit) / expected_ebit < tol, f"EBIT: {ebit}"
    if pd.notna(net_income):
        assert abs(net_income - expected_ni) / expected_ni < tol, f"Net income: {net_income}"


def test_roic_positive_and_reasonable() -> None:
    """ROIC must be positive and reasonable (not an invented 40%)."""
    wide = _load_wide()
    roic = kpis.compute_roic(wide)
    assert (roic["roic"] > 0).all()
    assert (roic["roic"] < 1.0).all()  # cannot exceed 100%


def test_leverage_reasonable() -> None:
    """Leverage must be low (WEG has a conservative balance sheet)."""
    wide = _load_wide()
    lev = kpis.compute_leverage(wide)
    assert (lev["debt_to_equity"] < 1.0).all()


def test_files_exist() -> None:
    """ETL artefacts must exist after a run."""
    _load_wide()  # skips if the ETL has not run
    assert (_PROCESSED / "WEGE3.SA_prices.parquet").exists()
    assert (_PROCESSED / "WEGE3.SA_statements_wide.parquet").exists()


# ----------------------------------------------------------------------
# (c) Regressions found in the audit
# ----------------------------------------------------------------------
def test_dcf_fx_is_level_not_compounded() -> None:
    """A weaker BRL should lift the revenue level once, not every year."""
    a = valuation.Assumptions(
        years=5,
        growth=[0.05, 0.05, 0.05, 0.05, 0.05],
        ebit_margin=0.20,
        tax=0.25,
        da_ratio=0.0,
        capex_ratio=0.0,
        wc_ratio=0.0,
        term_growth=0.0,
        rf=0.08,
        erp=0.02,
        beta=1.0,
        debt_spread=0.0,
        tax_rate=0.25,
        target_debt_v=0.0,
    )
    model = valuation.DCF(a)
    base = model.run(100.0, net_debt=0.0, shares=10.0, intl_share=0.4, fx=5.10)
    shock = model.run(100.0, net_debt=0.0, shares=10.0, intl_share=0.4, fx=5.80)

    factor = 0.6 + 0.4 * (5.80 / 5.10)
    assert shock.rev[0] == pytest.approx(base.rev[0] * factor)
    assert shock.rev[1] == pytest.approx(base.rev[1] * factor)
    assert shock.rev[2] / shock.rev[1] == pytest.approx(base.rev[2] / base.rev[1])


def test_dcf_working_capital_scales_with_revenue_change() -> None:
    """NWC investment is wc_ratio * delta revenue, not wc_ratio * revenue."""
    kw = dict(
        years=2, ebit_margin=0.0, tax=0.0, da_ratio=0.0, capex_ratio=0.0,
        term_growth=0.0, rf=0.08, erp=0.02, beta=1.0, debt_spread=0.0,
        tax_rate=0.0, target_debt_v=0.0,
    )
    growing = valuation.DCF(valuation.Assumptions(growth=[0.10, 0.10], wc_ratio=0.20, **kw))
    res = growing.run(100.0, net_debt=0.0, shares=1.0, intl_share=0.0)
    # rev: 110, 121 -> delta: 10, 11 -> FCFF = -0.20 * delta
    assert res.fcf[0] == pytest.approx(-2.0)
    assert res.fcf[1] == pytest.approx(-2.2)

    flat = valuation.DCF(valuation.Assumptions(growth=[0.0, 0.0], wc_ratio=0.20, **kw))
    res = flat.run(100.0, net_debt=0.0, shares=1.0, intl_share=0.0)
    assert res.fcf == [0.0, 0.0]


def test_total_debt_sums_current_and_noncurrent() -> None:
    """Both CVM debt lines must be added, not collapsed into one."""
    wide = pd.DataFrame({
        "fiscal_year": [2024],
        "Total Equity": [100.0],
        "Empréstimos e Financiamentos (Circulante)": [10.0],
        "Empréstimos e Financiamentos (Não Circulante)": [30.0],
        "Debêntures (Não Circulante)": [5.0],
        "Caixa e Equivalentes": [20.0],
    })
    lev = kpis.compute_leverage(wide)

    assert lev.iloc[0]["total_debt"] == pytest.approx(45.0)
    assert lev.iloc[0]["net_debt"] == pytest.approx(25.0)


def test_total_debt_accepts_legacy_collapsed_label() -> None:
    """Old processed files only have the generic CVM label."""
    wide = pd.DataFrame({
        "fiscal_year": [2024],
        "Total Equity": [100.0],
        "Empréstimos e Financiamentos": [25.0],
    })
    lev = kpis.compute_leverage(wide)

    assert lev.iloc[0]["total_debt"] == pytest.approx(25.0)


def test_cash_flow_derives_fcf_from_ocf_and_capex() -> None:
    """CVM has no FCF line; the report must derive it instead of dropping the year."""
    wide = pd.DataFrame({
        "fiscal_year": [2024],
        "Caixa Líquido Atividades Operacionais": [100.0],
        "Capital Expenditure": [-40.0],
        "Capital Expenditure (Intangibles)": [-10.0],
    })
    cf = kpis.compute_cash_flow(wide)

    assert cf.iloc[0]["ocf"] == pytest.approx(100.0)
    assert cf.iloc[0]["capex"] == pytest.approx(-50.0)
    assert cf.iloc[0]["fcf"] == pytest.approx(50.0)

    fcf = kpis.compute_fcf_yield(wide, market_cap=1_000.0)
    assert fcf.iloc[0]["fcf_yield"] == pytest.approx(0.05)
