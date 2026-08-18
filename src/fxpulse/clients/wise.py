"""Wise Platform API client (rates + temporary quotes).

Uses two read-only, no-profile-required endpoints from Wise's public
API (see https://github.com/transferwise/api-docs):

- `GET /v1/rates` returns Wise's reference (mid-market) exchange rate
  for a currency pair — this is the benchmark.
- `GET /v1/quotes` ("temporary quote", no `profile` needed) returns
  what a customer would actually pay to convert/send that amount,
  including the fee breakdown — this is the real cost.

The gap between the two is the transfer's effective markup, which is
what fxpulse's analytics layer reports on.

NOTE: verify exact response field names against your own Wise sandbox
account (register at https://sandbox.transferwise.tech/) — Wise's
interactive docs are JS-rendered and couldn't be scraped directly
while building this, so these shapes are taken from Wise's public
api-docs repo and may drift slightly from the live sandbox response.
"""

from __future__ import annotations

from typing import Any, cast

import httpx

from fxpulse.clients.errors import ApiError, AuthenticationError, RateLimitError
from fxpulse.config import WiseCredentials


class WiseClient:
    def __init__(self, credentials: WiseCredentials, timeout: float = 30.0) -> None:
        self._base_url = credentials.base_url
        self._client = httpx.Client(
            timeout=timeout,
            headers={"Authorization": f"Bearer {credentials.api_token}"},
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> WiseClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        response = self._client.get(f"{self._base_url}{path}", params=params)
        self._raise_for_status(response)
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

    def get_reference_rate(self, source: str, target: str) -> dict[str, Any]:
        """Wise's mid-market reference rate for a currency pair."""
        result = self._get("/v1/rates", {"source": source, "target": target})
        if isinstance(result, list):
            if not result:
                raise ApiError(f"No rate returned for {source}->{target}")
            return cast(dict[str, Any], result[0])
        return cast(dict[str, Any], result)

    def get_temporary_quote(
        self,
        source: str,
        target: str,
        source_amount: float,
    ) -> dict[str, Any]:
        """What a customer actually pays: quoted rate + fee breakdown."""
        return cast(
            dict[str, Any],
            self._get(
                "/v1/quotes",
                {
                    "source": source,
                    "target": target,
                    "sourceAmount": source_amount,
                    "rateType": "FIXED",
                },
            ),
        )
