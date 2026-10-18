"""Base REST client with retry and rate-limit handling."""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class ClientConfig:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        rate_limit_per_second: float = 1.0,
        mock_mode: bool = False,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.rate_limit_per_second = rate_limit_per_second
        self.mock_mode = mock_mode


class BaseClient(ABC):
    def __init__(self, config: ClientConfig) -> None:
        self.config = config
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "weg-equity-pipeline/1.0",
            }
        )
        if config.api_key:
            self._session.headers.update(self.auth_headers())
        self._setup_retries()
        self._last_call = 0.0

    @abstractmethod
    def auth_headers(self) -> Dict[str, str]:
        ...

    def _setup_retries(self) -> None:
        retry = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def _throttle(self) -> None:
        interval = 1.0 / max(self.config.rate_limit_per_second, 0.1)
        elapsed = time.time() - self._last_call
        if 0 <= elapsed < interval:
            time.sleep(interval - elapsed)

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self.config.mock_mode:
            return self._mock(path, params or {})

        self._throttle()
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        logger.info("GET %s", url)
        response = self._session.get(url, params=params, timeout=self.config.timeout)
        response.raise_for_status()
        self._last_call = time.time()
        return response.json()

    @abstractmethod
    def _mock(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def close(self) -> None:
        self._session.close()
