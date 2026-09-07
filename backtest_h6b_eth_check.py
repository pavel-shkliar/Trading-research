"""
Checks H6b on ETH - the only other asset Deribit publishes DVOL for.
Not a full walk-forward (too little data for one coin alone), just a
quick check that the direction and rough magnitude hold on a second asset.

Horizon: 60 days, where H6b performed best on BTC.

Usage:
    python backtest_h6b_eth_check.py
"""

import numpy as np
from scipy import stats

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return

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


def check(symbol: str):
    df = load_data(symbol)
    dvol_low = df["dvol_percentile_90d"] < DVOL_LOW
    episode_mask = collapse_to_episodes(dvol_low)

    fwd = forward_return(df["close"], HORIZON)
    episode_returns = fwd[episode_mask].dropna()
    baseline_returns = fwd.dropna()

    n = len(episode_returns)
    mean = episode_returns.mean()
    baseline_mean = baseline_returns.mean()
    edge = mean - baseline_mean

    if n < 5:
        print(f"{symbol}: n={n} episodes - too few for a significance test")
        return

    t_stat, p_ttest = stats.ttest_ind(episode_returns, baseline_returns, equal_var=False)
    u_stat, p_mw = stats.mannwhitneyu(episode_returns, baseline_returns, alternative="less")

    print(f"{symbol}: n={n}, signal={mean:.2f}%, baseline={baseline_mean:.2f}%, edge={edge:.2f}")
    print(f"  t-test p={p_ttest:.4f}, Mann-Whitney p={p_mw:.4f}")


if __name__ == "__main__":
    check("BTCUSDT")
    check("ETHUSDT")
