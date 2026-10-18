"""ETL entry point for WEGE3.SA."""

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import yaml

from .clients.brapi_client import BrapiClient
from .clients.base_client import ClientConfig
from .clients.fmp_client import FMPClient
from .clients.yfinance_client import PriceFrame, YFinanceClient
from .transform import clean_prices, combine, tidy, to_wide

logger = logging.getLogger("weg.etl")
STATEMENTS = ["income", "balance_sheet", "cash_flow"]


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def save_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)
    logger.info("Wrote %s", path)


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    logger.info("Wrote %s (%d rows)", path, len(df))


def extract_prices(client: YFinanceClient, ticker: str, period: str, raw_dir: Path) -> PriceFrame:
    frame = client.fetch_prices(ticker, period=period)
    save_json(
        {
            "ticker": ticker,
            "period": period,
            "extracted_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source": "yfinance",
            "prices": frame.prices.to_dict(orient="records"),
            "info": frame.info,
        },
        raw_dir / f"{ticker}_prices.json",
    )
    return frame


def extract_fundamentals(fmp: FMPClient, brapi: BrapiClient, ticker: str, raw_dir: Path, period: str = "annual") -> Dict[str, List[dict]]:
    payloads: Dict[str, List[dict]] = {}
    for name, getter in (("income", fmp.income_statement), ("balance_sheet", fmp.balance_sheet), ("cash_flow", fmp.cash_flow)):
        rows = getter(ticker, period=period)
        payloads[f"fmp_{name}"] = rows
        save_json({"ticker": ticker, "statement": name, "period": period, "provider": "fmp", "rows": rows}, raw_dir / f"{ticker}_fmp_{name}.json")

    for name, getter in (("income", brapi.financials), ("balance_sheet", brapi.financials), ("cash_flow", brapi.financials)):
        rows = getter(ticker, statement=name)
        payloads[f"brapi_{name}"] = rows
        save_json({"ticker": ticker, "statement": name, "period": period, "provider": "brapi", "rows": rows}, raw_dir / f"{ticker}_brapi_{name}.json")

    geo = brapi.geographic_revenue(ticker)
    payloads["brapi_geographic_revenue"] = geo
    save_json({"ticker": ticker, "statement": "geographic_revenue", "provider": "brapi", "rows": geo}, raw_dir / f"{ticker}_geographic_revenue.json")

    profile = fmp.profile(ticker)
    save_json({"ticker": ticker, "provider": "fmp", "profile": profile}, raw_dir / f"{ticker}_profile.json")
    quote = brapi.quote(ticker)
    save_json({"ticker": ticker, "provider": "brapi", "quote": quote}, raw_dir / f"{ticker}_quote.json")
    return payloads


def transform_all(price_frame: PriceFrame, fundamentals: Dict[str, List[dict]], ticker: str, currency: str, processed_dir: Path) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}

    prices = clean_prices(price_frame.prices, ticker)
    out["prices"] = prices
    save_parquet(prices, processed_dir / f"{ticker}_prices.parquet")

    frames: Dict[str, pd.DataFrame] = {}
    for stmt in STATEMENTS:
        rows = fundamentals.get(f"fmp_{stmt}") or fundamentals.get(f"brapi_{stmt}", [])
        frames[stmt] = tidy(rows, stmt, ticker, currency=currency, source="fmp")
        save_parquet(frames[stmt], processed_dir / f"{ticker}_{stmt}.parquet")

    combined = combine(frames)
    out["statements"] = combined
    save_parquet(combined, processed_dir / f"{ticker}_statements_long.parquet")

    wide = to_wide(combined)
    out["statements_wide"] = wide
    save_parquet(wide, processed_dir / f"{ticker}_statements_wide.parquet")

    geo = tidy(fundamentals.get("brapi_geographic_revenue", []), "geographic_revenue", ticker, currency=currency, source="brapi")
    out["geographic_revenue"] = geo
    save_parquet(geo, processed_dir / f"{ticker}_geographic_revenue.parquet")

    meta = pd.DataFrame([{
        "ticker": ticker,
        "short_name": price_frame.info.get("shortName"),
        "long_name": price_frame.info.get("longName"),
        "sector": price_frame.info.get("sector"),
        "industry": price_frame.info.get("industry"),
        "currency": currency,
        "market_cap": price_frame.info.get("marketCap"),
        "shares_outstanding": price_frame.info.get("sharesOutstanding"),
        "beta": price_frame.info.get("beta"),
    }])
    out["metadata"] = meta
    save_parquet(meta, processed_dir / f"{ticker}_metadata.parquet")
    return out


def build_clients(config: dict, ticker: str, mock: bool):
    yf = YFinanceClient()
    fmp = FMPClient(ClientConfig(base_url="https://financialmodelingprep.com/api", api_key=config.get("fmp_api_key"), mock_mode=mock, rate_limit_per_second=0.5))
    brapi = BrapiClient(ClientConfig(base_url="https://brapi.dev/api", api_key=config.get("brapi_api_key"), mock_mode=mock, rate_limit_per_second=0.5))
    return yf, fmp, brapi


def run(ticker: str, period: str, mock: bool, config_path: Path, output: Path) -> Dict[str, pd.DataFrame]:
    config = load_config(config_path)
    raw = output / config.get("data", {}).get("raw_dir", "data/raw")
    processed = output / config.get("data", {}).get("processed_dir", "data/processed")

    yf, fmp, brapi = build_clients(config, ticker, mock)
    prices = extract_prices(yf, ticker, period, raw)
    fundamentals = extract_fundamentals(fmp, brapi, ticker, raw, period=period)
    result = transform_all(prices, fundamentals, ticker, config.get("currency", "BRL"), processed)

    yf.close()
    fmp.close()
    brapi.close()
    logger.info("ETL done -> %s", processed)
    return result


def main() -> None:
    p = argparse.ArgumentParser(description="WEGE3.SA ETL pipeline")
    p.add_argument("--ticker", default="WEGE3.SA")
    p.add_argument("--period", default="5y")
    p.add_argument("--mock", action="store_true", default=True)
    p.add_argument("--live", action="store_true")
    p.add_argument("--config", default="config/settings.yaml")
    p.add_argument("--output", default=".")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    setup_logging(verbose=args.verbose)
    run(args.ticker, args.period, args.mock and not args.live, Path(args.config), Path(args.output))


if __name__ == "__main__":
    main()
