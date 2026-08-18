"""Minimal Revolut X market-data client.

Only the read-only, market-data surface fx-pulse needs (tickers,
candles) is implemented here — this is intentionally a much smaller
client than revolut-x-api's, focused on what the ingestion pipeline
consumes. Request signing matches revolut-x-api exactly (see
fxpulse/auth/signer.py) so it authenticates against the same
registered API key.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from fxpulse.auth.keypair import load_private_key
from fxpulse.auth.signer import build_auth_headers
from fxpulse.clients.errors import ApiError, AuthenticationError, RateLimitError
from fxpulse.config import RevolutXCredentials

DEFAULT_BASE_URL = "https://revx.revolut.com"

RESOLUTION_MAP: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "1w": 10080,
}


def _build_query_string(params: dict[str, Any]) -> str:
    entries = sorted(
        (str(k), str(v)) for k, v in params.items() if v is not None
    )
    return "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in entries)


class RevolutXMarketDataClient:
    def __init__(
        self,
        credentials: RevolutXCredentials,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = credentials.api_key
        self._private_key = load_private_key(credentials.private_key_path)
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RevolutXMarketDataClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query_string = _build_query_string(params or {})
        full_path = f"/api/1.0{path}"
        url = f"{self._base_url}{full_path}"
        if query_string:
            url = f"{url}?{query_string}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **build_auth_headers(
                self._api_key,
                self._private_key,
                "GET",
                full_path,
                query_string,
                "",
            ),
        }

        response = self._client.get(url, headers=headers)
        self._raise_for_status(response)
        if not response.content:
            return {}
        return response.json()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        message = f"HTTP {response.status_code}"
        try:
            body = response.json()
            if isinstance(body, dict) and body.get("message"):
                message = body["message"]
        except ValueError:
            pass

        if response.status_code == 401:
            raise AuthenticationError(message, response.status_code)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(message, float(retry_after) if retry_after else None)
        raise ApiError(message, response.status_code)

    def get_tickers(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if symbols:
            params["symbols"] = ",".join(symbols)
        result = self._get("/tickers", params)
        return list(result.get("data", []))

    def get_candles(
        self,
        symbol: str,
        interval: str | int = "1h",
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict[str, Any]]:
        resolution = (
            RESOLUTION_MAP.get(str(interval), interval) if isinstance(interval, str) else interval
        )
        params: dict[str, Any] = {"interval": resolution}
        if since is not None:
            params["since"] = int(since.astimezone(UTC).timestamp() * 1000)
        if until is not None:
            params["until"] = int(until.astimezone(UTC).timestamp() * 1000)
        result = self._get(f"/candles/{symbol}", params)
        return list(result.get("data", []))
