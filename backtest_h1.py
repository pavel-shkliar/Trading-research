"""
Бэктест гипотезы H1 (см. HYPOTHESES.md): экстремальный funding rate ->
последующее движение цены против перегруженной стороны.

Это ПЕРВЫЙ, разведочный прогон на всей истории целиком (не walk-forward
из PLAN.md) - чтобы понять, есть ли вообще что-то похожее на эффект,
прежде чем тратить время на более строгую walk-forward проверку. Если
здесь пусто - гипотезу можно закрыть как rejected сразу, не усложняя.

Методология (обсуждали в чате, коротко):
- Два сигнала считаются ОТДЕЛЬНО, не смешиваются в одну цифру:
    "перегружены лонгами"  (funding_percentile_90d > LONG_THRESHOLD)
      -> ждём ПАДЕНИЯ цены
    "перегружены шортами"  (funding_percentile_90d < SHORT_THRESHOLD)
      -> ждём РОСТА цены
- Для каждого сигнального дня и каждого горизонта N считаем ФАКТИЧЕСКУЮ
  (не бинарную верно/неверно) доходность цены через N дней
- Сравниваем с БАЗОВОЙ доходностью - тем же самым измерением, но по ВСЕМ
  дням истории (не только сигнальным). Отвечает на вопрос "а может, рынок
  просто в среднем растёт/падает, и сигнал тут ни при чём?"
- Считаем и среднее, и медиану (среднее может быть искажено редкими
  крупными движениями - медиана показывает "типичный" случай, но не
  выбрасывает крупные дни из данных - они остаются в выборке)
- Отдельно считаем частоту КРУПНЫХ движений (>= BIG_MOVE_PCT) именно
  в ожидаемую сторону - если гипотеза про сквизы верна, сигнал должен
  предсказывать учащение именно крупных движений, а не только небольшой
  перевес в среднем

ВАЖНАЯ ОГОВОРКА (честно, для протокола): funding rate часто остаётся
экстремальным несколько дней подряд - соседние сигнальные дни не совсем
независимы друг от друга, а их окна (особенно на 90/180 дней) сильно
пересекаются. Для разведочного прогона это допустимо, но при переходе
к walk-forward-подтверждению эффекта эту зависимость нужно будет учесть
отдельно.
"""

import pandas as pd

from db import read_df

SYMBOL = "BTCUSDT"
LONG_THRESHOLD = 0.95
SHORT_THRESHOLD = 0.05
BIG_MOVE_PCT = 5.0
HORIZONS = [3, 7, 14, 30, 60, 90, 180]


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
    """Доходность цены через `horizon` дней вперёд от каждой даты, в %."""
    return (close.shift(-horizon) - close) / close * 100


def summarize(returns: pd.Series, direction: str, big_move_pct: float) -> dict:
    """direction: 'down' - ждём падения (успех = return <= -big_move_pct),
    'up' - ждём роста (успех = return >= +big_move_pct)."""
    returns = returns.dropna()
    if len(returns) == 0:
        return {"n": 0, "mean": None, "median": None, "big_move_freq": None}

    if direction == "down":
        big_move_freq = (returns <= -big_move_pct).mean() * 100
    else:
        big_move_freq = (returns >= big_move_pct).mean() * 100

    return {
        "n": len(returns),
        "mean": returns.mean(),
        "median": returns.median(),
        "big_move_freq": big_move_freq,
    }


def run_backtest(symbol: str) -> pd.DataFrame:
    df = load_data(symbol)
    long_crowded = df["funding_percentile_90d"] > LONG_THRESHOLD
    short_crowded = df["funding_percentile_90d"] < SHORT_THRESHOLD

    rows = []
    for horizon in HORIZONS:
        fwd = forward_return(df["close"], horizon)

        for group_name, mask, direction in [
            ("long_crowded (ждём падения)", long_crowded, "down"),
            ("short_crowded (ждём роста)", short_crowded, "up"),
        ]:
            signal_stats = summarize(fwd[mask], direction, BIG_MOVE_PCT)
            baseline_stats = summarize(fwd, direction, BIG_MOVE_PCT)

            # "Эдж" - разница сигнала с базой, знак развёрнут так, чтобы
            # положительное число = "гипотеза подтверждается сильнее базы"
            if signal_stats["mean"] is not None and baseline_stats["mean"] is not None:
                sign = -1 if direction == "down" else 1
                edge_mean = sign * (signal_stats["mean"] - baseline_stats["mean"])
                edge_median = sign * (signal_stats["median"] - baseline_stats["median"])
                edge_big_move_freq = signal_stats["big_move_freq"] - baseline_stats["big_move_freq"]
            else:
                edge_mean = edge_median = edge_big_move_freq = None

            rows.append({
                "horizon_days": horizon,
                "group": group_name,
                "n_signals": signal_stats["n"],
                "mean_return": signal_stats["mean"],
                "median_return": signal_stats["median"],
                "big_move_freq_pct": signal_stats["big_move_freq"],
                "baseline_mean": baseline_stats["mean"],
                "baseline_median": baseline_stats["median"],
                "baseline_big_move_freq_pct": baseline_stats["big_move_freq"],
                "edge_mean": edge_mean,
                "edge_median": edge_median,
                "edge_big_move_freq_pct": edge_big_move_freq,
            })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    result = run_backtest(SYMBOL)
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(result.to_string(index=False))
    result.to_csv("h1_backtest_result.csv", index=False)
    print("\n(сохранено также в h1_backtest_result.csv для удобства просмотра - не в git, воспроизводимо запуском скрипта)")
