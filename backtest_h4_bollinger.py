"""
H4 (см. HYPOTHESES.md): касание полосы Боллинджера -> откат к среднему.

Классический контроль, как H2 (RSI) - учебниковая идея mean-reversion:
цена у нижней полосы (перепродано) -> ждём роста к средней линии
цена у верхней полосы (перекуплено) -> ждём падения к средней линии

Разведочный прогон на всех 7 горизонтах, эпизоды вместо сырых дней.

Запуск:
    python backtest_h4_bollinger.py
"""

import pandas as pd

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return, summarize

SYMBOL = "BTCUSDT"
HORIZONS = [3, 7, 14, 30, 60, 90, 180]


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        """
        SELECT i.date, i.bb_upper, i.bb_lower, c.close
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

    touch_lower = collapse_to_episodes(df["close"] <= df["bb_lower"])
    touch_upper = collapse_to_episodes(df["close"] >= df["bb_upper"])

    rows = []
    for horizon in HORIZONS:
        fwd = forward_return(df["close"], horizon)
        baseline = summarize(fwd)

        for label, mask in [
            ("Касание нижней полосы (ждём роста)", touch_lower),
            ("Касание верхней полосы (ждём падения)", touch_upper),
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
    result.to_csv("h4_bollinger_result.csv", index=False)
