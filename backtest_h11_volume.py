"""
H11: high/low trading volume -> different return?

Idea (independent of day-of-week): even in a 24/7 market, volume
fluctuates - checking whether volume ITSELF (not the day of week)
predicts anything about the next day's return.

Days are split by volume percentile over a rolling 90-day window (same
normalization logic as funding rate/DVOL, so we're measuring "unusually
high for the last 90 days," not "volume has grown over time in general").

Looks at the NEXT day's return (not the same day - that would just
measure the trivial same-day correlation between volume and volatility).

Usage:
    python backtest_h11_volume.py
"""

import pandas as pd

from db import read_df

VOLUME_WINDOW = 90
SYMBOLS = ["BTCUSDT", "ETHUSDT"]


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        "SELECT open_time AS date, close, volume FROM candles WHERE symbol = %(symbol)s ORDER BY open_time",
        params={"symbol": symbol},
    )
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.3f}")

    for symbol in SYMBOLS:
        df = load_data(symbol)

        volume_percentile = df["volume"].rolling(VOLUME_WINDOW).apply(
            lambda x: x.rank(pct=True).iloc[-1], raw=False
        )
        next_day_return = (df["close"].shift(-1) - df["close"]) / df["close"] * 100

        high_volume = volume_percentile > 0.90
        low_volume = volume_percentile < 0.10
        normal_volume = (volume_percentile >= 0.10) & (volume_percentile <= 0.90)

        print(f"=== {symbol} (next-day return after volume) ===")
        for label, mask in [("High volume (>90th pct)", high_volume),
                             ("Normal volume", normal_volume),
                             ("Low volume (<10th pct)", low_volume)]:
            vals = next_day_return[mask].dropna()
            print(f"  {label}: n={len(vals)}, mean={vals.mean():.3f}%, median={vals.median():.3f}%")
        print()
