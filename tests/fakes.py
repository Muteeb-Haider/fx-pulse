"""Fake clients/cursor for testing the pipeline orchestration layer
without any real network or database access."""

from __future__ import annotations

from typing import Any


class FakeCursor:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object]] = []
        self.executemany_calls: list[tuple[str, list[object]]] = []

    def execute(self, query: str, params: object = None) -> None:
        self.executed.append((query, params))

    def executemany(self, query: str, params_seq: object) -> None:
        self.executemany_calls.append((query, list(params_seq)))


class FakeRevolutClient:
    def get_tickers(self, symbols: list[str] | None = None) -> list[dict[str, Any]]:
        return [
            {
                "symbol": (symbols or ["BTC-USD"])[0],
                "bid": "1",
                "ask": "2",
                "mid": "1.5",
                "last_price": "1.5",
                "volume_24h": "10",
            }
        ]

    def get_candles(self, symbol: str, interval: str = "1h", **_: Any) -> list[dict[str, Any]]:
        return [{"start": 1_700_000_000_000, "open": "1", "high": "2", "low": "0.5", "close": "1.5", "volume": "10"}]


class FakeWiseClient:
    def __init__(self) -> None:
        self.rate_calls: list[tuple[str, str]] = []
        self.quote_calls: list[tuple[str, str, float]] = []

    def get_reference_rate(self, source: str, target: str) -> dict[str, Any]:
        self.rate_calls.append((source, target))
        return {"rate": 1.15, "source": source, "target": target}

    def get_quote(self, source: str, target: str, source_amount: float) -> dict[str, Any]:
        self.quote_calls.append((source, target, source_amount))
        return {
            "rate": 1.15,
            "paymentOptions": [
                {
                    "sourceAmount": source_amount,
                    "targetAmount": source_amount * 1.14,
                    "sourceCurrency": source,
                    "targetCurrency": target,
                    "fee": {"total": 5.0},
                }
            ],
        }
