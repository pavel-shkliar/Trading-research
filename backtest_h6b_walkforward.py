"""
Walk-forward проверка H6b: DVOL-самодовольство (percentile<0.05) ->
недоперформанс + учащение крупных падений ("затишье перед бурей").

DVOL существует только с 2021-03-24 (+90 дней на перцентиль = с
2021-06-21) - периоды 2019-2020 и часть 2021 года будут пустыми или
почти пустыми, это ожидаемо, не баг. База считается только по дням,
где DVOL вообще есть, для честного сравнения (см. проблему в H3, которую
уже решали похожим образом).

Горизонты 30/60/90 - там, где разведочный прогон показал наиболее
согласованный эффект. Прогоняем для BTC и ETH одновременно - DVOL
у Deribit есть только для этих двух монет, дальше расширять некуда.

Запуск:
    python backtest_h6b_walkforward.py
"""

import pandas as pd

from db import read_df
from walkforward_common import run_walkforward

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
DVOL_LOW = 0.05
HORIZONS = [30, 60, 90]


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
    return df


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)

    all_results = []
    for symbol in SYMBOLS:
        df = load_data(symbol)

        # Оставляем только дни, где DVOL вообще существует - иначе база
        # в ранних периодах (до 2021) включала бы дни без DVOL, что нечестно
        # сравнивать с сигнальными днями (у которых DVOL по определению есть).
        df = df[df["dvol_percentile_90d"].notna()].reset_index(drop=True)

        dvol_low = df["dvol_percentile_90d"] < DVOL_LOW
        result = run_walkforward(symbol, dvol_low, HORIZONS, df)
        result.insert(0, "symbol", symbol)

        print(f"=== {symbol} ===")
        print(result.to_string(index=False))
        print()
        all_results.append(result)

    combined = pd.concat(all_results, ignore_index=True)
    combined.to_csv("h6b_walkforward_result.csv", index=False)
