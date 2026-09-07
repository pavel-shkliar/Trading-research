"""
Downloads funding rate (perpetual futures financing rate, paid every 8
hours) from Binance Futures into the funding_rate table.

Extreme values relative to the symbol's own history (computed at the
indicators stage, not here) are a proxy for crowded positioning.

Usage:
    python downloaders/download_funding_rate.py --days 5
    python downloaders/download_funding_rate.py --days 2600  (full history since 2019)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
import time
from datetime import datetime, timedelta, timezone

from binance_api import get
from db import get_saved_range, upsert_rows

SYMBOL = "BTCUSDT"
LIMIT = 1000


def fetch_funding(symbol: str, start_ms: int, end_ms: int) -> list:
    return get("/fapi/v1/fundingRate", {
        "symbol": symbol,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": LIMIT,
    })


def _download_period(symbol: str, start_ms: int, end_ms: int) -> int:
    total = 0
    current_start = start_ms
    while current_start < end_ms:
        batch = fetch_funding(symbol, current_start, end_ms)
        if not batch:
            break

        rows = [
            (symbol, datetime.fromtimestamp(f["fundingTime"] / 1000, tz=timezone.utc), float(f["fundingRate"]))
            for f in batch
        ]
        total += upsert_rows(
            "funding_rate",
            ["symbol", "funding_time", "funding_rate"],
            rows,
            ["symbol", "funding_time"],
        )

        current_start = batch[-1]["fundingTime"] + 1
        if len(batch) < LIMIT:
            break
        time.sleep(0.2)

    return total


def download(symbol: str, days_back: int) -> int:
    end_dt = datetime.now(timezone.utc)
    requested_start = end_dt - timedelta(days=days_back)

    # Backfill both ends - see the comment in download_candles.py.
    existing_min, existing_max = get_saved_range("funding_rate", "funding_time", "symbol", symbol)

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

    print(f"Downloading {args.symbol} funding rate for the last {args.days} days...")
    saved = download(args.symbol, args.days)
    print(f"Done: {saved} funding rate records processed.")
