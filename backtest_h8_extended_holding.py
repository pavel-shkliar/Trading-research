"""
Расширение H8: не только "открылся и закрылся в тот же день", а полная
сетка "день входа (открытие) x срок удержания в днях (1-7) -> закрытие".
Например: "открылся в среду утром, закрылся в понедельник вечером" =
вход в среду, удержание 6 дней (среда, четверг, пятница, суббота,
воскресенье, понедельник).

ОСОБАЯ ОСТОРОЖНОСТЬ: это 7 дней входа x 7 сроков = 49 комбинаций за
раз - в разы больше "попыток", чем даже исходный скан 7 дней недели.
Чем больше комбинаций перебираем, тем выше шанс найти что-то "красивое"
просто по случайности (см. заметку про множественные сравнения). Лучшую
комбинацию логика найдёт всегда, даже если реального эффекта нет нигде -
поэтому результат тут смотрим только как "куда копать дальше", не как
готовый вывод.

Запуск:
    python backtest_h8_extended_holding.py
"""

import numpy as np
import pandas as pd

from db import read_df

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
WEEKDAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
MAX_HOLD_DAYS = 7


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        "SELECT open_time AS date, open, close FROM candles WHERE symbol = %(symbol)s ORDER BY open_time",
        params={"symbol": symbol},
    )
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["weekday"] = df["date"].dt.weekday
    return df


def build_grid(df: pd.DataFrame) -> pd.DataFrame:
    open_arr = df["open"].values
    close_arr = df["close"].values
    n = len(df)

    rows = []
    for hold in range(1, MAX_HOLD_DAYS + 1):
        # доходность входа в день t (open) с выходом в день t+hold-1 (close)
        exit_idx = np.arange(n) + hold - 1
        valid = exit_idx < n
        ret = np.full(n, np.nan)
        ret[valid] = (close_arr[exit_idx[valid]] - open_arr[valid]) / open_arr[valid] * 100

        temp = pd.DataFrame({"weekday": df["weekday"], "ret": ret})
        avg_by_weekday = temp.groupby("weekday")["ret"].mean()
        for wd in range(7):
            rows.append({
                "entry_weekday": WEEKDAY_NAMES[wd],
                "hold_days": hold,
                "avg_return": avg_by_weekday.get(wd, np.nan),
            })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")

    for symbol in SYMBOLS:
        df = load_data(symbol)
        grid = build_grid(df)
        pivot = grid.pivot(index="entry_weekday", columns="hold_days", values="avg_return")
        pivot = pivot.reindex(WEEKDAY_NAMES)

        print(f"=== {symbol}: средняя доходность (%) по (день входа x срок удержания) ===")
        print(pivot.to_string())

        best = grid.loc[grid["avg_return"].idxmax()]
        worst = grid.loc[grid["avg_return"].idxmin()]
        print(f"Лучшая комбинация: вход {best['entry_weekday']}, держать {int(best['hold_days'])} дн. -> {best['avg_return']:.2f}%")
        print(f"Худшая комбинация: вход {worst['entry_weekday']}, держать {int(worst['hold_days'])} дн. -> {worst['avg_return']:.2f}%")
        print()
