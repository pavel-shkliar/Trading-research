"""
H6 (see HYPOTHESES.md): DVOL extremes on their own, independent of funding.

Two separate, substantively different hypotheses (kept apart, not blended
into one number):

1. DVOL high (percentile > 0.95, options market in fear) -> expect a
   BOUNCE. Analogous to VIX on traditional markets, where extreme fear is
   often a contrarian signal.
2. DVOL low (percentile < 0.05, market "complacency") -> expect an
   INCREASE in large drops afterward. Options-market folklore: "calm
   before the storm" - if nobody is hedging, a surprise costs more.

DVOL data is only available from 2021-06-21 onward (see
compute_indicators.py) - shorter history than funding rate.

Exploratory pass across all 7 horizons, episodes instead of raw days.

Usage:
    python backtest_h6_dvol.py
"""

import pandas as pd

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return, summarize

SYMBOL = "BTCUSDT"
DVOL_HIGH = 0.95
DVOL_LOW = 0.05
BIG_MOVE_PCT = 5.0
HORIZONS = [3, 7, 14, 30, 60, 90, 180]


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


def big_down_freq(returns: pd.Series, big_move_pct: float) -> float:
    returns = returns.dropna()
    if len(returns) == 0:
        return None
    return (returns <= -big_move_pct).mean() * 100


if __name__ == "__main__":
    df = load_data(SYMBOL)
    has_dvol = df["dvol_percentile_90d"].notna()

    dvol_high = collapse_to_episodes(has_dvol & (df["dvol_percentile_90d"] > DVOL_HIGH))
    dvol_low = collapse_to_episodes(has_dvol & (df["dvol_percentile_90d"] < DVOL_LOW))

    rows = []
    for horizon in HORIZONS:
        fwd = forward_return(df["close"], horizon)
        baseline = summarize(fwd[has_dvol])  # baseline restricted to days DVOL exists, for a fair comparison
        baseline_down = big_down_freq(fwd[has_dvol], BIG_MOVE_PCT)

        # Hypothesis 1: DVOL high -> expect a bounce
        s_high = summarize(fwd[dvol_high])
        edge_mean_high = (s_high["mean"] - baseline["mean"]) if s_high["mean"] is not None else None
        edge_up_high = (s_high["big_up_freq"] - baseline["big_up_freq"]) if s_high["big_up_freq"] is not None else None
        rows.append({
            "horizon_days": horizon, "hypothesis": "DVOL high -> expect rally",
            "n_episodes": s_high["n"], "signal_mean": s_high["mean"], "baseline_mean": baseline["mean"],
            "edge_mean": edge_mean_high,
            "signal_metric_pct": s_high["big_up_freq"], "baseline_metric_pct": baseline["big_up_freq"],
            "edge_metric_pct": edge_up_high,
        })

        # Hypothesis 2: DVOL low -> expect more frequent large drops
        s_low_down = big_down_freq(fwd[dvol_low], BIG_MOVE_PCT)
        s_low_mean = summarize(fwd[dvol_low])["mean"]
        n_low = summarize(fwd[dvol_low])["n"]
        edge_mean_low = (s_low_mean - baseline["mean"]) if s_low_mean is not None else None
        edge_down_low = (s_low_down - baseline_down) if s_low_down is not None else None
        rows.append({
            "horizon_days": horizon, "hypothesis": "DVOL low -> expect large drops",
            "n_episodes": n_low, "signal_mean": s_low_mean, "baseline_mean": baseline["mean"],
            "edge_mean": edge_mean_low,
            "signal_metric_pct": s_low_down, "baseline_metric_pct": baseline_down,
            "edge_metric_pct": edge_down_low,
        })

    result = pd.DataFrame(rows)
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(result.to_string(index=False))
    result.to_csv("h6_dvol_result.csv", index=False)
