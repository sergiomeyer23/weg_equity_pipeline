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
