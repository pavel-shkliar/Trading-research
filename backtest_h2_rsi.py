"""
H2 (see HYPOTHESES.md): RSI extreme alone -> price reversal.

Classic textbook indicator, standard 30/70 thresholds (deliberately not
our own percentile - this is a sanity check on whether something this
well-known works at all on BTC, not a search for an optimal threshold).
Per PLAN.md, a weak or null result is expected here - a trustworthy
method should be able to show "nothing here" as confidently as it found
something in H1b.

RSI < 30 (oversold) -> expect a RALLY
RSI > 70 (overbought) -> expect a DROP

Exploratory pass across all 7 horizons, episodes instead of raw days,
full absolute numbers (not just the edge).

Usage:
    python backtest_h2_rsi.py
"""

import pandas as pd

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return, summarize

SYMBOL = "BTCUSDT"
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
HORIZONS = [3, 7, 14, 30, 60, 90, 180]


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        """
        SELECT i.date, i.rsi_14, c.close
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

    oversold = collapse_to_episodes(df["rsi_14"] < RSI_OVERSOLD)
    overbought = collapse_to_episodes(df["rsi_14"] > RSI_OVERBOUGHT)

    rows = []
    for horizon in HORIZONS:
        fwd = forward_return(df["close"], horizon)
        baseline = summarize(fwd)

        for label, mask in [
            ("RSI < 30 (oversold, expect rally)", oversold),
            ("RSI > 70 (overbought, expect drop)", overbought),
        ]:
            s = summarize(fwd[mask])
            edge_mean = (s["mean"] - baseline["mean"]) if s["mean"] is not None else None
            edge_big_up = (s["big_up_freq"] - baseline["big_up_freq"]) if s["big_up_freq"] is not None else None

            rows.append({
                "horizon_days": horizon,
                "group": label,
                "n_episodes": s["n"],
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
    result.to_csv("h2_rsi_result.csv", index=False)
