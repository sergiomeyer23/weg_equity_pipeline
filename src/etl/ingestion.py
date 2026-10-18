"""ETL entry point for WEGE3.SA.

Fontes padrão (sem API key): yfinance para preços e demonstrações;
CVM dados abertos para DRE/BPP/DFC da WEG.
FMP e Brapi só são usados se houver API key configurada.
"""

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

from .clients.brapi_client import BrapiClient
from .clients.base_client import ClientConfig
from .clients.cvm_client import CvmClient
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


def extract_fundamentals_real(
    cvm: CvmClient,
    yf: YFinanceClient,
    ticker: str,
    raw_dir: Path,
) -> Dict[str, List[dict]]:
    """Extrai demonstrações de fontes reais (CVM e yfinance)."""
    payloads: Dict[str, List[dict]] = {}

    # --- CVM dados abertos ---
    cvm_stmts = cvm.fetch_annual_statements()
    for stmt in STATEMENTS:
        df = cvm_stmts.get(stmt, pd.DataFrame())
        if df.empty:
            continue
        # CVM retorna valores em milhares (ESCALA_MOEDA = MIL). Multiplica por 1.000.
        df = df.copy()
        df["value"] = df["value"] * 1_000.0
        # Remove duplicatas: mesma conta+data, fica com o maior valor absoluto
        df = df.sort_values("value", key=lambda s: s.abs(), ascending=False)
        df = df.drop_duplicates(subset=["fiscal_date", "account_code"], keep="first")
        rows = (
            df[["fiscal_date", "value", "account_desc", "statement", "source"]]
            .rename(columns={"fiscal_date": "date", "account_desc": "line_item"})
            .to_dict(orient="records")
        )
        for r in rows:
            r["symbol"] = ticker
        payloads[f"cvm_{stmt}"] = rows
        save_json(
            {"ticker": ticker, "statement": stmt, "provider": "cvm", "rows": rows},
            raw_dir / f"{ticker}_cvm_{stmt}.json",
        )

    # --- yfinance demonstrações (fallback / complemento) ---
    yf_stmts = yf.fetch_annual_statements(ticker)
    for stmt in STATEMENTS:
        df = yf_stmts.get(stmt, pd.DataFrame())
        if df.empty:
            continue
        id_cols = ["fiscal_date", "statement", "ticker"]
        value_cols = [c for c in df.columns if c not in id_cols]
        long_df = df.melt(id_vars=id_cols, value_vars=value_cols, var_name="line_item", value_name="value")
        long_df = long_df.rename(columns={"fiscal_date": "date"})
        rows = long_df.to_dict(orient="records")
        payloads[f"yf_{stmt}"] = rows
        save_json(
            {"ticker": ticker, "statement": stmt, "provider": "yfinance", "rows": rows},
            raw_dir / f"{ticker}_yf_{stmt}.json",
        )

    return payloads


def extract_fundamentals_mock(
    fmp: Optional[FMPClient],
    brapi: Optional[BrapiClient],
    ticker: str,
    raw_dir: Path,
) -> Dict[str, List[dict]]:
    """Extrai de FMP/Brapi somente se houver API key. Senão, retorna vazio."""
    payloads: Dict[str, List[dict]] = {}
    if fmp is not None:
        for stmt in STATEMENTS:
            try:
                rows = getattr(fmp, stmt)(ticker)
            except Exception as exc:  # noqa: BLE001
                logger.warning("FMP %s falhou: %s", stmt, exc)
                rows = []
            payloads[f"fmp_{stmt}"] = rows
            save_json(
                {"ticker": ticker, "statement": stmt, "provider": "fmp", "rows": rows},
                raw_dir / f"{ticker}_fmp_{stmt}.json",
            )
    if brapi is not None:
        for stmt in STATEMENTS:
            try:
                rows = brapi.financials(ticker, statement=stmt)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Brapi %s falhou: %s", stmt, exc)
                rows = []
            payloads[f"brapi_{stmt}"] = rows
            save_json(
                {"ticker": ticker, "statement": stmt, "provider": "brapi", "rows": rows},
                raw_dir / f"{ticker}_brapi_{stmt}.json",
            )
    return payloads


def transform_all(
    price_frame: PriceFrame,
    fundamentals: Dict[str, List[dict]],
    ticker: str,
    currency: str,
    processed_dir: Path,
) -> Dict[str, pd.DataFrame]:
    out: Dict[str, pd.DataFrame] = {}

    prices = clean_prices(price_frame.prices, ticker)
    out["prices"] = prices
    save_parquet(prices, processed_dir / f"{ticker}_prices.parquet")

    frames: Dict[str, pd.DataFrame] = {}
    for stmt in STATEMENTS:
        # Prefere CVM, depois yfinance, depois FMP/Brapi
        rows = (
            fundamentals.get(f"cvm_{stmt}")
            or fundamentals.get(f"yf_{stmt}")
            or fundamentals.get(f"fmp_{stmt}")
            or fundamentals.get(f"brapi_{stmt}", [])
        )
        frames[stmt] = tidy(rows, stmt, ticker, currency=currency, source="cvm_or_yf")
        save_parquet(frames[stmt], processed_dir / f"{ticker}_{stmt}.parquet")

    combined = combine(frames)
    out["statements"] = combined
    save_parquet(combined, processed_dir / f"{ticker}_statements_long.parquet")

    wide = to_wide(combined)
    out["statements_wide"] = wide
    save_parquet(wide, processed_dir / f"{ticker}_statements_wide.parquet")

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
    cvm = CvmClient()

    fmp: Optional[FMPClient] = None
    brapi: Optional[BrapiClient] = None
    if config.get("fmp_api_key"):
        fmp = FMPClient(ClientConfig(
            base_url="https://financialmodelingprep.com/api",
            api_key=config.get("fmp_api_key"),
            rate_limit_per_second=0.5,
        ))
    if config.get("brapi_api_key"):
        brapi = BrapiClient(ClientConfig(
            base_url="https://brapi.dev/api",
            api_key=config.get("brapi_api_key"),
            rate_limit_per_second=0.5,
        ))

    return yf, cvm, fmp, brapi


def run(ticker: str, period: str, mock: bool, config_path: Path, output: Path) -> Dict[str, pd.DataFrame]:
    config = load_config(config_path)
    raw = output / config.get("data", {}).get("raw_dir", "data/raw")
    processed = output / config.get("data", {}).get("processed_dir", "data/processed")

    yf, cvm, fmp, brapi = build_clients(config, ticker, mock)

    if mock:
        logger.warning("Modo MOCK ativado — dados sintéticos de tests/fixtures/mocks.py")
        from tests.fixtures.mocks import STATEMENTS as MOCK_STATEMENTS  # noqa: PLC0415
        # Converte o fixture para o formato esperado pelo transform
        fundamentals: Dict[str, List[dict]] = {}
        for stmt in STATEMENTS:
            rows = getattr(MOCK_STATEMENTS, f"{stmt}_statement", [])
            # Reorganiza para o formato de lista de dicts que o transform entende
            fundamentals[f"mock_{stmt}"] = rows
        price_frame = extract_prices(yf, ticker, period, raw)
        result = transform_all(
            price_frame,
            {k: v for k, v in fundamentals.items()},
            ticker,
            config.get("currency", "BRL"),
            processed,
        )
    else:
        price_frame = extract_prices(yf, ticker, period, raw)
        fundamentals = extract_fundamentals_real(cvm, yf, ticker, raw)
        if fmp or brapi:
            mock_payloads = extract_fundamentals_mock(fmp, brapi, ticker, raw)
            fundamentals.update(mock_payloads)
        result = transform_all(
            price_frame,
            fundamentals,
            ticker,
            config.get("currency", "BRL"),
            processed,
        )

    yf.close()
    cvm.close()
    if fmp:
        fmp.close()
    if brapi:
        brapi.close()
    logger.info("ETL done -> %s", processed)
    return result


def main() -> None:
    p = argparse.ArgumentParser(description="WEGE3.SA ETL pipeline")
    p.add_argument("--ticker", default="WEGE3.SA")
    p.add_argument("--period", default="5y")
    p.add_argument("--mock", action="store_true", default=False, help="Usa dados sintéticos de tests/fixtures/")
    p.add_argument("--live", action="store_true", help="Força modo real (mesmo sem --mock)")
    p.add_argument("--config", default="config/settings.yaml")
    p.add_argument("--output", default=".")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    setup_logging(verbose=args.verbose)
    run(args.ticker, args.period, args.mock and not args.live, Path(args.config), Path(args.output))


if __name__ == "__main__":
    main()
