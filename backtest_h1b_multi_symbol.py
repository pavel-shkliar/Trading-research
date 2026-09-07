"""
H1b across multiple coins, not just BTC - if the pattern reflects real
derivatives mechanics, it should show up on more than one asset.
Percentile-normalized thresholds (self-relative per coin) make it
possible to compare and pool assets directly.

Coins with less than ~400 days of history are excluded as too thin to
be meaningful (see download_universe.py - MARSCOINUSDT had only 7 days).

Horizon: 90 days, the only walk-forward-confirmed horizon for H1b.

Each coin uses its own baseline. For the pooled result, each episode's
excess return (episode return minus that coin's own baseline) is combined
across coins into one sample, growing the effective sample size without
mixing coins with different overall drift directly.

Usage:
    python backtest_h1b_multi_symbol.py
"""

import numpy as np
import pandas as pd
from scipy import stats

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return, summarize

SHORT_THRESHOLD = 0.05
HORIZON = 90
MIN_HISTORY_DAYS = 400

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "ZECUSDT", "SOLUSDT", "XRPUSDT",
    "HYPEUSDT", "DOGEUSDT", "ARBUSDT", "BNBUSDT",
    "RAYSOLUSDT", "SUIUSDT", "NEARUSDT", "TAOUSDT", "LINKUSDT",
    "WLDUSDT", "UNIUSDT", "PUMPUSDT",
    # SNDKUSDT, BZUSDT, MARSCOINUSDT excluded (< 400 days) - replaced
    # with long-established coins to keep the universe at 20:
    "ADAUSDT", "LTCUSDT", "AVAXUSDT",
]


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        """
        SELECT i.date, i.funding_percentile_90d, c.close
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
    per_symbol_rows = []
    all_excess_returns = []

    for symbol in SYMBOLS:
        df = load_data(symbol)
        if len(df) < MIN_HISTORY_DAYS:
            print(f"{symbol}: skipped, {len(df)} days of history < {MIN_HISTORY_DAYS}")
            continue

        short_crowded = collapse_to_episodes(df["funding_percentile_90d"] < SHORT_THRESHOLD)
        fwd = forward_return(df["close"], HORIZON)

        signal_stats = summarize(fwd[short_crowded])
        baseline_stats = summarize(fwd)

        if signal_stats["mean"] is None or baseline_stats["mean"] is None:
            print(f"{symbol}: not enough signal days at horizon {HORIZON}")
            continue

        edge_mean = signal_stats["mean"] - baseline_stats["mean"]

        episode_returns = fwd[short_crowded].dropna()
        excess = (episode_returns - baseline_stats["mean"]).tolist()
        all_excess_returns.extend(excess)

        per_symbol_rows.append({
            "symbol": symbol,
            "history_days": len(df),
            "n_episodes": signal_stats["n"],
            "signal_mean": signal_stats["mean"],
            "baseline_mean": baseline_stats["mean"],
            "edge_mean": edge_mean,
        })

    result = pd.DataFrame(per_symbol_rows).sort_values("edge_mean", ascending=False)
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)
    print(result.to_string(index=False))
    result.to_csv("h1b_multi_symbol_result.csv", index=False)

    print(f"\n=== Pooled across all coins ===")
    all_excess = np.array(all_excess_returns)
    n_total = len(all_excess)
    mean_excess = all_excess.mean()
    se = all_excess.std() / np.sqrt(n_total)
    ci_low, ci_high = mean_excess - 1.96 * se, mean_excess + 1.96 * se
    t_stat, p_value = stats.ttest_1samp(all_excess, 0)

    print(f"Total episodes across all coins: {n_total}")
    print(f"Mean excess return (signal minus own baseline): {mean_excess:.2f}%")
    print(f"95% CI: [{ci_low:.2f}%, {ci_high:.2f}%]")
    print(f"t-test vs zero: t={t_stat:.2f}, p-value={p_value:.4f}")
