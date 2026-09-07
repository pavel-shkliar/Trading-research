"""
Digging into H6b's mechanism: what actually happens to price day by day
after the signal (DVOL complacency), not just the endpoint at day 60.

Answers:
- Does the underperformance build gradually or arrive as a sharp move?
- Where inside the 60-day window is the gap vs baseline largest?
- How deep is the worst drawdown WITHIN the window (not just at the
  end) - tests "calm before the storm" (a sharp crash) against "slow
  bleed" (gradual underperformance)

Method: for each day, compute the full return path (1, 2, 3, ..., 60
days forward), not just one fixed-horizon number. Average these paths
separately for signal episodes and for the baseline (all days) to get
two comparable curves.

Also computes the worst point reached within the 60-day window (max
drawdown from the signal day), separate from the final day-60 return.

Usage:
    python backtests/backtest_h6b_mechanism.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from db import read_df
from walkforward_common import collapse_to_episodes

DVOL_LOW = 0.05
MAX_HORIZON = 60
CHECKPOINTS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
SYMBOLS = ["BTCUSDT", "ETHUSDT"]


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
    df = df[df["dvol_percentile_90d"].notna()].reset_index(drop=True)
    return df


def build_return_matrix(close: pd.Series, max_horizon: int) -> np.ndarray:
    """[day, horizon] matrix of the return (%) from each day, 1..max_horizon
    days forward. NaN where the future doesn't exist yet (end of history)."""
    n = len(close)
    matrix = np.full((n, max_horizon), np.nan)
    close_arr = close.values
    for h in range(1, max_horizon + 1):
        shifted = np.roll(close_arr, -h)
        ret = (shifted - close_arr) / close_arr * 100
        ret[n - h:] = np.nan  # np.roll wraps around; these rows are invalid
        matrix[:, h - 1] = ret
    return matrix


def analyze(symbol: str) -> pd.DataFrame:
    df = load_data(symbol)
    episode_mask = collapse_to_episodes(df["dvol_percentile_90d"] < DVOL_LOW).values

    matrix = build_return_matrix(df["close"], MAX_HORIZON)

    signal_matrix = matrix[episode_mask]
    baseline_matrix = matrix

    rows = []
    for cp in CHECKPOINTS:
        signal_vals = signal_matrix[:, cp - 1]
        baseline_vals = baseline_matrix[:, cp - 1]
        rows.append({
            "day": cp,
            "signal_avg_return": np.nanmean(signal_vals),
            "baseline_avg_return": np.nanmean(baseline_vals),
        })

    # Worst point reached within the 60-day window (max drawdown from the signal day)
    signal_worst_point = np.nanmin(signal_matrix, axis=1)
    baseline_worst_point = np.nanmin(baseline_matrix, axis=1)

    result = pd.DataFrame(rows)
    result["edge"] = result["signal_avg_return"] - result["baseline_avg_return"]

    print(f"\n=== {symbol} ===")
    print(result.to_string(index=False))
    print(f"Average WORST point over 60 days (drawdown from start):")
    print(f"  signal episodes: {np.nanmean(signal_worst_point):.2f}%  (n={(~np.isnan(signal_worst_point)).sum()})")
    print(f"  baseline (all days): {np.nanmean(baseline_worst_point):.2f}%")

    return result


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    for symbol in SYMBOLS:
        analyze(symbol)
