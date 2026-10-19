"""Calculations shared by the dashboard (app.py) and the static report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .analytics import kpis, market, valuation
from .data import Dataset


@dataclass
class Analysis:
    margins: pd.DataFrame
    roic: pd.DataFrame
    leverage: pd.DataFrame
    fcf: pd.DataFrame
    cash_flow: pd.DataFrame
    geo: Optional[pd.DataFrame]
    market_px: float
    intl_share: float
    net_debt: float
    base_rev: float


def analyse(ds: Dataset, years: Optional[tuple] = None) -> Analysis:
    wide = ds.wide
    if years:
        wide = wide[wide["fiscal_year"].between(*years)].reset_index(drop=True)
    cf = []
    for y in wide["fiscal_year"]:
        cf.append({
            "fiscal_year": int(y),
            "ocf": kpis._get(wide, int(y), kpis.LINE["operating_cf"]),
            "capex": kpis._get(wide, int(y), kpis.LINE["capex"]),
            "fcf": kpis._get(wide, int(y), kpis.LINE["fcf"]),
        })
    lev = kpis.compute_leverage(wide)
    geo = ds.geo
    if geo is not None and years:
        geo = geo[geo["fiscal_year"].between(*years)].reset_index(drop=True)
    intl = float(geo.iloc[-1]["international_share"]) if geo is not None and len(geo) else 0.0
    return Analysis(
        margins=kpis.compute_margins(wide),
        roic=kpis.compute_roic(wide),
        leverage=lev,
        fcf=kpis.compute_fcf_yield(wide, ds.meta["market_cap"]),
        cash_flow=pd.DataFrame(cf).dropna(),
        geo=geo,
        market_px=float(ds.prices["close"].iloc[-1]),
        intl_share=intl,
        net_debt=float(lev.iloc[-1]["net_debt"]),
        base_rev=float(kpis._get(wide, int(wide["fiscal_year"].iloc[-1]), kpis.LINE["revenue"])),
    )


def dcf(ds: Dataset, an: Analysis, a: Optional[valuation.Assumptions] = None):
    model = valuation.DCF(a)
    res = model.run(an.base_rev, None, an.net_debt, ds.meta["shares"], an.intl_share)
    return model, res


def upside(target: float, px: float) -> float:
    return target / px - 1.0 if px > 0 else float("nan")


SELICS = [0.0925, 0.1075, 0.1175, 0.1325, 0.1425]
FXS = [4.40, 4.80, 5.10, 5.50, 5.80]


def sensitivity(ds: Dataset, an: Analysis, model: valuation.DCF) -> pd.DataFrame:
    return model.grid(an.base_rev, 0.0, an.net_debt, ds.meta["shares"], an.intl_share, FXS, SELICS)


def tornado(ds: Dataset, an: Analysis, a: valuation.Assumptions) -> pd.DataFrame:
    return valuation.tornado(a, an.base_rev, an.net_debt, ds.meta["shares"], an.intl_share)
