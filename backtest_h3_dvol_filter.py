"""
H3 (см. HYPOTHESES.md): DVOL как фильтр/подтверждение для H1b.

Идея (исходная для всего проекта, PLAN.md) - опционный рынок считается
более "умным" источником, чем розничная толпа на перпетуалах. Проверяем:
среди дней, когда сработал сигнал H1b (funding_percentile_90d < 0.05,
"перегружены шортами"), отличается ли результат в зависимости от того,
был ли ТАКЖЕ повышен DVOL (опционный рынок тоже видит стресс) или DVOL
был спокоен (только фьючерсный рынок в стрессе, опционы - нет)?

Ограничение данных: DVOL существует только с 2021-03-24, а перцентиль
DVOL считается с окном 90 дней - то есть эта проверка возможна только
для сигнальных дней ПОСЛЕ 2021-06-21 (когда набралось 90 дней истории
DVOL). Более ранние сигналы H1b (2019-2021) сюда не попадают - меньше
данных, чем в исходном H1b.

Порог разделения: DVOL percentile > 0.5 (выше своей медианы за 90 дней) =
"опционы тоже в стрессе", <= 0.5 = "опционы спокойны".

Запуск:
    python backtest_h3_dvol_filter.py
"""

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
        baseline = summarize(fwd[has_dvol])  # база - тоже только за период, где есть DVOL, для честного сравнения

        for label, mask in [
            ("DVOL тоже в стрессе (>0.5)", dvol_stressed),
            ("DVOL спокоен (<=0.5)", dvol_calm),
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
