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


def test_fx_quote_from_raw_derives_effective_rate_from_first_payment_option() -> None:
    """Mirrors a real Wise Sandbox V2 /v3/quotes response: the top-level `rate`
    is just the mid-market rate again, and the customer's actual effective
    rate has to be derived from a payment option's targetAmount/sourceAmount."""
    rate_response = {"rate": 1.16975, "source": "GBP", "target": "EUR", "time": "2026-01-01T00:00:00Z"}
    quote_response = {
        "rate": 1.16976,  # also mid-market, NOT the customer's rate
        "paymentOptions": [
            {
                "sourceAmount": 1000.0,
                "targetAmount": 1165.22,
                "sourceCurrency": "GBP",
                "targetCurrency": "EUR",
                "fee": {"total": 3.88},
            },
            {
                "sourceAmount": 1000.0,
                "targetAmount": 1161.51,
                "sourceCurrency": "GBP",
                "targetCurrency": "EUR",
                "fee": {"total": 7.05},
            },
        ],
    }

    quote = fx_quote_from_raw("GBP", "EUR", 1000.0, rate_response, quote_response)

    assert quote.source_currency == "GBP"
    assert quote.target_currency == "EUR"
    assert quote.mid_market_rate == Decimal("1.16975")
    assert quote.target_amount == Decimal("1165.22")
    assert quote.fee_amount == Decimal("3.88")
    assert quote.fee_currency == "GBP"
    # first payment option only, not the second
    assert quote.quoted_rate == Decimal("1165.22") / Decimal("1000.0")
    assert quote.markup_bps > 0  # quoted rate is worse than mid-market -> positive markup


def test_fx_quote_from_raw_raises_when_no_payment_options() -> None:
    with pytest.raises(ValueError, match="no payment options"):
        fx_quote_from_raw("GBP", "EUR", 1000.0, {"rate": 1.15}, {"paymentOptions": []})
