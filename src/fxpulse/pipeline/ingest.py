"""Ingestion orchestration: fetch -> normalize -> load.

Every function here takes its clients/cursor as arguments rather than
constructing them internally, so the orchestration logic is testable
with fakes and doesn't need a live network or database connection.
"""

from __future__ import annotations

import logging
from typing import Any

from fxpulse.clients.revolut import RevolutXMarketDataClient
from fxpulse.clients.wise import WiseClient
from fxpulse.db.repository import insert_fx_quotes, insert_tickers, upsert_candles
from fxpulse.models import FxQuote
from fxpulse.pipeline.transform import candles_from_raw, fx_quote_from_raw, tickers_from_raw

logger = logging.getLogger("fxpulse.ingest")

DEFAULT_CRYPTO_SYMBOLS = ["BTC-USD", "ETH-USD"]
DEFAULT_FX_PAIRS: list[tuple[str, str, float]] = [
    ("GBP", "EUR", 1000.0),
    ("GBP", "USD", 1000.0),
    ("EUR", "USD", 1000.0),
]


def ingest_crypto_tickers(
    client: RevolutXMarketDataClient,
    cursor: Any,
    symbols: list[str] | None = None,
) -> int:
    raw = client.get_tickers(symbols or DEFAULT_CRYPTO_SYMBOLS)
    tickers = tickers_from_raw(raw)
    insert_tickers(cursor, tickers)
    logger.info("Ingested %d crypto tickers", len(tickers))
    return len(tickers)


def ingest_crypto_candles(
    client: RevolutXMarketDataClient,
    cursor: Any,
    symbol: str,
    interval: str = "1h",
    resolution_minutes: int = 60,
) -> int:
    raw = client.get_candles(symbol, interval=interval)
    candles = candles_from_raw(symbol, resolution_minutes, raw)
    upsert_candles(cursor, candles)
    logger.info("Ingested %d candles for %s", len(candles), symbol)
    return len(candles)


def ingest_fx_quotes(
    client: WiseClient,
    cursor: Any,
    pairs: list[tuple[str, str, float]] | None = None,
) -> int:
    quotes: list[FxQuote] = []
    for source, target, amount in pairs or DEFAULT_FX_PAIRS:
        rate_response = client.get_reference_rate(source, target)
        quote_response = client.get_quote(source, target, amount)
        quotes.append(fx_quote_from_raw(source, target, amount, rate_response, quote_response))

    insert_fx_quotes(cursor, quotes)
    logger.info("Ingested %d FX quotes", len(quotes))
    return len(quotes)


def run_full_ingestion(
    revolut_client: RevolutXMarketDataClient | None,
    wise_client: WiseClient | None,
    cursor: Any,
    crypto_symbols: list[str] | None = None,
    fx_pairs: list[tuple[str, str, float]] | None = None,
) -> dict[str, int]:
    """Ingest from whichever sources have a client. Either client may be
    `None` — e.g. to run only the Wise half when Revolut X credentials
    aren't set up yet — in which case that source's counts are 0."""
    ticker_count = 0
    candle_count = 0
    if revolut_client is not None:
        ticker_count = ingest_crypto_tickers(revolut_client, cursor, crypto_symbols)
        candle_count = sum(
            ingest_crypto_candles(revolut_client, cursor, symbol)
            for symbol in (crypto_symbols or DEFAULT_CRYPTO_SYMBOLS)
        )

    quote_count = 0
    if wise_client is not None:
        quote_count = ingest_fx_quotes(wise_client, cursor, fx_pairs)

    return {"tickers": ticker_count, "candles": candle_count, "fx_quotes": quote_count}
