from __future__ import annotations

from fxpulse.pipeline.ingest import (
    ingest_crypto_candles,
    ingest_crypto_tickers,
    ingest_fx_quotes,
    run_full_ingestion,
)
from tests.fakes import FakeCursor, FakeRevolutClient, FakeWiseClient


def test_ingest_crypto_tickers_writes_normalized_rows() -> None:
    client = FakeRevolutClient()
    cursor = FakeCursor()

    count = ingest_crypto_tickers(client, cursor, symbols=["BTC-USD"])

    assert count == 1
    query, rows = cursor.executemany_calls[0]
    assert "crypto_tickers" in query
    assert rows[0]["symbol"] == "BTC-USD"


def test_ingest_crypto_candles_writes_normalized_rows() -> None:
    client = FakeRevolutClient()
    cursor = FakeCursor()

    count = ingest_crypto_candles(client, cursor, "BTC-USD")

    assert count == 1
    query, rows = cursor.executemany_calls[0]
    assert "crypto_candles" in query
    assert rows[0]["symbol"] == "BTC-USD"


def test_ingest_fx_quotes_pairs_rate_and_quote_calls() -> None:
    client = FakeWiseClient()
    cursor = FakeCursor()

    count = ingest_fx_quotes(client, cursor, pairs=[("GBP", "EUR", 1000.0)])

    assert count == 1
    assert client.rate_calls == [("GBP", "EUR")]
    assert client.quote_calls == [("GBP", "EUR", 1000.0)]


def test_run_full_ingestion_reports_counts_per_source() -> None:
    revolut_client = FakeRevolutClient()
    wise_client = FakeWiseClient()
    cursor = FakeCursor()

    counts = run_full_ingestion(
        revolut_client,
        wise_client,
        cursor,
        crypto_symbols=["BTC-USD"],
        fx_pairs=[("GBP", "EUR", 1000.0)],
    )

    assert counts == {"tickers": 1, "candles": 1, "fx_quotes": 1}
