"""
H8: calendar effects - day of week, and intraday (open->close) vs
overnight (yesterday's close -> today's open) returns.

A different dimension entirely from everything before it (time, not
derivatives) - checking for a systematic day-of-week difference. Crypto
trades 24/7, but volume and participants can still differ by day (fewer
institutional traders on weekends).

- Intraday return = (close - open) / open on the SAME day
- Overnight return = (today's open - yesterday's close) / yesterday's close

Averages each type by day of week, over the full BTC and ETH history.

Usage:
    python backtest_h8_calendar.py
"""

import pandas as pd

from db import read_df

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        "SELECT open_time AS date, open, close FROM candles WHERE symbol = %(symbol)s ORDER BY open_time",
        params={"symbol": symbol},
    )
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.3f}")

    for symbol in SYMBOLS:
        df = load_data(symbol)
        df["weekday"] = df["date"].dt.weekday  # 0 = Monday
        df["intraday_return"] = (df["close"] - df["open"]) / df["open"] * 100
        df["overnight_return"] = (df["open"] - df["close"].shift(1)) / df["close"].shift(1) * 100

        grouped = df.groupby("weekday").agg(
            n=("intraday_return", "count"),
            intraday_mean=("intraday_return", "mean"),
            overnight_mean=("overnight_return", "mean"),
        )
        grouped.index = [WEEKDAY_NAMES[i] for i in grouped.index]

        print(f"=== {symbol} ===")
        print(grouped.to_string())
        print()
