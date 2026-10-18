"""Financial Modeling Prep client (requer API key; sem mock em src/)."""

from typing import Any, Dict, List, Optional

from .base_client import BaseClient, ClientConfig


class FMPClient(BaseClient):
    def __init__(self, config: ClientConfig) -> None:
        if not config.requires_api_key:
            raise ValueError("FMPClient requer FMP_API_KEY configurada.")
        super().__init__(config)

    def auth_headers(self) -> Dict[str, str]:
        return {"apikey": self.config.api_key or ""}

    def _mock(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("FMP client does not support mock mode in src/.")

    def income_statement(self, ticker: str, period: str = "annual") -> List[Dict[str, Any]]:
        return self.get(f"v3/financial-statements/income-statement/{ticker}", {"period": period}).get("income_statement", [])

    def balance_sheet(self, ticker: str, period: str = "annual") -> List[Dict[str, Any]]:
        return self.get(f"v3/financial-statements/balance-sheet-statement/{ticker}", {"period": period}).get("balance_sheet", [])

    def cash_flow(self, ticker: str, period: str = "annual") -> List[Dict[str, Any]]:
        return self.get(f"v3/financial-statements/cash-flow-statement/{ticker}", {"period": period}).get("cash_flow", [])

    def profile(self, ticker: str) -> Optional[Dict[str, Any]]:
        rows = self.get(f"v3/profile/{ticker}").get("profile", [])
        return rows[0] if rows else None

    def quote(self, ticker: str) -> Optional[Dict[str, Any]]:
        rows = self.get(f"v3/quote/{ticker}").get("quote", [])
        return rows[0] if rows else None
