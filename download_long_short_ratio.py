"""
Downloads Top Trader Long/Short Ratio (Positions) from Binance Futures -
the long/short positioning of top traders, weighted by position SIZE
(not account count). "Top traders" are Binance's own top-20% of accounts
on this contract by margin balance.

Same 30-day history limit as Open Interest (a Binance API restriction).

Usage:
    python download_long_short_ratio.py --days 5
    python download_long_short_ratio.py --days 30
"""

import argparse
import time
from datetime import datetime, timedelta, timezone

from binance_api import get
from db import get_saved_range, upsert_rows

SYMBOL = "BTCUSDT"
PERIOD = "1d"
LIMIT = 500


def fetch(symbol: str, start_ms: int, end_ms: int) -> list:
    return get("/futures/data/topLongShortPositionRatio", {
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
                float(r["longAccount"]),
                float(r["shortAccount"]),
                float(r["longShortRatio"]),
            )
            for r in batch
        ]
        total += upsert_rows(
            "top_trader_ratio",
            ["symbol", "ts", "long_account_ratio", "short_account_ratio", "long_short_ratio"],
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
    existing_min, existing_max = get_saved_range("top_trader_ratio", "ts", "symbol", symbol)

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

    print(f"Downloading {args.symbol} Top Trader Long/Short Ratio for the last {args.days} days...")
    saved = download(args.symbol, args.days)
    print(f"Done: {saved} records processed.")
