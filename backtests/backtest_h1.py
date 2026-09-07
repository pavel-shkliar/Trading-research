"""
Backtest of H1 (see HYPOTHESES.md): extreme funding rate -> subsequent
price move against the crowded side.

First, exploratory pass over the full history (not yet walk-forward) to
see whether an effect exists at all before investing in a stricter
walk-forward check.

Methodology: the two sides are scored SEPARATELY, never blended into one
number - "crowded longs" (funding_percentile_90d > LONG_THRESHOLD) and
"crowded shorts" (< SHORT_THRESHOLD). Statistics are computed
symmetrically, with no assumption about which direction the price
"should" move: mean, median, volatility (std), and up/down big-move
frequency, all compared against the same-horizon baseline (all days).
An earlier version only measured "movement in the hypothesized
direction," which couldn't distinguish a real reversal from a merely
calmer market moving the same way, or from volatility simply dropping in
both directions - hence the full symmetric set here.

Caveat: funding rate often stays extreme for several consecutive days,
so neighboring signal days aren't fully independent and their forward
windows overlap heavily (especially at 90/180 days). Acceptable for this
exploratory pass; addressed separately before walk-forward validation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from db import read_df

SYMBOL = "BTCUSDT"
LONG_THRESHOLD = 0.95
SHORT_THRESHOLD = 0.05
BIG_MOVE_PCT = 5.0
HORIZONS = [3, 7, 14, 30, 60, 90, 180]


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


def summarize(returns: pd.Series, big_move_pct: float) -> dict:
    """Symmetric stats, direction-agnostic - see module docstring for why."""
    returns = returns.dropna()
    if len(returns) == 0:
        return {"n": 0, "mean": None, "median": None, "std": None,
                "big_up_freq": None, "big_down_freq": None}

    return {
        "n": len(returns),
        "mean": returns.mean(),
        "median": returns.median(),
        "std": returns.std(),
        "big_up_freq": (returns >= big_move_pct).mean() * 100,
        "big_down_freq": (returns <= -big_move_pct).mean() * 100,
    }


def run_backtest(symbol: str) -> pd.DataFrame:
    df = load_data(symbol)
    long_crowded = df["funding_percentile_90d"] > LONG_THRESHOLD
    short_crowded = df["funding_percentile_90d"] < SHORT_THRESHOLD

    rows = []
    for horizon in HORIZONS:
        fwd = forward_return(df["close"], horizon)
        baseline = summarize(fwd, BIG_MOVE_PCT)

        for group_name, mask in [
            ("long_crowded", long_crowded),
            ("short_crowded", short_crowded),
        ]:
            s = summarize(fwd[mask], BIG_MOVE_PCT)

            def edge(key):
                if s[key] is None or baseline[key] is None:
                    return None
                return s[key] - baseline[key]

            rows.append({
                "horizon_days": horizon,
                "group": group_name,
                "n_signals": s["n"],
                "mean_return": s["mean"],
                "median_return": s["median"],
                "volatility_std": s["std"],
                "big_up_freq_pct": s["big_up_freq"],
                "big_down_freq_pct": s["big_down_freq"],
                "baseline_mean": baseline["mean"],
                "baseline_volatility_std": baseline["std"],
                "baseline_big_up_freq_pct": baseline["big_up_freq"],
                "baseline_big_down_freq_pct": baseline["big_down_freq"],
                "edge_mean": edge("mean"),
                "edge_volatility_std": edge("std"),
                "edge_big_up_freq_pct": edge("big_up_freq"),
                "edge_big_down_freq_pct": edge("big_down_freq"),
            })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    result = run_backtest(SYMBOL)
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(result.to_string(index=False))
    result.to_csv("h1_backtest_result.csv", index=False)
