"""Wise Platform API client (rates + quotes).

Two calls, both verified live against a real Wise Sandbox V2 account
while building this (see notes below — the public docs describe an
older, no-longer-working flow):

- `GET /v1/rates` returns Wise's reference (mid-market) exchange rate
  for a currency pair — this is the benchmark. Confirmed working with
  just a Bearer Personal Token, response shape
  `{"rate": ..., "source": ..., "target": ..., "time": ...}`.
- `POST /v3/quotes` (with a `profileId`) returns what a customer would
  actually pay to convert/send that amount, across several payment
  options (bank transfer, card, etc.) each with their own fee
  breakdown — this is the real cost. The top-level `rate` field on
  this response is *also* just the mid-market rate, not the customer's
  effective rate — that has to be derived per payment option as
  `targetAmount / sourceAmount`.

The gap between the mid-market rate and a payment option's effective
rate (plus its explicit fee) is the transfer's real cost, which is
what fxpulse's analytics layer reports on.

Points at Wise's Sandbox V2 (`api.wise-sandbox.com`) — V1
(`api.sandbox.transferwise.tech`) was retired. Register a V2 test
account at https://wise-sandbox.com/register and create a Personal
Token from your account's "Connect and manage apps" -> API tokens
(needs 2-step verification enabled first; sandbox 2FA code is always
`111111`).

NOTE ON THE DOCS: Wise's public api-docs repo (and their JS-rendered
interactive docs, which couldn't be scraped directly while building
this) describe a `GET /v1/quotes` "temporary quote" endpoint that
needs no profile. Against a real Sandbox V2 account that endpoint
returned `401 {"errors":[{"code":"error.quote.mustBeAuthenticated",...}]}`
even with a valid Bearer token — empirically, quotes now require an
authenticated `POST /v3/quotes` with a real `profileId`. This client
reflects what was actually observed working, not what the docs say.
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
        self._profile_id: int | None = None

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

    def _post(self, path: str, json_body: dict[str, Any]) -> Any:
        response = self._client.post(f"{self._base_url}{path}", json=json_body)
        self._raise_for_status(response)
        return response.json()

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        message = f"HTTP {response.status_code}"
        try:
            body = response.json()
            if isinstance(body, dict):
                errors = body.get("errors")
                if isinstance(errors, list) and errors and errors[0].get("message"):
                    message = errors[0]["message"]
                elif body.get("message"):
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

    def _get_profile_id(self) -> int:
        if self._profile_id is None:
            profiles = self._get("/v2/profiles", {})
            if not profiles:
                raise ApiError("Wise account has no profiles to quote against")
            self._profile_id = cast(int, profiles[0]["id"])
        return self._profile_id

    def get_quote(self, source: str, target: str, source_amount: float) -> dict[str, Any]:
        """A real, profile-scoped quote: several payment options, each with its
        own effective rate and fee breakdown (see module docstring)."""
        profile_id = self._get_profile_id()
        return cast(
            dict[str, Any],
            self._post(
                "/v3/quotes",
                {
                    "profileId": profile_id,
                    "sourceCurrency": source,
                    "targetCurrency": target,
                    "sourceAmount": source_amount,
                },
            ),
        )
