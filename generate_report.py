"""Generate the project's static outputs: PNG/HTML figures and CSV tables.

Usage:
    python generate_report.py

To export PNGs, kaleido needs Chrome: run `plotly_get_chrome` or
`BROWSER_PATH=/path/to/chrome python generate_report.py`.

The figures feed the README and the tables serve as an executive summary for
anyone who wants the numbers without running the dashboard.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src import data, report
from src.analytics import market, valuation
from src.viz import charts

OUT = Path(__file__).parent / "outputs"
FIGS, TABLES = OUT / "figures", OUT / "tables"


def save_figure(fig, name: str, width: int = 1100, height: int = 560) -> None:
    """Save the figure as HTML (always) and PNG (if kaleido/Chrome is available)."""
    fig.write_html(FIGS / f"{name}.html", include_plotlyjs="cdn", full_html=True)
    try:
        fig.write_image(FIGS / f"{name}.png", width=width, height=height, scale=2)
        print(f"  ok {name}.png + .html")
    except Exception:  # kaleido/Chrome missing
        print(f"  ok {name}.html (PNG skipped: install 'kaleido' and Chrome to export images)")


def save_table(df, name: str) -> None:
    df.to_csv(TABLES / f"{name}.csv", index=False, encoding="utf-8-sig")
    print(f"  ok {name}.csv")


def main() -> int:
    if not data.data_available():
        print("Data not found. Run: python -m src.etl.ingestion --mock (or --live)")
        return 1
    FIGS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)

    ds = data.load()
    an = report.analyse(ds)
    a = valuation.Assumptions()
    model, res = report.dcf(ds, an, a)
    px = an.market_px
    print(f"Source: {'SYNTHETIC (mock)' if ds.synthetic else 'official (CVM + Yahoo Finance)'}")
    print(f"Target price BRL {res.target_price:.2f} | market BRL {px:.2f}\n")

    print("Generating figures...")
    save_figure(charts.revenue(an.margins), "01_annual_revenue")
    save_figure(charts.margins(an.margins), "02_margins")
    save_figure(charts.roic(an.roic, res.wacc), "03_roic_vs_wacc")
    save_figure(charts.nopat_capital(an.roic), "04_nopat_capital")
    save_figure(charts.leverage(an.leverage), "05_leverage")
    save_figure(charts.cash_flow(an.cash_flow), "06_cash_flow")
    save_figure(charts.fcf_yield(an.fcf), "07_fcf_yield")
    if an.geo is not None:
        save_figure(charts.geo(an.geo), "08_revenue_by_origin")
    save_figure(charts.price(market.with_moving_averages(ds.prices)), "09_price")
    save_figure(charts.drawdown(market.drawdown(ds.prices)), "10_drawdown")
    save_figure(charts.annual_returns(market.annual_returns(ds.prices)), "11_annual_returns")
    save_figure(charts.bridge(valuation.bridge(res)), "12_dcf_bridge")
    save_figure(charts.sensitivity(report.sensitivity(ds, an, model)), "13_sensitivity")
    save_figure(charts.tornado(report.tornado(ds, an, a)), "14_tornado", height=480)

    print("\nGenerating tables...")
    save_table(an.margins, "margins")
    save_table(an.roic, "roic")
    save_table(an.leverage, "leverage")
    save_table(an.fcf, "fcf")
    save_table(report.sensitivity(ds, an, model).reset_index(), "dcf_sensitivity")
    save_table(report.tornado(ds, an, a), "tornado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
