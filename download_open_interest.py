"""
Downloads Open Interest history from Binance Futures into the
open_interest table.

Binance API limitation (not ours): this endpoint only returns roughly the
last 30 days of history, regardless of the requested startTime. Longer
history isn't obtainable here - it's accumulated going forward instead by
re-running this script on a schedule (see the daily task).

Usage:
    python download_open_interest.py --days 5
    python download_open_interest.py --days 30
"""

import argparse
import time
from datetime import datetime, timedelta, timezone

from binance_api import get
from db import get_saved_range, upsert_rows

SYMBOL = "BTCUSDT"
PERIOD = "1d"  # daily aggregation, matches candle frequency
LIMIT = 500


def fetch(symbol: str, start_ms: int, end_ms: int) -> list:
    return get("/futures/data/openInterestHist", {
        "symbol": symbol,
        "period": PERIOD,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": LIMIT,
    })


def _download_period(symbol: str, start_ms: int, end_ms: int) -> int:
    total = 0
    current_start = start_ms
    while current_start < end_ms:
        batch = fetch(symbol, current_start, end_ms)
        if not batch:
            break

        rows = [
            (
                symbol,
                datetime.fromtimestamp(r["timestamp"] / 1000, tz=timezone.utc),
                float(r["sumOpenInterest"]),
                float(r["sumOpenInterestValue"]),
            )
            for r in batch
        ]
        total += upsert_rows(
            "open_interest",
            ["symbol", "ts", "sum_open_interest", "sum_open_interest_value"],
            rows,
            ["symbol", "ts"],
        )

        current_start = batch[-1]["timestamp"] + 1
        if len(batch) < LIMIT:
            break
        time.sleep(0.2)

    return total


def download(symbol: str, days_back: int) -> int:
    end_dt = datetime.now(timezone.utc)
    requested_start = end_dt - timedelta(days=days_back)

    # Backfill both ends - see the comment in download_candles.py.
    existing_min, existing_max = get_saved_range("open_interest", "ts", "symbol", symbol)

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
    parser.add_argument("--days", type=int, default=30, help="Binance retains at most ~30 days for this endpoint")
    parser.add_argument("--symbol", default=SYMBOL)
    args = parser.parse_args()

    print(f"Downloading {args.symbol} Open Interest for the last {args.days} days...")
    saved = download(args.symbol, args.days)
    print(f"Done: {saved} Open Interest records processed.")
