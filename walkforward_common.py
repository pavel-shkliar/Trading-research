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
    периода - по ВСЕМ дням этого периода, не только сигнальным."""
    rows = []
    for horizon in horizons:
        fwd = forward_return(df["close"], horizon)

        for start, end, label in PERIODS:
            period_mask = (df["date"] >= pd.Timestamp(start, tz="UTC")) & (df["date"] < pd.Timestamp(end, tz="UTC"))

            sig_stats = summarize(fwd[period_mask & signal_mask])
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
