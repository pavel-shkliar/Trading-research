"""
H8: календарные эффекты - день недели и "внутридневная" (open->close)
vs "ночная" (вчерашний close -> сегодняшний open) доходность.

Совсем другое измерение, чем всё предыдущее (не деривативы, а время) -
проверка, есть ли системная разница по дням недели. Крипта торгуется
24/7, но объёмы/участники могут отличаться по дням (меньше институционных
трейдеров в выходные).

- "Внутридневная" доходность = (close - open) / open за ТОТ ЖЕ день
- "Ночная" доходность = (open сегодня - close вчера) / close вчера

Считаем среднюю доходность каждого типа отдельно по каждому дню недели,
на полной истории BTC и ETH.

Запуск:
    python backtest_h8_calendar.py
"""

import pandas as pd

from db import read_df

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
WEEKDAY_NAMES = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        "SELECT open_time AS date, open, close FROM candles WHERE symbol = %(symbol)s ORDER BY open_time",
        params={"symbol": symbol},
    )
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.3f}")

    for symbol in SYMBOLS:
        df = load_data(symbol)
        df["weekday"] = df["date"].dt.weekday  # 0=Понедельник
        df["intraday_return"] = (df["close"] - df["open"]) / df["open"] * 100
        df["overnight_return"] = (df["open"] - df["close"].shift(1)) / df["close"].shift(1) * 100

        grouped = df.groupby("weekday").agg(
            n=("intraday_return", "count"),
            intraday_mean=("intraday_return", "mean"),
            overnight_mean=("overnight_return", "mean"),
        )
        grouped.index = [WEEKDAY_NAMES[i] for i in grouped.index]

        print(f"=== {symbol} ===")
        print(grouped.to_string())
        print()
