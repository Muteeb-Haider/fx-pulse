from __future__ import annotations

import logging
import sys

import click

from fxpulse.clients.revolut import RevolutXMarketDataClient
from fxpulse.clients.wise import WiseClient
from fxpulse.config import load_database_config, load_revolutx_credentials, load_wise_credentials
from fxpulse.db.repository import apply_schema, connect
from fxpulse.pipeline.ingest import run_full_ingestion

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@click.group()
def main() -> None:
    """fx-pulse: FX transparency pipeline (Revolut X market data + Wise transfer quotes)."""


@main.command()
def init_db() -> None:
    """Create/update the database schema."""
    db_config = load_database_config()
    with connect(db_config) as conn, conn.cursor() as cursor:
        apply_schema(cursor)
    click.echo("Schema applied.")


@main.command()
@click.option("--symbol", "symbols", multiple=True, help="Crypto pair, e.g. BTC-USD (repeatable).")
@click.option(
    "--fx-pair",
    "fx_pairs",
    multiple=True,
    help="SOURCE:TARGET:AMOUNT, e.g. GBP:EUR:1000 (repeatable).",
)
def run(symbols: tuple[str, ...], fx_pairs: tuple[str, ...]) -> None:
    """Run one ingestion pass: fetch market data + FX quotes, write to Postgres."""
    revolutx_creds = load_revolutx_credentials()
    wise_creds = load_wise_credentials()

    if revolutx_creds is None:
        click.echo(
            "No Revolut X credentials found. Run `revx auth setup` (revolut-x-api CLI) first.",
            err=True,
        )
        sys.exit(1)
    if wise_creds is None:
        click.echo(
            "No Wise credentials found. Set WISE_API_TOKEN in your environment or .env file.",
            err=True,
        )
        sys.exit(1)

    parsed_pairs = None
    if fx_pairs:
        parsed_pairs = []
        for pair in fx_pairs:
            source, target, amount = pair.split(":")
            parsed_pairs.append((source, target, float(amount)))

    db_config = load_database_config()
    with (
        RevolutXMarketDataClient(revolutx_creds) as revolut_client,
        WiseClient(wise_creds) as wise_client,
        connect(db_config) as conn,
        conn.cursor() as cursor,
    ):
        counts = run_full_ingestion(
            revolut_client,
            wise_client,
            cursor,
            crypto_symbols=list(symbols) or None,
            fx_pairs=parsed_pairs,
        )
    click.echo(f"Ingestion complete: {counts}")


if __name__ == "__main__":
    main()
