"""
H11: высокий/низкий объём торгов -> отличается ли доходность?

Идея (независимая от дня недели): даже в режиме 24/7 объём торгов
колеблется - проверяем, предсказывает ли САМ объём (не день недели)
что-то про доходность следующего дня.

Делим дни на квартили по объёму (относительно скользящего окна 90 дней -
та же логика нормализации, что и для funding rate/DVOL, чтобы не путать
"объём вырос со временем в принципе" с "сегодня объём необычно высокий
для последних 90 дней").

Смотрим доходность СЛЕДУЮЩЕГО дня (не того же дня - иначе просто измеряем
корреляцию объёма и волатильности внутри одного дня, что тривиально).

Запуск:
    python backtest_h11_volume.py
"""

import pandas as pd

from db import read_df

VOLUME_WINDOW = 90
SYMBOLS = ["BTCUSDT", "ETHUSDT"]


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        "SELECT open_time AS date, close, volume FROM candles WHERE symbol = %(symbol)s ORDER BY open_time",
        params={"symbol": symbol},
    )
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.3f}")

    for symbol in SYMBOLS:
        df = load_data(symbol)

        volume_percentile = df["volume"].rolling(VOLUME_WINDOW).apply(
            lambda x: x.rank(pct=True).iloc[-1], raw=False
        )
        next_day_return = (df["close"].shift(-1) - df["close"]) / df["close"] * 100

        high_volume = volume_percentile > 0.90
        low_volume = volume_percentile < 0.10
        normal_volume = (volume_percentile >= 0.10) & (volume_percentile <= 0.90)

        print(f"=== {symbol} (доходность СЛЕДУЮЩЕГО дня после объёма) ===")
        for label, mask in [("Высокий объём (>90 перцентиль)", high_volume),
                             ("Обычный объём", normal_volume),
                             ("Низкий объём (<10 перцентиль)", low_volume)]:
            vals = next_day_return[mask].dropna()
            print(f"  {label}: n={len(vals)}, среднее={vals.mean():.3f}%, медиана={vals.median():.3f}%")
        print()
