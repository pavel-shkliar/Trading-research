"""
Downloads daily candles (OHLCV) from Binance Futures into the candles
table. Incremental - only fetches what isn't already saved.

Usage:
    python download_candles.py --days 5     (quick smoke test)
    python download_candles.py --days 2600  (full history since 2019)
"""

import argparse
import time
from datetime import datetime, timedelta, timezone

from binance_api import get
from db import get_saved_range, upsert_rows

SYMBOL = "BTCUSDT"
INTERVAL = "1d"
LIMIT = 1500  # max candles per Binance request


def fetch_klines(symbol: str, start_ms: int, end_ms: int) -> list:
    return get("/fapi/v1/klines", {
        "symbol": symbol,
        "interval": INTERVAL,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": LIMIT,
    })


def _download_period(symbol: str, start_ms: int, end_ms: int) -> int:
    """Fetches and saves one contiguous [start_ms, end_ms] period,
    paginating across multiple requests if needed."""
    total = 0
    current_start = start_ms
    while current_start < end_ms:
        batch = fetch_klines(symbol, current_start, end_ms)
        if not batch:
            break

        rows = [
            (
                symbol,
                datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc),
                float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5]),
                int(c[8]),
            )
            for c in batch
        ]
        total += upsert_rows(
            "candles",
            ["symbol", "open_time", "open", "high", "low", "close", "volume", "trades"],
            rows,
            ["symbol", "open_time"],
        )

        current_start = batch[-1][0] + 1
        if len(batch) < LIMIT:
            break
        time.sleep(0.2)

    return total


def download(symbol: str, days_back: int) -> int:
    end_dt = datetime.now(timezone.utc)
    requested_start = end_dt - timedelta(days=days_back)

    # Backfill BOTH missing ends: older history (if only a recent test
    # window was fetched before) and newer history (the normal incremental
    # case). Without this, a one-off "last 5 days" test run followed by a
    # "last 730 days" request would never backfill the older gap, since a
    # naive incremental check only looks forward from the latest saved date.
    existing_min, existing_max = get_saved_range("candles", "open_time", "symbol", symbol)

    total = 0
    if existing_min is None:
        total += _download_period(symbol, int(requested_start.timestamp() * 1000), int(end_dt.timestamp() * 1000))
    else:
        if requested_start < existing_min:
            total += _download_period(
                symbol,
                int(requested_start.timestamp() * 1000),
                int(existing_min.timestamp() * 1000),
            )
        if existing_max < end_dt:
            gap_start = existing_max + timedelta(milliseconds=1)
            total += _download_period(symbol, int(gap_start.timestamp() * 1000), int(end_dt.timestamp() * 1000))

    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=2600)
    parser.add_argument("--symbol", default=SYMBOL)
    args = parser.parse_args()

    print(f"Downloading {args.symbol} candles for the last {args.days} days...")
    saved = download(args.symbol, args.days)
    print(f"Done: {saved} candles processed.")
