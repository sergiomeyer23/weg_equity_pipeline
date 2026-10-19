"""Plotly figures for the dashboard and the static report.

Conventions: one y-axis per chart (no dual axes), neutral ink for text, colour
only on marks; colour-blind-validated categorical palette (first 3 slots) and
a sequential blue for magnitude.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go

# Categorical (fixed order): blue, orange, aqua
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
# Status (always paired with a label/sign)
POS = "#1b7f4d"
NEG = "#c0392b"
INK = "#1f2328"
MUTED = "#6e7781"
GRID = "#e6e9ed"
SEQ = [[0, "#cde2fb"], [0.35, "#86b6ef"], [0.7, "#2a78d6"], [1, "#0d366b"]]

_BASE = dict(
    template="plotly_white",
    font=dict(family="Arial, sans-serif", size=12, color=INK),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    margin=dict(l=60, r=20, t=70, b=50),
    hovermode="x unified",
)


def _fig(title: str, ytitle: str = "", xtitle: str = "", **layout) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(title=dict(text=title, x=0, font=dict(size=15)), xaxis_title=xtitle,
                      yaxis_title=ytitle, **{**_BASE, **layout})
    fig.update_xaxes(showgrid=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def _years(df: pd.DataFrame) -> list:
    return [str(y) for y in df["fiscal_year"]]


def revenue(df: pd.DataFrame) -> go.Figure:
    fig = _fig("Annual net revenue", "BRL millions")
    fig.add_bar(x=_years(df), y=df["revenue"], marker_color=BLUE, name="Revenue",
                text=[f"{v:,.0f}" for v in df["revenue"]], textposition="outside", cliponaxis=False)
    fig.update_layout(showlegend=False, hovermode="closest")
    return fig


def margins(df: pd.DataFrame) -> go.Figure:
    fig = _fig("Margin profile", "% of revenue")
    for col, name, c in (("gross_margin", "Gross", BLUE), ("ebit_margin", "EBIT", ORANGE),
                         ("net_margin", "Net", AQUA)):
        fig.add_scatter(x=_years(df), y=df[col] * 100, mode="lines+markers", name=name,
                        line=dict(color=c, width=2), marker=dict(size=8, line=dict(color="white", width=2)),
                        hovertemplate="%{y:.1f}%")
    fig.update_yaxes(ticksuffix="%")
    return fig


def roic(df: pd.DataFrame, wacc: float = 0.16) -> go.Figure:
    fig = _fig("ROIC vs. cost of capital (WACC)", "%")
    fig.add_bar(x=_years(df), y=df["roic"] * 100, marker_color=BLUE, name="ROIC",
                text=[f"{v:.1%}" for v in df["roic"]], textposition="outside", cliponaxis=False)
    fig.add_scatter(x=_years(df), y=[wacc * 100] * len(df), mode="lines", name=f"WACC {wacc:.1%}",
                    line=dict(color=ORANGE, width=2, dash="dash"))
    fig.update_yaxes(ticksuffix="%")
    return fig


def leverage(df: pd.DataFrame) -> go.Figure:
    fig = _fig("Leverage", "x equity")
    fig.add_bar(x=_years(df), y=df["debt_to_equity"], name="Gross debt / equity", marker_color=BLUE)
    fig.add_bar(x=_years(df), y=df["net_debt_to_equity"], name="Net debt / equity", marker_color=ORANGE)
    fig.update_layout(barmode="group", bargap=0.3)
    return fig


def fcf(df: pd.DataFrame) -> go.Figure:
    fig = _fig("Free cash flow", "BRL millions")
    fig.add_bar(x=_years(df), y=df["free_cash_flow"], marker_color=BLUE, name="FCF",
                text=[f"{v:,.0f}" for v in df["free_cash_flow"]], textposition="outside", cliponaxis=False)
    fig.update_layout(showlegend=False, hovermode="closest")
    return fig


def fcf_yield(df: pd.DataFrame) -> go.Figure:
    fig = _fig("FCF yield (on current market cap)", "%")
    fig.add_scatter(x=_years(df), y=df["fcf_yield"] * 100, mode="lines+markers", name="FCF yield",
                    line=dict(color=AQUA, width=2), marker=dict(size=8, line=dict(color="white", width=2)),
                    hovertemplate="%{y:.1f}%")
    fig.update_yaxes(ticksuffix="%")
    fig.update_layout(showlegend=False)
    return fig


def cash_flow(df: pd.DataFrame) -> go.Figure:
    """df: fiscal_year, ocf, capex (negative), fcf."""
    fig = _fig("Operating cash flow, capex and free cash flow", "BRL millions")
    fig.add_bar(x=_years(df), y=df["ocf"], name="Operating cash flow", marker_color=BLUE)
    fig.add_bar(x=_years(df), y=df["capex"], name="Capex", marker_color=ORANGE)
    fig.add_bar(x=_years(df), y=df["fcf"], name="Free cash flow", marker_color=AQUA)
    fig.update_layout(barmode="group", bargap=0.3)
    return fig


def geo(df: pd.DataFrame) -> go.Figure:
    fig = _fig("Revenue by origin", "BRL millions")
    fig.add_bar(x=_years(df), y=df["domestic_revenue"], name="Brazil", marker_color=BLUE)
    fig.add_bar(x=_years(df), y=df["international_revenue"], name="International", marker_color=ORANGE)
    fig.update_layout(barmode="stack", bargap=0.3)
    fig.update_traces(marker_line=dict(color="white", width=2))
    return fig


def price(df: pd.DataFrame) -> go.Figure:
    """df: date, close, ma50, ma200."""
    fig = _fig("Closing price and moving averages", "BRL per share")
    fig.add_scatter(x=df["date"], y=df["close"], mode="lines", name="Close",
                    line=dict(color=BLUE, width=1.5), hovertemplate="BRL %{y:.2f}")
    fig.add_scatter(x=df["date"], y=df["ma50"], mode="lines", name="50-day MA",
                    line=dict(color=ORANGE, width=2), hovertemplate="BRL %{y:.2f}")
    fig.add_scatter(x=df["date"], y=df["ma200"], mode="lines", name="200-day MA",
                    line=dict(color=AQUA, width=2), hovertemplate="BRL %{y:.2f}")
    return fig


def drawdown(df: pd.DataFrame) -> go.Figure:
    fig = _fig("Drawdown from peak", "%")
    fig.add_scatter(x=df["date"], y=df["drawdown"] * 100, mode="lines", fill="tozeroy",
                    line=dict(color=NEG, width=1.5), fillcolor="rgba(192,57,43,0.18)",
                    name="Drawdown", hovertemplate="%{y:.1f}%")
    fig.update_yaxes(ticksuffix="%")
    fig.update_layout(showlegend=False)
    return fig


def annual_returns(df: pd.DataFrame) -> go.Figure:
    fig = _fig("Annual share return (latest year may be partial)", "%")
    fig.add_bar(x=df["year"].astype(str), y=df["return"] * 100,
                marker_color=[POS if v >= 0 else NEG for v in df["return"]],
                text=[f"{'▲' if v >= 0 else '▼'} {v:+.1%}" for v in df["return"]],
                textposition="outside", cliponaxis=False)
    fig.update_yaxes(ticksuffix="%")
    fig.update_layout(showlegend=False, hovermode="closest")
    return fig


def bridge(df: pd.DataFrame) -> go.Figure:
    fig = _fig("DCF bridge: enterprise value to equity value", "BRL millions", hovermode="closest")
    fig.add_trace(go.Waterfall(
        measure=["relative", "relative", "total", "relative", "total"],
        x=df["item"], y=df["value"], text=[f"BRL {v:,.0f}M" for v in df["value"]], textposition="outside",
        connector=dict(line=dict(color=GRID, width=1)),
        decreasing=dict(marker=dict(color=NEG)), increasing=dict(marker=dict(color=BLUE)),
        totals=dict(marker=dict(color=INK)),
    ))
    fig.update_layout(showlegend=False)
    return fig


def sensitivity(grid: pd.DataFrame, market_price: Optional[float] = None) -> go.Figure:
    fig = _fig("Target price (BRL): Selic × USD/BRL", "Selic", "USD/BRL", hovermode="closest")
    fig.add_trace(go.Heatmap(
        z=grid.values, x=[f"{c:.2f}" for c in grid.columns], y=[f"{r:.2%}" for r in grid.index],
        colorscale=SEQ, colorbar=dict(title="BRL"), xgap=2, ygap=2,
        texttemplate="%{z:.2f}", textfont=dict(size=12),
        hovertemplate="Selic %{y} · USD/BRL %{x}<br>BRL %{z:.2f}<extra></extra>",
    ))
    return fig


def tornado(df: pd.DataFrame) -> go.Figure:
    base = float(df["base"].iloc[0])
    fig = _fig("How much each assumption moves the target price", "", "Target price (BRL)", hovermode="closest")
    fig.add_bar(y=df["driver"], x=df["low"] - base, base=base, orientation="h", name="Adverse case",
                marker_color=ORANGE, hovertemplate="BRL %{customdata:.2f}<extra>adverse</extra>", customdata=df["low"])
    fig.add_bar(y=df["driver"], x=df["high"] - base, base=base, orientation="h", name="Favourable case",
                marker_color=BLUE, hovertemplate="BRL %{customdata:.2f}<extra>favourable</extra>", customdata=df["high"])
    fig.add_vline(x=base, line=dict(color=INK, width=1), annotation_text=f"Base BRL {base:.2f}",
                  annotation_position="top")
    fig.update_layout(barmode="overlay", bargap=0.35)
    fig.update_yaxes(showgrid=False)
    fig.update_xaxes(showgrid=True, gridcolor=GRID)
    return fig


def nopat_capital(df: pd.DataFrame) -> go.Figure:
    fig = _fig("Net operating profit after tax (NOPAT) and invested capital", "BRL millions")
    fig.add_bar(x=_years(df), y=df["nopat"], name="NOPAT", marker_color=BLUE)
    fig.add_bar(x=_years(df), y=df["invested_capital"], name="Invested capital", marker_color=ORANGE)
    fig.update_layout(barmode="group", bargap=0.3)
    return fig
