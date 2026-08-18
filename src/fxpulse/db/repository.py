"""Postgres persistence for normalized market data and FX quotes.

Kept as a thin wrapper around plain SQL (no ORM). Every function takes
a cursor-like object as its first argument rather than opening its own
connection, so the pipeline logic stays testable with a fake cursor
(see tests/fakes.py) instead of a live database. The cursor is typed
as `Any` here rather than a structural Protocol: psycopg's real
`Cursor.execute`/`executemany` overloads (prepare/binary/returning
kwargs) don't reduce cleanly to a simple Protocol, and the boundary
with an external DB driver is exactly the kind of place where fighting
mypy for its own sake isn't worth it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg

from fxpulse.config import DatabaseConfig
from fxpulse.models import CryptoCandle, CryptoTicker, FxQuote

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_INSERT_TICKERS_SQL = """
    INSERT INTO crypto_tickers (symbol, bid, ask, mid, last_price, volume_24h, fetched_at)
    VALUES (%(symbol)s, %(bid)s, %(ask)s, %(mid)s, %(last_price)s, %(volume_24h)s, %(fetched_at)s)
"""

_UPSERT_CANDLES_SQL = """
    INSERT INTO crypto_candles
        (symbol, resolution_minutes, start_time, open, high, low, close, volume)
    VALUES
        (%(symbol)s, %(resolution_minutes)s, %(start_time)s, %(open)s,
         %(high)s, %(low)s, %(close)s, %(volume)s)
    ON CONFLICT (symbol, resolution_minutes, start_time)
    DO UPDATE SET open = EXCLUDED.open, high = EXCLUDED.high,
                  low = EXCLUDED.low, close = EXCLUDED.close, volume = EXCLUDED.volume
"""

_INSERT_FX_QUOTES_SQL = """
    INSERT INTO fx_quotes (
        source_currency, target_currency, source_amount, mid_market_rate,
        quoted_rate, fee_amount, fee_currency, target_amount,
        markup_bps, implied_fee_pct, fetched_at
    ) VALUES (
        %(source_currency)s, %(target_currency)s, %(source_amount)s, %(mid_market_rate)s,
        %(quoted_rate)s, %(fee_amount)s, %(fee_currency)s, %(target_amount)s,
        %(markup_bps)s, %(implied_fee_pct)s, %(fetched_at)s
    )
"""


def connect(config: DatabaseConfig) -> psycopg.Connection:
    return psycopg.connect(config.dsn, autocommit=True)


def apply_schema(cursor: Any) -> None:
    cursor.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def insert_tickers(cursor: Any, tickers: list[CryptoTicker]) -> None:
    if not tickers:
        return
    cursor.executemany(_INSERT_TICKERS_SQL, [t.model_dump() for t in tickers])


def upsert_candles(cursor: Any, candles: list[CryptoCandle]) -> None:
    if not candles:
        return
    rows = [
        {
            "symbol": c.symbol,
            "resolution_minutes": c.resolution_minutes,
            "start_time": c.start,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        }
        for c in candles
    ]
    cursor.executemany(_UPSERT_CANDLES_SQL, rows)


def insert_fx_quotes(cursor: Any, quotes: list[FxQuote]) -> None:
    if not quotes:
        return
    rows = [
        {
            "source_currency": q.source_currency,
            "target_currency": q.target_currency,
            "source_amount": q.source_amount,
            "mid_market_rate": q.mid_market_rate,
            "quoted_rate": q.quoted_rate,
            "fee_amount": q.fee_amount,
            "fee_currency": q.fee_currency,
            "target_amount": q.target_amount,
            "markup_bps": q.markup_bps,
            "implied_fee_pct": q.implied_fee_pct,
            "fetched_at": q.fetched_at,
        }
        for q in quotes
    ]
    cursor.executemany(_INSERT_FX_QUOTES_SQL, rows)
