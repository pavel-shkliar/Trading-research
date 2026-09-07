"""
Walk-forward validation of H1c: crowded LONGS -> BUY (follow the crowd
rather than fade it).

Background: the exploratory pass found that price often rose after a
"crowded longs" signal, but the baseline (the whole market over the same
period) rose almost as often too - so raw positive returns alone prove
nothing. The full-history edge was inconsistent (positive on 5 horizons,
negative on 2), unlike H1b where it was positive on all 7. Tested with
the same walk-forward procedure as H1b for a fair comparison.

Usage:
    python backtest_h1c_walkforward.py
"""

import pandas as pd

from walkforward_common import load_data, run_walkforward

SYMBOL = "BTCUSDT"
LONG_THRESHOLD = 0.95
HORIZONS = [30, 90]


if __name__ == "__main__":
    df = load_data(SYMBOL)
    long_crowded = df["funding_percentile_90d"] > LONG_THRESHOLD

    result = run_walkforward(SYMBOL, long_crowded, HORIZONS, df)

    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(result.to_string(index=False))
    result.to_csv("h1c_walkforward_result.csv", index=False)
