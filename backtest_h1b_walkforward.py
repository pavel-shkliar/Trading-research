"""
Walk-forward проверка H1b (см. HYPOTHESES.md): перегруженные шорты -> рост.

Зачем (обсуждали в чате): один общий эдж по всей истории 2019-2026 не
может отличить "эффект стабильно повторяется в разные годы" от "эффект
целиком держится на одном периоде (например, бычьем 2023-2026), а среднее
по всей истории это просто отражает". Решение - не искать новые данные
(взять больше неоткуда), а разбить УЖЕ ИМЕЮЩИЕСЯ 2556 дней на отдельные
периоды по времени и посчитать эдж ОТДЕЛЬНО для каждого. Если положительный
эдж появляется в нескольких разных периодах, включая медвежьи - это
убедительнее одного общего числа. Если эдж есть только в одном периоде -
это статистический мираж одного удачного отрезка, а не закономерность.

Периоды выбраны по годам, чтобы захватить разные известные режимы рынка
BTC: 2019-2020 (COVID-крах и восстановление), 2021 (бычий, затем
коррекция), 2022 (медвежий - крах Luna/FTX), 2023 (восстановление),
2024 (ETF-ралли), 2025-2026 (последний период).

База считается ОТДЕЛЬНО для каждого периода (по всем дням этого периода,
не только сигнальным) - иначе "эдж" перепутается с "это был хороший
период для рынка вообще, сигнал ни при чём".
"""

import pandas as pd

from db import read_df

SYMBOL = "BTCUSDT"
SHORT_THRESHOLD = 0.05
BIG_MOVE_PCT = 5.0
HORIZONS = [30, 90]

PERIODS = [
    ("2019-09-08", "2021-01-01", "2019-2020 (COVID-крах и восстановление)"),
    ("2021-01-01", "2022-01-01", "2021 (бычий, затем коррекция)"),
    ("2022-01-01", "2023-01-01", "2022 (медвежий - крах Luna/FTX)"),
    ("2023-01-01", "2024-01-01", "2023 (восстановление)"),
    ("2024-01-01", "2025-01-01", "2024 (ETF-ралли)"),
    ("2025-01-01", "2026-09-07", "2025-2026 (последний период)"),
]


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


def forward_return(close: pd.Series, horizon: int) -> pd.Series:
    return (close.shift(-horizon) - close) / close * 100


def summarize(returns: pd.Series, big_move_pct: float) -> dict:
    returns = returns.dropna()
    if len(returns) == 0:
        return {"n": 0, "mean": None, "median": None, "big_up_freq": None}
    return {
        "n": len(returns),
        "mean": returns.mean(),
        "median": returns.median(),
        "big_up_freq": (returns >= big_move_pct).mean() * 100,
    }


def run_walkforward(symbol: str) -> pd.DataFrame:
    df = load_data(symbol)
    short_crowded = df["funding_percentile_90d"] < SHORT_THRESHOLD

    rows = []
    for horizon in HORIZONS:
        fwd = forward_return(df["close"], horizon)

        for start, end, label in PERIODS:
            period_mask = (df["date"] >= pd.Timestamp(start, tz="UTC")) & (df["date"] < pd.Timestamp(end, tz="UTC"))

            sig_stats = summarize(fwd[period_mask & short_crowded], BIG_MOVE_PCT)
            base_stats = summarize(fwd[period_mask], BIG_MOVE_PCT)

            edge_mean = edge_big_up = None
            if sig_stats["mean"] is not None and base_stats["mean"] is not None:
                edge_mean = sig_stats["mean"] - base_stats["mean"]
                edge_big_up = sig_stats["big_up_freq"] - base_stats["big_up_freq"]

            rows.append({
                "horizon_days": horizon,
                "period": label,
                "n_signals": sig_stats["n"],
                "signal_mean": sig_stats["mean"],
                "signal_big_up_pct": sig_stats["big_up_freq"],
                "baseline_mean": base_stats["mean"],
                "baseline_big_up_pct": base_stats["big_up_freq"],
                "edge_mean": edge_mean,
                "edge_big_up_pct": edge_big_up,
            })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    result = run_walkforward(SYMBOL)
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(result.to_string(index=False))
    result.to_csv("h1b_walkforward_result.csv", index=False)
