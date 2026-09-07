"""
Общие функции для walk-forward проверок (используется backtest_h1b_walkforward.py
и backtest_h1c_walkforward.py) - чтобы не дублировать одну и ту же логику
разбивки на периоды и расчёта статистики для каждой новой гипотезы.
"""

import pandas as pd

from db import read_df

BIG_MOVE_PCT = 5.0

# Периоды по годам - захватывают разные известные режимы рынка BTC.
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


def collapse_to_episodes(mask: pd.Series) -> pd.Series:
    """Возвращает булеву маску той же длины, где True стоит только в ПЕРВЫЙ
    день каждого непрерывного эпизода сигнала - соседние дни одного и того
    же стресса схлопываются в одно событие.

    Зачем (обсуждали в чате): 90-дневные окна доходности для двух соседних
    дней одного эпизода почти целиком пересекаются (отличаются на 1-2 дня
    из 90) - это физически одно и то же движение цены, посчитанное
    несколько раз. Без схлопывания n искусственно завышается, доверительные
    интервалы/p-value становятся обманчиво "увереннее", чем есть на самом
    деле. Требует, чтобы mask.index был простым диапазоном 0..N-1
    (последовательные дни без пропусков) - иначе "соседние по индексу"
    не будет значить "соседние по дате"."""
    idx = pd.Series(mask.index[mask])
    if len(idx) == 0:
        return mask & False

    gaps = idx.diff()
    is_new_episode = (gaps != 1) | gaps.isna()
    first_of_episode = idx[is_new_episode.values]

    result = pd.Series(False, index=mask.index)
    result.loc[first_of_episode] = True
    return result


def summarize(returns: pd.Series, big_move_pct: float = BIG_MOVE_PCT) -> dict:
    returns = returns.dropna()
    if len(returns) == 0:
        return {"n": 0, "mean": None, "median": None, "big_up_freq": None}
    return {
        "n": len(returns),
        "mean": returns.mean(),
        "median": returns.median(),
        "big_up_freq": (returns >= big_move_pct).mean() * 100,
    }


def run_walkforward(symbol: str, signal_mask: pd.Series, horizons: list, df: pd.DataFrame) -> pd.DataFrame:
    """signal_mask - булева серия той же длины и с тем же индексом, что df,
    True в дни, когда сигнал сработал. База считается отдельно для каждого
    периода - по ВСЕМ дням этого периода, не только сигнальным.

    Сигнальные дни схлопываются в независимые эпизоды ГЛОБАЛЬНО (по всей
    истории, до разбивки на периоды) - иначе эпизод, случайно попавший на
    границу периодов, схлопнулся бы неправильно."""
    episode_mask = collapse_to_episodes(signal_mask)

    rows = []
    for horizon in horizons:
        fwd = forward_return(df["close"], horizon)

        for start, end, label in PERIODS:
            period_mask = (df["date"] >= pd.Timestamp(start, tz="UTC")) & (df["date"] < pd.Timestamp(end, tz="UTC"))

            sig_stats = summarize(fwd[period_mask & episode_mask])
            base_stats = summarize(fwd[period_mask])

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
