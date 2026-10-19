"""Interactive fundamental-analysis dashboard for WEG S.A. (WEGE3.SA).

Run with:
    streamlit run app.py
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import streamlit as st

from src import data, report
from src.analytics import market, valuation
from src.viz import charts

st.set_page_config(page_title="WEG | Fundamental Analysis", page_icon=None,
                   layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
      .block-container {padding-top: 2.2rem; padding-bottom: 3rem;}
      [data-testid="stMetricValue"] {font-size: 1.6rem;}
      [data-testid="stMetricLabel"] {color: #6e7781;}
      h1, h2, h3 {letter-spacing: -0.01em;}
      .insight-box {
        background: #f3f7ff; border-left: 4px solid #1f6feb;
        padding: 0.9rem 1.1rem; border-radius: 6px; margin: 0.6rem 0 1.2rem 0;
        font-size: 0.94rem; line-height: 1.55;
      }
      .warn-box {
        background: #fff8e6; border-left: 4px solid #f2a900;
        padding: 0.9rem 1.1rem; border-radius: 6px; margin: 0 0 1.2rem 0;
        font-size: 0.94rem; line-height: 1.55;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def insight(text: str) -> None:
    st.markdown(f"<div class='insight-box'>{text}</div>", unsafe_allow_html=True)


def brl(v: float, unit: str = "M") -> str:
    return f"BRL {v:,.0f}{unit}"


@st.cache_data(show_spinner="Loading data...")
def load() -> data.Dataset:
    return data.load()


if not data.data_available():
    st.error("Processed data not found. Run: `python -m src.etl.ingestion --mock` "
             "(synthetic) or `--live` (official: CVM + Yahoo Finance).")
    st.stop()

ds = load()
all_years = [int(y) for y in ds.wide["fiscal_year"]]

# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
st.sidebar.title("WEG Analytics")
st.sidebar.caption("WEGE3.SA | B3 | Capital goods")
st.sidebar.markdown("---")
st.sidebar.subheader("Filters")
y0, y1 = st.sidebar.select_slider("Fiscal years", options=all_years, value=(all_years[0], all_years[-1]))
price_years = st.sidebar.selectbox("Price window", ["All", "1 year", "3 years"], index=0)

prices = ds.prices
if price_years != "All":
    n = 1 if price_years == "1 year" else 3
    prices = prices[prices["date"] >= prices["date"].iloc[-1] - pd.DateOffset(years=n)]

an = report.analyse(ds, (y0, y1))
px_now = float(ds.prices["close"].iloc[-1])

st.sidebar.markdown("---")
st.sidebar.caption("Values in **BRL millions** unless noted. Not investment advice.")

st.title("WEG S.A. - Fundamental Analysis")
if ds.synthetic:
    st.markdown(
        "<div class='warn-box'><b>Synthetic data.</b> This dashboard is reading the test fixture "
        "(<code>--mock</code>), not official figures. For real data run "
        "<code>python -m src.etl.ingestion --live</code>.</div>",
        unsafe_allow_html=True,
    )

# KPIs ------------------------------------------------------------------------
last_m, last_r = an.margins.iloc[-1], an.roic.iloc[-1]
last_l, last_f = an.leverage.iloc[-1], an.fcf.iloc[-1]
cagr = (an.margins["revenue"].iloc[-1] / an.margins["revenue"].iloc[0]) ** (1 / max(len(an.margins) - 1, 1)) - 1

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Net revenue", brl(last_m["revenue"]), f"CAGR {cagr:.1%}")
c2.metric("EBIT margin", f"{last_m['ebit_margin']:.1%}", f"{last_m['ebit_margin_yoy'] * 100:+.1f} pp")
c3.metric("ROIC", f"{last_r['roic']:.1%}")
c4.metric("FCF yield", f"{last_f['fcf_yield']:.1%}")
c5.metric("Net debt / equity", f"{last_l['net_debt_to_equity']:.2f}x")

# Premissas do DCF (sidebar) ----------------------------------------------------
st.sidebar.subheader("DCF assumptions")
base_a = valuation.Assumptions()
hist_margin = float(an.margins["ebit_margin"].iloc[-1])
ebit_margin = st.sidebar.slider("Projected EBIT margin", 0.10, 0.30, base_a.ebit_margin, 0.005, format="%.3f",
                                help=f"EBIT margin of the latest fiscal year: {hist_margin:.1%}")
selic = st.sidebar.slider("Selic / risk-free rate", 0.08, 0.16, base_a.rf, 0.0025, format="%.4f")
term_g = st.sidebar.slider("Perpetuity growth", 0.02, 0.07, base_a.term_growth, 0.0025, format="%.4f")
beta = st.sidebar.slider("Beta", 0.6, 1.4, base_a.beta, 0.05)
assump = replace(base_a, ebit_margin=ebit_margin, rf=selic, term_growth=term_g, beta=beta)

tab_ov, tab_prof, tab_bal, tab_val, tab_mkt, tab_data = st.tabs(
    ["Overview", "Profitability", "Balance sheet & cash", "Valuation (DCF)", "Market", "Data"]
)

# --------------------------------------------------------------------------- #
with tab_ov:
    st.subheader("Is the company growing, and is growth turning into profit?")
    a, b = st.columns(2)
    a.plotly_chart(charts.revenue(an.margins), use_container_width=True)
    b.plotly_chart(charts.margins(an.margins), use_container_width=True)
    insight(
        f"Revenue grew **{cagr:.1%} a year** over the period and the EBIT margin moved from "
        f"**{an.margins['ebit_margin'].iloc[0]:.1%}** to **{last_m['ebit_margin']:.1%}**. "
        "Margins rising alongside revenue point to scale or pricing gains, not just volume."
    )
    if an.geo is not None and len(an.geo):
        st.plotly_chart(charts.geo(an.geo), use_container_width=True)
        insight(f"International sales are **{an.intl_share:.0%}** of revenue: the dollar and global demand "
                "matter as much as the Brazilian market.")

with tab_prof:
    st.subheader("Does invested capital earn more than it costs?")
    model, res = report.dcf(ds, an, assump)
    a, b = st.columns(2)
    a.plotly_chart(charts.roic(an.roic, wacc=res.wacc), use_container_width=True)
    b.plotly_chart(charts.nopat_capital(an.roic), use_container_width=True)
    spread = last_r["roic"] - res.wacc
    insight(
        f"ROIC of **{last_r['roic']:.1%}** against a WACC of **{res.wacc:.1%}**: a spread of "
        f"**{spread * 100:+.1f} pp** — the company {'creates' if spread > 0 else 'destroys'} value "
        "on every real reinvested."
    )

with tab_bal:
    st.subheader("Is the balance sheet sound, and does cash fund growth?")
    a, b = st.columns(2)
    a.plotly_chart(charts.leverage(an.leverage), use_container_width=True)
    b.plotly_chart(charts.cash_flow(an.cash_flow), use_container_width=True)
    a, b = st.columns(2)
    a.plotly_chart(charts.fcf(an.fcf), use_container_width=True)
    b.plotly_chart(charts.fcf_yield(an.fcf), use_container_width=True)
    insight(
        f"Net debt of **{brl(last_l['net_debt'])}** "
        f"({'net cash' if last_l['net_debt'] < 0 else 'leverage of ' + format(last_l['net_debt_to_equity'], '.2f') + 'x equity'}). "
        "A conservative balance sheet lowers risk when the Selic rises."
    )

with tab_val:
    st.subheader("What is the share worth on discounted cash flow?")
    model, res = report.dcf(ds, an, assump)
    up = report.upside(res.target_price, px_now)
    a, b, c, d = st.columns(4)
    a.metric("Target price (DCF)", f"BRL {res.target_price:.2f}")
    b.metric("Current price", f"BRL {px_now:.2f}")
    c.metric("Upside", f"{up:+.1%}")
    d.metric("WACC", f"{res.wacc:.2%}")
    tv_share = res.pv_terminal / res.ev
    insight(
        f"The model points to **{abs(up):.0%} {'upside' if up > 0 else 'downside'}**. "
        f"Terminal value is **{tv_share:.0%}** of enterprise value and the projected EBIT margin "
        f"({ebit_margin:.1%}) is {'below' if ebit_margin < hist_margin else 'above'} the historical one "
        f"({hist_margin:.1%}) — use the sidebar controls to test it."
    )
    a, b = st.columns(2)
    a.plotly_chart(charts.bridge(valuation.bridge(res)), use_container_width=True)
    b.plotly_chart(charts.tornado(report.tornado(ds, an, assump)), use_container_width=True)
    st.plotly_chart(charts.sensitivity(report.sensitivity(ds, an, model)), use_container_width=True)
    st.caption(f"Shares: {ds.meta['shares']:,.0f}M | Net debt: {brl(an.net_debt)} | "
               f"Cost of equity (CAPM): {res.ke:.2%} | After-tax cost of debt: {res.kd_at:.2%}")

with tab_mkt:
    st.subheader("How has the market been pricing the share?")
    s = market.summary(prices)
    a, b, c, d = st.columns(4)
    a.metric("Last close", f"BRL {s['last']:.2f}")
    b.metric("Annualised return", f"{s['cagr']:.1%}")
    c.metric("Annual volatility", f"{s['vol']:.1%}")
    d.metric("Max drawdown", f"{s['max_drawdown']:.1%}")
    st.plotly_chart(charts.price(market.with_moving_averages(prices)), use_container_width=True)
    a, b = st.columns(2)
    a.plotly_chart(charts.drawdown(market.drawdown(prices)), use_container_width=True)
    b.plotly_chart(charts.annual_returns(market.annual_returns(prices)), use_container_width=True)

with tab_data:
    st.subheader("Methodology and data")
    st.markdown(
        "- **Sources (live mode):** CVM open data (DFP) for the statements; Yahoo Finance for prices, "
        "market cap and share count.\n"
        "- **ROIC** = EBIT × (1 − effective tax rate) ÷ (debt − cash + equity).\n"
        "- **FCF yield** = free cash flow ÷ current market cap (every year uses the same market cap).\n"
        "- **DCF:** 5 explicit years + perpetuity (Gordon growth), discounted at WACC; international revenue "
        "translated at USD/BRL.\n"
        f"- **Current data origin:** {'synthetic (mock)' if ds.synthetic else 'official (CVM + Yahoo Finance)'}."
    )
    st.dataframe(ds.wide.round(2), use_container_width=True, hide_index=True)
    st.download_button("Download statements (CSV)", ds.wide.to_csv(index=False).encode("utf-8-sig"),
                       "weg_statements.csv", "text/csv")

