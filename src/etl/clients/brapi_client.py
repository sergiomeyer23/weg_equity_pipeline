"""Brapi client (requer API key; sem mock em src/)."""

from typing import Any, Dict, List, Optional

from .base_client import BaseClient, ClientConfig


class BrapiClient(BaseClient):
    def __init__(self, config: ClientConfig) -> None:
        if not config.requires_api_key:
            raise ValueError("BrapiClient requer BRAPI_API_KEY configurada.")
        super().__init__(config)

    def auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.config.api_key}"}

    def _mock(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Brapi client does not support mock mode in src/.")

    def quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        results = self.get(f"quote/{ticker}").get("results", [])
        return results[0] if results else None

    def financials(self, ticker: str, statement: str) -> List[Dict[str, Any]]:
        results = self.get(f"financials/{ticker}", {"statement": statement}).get("results", [])
        if not results:
            return []
        key_map = {
            "income": "income_statement",
            "balance_sheet": "balance_sheet",
            "cash_flow": "cash_flow",
        }
        key = key_map.get(statement, statement)
        return results[0].get(key, [])
