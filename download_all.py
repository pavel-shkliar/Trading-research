"""
Runs all of the project's data downloaders in sequence, saving results to
Postgres.

Usage:
    python download_all.py --days 5      # short pipeline smoke test
    python download_all.py --days 2600   # full history (where available)

Open Interest / Long-Short Ratio / Taker Volume are capped at ~30 days by
Binance regardless of what's requested here - handled automatically below.
"""

import argparse

import download_candles
import download_funding_rate
import download_open_interest
import download_long_short_ratio
import download_taker_volume
import download_dvol

SYMBOL = "BTCUSDT"
CURRENCY = "BTC"
BINANCE_SHORT_HISTORY_LIMIT = 30  # applies to the OI/ratio/taker-volume endpoints


def main(days: int):
    print(f"=== Candles ({days}d) ===")
    print(download_candles.download(SYMBOL, days), "records")

    print(f"=== Funding rate ({days}d) ===")
    print(download_funding_rate.download(SYMBOL, days), "records")

    short_days = min(days, BINANCE_SHORT_HISTORY_LIMIT)

    print(f"=== Open Interest ({short_days}d, Binance limit) ===")
    print(download_open_interest.download(SYMBOL, short_days), "records")

    print(f"=== Top Trader Long/Short Ratio ({short_days}d, Binance limit) ===")
    print(download_long_short_ratio.download(SYMBOL, short_days), "records")

    print(f"=== Taker Buy/Sell Volume ({short_days}d, Binance limit) ===")
    print(download_taker_volume.download(SYMBOL, short_days), "records")

    print(f"=== DVOL ({days}d) ===")
    print(download_dvol.download(CURRENCY, days), "records")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=2600)
    args = parser.parse_args()
    main(args.days)
