from __future__ import annotations

import base64

import httpx
import respx

from fxpulse.clients.errors import AuthenticationError
from fxpulse.clients.revolut import RevolutXMarketDataClient, _build_query_string
from fxpulse.config import RevolutXCredentials


def test_build_query_string_sorts_keys_and_url_encodes() -> None:
    query = _build_query_string({"symbols": "BTC-USD,ETH-USD", "interval": 60, "since": None})
    assert query == "interval=60&symbols=BTC-USD%2CETH-USD"


@respx.mock
def test_get_tickers_signs_request_and_parses_response(revolutx_credentials: RevolutXCredentials) -> None:
    route = respx.get("https://revx.revolut.com/api/1.0/tickers").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"symbol": "BTC-USD", "bid": "1", "ask": "2", "mid": "1.5", "last_price": "1.5", "volume_24h": "10"}]},
        )
    )

    with RevolutXMarketDataClient(revolutx_credentials) as client:
        tickers = client.get_tickers(["BTC-USD"])

    assert route.called
    request = route.calls.last.request
    assert request.url.params["symbols"] == "BTC-USD"
    assert request.headers["X-Revx-API-Key"] == "test-api-key"
    assert request.headers["X-Revx-Timestamp"].isdigit()
    assert len(base64.b64decode(request.headers["X-Revx-Signature"])) == 64
    assert tickers[0]["symbol"] == "BTC-USD"


@respx.mock
def test_get_candles_maps_named_interval_to_minutes(revolutx_credentials: RevolutXCredentials) -> None:
    route = respx.get("https://revx.revolut.com/api/1.0/candles/BTC-USD").mock(
        return_value=httpx.Response(200, json={"data": []})
    )

    with RevolutXMarketDataClient(revolutx_credentials) as client:
        client.get_candles("BTC-USD", interval="1h")

    request = route.calls.last.request
    assert request.url.params["interval"] == "60"


@respx.mock
def test_raises_authentication_error_on_401(revolutx_credentials: RevolutXCredentials) -> None:
    respx.get("https://revx.revolut.com/api/1.0/tickers").mock(
        return_value=httpx.Response(401, json={"message": "invalid signature"})
    )

    with RevolutXMarketDataClient(revolutx_credentials) as client:
        try:
            client.get_tickers()
        except AuthenticationError as exc:
            assert "invalid signature" in str(exc)
        else:
            raise AssertionError("expected AuthenticationError")
