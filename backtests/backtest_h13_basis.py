"""
H13: extreme futures/spot basis -> convergence.

A fresh but classic derivatives angle with a real economic rationale
(unlike H8): basis = (futures price - spot price) / spot price. In
theory, arbitrage should keep this small - if futures trade well above
spot (contango), selling futures and buying spot (cash-and-carry) is
profitable and pushes the basis back toward zero.

Hypothesis: extremely high basis (futures far above spot,
percentile > 0.95) -> the futures price subsequently UNDERPERFORMS spot
(the basis converges via the futures side lagging, not only via spot
catching up).

Measured through the FUTURES return (what we actually trade) relative to
its own history, baseline = all days, as elsewhere.

Horizon: 60 days. Full routine: 90d percentile, episodes, walk-forward,
significance tests.

Usage:
    python backtests/backtest_h13_basis.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from scipy import stats

from db import read_df
from walkforward_common import PERIODS, collapse_to_episodes, forward_return, summarize

BASIS_HIGH = 0.95
BASIS_LOW = 0.05
HORIZON = 60
SYMBOLS = ["BTCUSDT", "ETHUSDT"]


def load_data(symbol: str) -> pd.DataFrame:
    futures = read_df(
        "SELECT open_time AS date, close FROM candles WHERE symbol = %(s)s ORDER BY open_time",
        params={"s": symbol},
    )
    spot = read_df(
        "SELECT open_time AS date, close AS spot_close FROM spot_candles WHERE symbol = %(s)s ORDER BY open_time",
        params={"s": symbol},
    )
    futures["date"] = pd.to_datetime(futures["date"], utc=True)
    spot["date"] = pd.to_datetime(spot["date"], utc=True)

    df = futures.merge(spot, on="date").reset_index(drop=True)
    df["basis"] = (df["close"] - df["spot_close"]) / df["spot_close"] * 100
    df["basis_pct"] = df["basis"].rolling(90).apply(lambda x: x.rank(pct=True).iloc[-1], raw=False)
    return df


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")

    for symbol in SYMBOLS:
        df = load_data(symbol)
        high_basis = collapse_to_episodes(df["basis_pct"] > BASIS_HIGH)
        low_basis = collapse_to_episodes(df["basis_pct"] < BASIS_LOW)

        fwd = forward_return(df["close"], HORIZON)
        baseline = summarize(fwd)

        print(f"=== {symbol} (horizon {HORIZON}d) ===")
        for label, mask in [
            ("Basis high (futures expensive, expect underperformance)", high_basis),
            ("Basis low (futures cheap, expect outperformance)", low_basis),
        ]:
            s = summarize(fwd[mask])
            if s["mean"] is None or s["n"] < 5:
                print(f"  {label}: n={s['n']} - not enough data")
                continue
            edge = s["mean"] - baseline["mean"]
            episode_returns = fwd[mask].dropna()
            t, p_ttest = stats.ttest_ind(episode_returns, fwd.dropna(), equal_var=False)
            print(f"  {label}: n={s['n']}, return={s['mean']:.2f}%, baseline={baseline['mean']:.2f}%, edge={edge:.2f}, p={p_ttest:.4f}")

        print("  Walk-forward (high basis):")
        for start, end, label in PERIODS:
            mask = (df["date"] >= pd.Timestamp(start, tz="UTC")) & (df["date"] < pd.Timestamp(end, tz="UTC"))
            sig = fwd[mask & high_basis].dropna()
            base = fwd[mask].dropna()
            if len(sig) < 3:
                print(f"    {label}: n={len(sig)} - too little data")
                continue
            print(f"    {label}: n={len(sig)}, return={sig.mean():.2f}%, baseline={base.mean():.2f}%, edge={sig.mean()-base.mean():.2f}")
        print()
