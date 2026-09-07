"""
Shared walk-forward machinery: period splitting, episode collapsing, and
forward-return statistics, reused by every hypothesis's backtest script.
"""

import pandas as pd

from db import read_df

BIG_MOVE_PCT = 5.0

# Yearly periods chosen to span distinct BTC market regimes.
PERIODS = [
    ("2019-09-08", "2021-01-01", "2019-2020 (COVID crash and recovery)"),
    ("2021-01-01", "2022-01-01", "2021 (bull, then correction)"),
    ("2022-01-01", "2023-01-01", "2022 (bear - Luna/FTX collapse)"),
    ("2023-01-01", "2024-01-01", "2023 (recovery)"),
    ("2024-01-01", "2025-01-01", "2024 (ETF rally)"),
    ("2025-01-01", "2026-09-07", "2025-2026 (latest period)"),
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


def forward_return(close: pd.Series, horizon: int) -> pd.Series:
    return (close.shift(-horizon) - close) / close * 100


def collapse_to_episodes(mask: pd.Series) -> pd.Series:
    """Keep only the first day of each run of consecutive True values.

    Two consecutive signal days have forward-return windows that overlap
    almost entirely (a 90-day window is unchanged by a 1-day shift) - they
    are the same price move counted twice, not two independent
    observations. Left uncollapsed, sample size is inflated and confidence
    intervals/p-values look far more certain than they are. Requires
    mask.index to be a plain 0..N-1 range so "adjacent by index" implies
    "adjacent by date"."""
    idx = pd.Series(mask.index[mask])
    if len(idx) == 0:
        return mask & False

    gaps = idx.diff()
    is_new_episode = (gaps != 1) | gaps.isna()
    first_of_episode = idx[is_new_episode.values]

    result = pd.Series(False, index=mask.index)
    result.loc[first_of_episode] = True
    return result


def summarize(returns: pd.Series, big_move_pct: float = BIG_MOVE_PCT) -> dict:
    returns = returns.dropna()
    if len(returns) == 0:
        return {"n": 0, "mean": None, "median": None, "big_up_freq": None}
    return {
        "n": len(returns),
        "mean": returns.mean(),
        "median": returns.median(),
        "big_up_freq": (returns >= big_move_pct).mean() * 100,
    }


def run_walkforward(symbol: str, signal_mask: pd.Series, horizons: list, df: pd.DataFrame) -> pd.DataFrame:
    """signal_mask: boolean series aligned with df, True on signal days.
    The baseline is computed per period over ALL days in that period, not
    just signal days.

    Episodes are collapsed globally (across the whole history) before
    splitting into periods, so an episode straddling a period boundary
    isn't collapsed incorrectly."""
    episode_mask = collapse_to_episodes(signal_mask)

    rows = []
    for horizon in horizons:
        fwd = forward_return(df["close"], horizon)

        for start, end, label in PERIODS:
            period_mask = (df["date"] >= pd.Timestamp(start, tz="UTC")) & (df["date"] < pd.Timestamp(end, tz="UTC"))

            sig_stats = summarize(fwd[period_mask & episode_mask])
            base_stats = summarize(fwd[period_mask])

            edge_mean = edge_big_up = None
            if sig_stats["mean"] is not None and base_stats["mean"] is not None:
                edge_mean = sig_stats["mean"] - base_stats["mean"]
                edge_big_up = sig_stats["big_up_freq"] - base_stats["big_up_freq"]

            rows.append({
                "horizon_days": horizon,
                "period": label,
                "n_signals": sig_stats["n"],
                "signal_mean": sig_stats["mean"],
                "signal_big_up_pct": sig_stats["big_up_freq"],
                "baseline_mean": base_stats["mean"],
                "baseline_big_up_pct": base_stats["big_up_freq"],
                "edge_mean": edge_mean,
                "edge_big_up_pct": edge_big_up,
            })

    return pd.DataFrame(rows)
