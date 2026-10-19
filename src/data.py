"""Loading and normalising processed data for the dashboard and the report."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from .analytics import kpis

TICKER = "WEGE3.SA"
PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"
_MILLION = 1_000_000.0


@dataclass
class Dataset:
    wide: pd.DataFrame          # statements, BRL millions
    prices: pd.DataFrame
    meta: dict                  # market_cap (R$ mi), shares (mi), ...
    geo: Optional[pd.DataFrame]  # fiscal_year, domestic/international_revenue, shares
    synthetic: bool             # True when the data comes from the test fixture (mock)


def _path(name: str) -> Path:
    return PROCESSED / f"{TICKER}_{name}.parquet"


def data_available() -> bool:
    return _path("statements_wide").exists() and _path("prices").exists()


def to_millions(wide: pd.DataFrame) -> pd.DataFrame:
    """CVM reports values in reais; the mock is already in millions."""
    out = wide.copy()
    rev = kpis._get(out, int(out["fiscal_year"].iloc[-1]), kpis.LINE["revenue"])
    if rev is not None and abs(rev) > 1e9:
        cols = [c for c in out.columns if c != "fiscal_year"]
        out[cols] = out[cols] / _MILLION
    return out


def load() -> Dataset:
    wide = to_millions(pd.read_parquet(_path("statements_wide")))
    prices = pd.read_parquet(_path("prices")).sort_values("date").reset_index(drop=True)
    m = pd.read_parquet(_path("metadata")).iloc[0]

    mcap = float(m.get("market_cap") or 0.0)
    shares = float(m.get("shares_outstanding") or 0.0)
    if mcap > 1e9:
        mcap /= _MILLION
    if shares > 1e6:
        shares /= _MILLION
    meta = {"market_cap": mcap, "shares": shares, "beta": m.get("beta"),
            "name": m.get("long_name") or "WEG S.A."}

    geo = None
    if _path("geographic_revenue").exists():
        g = pd.read_parquet(_path("geographic_revenue"))
        gw = g.pivot(index="fiscal_year", columns="line_item", values="value").reset_index()
        geo = kpis.geographic_shares(gw)

    long_path = _path("statements_long")
    synthetic = False
    if long_path.exists():
        src = pd.read_parquet(long_path, columns=["source"])["source"]
        synthetic = bool((src == "mock").all())
    return Dataset(wide, prices, meta, geo, synthetic)
