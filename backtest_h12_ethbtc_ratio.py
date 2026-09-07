"""
H12: ETH/BTC ratio extreme -> reversal of relative strength.

A fresh angle (not derivatives, not calendar) - cross-asset rotation. The
ETH/BTC ratio is a classic "alt season" indicator: when ETH strengthens
against BTC more than usual, altcoins are said to be "in favor"; a low
ratio means BTC dominance.

Hypothesis (asymmetric, like much of this project): extreme alt season
(ratio high) -> ETH subsequently LAGS BTC (reversal back toward BTC).
The other side (BTC dominance -> ETH catches up) did NOT hold up in the
exploratory pass (p=0.89) - only the confirmed half is tested here.

Relative return = ETH's return minus BTC's return over the same period.
Positive = ETH beat BTC, negative = BTC beat ETH.

Horizon: 60 days (the project's common anchor). Walk-forward by year,
episodes instead of raw days.

Usage:
    python backtest_h12_ethbtc_ratio.py
"""

import numpy as np
import pandas as pd
from scipy import stats

from db import read_df
from walkforward_common import PERIODS, collapse_to_episodes

RATIO_HIGH = 0.95
HORIZON = 60


def load_data() -> pd.DataFrame:
    btc = read_df("SELECT open_time AS date, close FROM candles WHERE symbol=%(s)s ORDER BY open_time", params={"s": "BTCUSDT"})
    eth = read_df("SELECT open_time AS date, close FROM candles WHERE symbol=%(s)s ORDER BY open_time", params={"s": "ETHUSDT"})
    btc["date"] = pd.to_datetime(btc["date"], utc=True)
    eth["date"] = pd.to_datetime(eth["date"], utc=True)
    df = btc.merge(eth, on="date", suffixes=("_btc", "_eth")).reset_index(drop=True)
    df["ratio"] = df["close_eth"] / df["close_btc"]
    df["ratio_pct"] = df["ratio"].rolling(90).apply(lambda x: x.rank(pct=True).iloc[-1], raw=False)
    return df


def relative_forward_return(df: pd.DataFrame, horizon: int) -> pd.Series:
    btc_fwd = (df["close_btc"].shift(-horizon) - df["close_btc"]) / df["close_btc"] * 100
    eth_fwd = (df["close_eth"].shift(-horizon) - df["close_eth"]) / df["close_eth"] * 100
    return eth_fwd - btc_fwd


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")

    df = load_data()
    high_ratio = collapse_to_episodes(df["ratio_pct"] > RATIO_HIGH)
    rel_fwd = relative_forward_return(df, HORIZON)
    baseline = rel_fwd.dropna()

    # --- Significance on episodes ---
    episode_returns = rel_fwd[high_ratio].dropna()
    t, p_ttest = stats.ttest_ind(episode_returns, baseline, equal_var=False)
    u, p_mw = stats.mannwhitneyu(episode_returns, baseline, alternative="less")
    print(f"n episodes = {len(episode_returns)}, mean relative return = {episode_returns.mean():.2f}%, baseline = {baseline.mean():.2f}%")
    print(f"t-test p={p_ttest:.4f}, Mann-Whitney p={p_mw:.4f}")
    print()

    # --- Walk-forward by year ---
    print("Walk-forward by year:")
    for start, end, label in PERIODS:
        mask = (df["date"] >= pd.Timestamp(start, tz="UTC")) & (df["date"] < pd.Timestamp(end, tz="UTC"))
        sig = rel_fwd[mask & high_ratio].dropna()
        base = rel_fwd[mask].dropna()
        if len(sig) < 3:
            print(f"  {label}: n={len(sig)} - not enough data")
            continue
        print(f"  {label}: n={len(sig)}, relative return={sig.mean():.2f}%, baseline={base.mean():.2f}%, edge={sig.mean()-base.mean():.2f}")
