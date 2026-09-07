"""
Downloads DVOL (Deribit's options-implied volatility index, analogous to
VIX) into the dvol table.

Usage:
    python downloaders/download_dvol.py --days 5
    python downloaders/download_dvol.py --days 2600  (Deribit returns empty before 2021, when DVOL launched)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import argparse
from datetime import datetime, timedelta, timezone

from deribit_api import get
from db import get_saved_range, upsert_rows

CURRENCY = "BTC"
RESOLUTION = 86400  # index candle size in seconds (1 day)
CHUNK_DAYS = 80      # fetch history in chunks to stay under Deribit's per-request limits


def fetch_chunk(currency: str, start_ms: int, end_ms: int) -> list:
    result = get("/public/get_volatility_index_data", {
        "currency": currency,
        "start_timestamp": start_ms,
        "end_timestamp": end_ms,
        "resolution": RESOLUTION,
    })
    return result["data"]


def _download_period(currency: str, period_start: datetime, period_end: datetime) -> int:
    """Fetches one contiguous period in CHUNK_DAYS-sized chunks."""
    total = 0
    chunk_start = period_start
    while chunk_start < period_end:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS), period_end)

        data = fetch_chunk(
            currency,
            int(chunk_start.timestamp() * 1000),
            int(chunk_end.timestamp() * 1000),
        )

        # Each point is [timestamp_ms, open, high, low, close]
        rows = [
            (
                currency,
                datetime.fromtimestamp(point[0] / 1000, tz=timezone.utc),
                float(point[1]), float(point[2]), float(point[3]), float(point[4]),
            )
            for point in data
        ]
        total += upsert_rows(
            "dvol",
            ["currency", "ts", "open", "high", "low", "close"],
            rows,
            ["currency", "ts"],
        )

        chunk_start = chunk_end

    return total


def download(currency: str, days_back: int) -> int:
    end_dt = datetime.now(timezone.utc)
    requested_start = end_dt - timedelta(days=days_back)

    # Backfill both ends - see the comment in download_candles.py.
    existing_min, existing_max = get_saved_range("dvol", "ts", "currency", currency)

    total = 0
    if existing_min is None:
        total += _download_period(currency, requested_start, end_dt)
    else:
        if requested_start < existing_min:
            total += _download_period(currency, requested_start, existing_min)
        if existing_max < end_dt:
            gap_start = existing_max + timedelta(milliseconds=1)
            total += _download_period(currency, gap_start, end_dt)

    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=2600)
    parser.add_argument("--currency", default=CURRENCY)
    args = parser.parse_args()

    print(f"Downloading {args.currency} DVOL for the last {args.days} days...")
    saved = download(args.currency, args.days)
    print(f"Done: {saved} DVOL records processed.")
