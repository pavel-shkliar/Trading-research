"""
H8, extended: the original Wednesday-effect check only covered BTC and
ETH - not because the hypothesis needs DVOL (it doesn't, it's pure price
data), but because it was written from the H6b/H7 template that does.
Re-tests across the full 20-coin universe to see whether the effect is
real and broad, or an artifact of picking 2 assets.

Usage:
    python backtests/backtest_h8_universe_check.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from scipy import stats

from db import read_df

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "ZECUSDT", "SOLUSDT", "XRPUSDT",
    "HYPEUSDT", "DOGEUSDT", "ARBUSDT", "BNBUSDT",
    "RAYSOLUSDT", "SUIUSDT", "NEARUSDT", "TAOUSDT", "LINKUSDT",
    "WLDUSDT", "UNIUSDT", "PUMPUSDT", "ADAUSDT", "LTCUSDT", "AVAXUSDT",
]
MIN_HISTORY_DAYS = 400


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        "SELECT open_time AS date, open, close FROM candles WHERE symbol = %(s)s ORDER BY open_time",
        params={"s": symbol},
    )
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.4f}")

    rows = []
    for symbol in SYMBOLS:
        df = load_data(symbol)
        if len(df) < MIN_HISTORY_DAYS:
            continue

        df["weekday"] = df["date"].dt.weekday
        df["intraday_return"] = (df["close"] - df["open"]) / df["open"] * 100

        wed = df[df["weekday"] == 2]["intraday_return"]
        other = df[df["weekday"] != 2]["intraday_return"]
        t, p = stats.ttest_ind(wed, other, equal_var=False)
        rows.append({"symbol": symbol, "n_days": len(df), "wed_mean": wed.mean(),
                      "other_mean": other.mean(), "p_value": p})

    result = pd.DataFrame(rows).sort_values("p_value")
    print(result.to_string(index=False))

    significant_positive = ((result["p_value"] < 0.05) & (result["wed_mean"] > result["other_mean"])).sum()
    positive_direction = (result["wed_mean"] > result["other_mean"]).sum()
    print(f"\nSignificant (p<0.05) AND positive: {significant_positive} of {len(result)}")
    print(f"Positive direction (regardless of significance): {positive_direction} of {len(result)}")
