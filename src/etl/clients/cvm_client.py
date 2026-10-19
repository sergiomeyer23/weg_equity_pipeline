"""Pulls WEG's annual statements (DFP) from the CVM open data portal. No API key needed."""

from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

WEG_CNPJ = "84429695000111"

_DFP_BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/"

# Maps the CSV file prefix inside the ZIP to the statement type
_STATEMENT_PREFIX: Dict[str, str] = {
    "DRE": "income",
    "BPP": "balance_sheet",
    "DFC": "cash_flow",
    "DRA": "income",  # cumulative income statement
    "BPA": "balance_sheet",  # Balance sheet, assets
    "BPP": "balance_sheet",
}

# Column names in the CVM CSVs (may vary by year)
_COLUMN_ALIASES: Dict[str, List[str]] = {
    "cnpj": ["CNPJ_CIA", "CNPJ"],
    "ref_date": ["DT_REF", "DATA_REFERENCIA", "DT_FIM_EXERC"],
    "account": ["CD_CONTA", "CONTA"],
    "account_desc": ["DS_CONTA", "DESCRICAO"],
    "value": ["VL_CONTA", "VALOR"],
}


class CvmClient:
    """Client for CVM DFP filings (open data)."""

    def __init__(self, timeout: float = 60.0) -> None:
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "weg-equity-pipeline/1.0"})

    def _download_dfp_zip(self, year: int) -> Optional[bytes]:
        url = f"{_DFP_BASE}dfp_cia_aberta_{year}.zip"
        logger.info("Downloading DFP %d: %s", year, url)
        try:
            resp = self._session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as exc:
            logger.error("Failed to download %s: %s", url, exc)
            return None

    def _extract_csvs(self, zip_bytes: bytes) -> Dict[str, pd.DataFrame]:
        """Extract CSVs from the ZIP, keyed by statement type (DRE, BPP, DFC...)."""
        out: Dict[str, pd.DataFrame] = {}
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                for name in zf.namelist():
                    if not name.lower().endswith(".csv"):
                        continue
                    # Consolidated statements only: the _ind_ files are parent-company
                    # numbers (equity-method income, intercompany dividends) and DRA is
                    # comprehensive income, neither of which belongs next to the DRE/BP/DFC.
                    if "_ind" in name.lower() or "_DRA_" in name.upper():
                        continue
                    upper = name.upper()
                    stmt_type = None
                    for key, val in _STATEMENT_PREFIX.items():
                        if f"_{key}_" in f"_{upper}_" or upper.endswith(f"_{key}_"):
                            stmt_type = val
                            break
                    if stmt_type is None:
                        continue
                    try:
                        with zf.open(name) as f:
                            df = pd.read_csv(f, sep=";", encoding="latin-1", low_memory=False)
                            if stmt_type in out:
                                out[stmt_type] = pd.concat([out[stmt_type], df], ignore_index=True)
                            else:
                                out[stmt_type] = df
                            logger.info("Read %s (%d rows, %s)", name, len(df), stmt_type)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to read %s: %s", name, exc)
        except zipfile.BadZipFile as exc:
            logger.error("Invalid ZIP: %s", exc)
        return out

    def _filter_weg(self, df: pd.DataFrame) -> pd.DataFrame:
        cnpj_cols = [c for c in df.columns if c.upper() in _COLUMN_ALIASES["cnpj"]]
        if not cnpj_cols:
            return pd.DataFrame()
        cnpj_col = cnpj_cols[0]
        cnpj_clean = df[cnpj_col].astype(str).str.replace(r"[.\-/]", "", regex=True)
        return df[cnpj_clean.str.contains(WEG_CNPJ, na=False)].copy()

    def _first_col(self, df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
        for c in aliases:
            if c in df.columns:
                return c
        return None

    def fetch_annual_statements(self, years: Optional[List[int]] = None) -> Dict[str, pd.DataFrame]:
        """Extract income statement, balance sheet and cash flow for WEG from CVM, for the available years."""
        if years is None:
            # DFP for year N is filed in early N+1, so the latest candidate is last year.
            # Years that aren't published yet just fail the download and get skipped.
            last = date.today().year - 1
            years = list(range(last, last - 6, -1))

        combined: Dict[str, List[pd.DataFrame]] = {"income": [], "balance_sheet": [], "cash_flow": []}

        for year in years:
            zip_bytes = self._download_dfp_zip(year)
            if zip_bytes is None:
                continue
            dfs = self._extract_csvs(zip_bytes)
            for stmt_type, df in dfs.items():
                weg_df = self._filter_weg(df)
                if weg_df.empty:
                    continue
                date_col = self._first_col(weg_df, _COLUMN_ALIASES["ref_date"])
                val_col = self._first_col(weg_df, _COLUMN_ALIASES["value"])
                if date_col is None or val_col is None:
                    continue
                # Each filing repeats the prior year as "PENÚLTIMO"; keep the current year only.
                if "ORDEM_EXERC" in weg_df.columns:
                    weg_df = weg_df[weg_df["ORDEM_EXERC"].astype(str).str.upper().str.startswith("ÚLTIMO")]
                result = weg_df[[date_col, val_col, "CD_CONTA", "DS_CONTA"]].copy()
                result.columns = ["fiscal_date", "value", "account_code", "account_desc"]
                result["fiscal_date"] = pd.to_datetime(result["fiscal_date"], errors="coerce")
                result["statement"] = stmt_type
                result["source"] = "cvm"
                combined[stmt_type].append(result.dropna(subset=["fiscal_date", "value"]))

        out: Dict[str, pd.DataFrame] = {}
        for stmt_type in ("income", "balance_sheet", "cash_flow"):
            frames = combined[stmt_type]
            out[stmt_type] = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        return out

    def close(self) -> None:
        self._session.close()
