"""
Бэктест гипотезы H1 (см. HYPOTHESES.md): экстремальный funding rate ->
последующее движение цены против перегруженной стороны.

Это ПЕРВЫЙ, разведочный прогон на всей истории целиком (не walk-forward
из PLAN.md) - чтобы понять, есть ли вообще что-то похожее на эффект,
прежде чем тратить время на более строгую walk-forward проверку. Если
здесь пусто - гипотезу можно закрыть как rejected сразу, не усложняя.

Методология (v2 - исправлена после разбора в чате, см. HYPOTHESES.md):
- Два сигнала считаются ОТДЕЛЬНО, не смешиваются в одну цифру:
    "перегружены лонгами"   (funding_percentile_90d > LONG_THRESHOLD)
    "перегружены шортами"   (funding_percentile_90d < SHORT_THRESHOLD)
- ВАЖНО: статистика считается СИММЕТРИЧНО, без предположения заранее,
  в какую сторону "должна" пойти цена. Первая версия скрипта считала
  только "движение в ожидаемую сторону" для каждой группы - из-за этого
  "крупных падений после перегруженных лонгов стало реже" выглядело как
  готовый вывод "значит, будет расти". На самом деле это могло означать
  и "будет расти", и "будет просто более гладкое падение" (то же
  направление, но без резких обвалов), и "волатильность вообще упала
  в обе стороны" - одна урезанная цифра не могла их отличить. Поэтому
  теперь для КАЖДОЙ группы считаем:
    - среднее и медиану сырого возврата (без разворота знака)
    - волатильность (стандартное отклонение) - отвечает на вопрос
      "стало ли вообще спокойнее", независимо от направления
    - частоту крупных движений ВВЕРХ и ВНИЗ отдельно (не только
      в "ожидаемую" по исходной гипотезе сторону)
- Сравниваем каждую из этих цифр с БАЗОВОЙ - тем же измерением по ВСЕМ
  дням истории (не только сигнальным)

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


def summarize(returns: pd.Series, big_move_pct: float) -> dict:
    """Полная СИММЕТРИЧНАЯ статистика - без предположения о том, в какую
    сторону "должно" двигаться. Считаем частоту крупных движений В ОБЕ
    стороны и волатильность (std) - иначе "крупных падений стало меньше"
    невозможно отличить от "стало меньше движений вообще" (ниже
    волатильность) или "стало больше движений вверх" (реальный разворот)."""
    returns = returns.dropna()
    if len(returns) == 0:
        return {"n": 0, "mean": None, "median": None, "std": None,
                "big_up_freq": None, "big_down_freq": None}

    return {
        "n": len(returns),
        "mean": returns.mean(),
        "median": returns.median(),
        "std": returns.std(),
        "big_up_freq": (returns >= big_move_pct).mean() * 100,
        "big_down_freq": (returns <= -big_move_pct).mean() * 100,
    }


def run_backtest(symbol: str) -> pd.DataFrame:
    df = load_data(symbol)
    long_crowded = df["funding_percentile_90d"] > LONG_THRESHOLD
    short_crowded = df["funding_percentile_90d"] < SHORT_THRESHOLD

    rows = []
    for horizon in HORIZONS:
        fwd = forward_return(df["close"], horizon)
        baseline = summarize(fwd, BIG_MOVE_PCT)

        for group_name, mask in [
            ("long_crowded", long_crowded),
            ("short_crowded", short_crowded),
        ]:
            s = summarize(fwd[mask], BIG_MOVE_PCT)

            def edge(key):
                if s[key] is None or baseline[key] is None:
                    return None
                return s[key] - baseline[key]

            rows.append({
                "horizon_days": horizon,
                "group": group_name,
                "n_signals": s["n"],
                "mean_return": s["mean"],
                "median_return": s["median"],
                "volatility_std": s["std"],
                "big_up_freq_pct": s["big_up_freq"],
                "big_down_freq_pct": s["big_down_freq"],
                "baseline_mean": baseline["mean"],
                "baseline_volatility_std": baseline["std"],
                "baseline_big_up_freq_pct": baseline["big_up_freq"],
                "baseline_big_down_freq_pct": baseline["big_down_freq"],
                "edge_mean": edge("mean"),
                "edge_volatility_std": edge("std"),
                "edge_big_up_freq_pct": edge("big_up_freq"),
                "edge_big_down_freq_pct": edge("big_down_freq"),
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
