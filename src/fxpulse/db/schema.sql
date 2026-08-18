-- fx-pulse schema.
--
-- Two ingestion-facing fact tables (crypto_tickers, crypto_candles from
-- Revolut X; fx_quotes from Wise), plus a couple of analytics views on
-- top for the "what does this actually cost" reporting layer.

CREATE TABLE IF NOT EXISTS crypto_tickers (
    id           BIGSERIAL PRIMARY KEY,
    symbol       TEXT NOT NULL,
    bid          NUMERIC(24, 8) NOT NULL,
    ask          NUMERIC(24, 8) NOT NULL,
    mid          NUMERIC(24, 8) NOT NULL,
    last_price   NUMERIC(24, 8) NOT NULL,
    volume_24h   NUMERIC(24, 8) NOT NULL,
    fetched_at   TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_crypto_tickers_symbol_time
    ON crypto_tickers (symbol, fetched_at DESC);

CREATE TABLE IF NOT EXISTS crypto_candles (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              TEXT NOT NULL,
    resolution_minutes  INTEGER NOT NULL,
    start_time          TIMESTAMPTZ NOT NULL,
    open                NUMERIC(24, 8) NOT NULL,
    high                NUMERIC(24, 8) NOT NULL,
    low                 NUMERIC(24, 8) NOT NULL,
    close               NUMERIC(24, 8) NOT NULL,
    volume              NUMERIC(24, 8) NOT NULL,
    UNIQUE (symbol, resolution_minutes, start_time)
);

CREATE TABLE IF NOT EXISTS fx_quotes (
    id                  BIGSERIAL PRIMARY KEY,
    source_currency     TEXT NOT NULL,
    target_currency     TEXT NOT NULL,
    source_amount       NUMERIC(18, 4) NOT NULL,
    mid_market_rate     NUMERIC(18, 8) NOT NULL,
    quoted_rate         NUMERIC(18, 8) NOT NULL,
    fee_amount          NUMERIC(18, 4) NOT NULL,
    fee_currency        TEXT NOT NULL,
    target_amount       NUMERIC(18, 4) NOT NULL,
    markup_bps          NUMERIC(10, 2) NOT NULL,
    implied_fee_pct     NUMERIC(10, 4) NOT NULL,
    fetched_at          TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fx_quotes_pair_time
    ON fx_quotes (source_currency, target_currency, fetched_at DESC);

-- Daily rollup of transfer cost per currency pair, for a "how expensive
-- is sending X->Y trending" report.
CREATE OR REPLACE VIEW fx_spread_daily AS
SELECT
    source_currency,
    target_currency,
    date_trunc('day', fetched_at) AS day,
    COUNT(*)                       AS sample_count,
    AVG(markup_bps)                AS avg_markup_bps,
    MIN(markup_bps)                AS min_markup_bps,
    MAX(markup_bps)                AS max_markup_bps,
    AVG(implied_fee_pct)           AS avg_implied_fee_pct
FROM fx_quotes
GROUP BY source_currency, target_currency, date_trunc('day', fetched_at);

-- Daily crypto volatility rollup from candle data, for a lightweight
-- "how much did this pair move today" companion report.
CREATE OR REPLACE VIEW crypto_volatility_daily AS
SELECT
    symbol,
    date_trunc('day', start_time)                          AS day,
    MIN(low)                                                AS day_low,
    MAX(high)                                               AS day_high,
    (MAX(high) - MIN(low)) / NULLIF(MIN(low), 0) * 100      AS range_pct,
    SUM(volume)                                             AS volume
FROM crypto_candles
GROUP BY symbol, date_trunc('day', start_time);
