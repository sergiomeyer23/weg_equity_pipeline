"""Brapi client (live or mock)."""

from typing import Any, Dict, List, Optional

from .base_client import BaseClient, ClientConfig
from .mocks import STATEMENTS


def _group(rows) -> Dict[int, Dict[str, float]]:
    grouped: Dict[int, Dict[str, float]] = {}
    for row in rows:
        grouped.setdefault(int(str(row["date"])[:4]), {})[row["line_item"]] = float(row["value"])
    return grouped


def _wrap(rows, key: str) -> Dict[str, Any]:
    return {"results": [{"ticker": "WEGE3.SA", key: [{"year": y, "items": _group(rows)[y]} for y in sorted(_group(rows))]}]}


class BrapiClient(BaseClient):
    def __init__(self, config: ClientConfig) -> None:
        super().__init__(config)

    def auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.config.api_key}"} if self.config.api_key else {}

    def _mock(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        path = path.lstrip("/")
        if path in ("quote/WEGE3.SA", "quote/WEGE3"):
            return {"results": [STATEMENTS.quote]}
        if path.startswith("financials/"):
            stmt = params.get("statement", "income")
            if stmt == "income":
                return _wrap(STATEMENTS.income_statement, "income_statement")
            if stmt == "balance_sheet":
                return _wrap(STATEMENTS.balance_sheet, "balance_sheet")
            if stmt == "cash_flow":
                return _wrap(STATEMENTS.cash_flow, "cash_flow")
            if stmt == "geographic":
                return {"geographic_revenue": STATEMENTS.geographic_revenue}
            raise KeyError(f"Unknown Brapi statement: {stmt}")
        if "geographic-revenue" in path:
            return {"geographic_revenue": STATEMENTS.geographic_revenue}
        if path.startswith("quote/"):
            return {"results": [STATEMENTS.quote]}
        raise KeyError(f"Unknown Brapi mock endpoint: {path}")

    def quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        results = self.get(f"quote/{ticker}").get("results", [])
        return results[0] if results else None

    def financials(self, ticker: str, statement: str) -> List[Dict[str, Any]]:
        results = self.get(f"financials/{ticker}", {"statement": statement}).get("results", [])
        if not results:
            return []
        key = {"income": "income_statement", "balance_sheet": "balance_sheet", "cash_flow": "cash_flow", "geographic": "geographic_revenue"}.get(statement, statement)
        return results[0].get(key, [])

    def geographic_revenue(self, ticker: str) -> List[Dict[str, Any]]:
        return self.get(f"geographic-revenue/{ticker}").get("geographic_revenue", [])
