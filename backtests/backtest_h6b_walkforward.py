"""
Walk-forward validation of H6b: DVOL complacency (percentile < 0.05) ->
underperformance + more frequent large drops ("calm before the storm").

DVOL exists only from 2021-03-24 (+90 days for the percentile = usable
from 2021-06-21) - 2019-2020 and part of 2021 are empty or near-empty by
design, not a bug. The baseline is restricted to days where DVOL exists,
for a fair comparison (same issue as H3).

Horizons 30/60/90 - where the exploratory pass showed the most consistent
effect. Run for BTC and ETH together, the only two assets Deribit
publishes DVOL for.

Usage:
    python backtests/backtest_h6b_walkforward.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from db import read_df
from walkforward_common import run_walkforward

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
DVOL_LOW = 0.05
HORIZONS = [30, 60, 90]


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        """
        SELECT i.date, i.dvol_percentile_90d, c.close
        FROM indicators i
        JOIN candles c ON c.symbol = i.symbol AND c.open_time = i.date
        WHERE i.symbol = %(symbol)s
        ORDER BY i.date
        """,
        params={"symbol": symbol},
    )
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)

    all_results = []
    for symbol in SYMBOLS:
        df = load_data(symbol)
        df = df[df["dvol_percentile_90d"].notna()].reset_index(drop=True)

        dvol_low = df["dvol_percentile_90d"] < DVOL_LOW
        result = run_walkforward(symbol, dvol_low, HORIZONS, df)
        result.insert(0, "symbol", symbol)

        print(f"=== {symbol} ===")
        print(result.to_string(index=False))
        print()
        all_results.append(result)

    combined = pd.concat(all_results, ignore_index=True)
    combined.to_csv("h6b_walkforward_result.csv", index=False)
