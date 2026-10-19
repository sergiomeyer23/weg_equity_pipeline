"""Testes de qualidade para o pipeline WEGE3.SA.

Substitui os antigos testes tautológicos (que apenas confirmavam que o mock
é consistente consigo mesmo) por: (a) validação do DCF contra cálculo manual
independente e (b) comparação de dados reais da CVM contra valores publicados.
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
        pytest.skip("Rode o ETL antes: python -m src.etl.ingestion --mock")
    return pd.read_parquet(path)


# ----------------------------------------------------------------------
# (a) DCF contra cálculo manual independente
# ----------------------------------------------------------------------
def test_dcf_matches_manual_calculation() -> None:
    """DCF deve reproduzir um cálculo manual passo a passo em caso simples.

    Cenário: receita base R$ 100M, crescimento 0%, margem EBIT 20%,
    imposto 25%, sem D&A, sem CAPEX, sem capital de giro, crescimento
    perpétuo 0%, WACC 10%, sem dívida líquida, 10M de ações.

    FCFF anual = 100 * 0.20 * (1 - 0.25) = 15M (constante)
    PV explícito (5 anos) = 15 * sum(1.1^-i, i=1..5) = 56.86M
    Valor terminal = 15 / 0.10 = 150M (g=0)
    PV terminal = 150 * 1.1^-5 = 93.14M
    EV = 56.86 + 93.14 = 150.0M
    Equity = 150.0 - 0 = 150.0M
    Preço = 150.0 / 10 = R$ 15.00
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

    # Cálculo manual independente
    fcf = 100.0 * 0.20 * (1.0 - 0.25)  # 15M por ano
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
    """Selic maior → WACC maior → preço-alvo menor (ceteris paribus)."""
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
    # Uma única coluna de FX; três linhas de Selic
    assert g.shape == (3, 1)
    assert g.loc[0.1425, 5.10] < g.loc[0.1175, 5.10] < g.loc[0.0925, 5.10]


# ----------------------------------------------------------------------
# (b) Dados reais da CVM contra valores publicados
# ----------------------------------------------------------------------
def test_cvm_revenue_ebit_net_income_2024() -> None:
    """Receita, EBIT e lucro líquido 2024 da CVM devem bater com o RI da WEG.

    Valores de referência do DFP 2024 da WEG S.A. (CVM dados abertos):
    - Receita líquida: ~R$ 37,99 bi
    - EBIT (Resultado antes do resultado financeiro): ~R$ 7,69 bi
    - Lucro líquido: ~R$ 6,04 bi

    Tolerância: 5% (diferenças podem surgir de classificação contábil).
    """
    wide = _load_wide()
    if "Receita de Venda de Bens e/ou Serviços" not in wide.columns:
        pytest.skip("Dados da CVM ausentes (rode o ETL sem --mock).")
    row = wide[wide["fiscal_year"] == 2024].iloc[0]

    revenue = float(row["Receita de Venda de Bens e/ou Serviços"])
    ebit = float(row["Resultado Antes do Resultado Financeiro e dos Tributos"])

    # Lucro líquido pode ter nomes diferentes no DFP
    ni_cols = [c for c in wide.columns if "Lucro" in c and "Período" in c]
    net_income = float(row[ni_cols[0]]) if ni_cols else float("nan")

    # Valores de referência do DFP 2024 (valores em reais, não milhões)
    expected_revenue = 37_986_941_000.0
    expected_ebit = 7_690_528_000.0
    expected_ni = 6_042_593_000.0

    tol = 0.05
    assert abs(revenue - expected_revenue) / expected_revenue < tol, f"Revenue: {revenue}"
    assert abs(ebit - expected_ebit) / expected_ebit < tol, f"EBIT: {ebit}"
    if pd.notna(net_income):
        assert abs(net_income - expected_ni) / expected_ni < tol, f"Net income: {net_income}"


def test_roic_positive_and_reasonable() -> None:
    """ROIC deve ser positivo e razoável (não 40% inventado)."""
    wide = _load_wide()
    roic = kpis.compute_roic(wide)
    assert (roic["roic"] > 0).all()
    assert (roic["roic"] < 1.0).all()  # não pode ser > 100%


def test_leverage_reasonable() -> None:
    """Alavancagem deve ser baixa (WEG tem balanço conservador)."""
    wide = _load_wide()
    lev = kpis.compute_leverage(wide)
    assert (lev["debt_to_equity"] < 1.0).all()


def test_files_exist() -> None:
    """Artefatos do ETL devem existir após a execução."""
    _load_wide()  # pula se o ETL não rodou
    assert (_PROCESSED / "WEGE3.SA_prices.parquet").exists()
    assert (_PROCESSED / "WEGE3.SA_statements_wide.parquet").exists()
