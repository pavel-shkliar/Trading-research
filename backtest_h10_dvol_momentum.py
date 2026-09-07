"""
H10: уточнение H6b - DVOL-самодовольство ПОСЛЕ ралли vs БЕЗ
предшествующего ралли.

Идея: "самодовольство после ралли" может быть частично нормальной
реакцией (люди довольны прибылью, расслабились заслуженно). А вот
"самодовольство БЕЗ ралли" - более странная ситуация: почему рынок
спокоен, если цена даже не росла? Возможно, это более чистый признак
недооценки риска.

Разделяем по 90-дневной доходности ДО сигнала: положительная = "после
ралли", отрицательная/нулевая = "без ралли".

Горизонт 60 дней - якорный для H6b.

Запуск:
    python backtest_h10_dvol_momentum.py
"""

import pandas as pd

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return, summarize

DVOL_LOW = 0.05
TRAILING_WINDOW = 90
HORIZON = 60
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
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df[df["dvol_percentile_90d"].notna()].reset_index(drop=True)


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")

    for symbol in SYMBOLS:
        df = load_data(symbol)
        trailing_return = (df["close"] - df["close"].shift(TRAILING_WINDOW)) / df["close"].shift(TRAILING_WINDOW) * 100
        dvol_low = df["dvol_percentile_90d"] < DVOL_LOW

        after_rally = collapse_to_episodes(dvol_low & (trailing_return > 0))
        without_rally = collapse_to_episodes(dvol_low & (trailing_return <= 0))

        fwd = forward_return(df["close"], HORIZON)
        baseline = summarize(fwd)

        print(f"=== {symbol} (горизонт {HORIZON} дней) ===")
        for label, mask in [
            ("После ралли (90д доходность > 0)", after_rally),
            ("Без ралли (90д доходность <= 0)", without_rally),
        ]:
            s = summarize(fwd[mask])
            if s["mean"] is None:
                print(f"  {label}: недостаточно данных")
                continue
            edge = s["mean"] - baseline["mean"]
            print(f"  {label}: n={s['n']}, доходность={s['mean']:.2f}%, база={baseline['mean']:.2f}%, эдж={edge:.2f}")
        print()
