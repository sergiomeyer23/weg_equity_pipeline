"""Yahoo Finance client for prices and reported financials (no API key required)."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd
import yfinance as yf

from .base_client import BaseClient, ClientConfig

_COLUMN_MAP = {
    "Date": "date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adjusted_close",
    "Volume": "volume",
}

_COLUMNS = [
    "ticker",
    "date",
    "open",
    "high",
    "low",
    "close",
    "adjusted_close",
    "volume",
]


@dataclass
class PriceFrame:
    ticker: str
    prices: pd.DataFrame
    info: Dict[str, Any]


class YFinanceClient(BaseClient):
    def __init__(self, config: Optional[ClientConfig] = None) -> None:
        cfg = config or ClientConfig(
            base_url="https://query1.finance.yahoo.com",
            rate_limit_per_second=1.0,
        )
        super().__init__(cfg)

    def auth_headers(self) -> Dict[str, str]:
        return {}

    def _mock(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("YFinance client does not support mock mode.")

    def fetch_prices(self, ticker: str, period: str = "5y") -> PriceFrame:
        tk = yf.Ticker(ticker)
        hist = tk.history(period=period, auto_adjust=False, actions=False)
        if hist.empty:
            raise ValueError(f"No price history for {ticker}")

        df = hist.reset_index().rename(columns=_COLUMN_MAP)
        df["ticker"] = ticker
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df = df[_COLUMNS].sort_values("date", kind="mergesort").reset_index(drop=True)
        return PriceFrame(ticker=ticker, prices=df, info=tk.info or {})

    def fetch_annual_statements(self, ticker: str) -> Dict[str, pd.DataFrame]:
        """Extract income statement, balance sheet and cash flow from yfinance (no API key)."""
        tk = yf.Ticker(ticker)
        out: Dict[str, pd.DataFrame] = {}
        for name, attr in (
            ("income", "income_stmt"),
            ("balance_sheet", "balance_sheet"),
            ("cash_flow", "cashflow"),
        ):
            raw = getattr(tk, attr, None)
            if raw is None or raw.empty:
                out[name] = pd.DataFrame()
                continue
            df = raw.T.reset_index().rename(columns={"index": "fiscal_date"})
            df["statement"] = name
            df["ticker"] = ticker
            out[name] = df
        return out

    def close(self) -> None:
        pass
