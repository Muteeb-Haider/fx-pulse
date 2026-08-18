"""Normalized domain models shared between the clients, transforms, and DB layer."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class CryptoTicker(BaseModel):
    symbol: str
    bid: Decimal
    ask: Decimal
    mid: Decimal
    last_price: Decimal
    volume_24h: Decimal
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> CryptoTicker:
        return cls(
            symbol=raw["symbol"],
            bid=raw["bid"],
            ask=raw["ask"],
            mid=raw["mid"],
            last_price=raw["last_price"],
            volume_24h=raw["volume_24h"],
        )


class CryptoCandle(BaseModel):
    symbol: str
    resolution_minutes: int
    start: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    @classmethod
    def from_api(cls, symbol: str, resolution_minutes: int, raw: dict[str, Any]) -> CryptoCandle:
        return cls(
            symbol=symbol,
            resolution_minutes=resolution_minutes,
            start=datetime.fromtimestamp(raw["start"] / 1000, tz=UTC),
            open=raw["open"],
            high=raw["high"],
            low=raw["low"],
            close=raw["close"],
            volume=raw["volume"],
        )


class FxQuote(BaseModel):
    """A Wise transfer quote paired with the mid-market reference rate."""

    source_currency: str
    target_currency: str
    source_amount: Decimal
    mid_market_rate: Decimal
    quoted_rate: Decimal
    fee_amount: Decimal
    fee_currency: str
    target_amount: Decimal
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def markup_bps(self) -> Decimal:
        """Effective markup of the quoted rate vs. the mid-market rate, in basis points."""
        if self.mid_market_rate == 0:
            return Decimal(0)
        diff = (self.mid_market_rate - self.quoted_rate) / self.mid_market_rate
        return (diff * Decimal(10_000)).quantize(Decimal("0.01"))

    @property
    def implied_fee_pct(self) -> Decimal:
        """Total cost (rate markup + explicit fee) as a percentage of the send amount."""
        if self.source_amount == 0:
            return Decimal(0)
        equivalent_at_mid_market = self.source_amount * self.mid_market_rate
        shortfall = equivalent_at_mid_market - self.target_amount
        cost_in_source_ccy = (
            shortfall / self.mid_market_rate if self.mid_market_rate else Decimal(0)
        )
        pct = (cost_in_source_ccy / self.source_amount) * Decimal(100)
        return pct.quantize(Decimal("0.0001"))
