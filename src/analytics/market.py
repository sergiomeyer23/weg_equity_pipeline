"""Market statistics derived from the price series."""

from __future__ import annotations

import numpy as np
import pandas as pd


def with_moving_averages(prices: pd.DataFrame, windows=(50, 200)) -> pd.DataFrame:
    out = prices[["date", "close"]].copy()
    for w in windows:
        out[f"ma{w}"] = out["close"].rolling(w).mean()
    return out


def drawdown(prices: pd.DataFrame) -> pd.DataFrame:
    out = prices[["date", "close"]].copy()
    out["drawdown"] = out["close"] / out["close"].cummax() - 1.0
    return out


def annual_returns(prices: pd.DataFrame) -> pd.DataFrame:
    s = prices.set_index("date")["close"]
    last = s.groupby(s.index.year).last()
    first_year = s.groupby(s.index.year).first()
    ret = last.pct_change()
    ret.iloc[0] = last.iloc[0] / first_year.iloc[0] - 1.0  # partial year
    return pd.DataFrame({"year": ret.index, "return": ret.values})


def summary(prices: pd.DataFrame) -> dict:
    r = prices["close"].pct_change().dropna()
    days = (prices["date"].iloc[-1] - prices["date"].iloc[0]).days
    total = prices["close"].iloc[-1] / prices["close"].iloc[0]
    return {
        "last": float(prices["close"].iloc[-1]),
        "cagr": float(total ** (365.25 / days) - 1.0) if days > 0 else float("nan"),
        "vol": float(r.std() * np.sqrt(252)),
        "max_drawdown": float(drawdown(prices)["drawdown"].min()),
    }
