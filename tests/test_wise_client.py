from __future__ import annotations

import json

import httpx
import respx

from fxpulse.clients.errors import AuthenticationError, RateLimitError
from fxpulse.clients.wise import WiseClient
from fxpulse.config import WiseCredentials


@respx.mock
def test_get_reference_rate_uses_bearer_auth_and_unwraps_list(wise_credentials: WiseCredentials) -> None:
    route = respx.get("https://api.wise-sandbox.com/v1/rates").mock(
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
def test_get_quote_looks_up_profile_id_then_posts_v3_quotes(wise_credentials: WiseCredentials) -> None:
    profiles_route = respx.get("https://api.wise-sandbox.com/v2/profiles").mock(
        return_value=httpx.Response(200, json=[{"id": 12345, "type": "PERSONAL"}])
    )
    quotes_route = respx.post("https://api.wise-sandbox.com/v3/quotes").mock(
        return_value=httpx.Response(
            200,
            json={
                "rate": 1.17,
                "paymentOptions": [
                    {
                        "sourceAmount": 1000.0,
                        "targetAmount": 1165.22,
                        "sourceCurrency": "GBP",
                        "targetCurrency": "EUR",
                        "fee": {"total": 3.88},
                    }
                ],
            },
        )
    )

    with WiseClient(wise_credentials) as client:
        quote = client.get_quote("GBP", "EUR", 1000.0)

    assert profiles_route.called
    request = quotes_route.calls.last.request
    body = json.loads(request.content)
    assert body == {
        "profileId": 12345,
        "sourceCurrency": "GBP",
        "targetCurrency": "EUR",
        "sourceAmount": 1000.0,
    }
    assert quote["paymentOptions"][0]["targetAmount"] == 1165.22


@respx.mock
def test_get_quote_caches_profile_id_across_calls(wise_credentials: WiseCredentials) -> None:
    profiles_route = respx.get("https://api.wise-sandbox.com/v2/profiles").mock(
        return_value=httpx.Response(200, json=[{"id": 12345, "type": "PERSONAL"}])
    )
    respx.post("https://api.wise-sandbox.com/v3/quotes").mock(
        return_value=httpx.Response(200, json={"rate": 1.17, "paymentOptions": []})
    )

    with WiseClient(wise_credentials) as client:
        client.get_quote("GBP", "EUR", 1000.0)
        client.get_quote("GBP", "USD", 500.0)

    assert profiles_route.call_count == 1


@respx.mock
def test_raises_rate_limit_error_on_429(wise_credentials: WiseCredentials) -> None:
    respx.get("https://api.wise-sandbox.com/v1/rates").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "30"}, json={"message": "slow down"})
    )

    with WiseClient(wise_credentials) as client:
        try:
            client.get_reference_rate("GBP", "EUR")
        except RateLimitError as exc:
            assert exc.retry_after == 30.0
        else:
            raise AssertionError("expected RateLimitError")


@respx.mock
def test_extracts_message_from_wise_errors_array_shape(wise_credentials: WiseCredentials) -> None:
    """Wise's real error responses are `{"errors":[{"code":...,"message":...}]}`,
    not the flat `{"message": ...}` shape assumed elsewhere — this is what
    /v1/quotes actually returned when hit without a profileId."""
    respx.get("https://api.wise-sandbox.com/v1/rates").mock(
        return_value=httpx.Response(
            401,
            json={"errors": [{"code": "error.quote.mustBeAuthenticated", "message": "Not authenticated."}]},
        )
    )

    with WiseClient(wise_credentials) as client:
        try:
            client.get_reference_rate("GBP", "EUR")
        except AuthenticationError as exc:
            assert "Not authenticated." in str(exc)
        else:
            raise AssertionError("expected AuthenticationError")
