"""
Углубление в механику H6b: что именно происходит с ценой день за днём
после сигнала (DVOL-самодовольство), а не только итоговая точка на
60-й день.

Отвечает на вопросы:
- Недоперформанс нарастает постепенно или происходит резким рывком?
- В какой момент внутри 60-дневного окна разница с базой самая большая?
- Насколько глубокая просадка случается ВНУТРИ окна (не только в конце) -
  проверка идеи "затишье перед бурей" (резкий обвал), а не "медленное
  сползание"

Метод: для каждого дня считаем не одну доходность (через фиксированный
горизонт), а ВЕСЬ путь - доходность через 1, 2, 3, ..., 60 дней вперёд.
Усредняем эти пути отдельно для сигнальных эпизодов и для базы (всех
дней) - получаем две кривые для сравнения.

Также считаем "худшую точку" внутри окна (максимальную просадку от
дня сигнала за 60 дней) - отдельно от финальной доходности на 60-й день.

Запуск:
    python backtest_h6b_mechanism.py
"""

import numpy as np
import pandas as pd

from db import read_df
from walkforward_common import collapse_to_episodes

DVOL_LOW = 0.05
MAX_HORIZON = 60
CHECKPOINTS = [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60]
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
    df = df[df["dvol_percentile_90d"].notna()].reset_index(drop=True)
    return df


def build_return_matrix(close: pd.Series, max_horizon: int) -> np.ndarray:
    """Строит матрицу [день, горизонт] - доходность (%) от каждого дня
    через 1, 2, ..., max_horizon дней вперёд. NaN там, где будущего ещё
    нет (конец истории)."""
    n = len(close)
    matrix = np.full((n, max_horizon), np.nan)
    close_arr = close.values
    for h in range(1, max_horizon + 1):
        shifted = np.roll(close_arr, -h)
        ret = (shifted - close_arr) / close_arr * 100
        ret[n - h:] = np.nan  # конец ряда - там "будущее" на самом деле начало ряда из-за roll
        matrix[:, h - 1] = ret
    return matrix


def analyze(symbol: str) -> pd.DataFrame:
    df = load_data(symbol)
    episode_mask = collapse_to_episodes(df["dvol_percentile_90d"] < DVOL_LOW).values

    matrix = build_return_matrix(df["close"], MAX_HORIZON)

    signal_matrix = matrix[episode_mask]
    baseline_matrix = matrix

    # Средняя траектория в каждой контрольной точке
    rows = []
    for cp in CHECKPOINTS:
        signal_vals = signal_matrix[:, cp - 1]
        baseline_vals = baseline_matrix[:, cp - 1]
        rows.append({
            "day": cp,
            "signal_avg_return": np.nanmean(signal_vals),
            "baseline_avg_return": np.nanmean(baseline_vals),
        })

    # Худшая точка внутри 60-дневного окна (максимальная просадка от дня сигнала)
    signal_worst_point = np.nanmin(signal_matrix, axis=1)
    baseline_worst_point = np.nanmin(baseline_matrix, axis=1)

    result = pd.DataFrame(rows)
    result["edge"] = result["signal_avg_return"] - result["baseline_avg_return"]

    print(f"\n=== {symbol} ===")
    print(result.to_string(index=False))
    print(f"Средняя ХУДШАЯ точка за 60 дней (просадка от старта):")
    print(f"  сигнальные эпизоды: {np.nanmean(signal_worst_point):.2f}%  (n={(~np.isnan(signal_worst_point)).sum()})")
    print(f"  база (все дни):      {np.nanmean(baseline_worst_point):.2f}%")

    return result


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    for symbol in SYMBOLS:
        analyze(symbol)
