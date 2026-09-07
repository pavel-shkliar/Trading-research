"""
H7: скорость изменения funding rate, а не только его уровень.

Идея: "перегружены шортами" (funding_percentile_90d < 0.05) может
случиться двумя разными путями:
- РЕЗКИЙ РАЗВОРОТ: ещё 14 дней назад рынок не был перегружен, а сейчас
  уже да - быстрая капитуляция шортов в панике
- ХРОНИЧЕСКОЕ СОСТОЯНИЕ: уже был перегружен 14 дней назад и остаётся
  таким же - вялый, затянувшийся пессимизм, не резкое событие

Гипотеза: резкий разворот - более сильный сигнал (паническая капитуляция
исчерпывает продавцов быстрее), чем хроническое состояние.

Горизонт 60 дней (якорный для H6b/H1b). Проверяем на BTC и ETH.

Запуск:
    python backtest_h7_funding_velocity.py
"""

import pandas as pd

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return, summarize

SHORT_THRESHOLD = 0.05
LOOKBACK = 14
HORIZON = 60
SYMBOLS = ["BTCUSDT", "ETHUSDT"]


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


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)

    for symbol in SYMBOLS:
        df = load_data(symbol)
        short_crowded_now = df["funding_percentile_90d"] < SHORT_THRESHOLD
        short_crowded_before = short_crowded_now.shift(LOOKBACK).fillna(False).astype(bool)

        sudden_flip = collapse_to_episodes(short_crowded_now & ~short_crowded_before)
        chronic = collapse_to_episodes(short_crowded_now & short_crowded_before)

        fwd = forward_return(df["close"], HORIZON)
        baseline = summarize(fwd)

        print(f"=== {symbol} (горизонт {HORIZON} дней) ===")
        for label, mask in [("Резкий разворот (не был перегружен 14д назад)", sudden_flip),
                             ("Хроническое состояние (был перегружен и 14д назад)", chronic)]:
            s = summarize(fwd[mask])
            if s["mean"] is None:
                print(f"  {label}: недостаточно данных")
                continue
            edge = s["mean"] - baseline["mean"]
            print(f"  {label}: n={s['n']}, доходность={s['mean']:.2f}%, база={baseline['mean']:.2f}%, эдж={edge:.2f}")
        print()
