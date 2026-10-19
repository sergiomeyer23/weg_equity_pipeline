"""Streamlit dashboard for WEGE3.SA fundamental tear sheet.

Run: streamlit run app.py
"""

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from src.analytics import kpis, valuation
from src.viz import charts

st.set_page_config(page_title="WEGE3.SA — Fundamental Tear Sheet",
                   page_icon=":chart_with_upwards_trend:", layout="wide")

TICKER = "WEGE3.SA"
DATA = Path(__file__).parent / "data" / "processed"


@st.cache_data(show_spinner=False)
def load(name: str) -> pd.DataFrame:
    return pd.read_parquet(DATA / f"{TICKER}_{name}.parquet")


def main() -> None:
    st.title(f"{TICKER} — WEG S.A. Fundamental Tear Sheet")
    st.caption("B3 | Industrials | BRL millions unless noted | Quantitative equity research")
    st.divider()

    if not (DATA / f"{TICKER}_statements_wide.parquet").exists():
        st.error("Dados processados não encontrados. Rode: `python -m src.etl.ingestion --mock`")
        st.stop()

    wide = load("statements_wide")
    prices = load("prices")
    meta = load("metadata")
    geo_long = load("geographic_revenue")

    roic_df = kpis.compute_roic(wide)
    marg_df = kpis.compute_margins(wide)
    lev_df = kpis.compute_leverage(wide)
    fcf_df = kpis.compute_fcf_yield(wide, market_cap=float(meta["market_cap"].iloc[0] or 0.0))

    geo_wide = geo_long.pivot(index="fiscal_year", columns="line_item", values="value").reset_index().sort_values("fiscal_year")
    geo_df = kpis.geographic_shares(geo_wide)

    latest = wide.iloc[-1]
    latest_roic = roic_df.iloc[-1]["roic"]
    latest_fy = fcf_df.iloc[-1]["fcf_yield"]
    latest_de = lev_df.iloc[-1]["debt_to_equity"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Net revenue (latest)", f"R$ {latest['Revenue']:,.0f}M")
    c2.metric("EBIT margin (latest)", f"{latest['Operating Income (EBIT)'] / latest['Revenue']:.1%}")
    c3.metric("ROIC (latest)", f"{latest_roic:.1%}")
    c4.metric("FCF yield (latest)", f"{latest_fy:.1%}" if pd.notna(latest_fy) else "n/a")
    c5.metric("Debt-to-equity (latest)", f"{latest_de:.2f}x")

    st.divider()

    # DCF
    st.header("Valuation — DCF")
    left, right = st.columns([0.55, 0.45])
    model = valuation.DCF()
    rev = float(latest["Revenue"])
    fcf0 = float(latest["Free Cash Flow"])
    nd = float(lev_df.iloc[-1]["net_debt"])
    sh = float(meta["shares_outstanding"].iloc[0])  # contagem real de ações (yfinance)
    intl = float(geo_df.iloc[-1]["international_share"])
    # Preço de mercado atual: último close da série de preços
    px_series = prices.sort_values("date")
    px_now = float(px_series["close"].iloc[-1]) if not px_series.empty else float("nan")

    res = model.run(base_rev=rev, base_fcf=fcf0, net_debt=nd, shares=sh, intl_share=intl)
    upside = (res.target_price / px_now - 1.0) if pd.notna(px_now) and px_now > 0 else float("nan")

    with left:
        st.subheader("DCF summary")
        st.metric("Preço de mercado (último close)", f"R$ {px_now:.2f}" if pd.notna(px_now) else "n/a")
        st.metric("Target price (DCF)", f"R$ {res.target_price:.2f}", delta=f"{upside:.1%}" if pd.notna(upside) else None)
        st.metric("Enterprise value", f"R$ {res.ev:,.0f}M")
        st.metric("Equity value", f"R$ {res.equity:,.0f}M")
        st.metric("WACC", f"{res.wacc:.2%}")
        st.metric("Cost of equity (CAPM)", f"{res.ke:.2%}")
        st.metric("After-tax cost of debt", f"{res.kd_at:.2%}")
        st.caption(f"Ações em circulação: {sh:,.0f} | Dívida líquida: R$ {nd:,.0f}M")
        st.plotly_chart(charts.bridge(valuation.bridge(res)), use_container_width=True)

    with right:
        st.subheader("Sensitivity — target price (R$)")
        st.caption("Selic move WACC; USD/BRL move tradução da receita internacional em BRL.")
        grid = model.grid(base_rev=rev, base_fcf=fcf0, net_debt=nd, shares=sh, intl_share=intl,
                          fxs=[4.40, 4.80, 5.10, 5.50, 5.80],
                          selics=[0.0925, 0.1075, 0.1175, 0.1325, 0.1425])
        st.plotly_chart(charts.sensitivity(grid), use_container_width=True)
        st.dataframe(grid.style.format("{:.2f}"), use_container_width=True)

    st.divider()

    # KPIs
    st.header("Fundamental KPIs")
    a, b = st.columns(2)
    with a:
        st.plotly_chart(charts.roic(roic_df, wacc=res.wacc), use_container_width=True)
        st.plotly_chart(charts.leverage(lev_df), use_container_width=True)
    with b:
        st.plotly_chart(charts.margins(marg_df), use_container_width=True)
        st.plotly_chart(charts.fcf(fcf_df), use_container_width=True)
    st.plotly_chart(charts.geo(geo_df), use_container_width=True)

    st.subheader("Statements (wide, last 5 years)")
    st.dataframe(wide.round(2), use_container_width=True, hide_index=True)

    st.divider()
    st.caption("Mock fundamental data for offline/CI use. Not investment advice.")


if __name__ == "__main__":
    main()
