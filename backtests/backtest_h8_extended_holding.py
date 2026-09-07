"""
Extension of H8: not just "enter and exit same day," but the full grid of
entry weekday x holding period (1-7 days) -> exit. E.g. "enter Wednesday
morning, exit Monday evening" = enter Wednesday, hold 6 days (Wed, Thu,
Fri, Sat, Sun, Mon).

CAUTION: this is 7 entry days x 7 hold lengths = 49 combinations at once
- far more "attempts" than even the original 7-day scan (see the
multiple-comparisons note in HYPOTHESES.md). The logic will always find
some "best" combination, even with no real effect anywhere - treat this
as a map of where to look further, not a finished conclusion.

Usage:
    python backtests/backtest_h8_extended_holding.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from db import read_df

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MAX_HOLD_DAYS = 7


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        "SELECT open_time AS date, open, close FROM candles WHERE symbol = %(symbol)s ORDER BY open_time",
        params={"symbol": symbol},
    )
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["weekday"] = df["date"].dt.weekday
    return df


def build_grid(df: pd.DataFrame) -> pd.DataFrame:
    open_arr = df["open"].values
    close_arr = df["close"].values
    n = len(df)

    rows = []
    for hold in range(1, MAX_HOLD_DAYS + 1):
        # Return for entering at day t's open, exiting at day t+hold-1's close.
        exit_idx = np.arange(n) + hold - 1
        valid = exit_idx < n
        ret = np.full(n, np.nan)
        ret[valid] = (close_arr[exit_idx[valid]] - open_arr[valid]) / open_arr[valid] * 100

        temp = pd.DataFrame({"weekday": df["weekday"], "ret": ret})
        avg_by_weekday = temp.groupby("weekday")["ret"].mean()
        for wd in range(7):
            rows.append({
                "entry_weekday": WEEKDAY_NAMES[wd],
                "hold_days": hold,
                "avg_return": avg_by_weekday.get(wd, np.nan),
            })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")

    for symbol in SYMBOLS:
        df = load_data(symbol)
        grid = build_grid(df)
        pivot = grid.pivot(index="entry_weekday", columns="hold_days", values="avg_return")
        pivot = pivot.reindex(WEEKDAY_NAMES)

        print(f"=== {symbol}: average return (%) by (entry weekday x hold days) ===")
        print(pivot.to_string())

        best = grid.loc[grid["avg_return"].idxmax()]
        worst = grid.loc[grid["avg_return"].idxmin()]
        print(f"Best combo: enter {best['entry_weekday']}, hold {int(best['hold_days'])}d -> {best['avg_return']:.2f}%")
        print(f"Worst combo: enter {worst['entry_weekday']}, hold {int(worst['hold_days'])}d -> {worst['avg_return']:.2f}%")
        print()
