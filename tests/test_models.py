from __future__ import annotations

from decimal import Decimal

from fxpulse.models import FxQuote


def test_markup_bps_when_quoted_rate_is_worse_than_mid_market() -> None:
    quote = FxQuote(
        source_currency="GBP",
        target_currency="EUR",
        source_amount=Decimal("1000"),
        mid_market_rate=Decimal("1.20"),
        quoted_rate=Decimal("1.176"),
        fee_amount=Decimal("5"),
        fee_currency="GBP",
        target_amount=Decimal("1170"),
    )

    assert quote.markup_bps == Decimal("200.00")


def test_markup_bps_is_zero_when_quoted_matches_mid_market() -> None:
    quote = FxQuote(
        source_currency="GBP",
        target_currency="EUR",
        source_amount=Decimal("1000"),
        mid_market_rate=Decimal("1.20"),
        quoted_rate=Decimal("1.20"),
        fee_amount=Decimal("0"),
        fee_currency="GBP",
        target_amount=Decimal("1200"),
    )

    assert quote.markup_bps == Decimal("0.00")


def test_implied_fee_pct_reflects_total_cost() -> None:
    quote = FxQuote(
        source_currency="GBP",
        target_currency="EUR",
        source_amount=Decimal("1000"),
        mid_market_rate=Decimal("1.20"),
        quoted_rate=Decimal("1.176"),
        fee_amount=Decimal("5"),
        fee_currency="GBP",
        target_amount=Decimal("1170"),
    )

    assert quote.implied_fee_pct == Decimal("2.5000")
