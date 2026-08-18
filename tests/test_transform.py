from __future__ import annotations

from decimal import Decimal

import pytest

from fxpulse.pipeline.transform import candles_from_raw, fx_quote_from_raw, tickers_from_raw


def test_tickers_from_raw() -> None:
    raw = [
        {
            "symbol": "BTC-USD",
            "bid": "94999.5",
            "ask": "95000.5",
            "mid": "95000.0",
            "last_price": "95000.0",
            "low_24h": "94000",
            "high_24h": "96000",
            "price_change_24h": "1.5",
            "volume_24h": "1234.5",
        }
    ]

    tickers = tickers_from_raw(raw)

    assert len(tickers) == 1
    assert tickers[0].symbol == "BTC-USD"
    assert tickers[0].mid == Decimal("95000.0")


def test_candles_from_raw_converts_ms_epoch_to_datetime() -> None:
    raw = [{"start": 1_700_000_000_000, "open": "1", "high": "2", "low": "0.5", "close": "1.5", "volume": "10"}]

    candles = candles_from_raw("BTC-USD", 60, raw)

    assert len(candles) == 1
    assert candles[0].symbol == "BTC-USD"
    assert candles[0].resolution_minutes == 60
    assert candles[0].start.timestamp() == 1_700_000_000


def test_fx_quote_from_raw_direct_fields() -> None:
    rate_response = {"rate": 1.15, "source": "GBP", "target": "EUR", "time": "2026-01-01T00:00:00Z"}
    quote_response = {"rate": 1.145, "fee": 5.0, "targetAmount": 1140.0, "feeCurrency": "GBP"}

    quote = fx_quote_from_raw("GBP", "EUR", 1000.0, rate_response, quote_response)

    assert quote.source_currency == "GBP"
    assert quote.target_currency == "EUR"
    assert quote.mid_market_rate == Decimal("1.15")
    assert quote.quoted_rate == Decimal("1.145")
    assert quote.fee_amount == Decimal("5.0")
    assert quote.markup_bps > 0  # quoted rate is worse than mid-market -> positive markup


def test_fx_quote_from_raw_falls_back_to_payment_options() -> None:
    rate_response = {"rate": 1.15}
    quote_response = {
        "paymentOptions": [
            {"rate": 1.14, "fee": {"total": 6.5}, "targetAmount": 1130.0},
        ]
    }

    quote = fx_quote_from_raw("GBP", "EUR", 1000.0, rate_response, quote_response)

    assert quote.quoted_rate == Decimal("1.14")
    assert quote.fee_amount == Decimal("6.5")
    assert quote.target_amount == Decimal("1130.0")


def test_fx_quote_from_raw_raises_when_no_usable_fields() -> None:
    with pytest.raises(ValueError, match="missing rate/fee/targetAmount"):
        fx_quote_from_raw("GBP", "EUR", 1000.0, {"rate": 1.15}, {})
