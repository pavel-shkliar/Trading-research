"""
H5 (см. HYPOTHESES.md): RSI-перепроданность как дополнительное подтверждение
для H1b (перегруженные шорты -> рост).

Идея: RSI(14) и funding rate percentile - НЕЗАВИСИМО посчитанные
индикаторы (один из цены/объёма, другой из ставки финансирования). Если
оба одновременно показывают "перепроданность" - это два независимых
голоса за один и тот же вывод, что может быть сильнее, чем один
индикатор сам по себе (см. PLAN.md - ценность в комбинациях, а не
в классике по отдельности).

Порог: RSI_14 < 30 - стандартный учебниковый порог перепроданности
(сознательно берём готовый порог здесь, а не свой перцентиль - RSI и так
не даёт эдж сам по себе по PLAN.md, интересна именно комбинация).

Методология - разведочный прогон на всех 7 горизонтах (полный список из
исходного плана), эпизоды вместо сырых дней (см. чек-лист в HYPOTHESES.md),
полные абсолютные числа + отдельные Δ-столбцы (не "эдж" одним числом).

Запуск:
    python backtest_h5_rsi_funding.py
"""

import pandas as pd

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return, summarize

SYMBOL = "BTCUSDT"
SHORT_THRESHOLD = 0.05
RSI_OVERSOLD = 30
HORIZONS = [3, 7, 14, 30, 60, 90, 180]


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        """
        SELECT i.date, i.funding_percentile_90d, i.rsi_14, c.close
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
    rsi_oversold = df["rsi_14"] < RSI_OVERSOLD

    both_confirm = collapse_to_episodes(short_crowded & rsi_oversold)
    funding_only = collapse_to_episodes(short_crowded & ~rsi_oversold)

    rows = []
    for horizon in HORIZONS:
        fwd = forward_return(df["close"], horizon)
        baseline = summarize(fwd)

        for label, mask in [
            ("Funding + RSI оба перепроданы", both_confirm),
            ("Только funding (RSI не подтверждает)", funding_only),
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
    result.to_csv("h5_rsi_funding_result.csv", index=False)
