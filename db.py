"""
Postgres connection and schema module, shared by every download and
analysis script in the project.
"""

import os

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


# Every table has a UNIQUE(symbol, time) constraint, enforced together with
# ON CONFLICT DO NOTHING in upsert_rows() below - the de-duplication guard
# for incremental, idempotent re-runs.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    open_time TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    trades BIGINT NOT NULL,
    UNIQUE (symbol, open_time)
);

CREATE TABLE IF NOT EXISTS funding_rate (
    symbol TEXT NOT NULL,
    funding_time TIMESTAMPTZ NOT NULL,
    funding_rate DOUBLE PRECISION NOT NULL,
    UNIQUE (symbol, funding_time)
);

CREATE TABLE IF NOT EXISTS open_interest (
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    sum_open_interest DOUBLE PRECISION NOT NULL,
    sum_open_interest_value DOUBLE PRECISION NOT NULL,
    UNIQUE (symbol, ts)
);

CREATE TABLE IF NOT EXISTS top_trader_ratio (
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    long_account_ratio DOUBLE PRECISION NOT NULL,
    short_account_ratio DOUBLE PRECISION NOT NULL,
    long_short_ratio DOUBLE PRECISION NOT NULL,
    UNIQUE (symbol, ts)
);

CREATE TABLE IF NOT EXISTS taker_volume (
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    buy_sell_ratio DOUBLE PRECISION NOT NULL,
    buy_vol DOUBLE PRECISION NOT NULL,
    sell_vol DOUBLE PRECISION NOT NULL,
    UNIQUE (symbol, ts)
);

CREATE TABLE IF NOT EXISTS dvol (
    currency TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    UNIQUE (currency, ts)
);

CREATE TABLE IF NOT EXISTS spot_candles (
    symbol TEXT NOT NULL,
    open_time TIMESTAMPTZ NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    UNIQUE (symbol, open_time)
);

-- Derived indicators, kept separate from the raw candles table so they can
-- be recomputed/dropped without touching raw exchange data.
CREATE TABLE IF NOT EXISTS indicators (
    symbol TEXT NOT NULL,
    date TIMESTAMPTZ NOT NULL,
    rsi_14 DOUBLE PRECISION,
    bb_upper DOUBLE PRECISION,
    bb_mid DOUBLE PRECISION,
    bb_lower DOUBLE PRECISION,
    vwap_20 DOUBLE PRECISION,
    funding_rate_daily_avg DOUBLE PRECISION,
    funding_percentile_90d DOUBLE PRECISION,
    dvol_close DOUBLE PRECISION,
    dvol_percentile_90d DOUBLE PRECISION,
    oi_change_pct DOUBLE PRECISION,
    price_oi_divergence TEXT,
    UNIQUE (symbol, date)
);
"""


def create_tables():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def upsert_rows(table: str, columns: list, rows: list, conflict_columns: list) -> int:
    """Bulk-insert rows, silently skipping any that violate the table's
    UNIQUE(conflict_columns) constraint. Returns the number of rows
    attempted, not the number actually new (duplicates are skipped, not
    counted separately)."""
    if not rows:
        return 0

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            columns_sql = ", ".join(columns)
            conflict_sql = ", ".join(conflict_columns)
            query = (
                f"INSERT INTO {table} ({columns_sql}) VALUES %s "
                f"ON CONFLICT ({conflict_sql}) DO NOTHING"
            )
            execute_values(cur, query, rows)
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def get_last_timestamp(table: str, time_column: str, symbol_column: str, symbol_value: str):
    """Latest saved timestamp for a symbol - used to fetch only new data."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT MAX({time_column}) FROM {table} WHERE {symbol_column} = %s",
                (symbol_value,),
            )
            return cur.fetchone()[0]
    finally:
        conn.close()


def get_saved_range(table: str, time_column: str, symbol_column: str, symbol_value: str):
    """(earliest, latest) saved timestamp for a symbol. Backfilling needs
    both ends: older history (if only a recent test window was ever
    fetched) and newer history (the normal incremental case). Returns
    (None, None) if nothing is saved yet."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT MIN({time_column}), MAX({time_column}) FROM {table} WHERE {symbol_column} = %s",
                (symbol_value,),
            )
            return cur.fetchone()
    finally:
        conn.close()


def read_df(query: str, params: tuple = None):
    """Run a query and return the result as a pandas DataFrame."""
    import pandas as pd  # local import so db.py stays light for scripts that don't need pandas

    conn = get_connection()
    try:
        return pd.read_sql(query, conn, params=params)
    finally:
        conn.close()


if __name__ == "__main__":
    create_tables()
    print("Tables created (or already existed).")
