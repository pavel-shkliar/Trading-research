"""
H10: refines H6b - DVOL complacency AFTER a rally vs WITHOUT a preceding
rally.

Idea: "complacency after a rally" may partly be a normal reaction (people
are content with their gains, relaxed for a reason). "Complacency
WITHOUT a rally" is stranger - why would the market be calm if price
hasn't even gone up? Possibly a cleaner signal of risk underpricing.

Split by the trailing 90-day return before the signal: positive = "after
a rally", negative/zero = "without a rally".

Horizon: 60 days, the H6b anchor.

Usage:
    python backtest_h10_dvol_momentum.py
"""

import pandas as pd

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return, summarize

DVOL_LOW = 0.05
TRAILING_WINDOW = 90
HORIZON = 60
SYMBOLS = ["BTCUSDT", "ETHUSDT"]


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
    return df[df["dvol_percentile_90d"].notna()].reset_index(drop=True)


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")

    for symbol in SYMBOLS:
        df = load_data(symbol)
        trailing_return = (df["close"] - df["close"].shift(TRAILING_WINDOW)) / df["close"].shift(TRAILING_WINDOW) * 100
        dvol_low = df["dvol_percentile_90d"] < DVOL_LOW

        after_rally = collapse_to_episodes(dvol_low & (trailing_return > 0))
        without_rally = collapse_to_episodes(dvol_low & (trailing_return <= 0))

        fwd = forward_return(df["close"], HORIZON)
        baseline = summarize(fwd)

        print(f"=== {symbol} (horizon {HORIZON}d) ===")
        for label, mask in [
            ("After a rally (90d return > 0)", after_rally),
            ("Without a rally (90d return <= 0)", without_rally),
        ]:
            s = summarize(fwd[mask])
            if s["mean"] is None:
                print(f"  {label}: not enough data")
                continue
            edge = s["mean"] - baseline["mean"]
            print(f"  {label}: n={s['n']}, return={s['mean']:.2f}%, baseline={baseline['mean']:.2f}%, edge={edge:.2f}")
        print()
