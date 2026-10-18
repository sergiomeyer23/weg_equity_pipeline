"""Plotly charts for the WEG tear sheet."""

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

NAVY = "#12355B"
SLATE = "#5B6770"
TEAL = "#0E7C7B"
GOLD = "#C9A227"
GRAY = "#D8DEE6"
RED = "#B23A48"

_BASE = dict(
    template="plotly_white",
    font=dict(family="Arial, sans-serif", size=12, color="#22303C"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    margin=dict(l=60, r=20, t=60, b=60),
    hovermode="x unified",
)


def roic(df: pd.DataFrame) -> go.Figure:  # type: ignore[name-defined]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["fiscal_year"], y=df["roic"] * 100, name="ROIC", marker_color=NAVY))
    fig.add_trace(go.Scatter(x=df["fiscal_year"], y=[16.0] * len(df), mode="lines", name="WACC hurdle",
                             line=dict(color=RED, width=2, dash="dash")))
    fig.update_layout(title="Return on Invested Capital (ROIC)", xaxis_title="Fiscal year",
                      yaxis_title="ROIC (%)", yaxis=dict(ticksuffix="%"), **_BASE)
    return fig


def margins(df: pd.DataFrame) -> go.Figure:  # type: ignore[name-defined]
    fig = go.Figure()
    for col, name, c in (("gross_margin", "Gross margin", SLATE), ("ebit_margin", "EBIT margin", TEAL),
                         ("net_margin", "Net margin", NAVY)):
        fig.add_trace(go.Scatter(x=df["fiscal_year"], y=df[col] * 100, mode="lines+markers", name=name,
                                 line=dict(color=c, width=3)))
    fig.update_layout(title="Margin Profile", xaxis_title="Fiscal year", yaxis_title="Margin (% of revenue)",
                      yaxis=dict(ticksuffix="%"), **_BASE)
    return fig


def geo(df: pd.DataFrame) -> go.Figure:  # type: ignore[name-defined]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["fiscal_year"], y=df["domestic_revenue"], name="Domestic", marker_color=NAVY))
    fig.add_trace(go.Bar(x=df["fiscal_year"], y=df["international_revenue"], name="International", marker_color=TEAL))
    fig.update_layout(title="Revenue by Geography", xaxis_title="Fiscal year", yaxis_title="Revenue (R$ M)",
                      barmode="stack", **_BASE)
    return fig


def fcf(df: pd.DataFrame) -> go.Figure:  # type: ignore[name-defined]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=df["fiscal_year"], y=df["free_cash_flow"], name="FCF", marker_color=TEAL), secondary_y=False)
    fig.add_trace(go.Scatter(x=df["fiscal_year"], y=df["fcf_yield"] * 100, mode="lines+markers", name="FCF yield",
                             line=dict(color=NAVY, width=3)), secondary_y=True)
    fig.update_layout(title="Free Cash Flow and Yield", xaxis_title="Fiscal year", **_BASE)
    fig.update_yaxes(title_text="FCF (R$ M)", secondary_y=False)
    fig.update_yaxes(title_text="FCF yield (% of mkt cap)", ticksuffix="%", secondary_y=True)
    return fig


def leverage(df: pd.DataFrame) -> go.Figure:  # type: ignore[name-defined]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["fiscal_year"], y=df["debt_to_equity"], name="Total debt / equity", marker_color=SLATE))
    fig.add_trace(go.Bar(x=df["fiscal_year"], y=df["net_debt_to_equity"], name="Net debt / equity", marker_color=NAVY))
    fig.update_layout(title="Leverage", xaxis_title="Fiscal year", yaxis_title="x", barmode="group", **_BASE)
    return fig


def sensitivity(grid: pd.DataFrame) -> go.Figure:  # type: ignore[name-defined]
    z = grid.values
    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=[f"{c:.2f}" for c in grid.columns],
        y=[f"{r:.1%}" for r in grid.index],
        colorscale=[[0.0, "#F7C6C7"], [0.45, "#F3E2A5"], [0.45, "#FFFFFF"], [0.55, "#FFFFFF"],
                    [0.55, "#D8E8D8"], [1.0, "#0E7C7B"]],
        colorbar=dict(title="Target price (R$)"),
    ))
    for i, row in enumerate(z):
        for j, v in enumerate(row):
            fig.add_annotation(x=f"{grid.columns[j]:.2f}", y=f"{grid.index[i]:.1%}", text=f"{v:.2f}",
                               showarrow=False, font=dict(color="black", size=11))
    fig.update_layout(title="Target Price Sensitivity — Selic vs. USD/BRL",
                      xaxis_title="USD/BRL", yaxis_title="Selic", **_BASE)
    return fig


def bridge(df: pd.DataFrame) -> go.Figure:  # type: ignore[name-defined]
    fig = go.Figure(go.Waterfall(
        measure=["relative", "relative", "total", "relative", "total"],
        x=df["item"], text=[f"R$ {v:,.0f}M" for v in df["value"]], y=df["value"],
        connector=dict(line=dict(color=GRAY, width=1)),
        decreasing=dict(marker=dict(color=RED)),
        increasing=dict(marker=dict(color=TEAL)),
        totals=dict(marker=dict(color=NAVY)),
    ))
    fig.update_layout(title="DCF Bridge — EV to Equity", yaxis_title="R$ M", showlegend=False, **_BASE)
    return fig
