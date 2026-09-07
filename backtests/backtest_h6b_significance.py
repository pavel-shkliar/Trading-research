"""
Statistical significance check for H6b (DVOL complacency ->
underperformance) at the 60-day horizon, where walk-forward showed the
most consistent result (5 of 5 available periods).

Same methodology as H1b: signal days collapsed into independent episodes
(guards against autocorrelated overlapping return windows), two
significance tests - Welch's t-test (sensitive to the mean) and
Mann-Whitney U (robust to outliers, compares rank distributions).

Usage:
    python backtests/backtest_h6b_significance.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from scipy import stats

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return

SYMBOL = "BTCUSDT"
DVOL_LOW = 0.05
HORIZON = 60


def load_data(symbol: str):
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
    return df[df["dvol_percentile_90d"].notna()].reset_index(drop=True)


if __name__ == "__main__":
    df = load_data(SYMBOL)

    dvol_low = df["dvol_percentile_90d"] < DVOL_LOW
    episode_mask = collapse_to_episodes(dvol_low)

    fwd = forward_return(df["close"], HORIZON)
    episode_returns = fwd[episode_mask].dropna()
    baseline_returns = fwd.dropna()

    n = len(episode_returns)
    mean = episode_returns.mean()
    se = episode_returns.std() / np.sqrt(n)
    ci_low, ci_high = mean - 1.96 * se, mean + 1.96 * se
    baseline_mean = baseline_returns.mean()

    t_stat, p_ttest = stats.ttest_ind(episode_returns, baseline_returns, equal_var=False)
    u_stat, p_mw = stats.mannwhitneyu(episode_returns, baseline_returns, alternative="less")

    print(f"Horizon: {HORIZON} days")
    print(f"n episodes = {n}")
    print(f"Signal group mean = {mean:.2f}%, baseline = {baseline_mean:.2f}%")
    print(f"95% CI for the signal group: [{ci_low:.2f}%, {ci_high:.2f}%]")
    print(f"Welch t-test (signal vs baseline): t={t_stat:.2f}, p-value={p_ttest:.4f}")
    print(f"Mann-Whitney U (one-sided, signal < baseline): p-value={p_mw:.4f}")
