"""Pure functions turning raw API payloads into normalized domain models.

Kept separate from the clients and the DB layer so this logic can be
unit tested without any network or database access.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fxpulse.models import CryptoCandle, CryptoTicker, FxQuote


def tickers_from_raw(raw_tickers: list[dict[str, Any]]) -> list[CryptoTicker]:
    return [CryptoTicker.from_api(t) for t in raw_tickers]


def candles_from_raw(
    symbol: str, resolution_minutes: int, raw_candles: list[dict[str, Any]]
) -> list[CryptoCandle]:
    return [CryptoCandle.from_api(symbol, resolution_minutes, c) for c in raw_candles]


def fx_quote_from_raw(
    source_currency: str,
    target_currency: str,
    source_amount: float,
    rate_response: dict[str, Any],
    quote_response: dict[str, Any],
) -> FxQuote:
    mid_market_rate = rate_response["rate"]

    quoted_rate = quote_response.get("rate")
    fee = quote_response.get("fee")
    target_amount = quote_response.get("targetAmount")

    if quoted_rate is None or fee is None or target_amount is None:
        payment_options = quote_response.get("paymentOptions") or []
        if not payment_options:
            raise ValueError(f"Quote response missing rate/fee/targetAmount: {quote_response!r}")
        option = payment_options[0]
        if quoted_rate is None:
            quoted_rate = option.get("rate", mid_market_rate)
        if fee is None:
            fee = option.get("fee", {}).get("total", 0)
        if target_amount is None:
            target_amount = option.get("targetAmount")

    return FxQuote(
        source_currency=source_currency,
        target_currency=target_currency,
        source_amount=Decimal(str(source_amount)),
        mid_market_rate=Decimal(str(mid_market_rate)),
        quoted_rate=Decimal(str(quoted_rate)),
        fee_amount=Decimal(str(fee)),
        fee_currency=quote_response.get("feeCurrency", source_currency),
        target_amount=Decimal(str(target_amount)),
    )
