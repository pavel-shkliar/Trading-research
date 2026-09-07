"""
Walk-forward проверка H8 (эффект среды) по годам - разведочный прогон
(backtest_h8_calendar.py) нашёл эффект по всей истории сразу, тут
проверяем устойчивость по разным рыночным периодам, как для остальных
гипотез.

Запуск:
    python backtest_h8_calendar_walkforward.py
"""

import pandas as pd

from db import read_df

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
PERIODS = [
    ("2019-09-08", "2021-01-01", "2019-2020"),
    ("2021-01-01", "2022-01-01", "2021"),
    ("2022-01-01", "2023-01-01", "2022"),
    ("2023-01-01", "2024-01-01", "2023"),
    ("2024-01-01", "2025-01-01", "2024"),
    ("2025-01-01", "2026-09-07", "2025-2026"),
]


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
        print(f"=== {symbol} ===")
        df = load_data(symbol)
        df["weekday"] = df["date"].dt.weekday
        df["intraday_return"] = (df["close"] - df["open"]) / df["open"] * 100

        for start, end, label in PERIODS:
            mask = (df["date"] >= pd.Timestamp(start, tz="UTC")) & (df["date"] < pd.Timestamp(end, tz="UTC"))
            period_df = df[mask]
            wed = period_df[period_df["weekday"] == 2]["intraday_return"].mean()
            other = period_df[period_df["weekday"] != 2]["intraday_return"].mean()
            print(f"  {label}: среда={wed:.3f}%, остальные={other:.3f}%, разница={wed - other:.3f}")
        print()
