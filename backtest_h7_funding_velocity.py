"""
H7: funding rate velocity, not just its level.

"Crowded shorts" (funding_percentile_90d < 0.05) can arise two ways:
- SUDDEN FLIP: not crowded 14 days ago, crowded now - a fast panic
  capitulation.
- CHRONIC STATE: was already crowded 14 days ago and still is - a
  drawn-out, low-intensity pessimism rather than a sharp event.

Hypothesis: a sudden flip is a stronger signal (panic capitulation
exhausts sellers faster) than a chronic state.

Horizon: 60 days (the H1b/H6b anchor). Checked on BTC and ETH.

Usage:
    python backtest_h7_funding_velocity.py
"""

import pandas as pd

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return, summarize

SHORT_THRESHOLD = 0.05
LOOKBACK = 14
HORIZON = 60
SYMBOLS = ["BTCUSDT", "ETHUSDT"]


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
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)

    for symbol in SYMBOLS:
        df = load_data(symbol)
        short_crowded_now = df["funding_percentile_90d"] < SHORT_THRESHOLD
        short_crowded_before = short_crowded_now.shift(LOOKBACK).fillna(False).astype(bool)

        sudden_flip = collapse_to_episodes(short_crowded_now & ~short_crowded_before)
        chronic = collapse_to_episodes(short_crowded_now & short_crowded_before)

        fwd = forward_return(df["close"], HORIZON)
        baseline = summarize(fwd)

        print(f"=== {symbol} (horizon {HORIZON}d) ===")
        for label, mask in [("Sudden flip (not crowded 14d ago)", sudden_flip),
                             ("Chronic (crowded 14d ago too)", chronic)]:
            s = summarize(fwd[mask])
            if s["mean"] is None:
                print(f"  {label}: not enough data")
                continue
            edge = s["mean"] - baseline["mean"]
            print(f"  {label}: n={s['n']}, return={s['mean']:.2f}%, baseline={baseline['mean']:.2f}%, edge={edge:.2f}")
        print()
