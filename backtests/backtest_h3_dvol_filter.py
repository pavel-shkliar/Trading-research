"""
H3 (see HYPOTHESES.md): DVOL as a confirmation filter for H1b.

The project's original premise: the options market is a "smarter" source
than the retail crowd on perpetuals. Tested here: among days where H1b's
signal fires (funding_percentile_90d < 0.05, "crowded shorts"), does the
outcome differ depending on whether DVOL was ALSO elevated (options
market also seeing stress) vs calm (only the futures market is stressed)?

Data constraint: DVOL exists only from 2021-03-24, and its percentile
needs a 90-day window, so this check only applies to H1b signal days
after 2021-06-21 - a smaller sample than the original H1b.

Split threshold: DVOL percentile > 0.5 (above its own 90-day median) =
"options also stressed", <= 0.5 = "options calm".

Usage:
    python backtests/backtest_h3_dvol_filter.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return, summarize

SYMBOL = "BTCUSDT"
SHORT_THRESHOLD = 0.05
DVOL_SPLIT = 0.5
HORIZONS = [30, 90]


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        """
        SELECT i.date, i.funding_percentile_90d, i.dvol_percentile_90d, c.close
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
    df = load_data(SYMBOL)

    short_crowded = df["funding_percentile_90d"] < SHORT_THRESHOLD
    has_dvol = df["dvol_percentile_90d"].notna()

    dvol_stressed = collapse_to_episodes(short_crowded & has_dvol & (df["dvol_percentile_90d"] > DVOL_SPLIT))
    dvol_calm = collapse_to_episodes(short_crowded & has_dvol & (df["dvol_percentile_90d"] <= DVOL_SPLIT))

    rows = []
    for horizon in HORIZONS:
        fwd = forward_return(df["close"], horizon)
        baseline = summarize(fwd[has_dvol])  # baseline restricted to days where DVOL exists too, for a fair comparison

        for label, mask in [
            ("DVOL also stressed (>0.5)", dvol_stressed),
            ("DVOL calm (<=0.5)", dvol_calm),
        ]:
            s = summarize(fwd[mask])
            edge_mean = (s["mean"] - baseline["mean"]) if s["mean"] is not None else None
            edge_big_up = (s["big_up_freq"] - baseline["big_up_freq"]) if s["big_up_freq"] is not None else None

            rows.append({
                "horizon_days": horizon,
                "group": label,
                "n_signals": s["n"],
                "signal_mean": s["mean"],
                "signal_big_up_pct": s["big_up_freq"],
                "baseline_mean": baseline["mean"],
                "baseline_big_up_pct": baseline["big_up_freq"],
                "edge_mean": edge_mean,
                "edge_big_up_pct": edge_big_up,
            })

    result = pd.DataFrame(rows)
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(result.to_string(index=False))
    result.to_csv("h3_dvol_filter_result.csv", index=False)
