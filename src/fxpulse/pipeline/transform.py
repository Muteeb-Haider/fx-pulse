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
    """Build an FxQuote from a Wise `/v1/rates` response (the mid-market
    benchmark) and a `/v3/quotes` response (the real, profile-scoped quote).

    The quote response's own top-level `rate` field is *also* just the
    mid-market rate, not what the customer actually gets — that only
    shows up per payment option, as `targetAmount / sourceAmount`. This
    picks the first payment option (Wise's own default/cheapest pick,
    typically a bank-transfer payout) as "the" quote.
    """
    mid_market_rate = rate_response["rate"]

    payment_options = quote_response.get("paymentOptions") or []
    if not payment_options:
        raise ValueError(f"Quote response has no payment options: {quote_response!r}")
    option = payment_options[0]

    option_source_amount = Decimal(str(option["sourceAmount"]))
    target_amount = Decimal(str(option["targetAmount"]))
    quoted_rate = target_amount / option_source_amount
    fee = option["fee"]["total"]
    fee_currency = option.get("sourceCurrency", source_currency)

    return FxQuote(
        source_currency=source_currency,
        target_currency=target_currency,
        source_amount=Decimal(str(source_amount)),
        mid_market_rate=Decimal(str(mid_market_rate)),
        quoted_rate=quoted_rate,
        fee_amount=Decimal(str(fee)),
        fee_currency=fee_currency,
        target_amount=target_amount,
    )
