from __future__ import annotations

import httpx
import respx

from fxpulse.clients.errors import RateLimitError
from fxpulse.clients.wise import WiseClient
from fxpulse.config import WiseCredentials


@respx.mock
def test_get_reference_rate_uses_bearer_auth_and_unwraps_list(wise_credentials: WiseCredentials) -> None:
    route = respx.get("https://api.sandbox.transferwise.tech/v1/rates").mock(
        return_value=httpx.Response(200, json=[{"rate": 1.15, "source": "GBP", "target": "EUR", "time": "x"}])
    )

    with WiseClient(wise_credentials) as client:
        rate = client.get_reference_rate("GBP", "EUR")

    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer test-wise-token"
    assert request.url.params["source"] == "GBP"
    assert request.url.params["target"] == "EUR"
    assert rate["rate"] == 1.15


@respx.mock
def test_get_temporary_quote_sends_fixed_rate_type(wise_credentials: WiseCredentials) -> None:
    route = respx.get("https://api.sandbox.transferwise.tech/v1/quotes").mock(
        return_value=httpx.Response(200, json={"rate": 1.14, "fee": 5.0, "targetAmount": 1135.0})
    )

    with WiseClient(wise_credentials) as client:
        quote = client.get_temporary_quote("GBP", "EUR", 1000.0)

    request = route.calls.last.request
    assert request.url.params["rateType"] == "FIXED"
    assert request.url.params["sourceAmount"] == "1000.0"
    assert quote["targetAmount"] == 1135.0


@respx.mock
def test_raises_rate_limit_error_on_429(wise_credentials: WiseCredentials) -> None:
    respx.get("https://api.sandbox.transferwise.tech/v1/rates").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "30"}, json={"message": "slow down"})
    )

    with WiseClient(wise_credentials) as client:
        try:
            client.get_reference_rate("GBP", "EUR")
        except RateLimitError as exc:
            assert exc.retry_after == 30.0
        else:
            raise AssertionError("expected RateLimitError")
