"""
Downloads Taker Buy/Sell Volume Ratio from Binance Futures - the ratio of
aggressive (market-order) buy volume to sell volume.

Reflects current order-flow pressure, distinct from long/short ratio
(which is about already-open positions). Same 30-day history limit as
Open Interest / Long-Short Ratio.

Usage:
    python downloaders/download_taker_volume.py --days 5
    python downloaders/download_taker_volume.py --days 30
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
PERIOD = "1d"
LIMIT = 500


def fetch(symbol: str, start_ms: int, end_ms: int) -> list:
    return get("/futures/data/takerlongshortRatio", {
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
                float(r["buySellRatio"]),
                float(r["buyVol"]),
                float(r["sellVol"]),
            )
            for r in batch
        ]
        total += upsert_rows(
            "taker_volume",
            ["symbol", "ts", "buy_sell_ratio", "buy_vol", "sell_vol"],
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
    existing_min, existing_max = get_saved_range("taker_volume", "ts", "symbol", symbol)

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

    print(f"Downloading {args.symbol} Taker Buy/Sell Volume for the last {args.days} days...")
    saved = download(args.symbol, args.days)
    print(f"Done: {saved} records processed.")
