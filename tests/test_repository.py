from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fxpulse.db.repository import insert_fx_quotes, insert_tickers, upsert_candles
from fxpulse.models import CryptoCandle, CryptoTicker, FxQuote


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object]] = []
        self.executemany_calls: list[tuple[str, list[object]]] = []

    def execute(self, query: str, params: object = None) -> None:
        self.executed.append((query, params))

    def executemany(self, query: str, params_seq: object) -> None:
        self.executemany_calls.append((query, list(params_seq)))


def test_insert_tickers_batches_all_rows_in_one_call() -> None:
    cursor = FakeCursor()
    tickers = [
        CryptoTicker(
            symbol="BTC-USD",
            bid=Decimal("1"),
            ask=Decimal("2"),
            mid=Decimal("1.5"),
            last_price=Decimal("1.5"),
            volume_24h=Decimal("10"),
            fetched_at=datetime.now(UTC),
        )
    ]

    insert_tickers(cursor, tickers)

    assert len(cursor.executemany_calls) == 1
    query, rows = cursor.executemany_calls[0]
    assert "INSERT INTO crypto_tickers" in query
    assert len(rows) == 1
    assert rows[0]["symbol"] == "BTC-USD"


def test_insert_tickers_no_op_on_empty_list() -> None:
    cursor = FakeCursor()
    insert_tickers(cursor, [])
    assert cursor.executemany_calls == []


def test_upsert_candles_includes_on_conflict_clause() -> None:
    cursor = FakeCursor()
    candle = CryptoCandle(
        symbol="BTC-USD",
        resolution_minutes=60,
        start=datetime.now(UTC),
        open=Decimal("1"),
        high=Decimal("2"),
        low=Decimal("0.5"),
        close=Decimal("1.5"),
        volume=Decimal("10"),
    )

    upsert_candles(cursor, [candle])

    query, rows = cursor.executemany_calls[0]
    assert "ON CONFLICT" in query
    assert rows[0]["resolution_minutes"] == 60


def test_insert_fx_quotes_includes_derived_fields() -> None:
    cursor = FakeCursor()
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

    insert_fx_quotes(cursor, [quote])

    query, rows = cursor.executemany_calls[0]
    assert "INSERT INTO fx_quotes" in query
    assert rows[0]["markup_bps"] == Decimal("200.00")
