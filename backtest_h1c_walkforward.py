"""
Walk-forward проверка H1c (новая гипотеза, предложена в чате):
перегруженные ЛОНГИ -> ПОКУПАТЬ (следовать за толпой, не идти против неё).

Причина появления: разведочный прогон на всей истории показал, что цена
после сигнала "перегружены лонгами" часто росла - но база (весь рынок
за то же время) тоже росла почти всегда, поэтому "положительная
доходность" сама по себе ничего не доказывает. Разница (эдж) на всей
истории была нестабильной - плюс на 5 горизонтах, минус на 2 (30 и 180
дней) - в отличие от H1b, где эдж был плюсовым на всех 7 горизонтах.

Проверяем той же процедурой walk-forward, что и H1b - иначе было бы
нечестно проверять одну гипотезу строго, а другую отбрасывать на глаз.

Запуск:
    python backtest_h1c_walkforward.py
"""

import pandas as pd

from walkforward_common import load_data, run_walkforward

SYMBOL = "BTCUSDT"
LONG_THRESHOLD = 0.95
HORIZONS = [30, 90]


if __name__ == "__main__":
    df = load_data(SYMBOL)
    long_crowded = df["funding_percentile_90d"] > LONG_THRESHOLD

    result = run_walkforward(SYMBOL, long_crowded, HORIZONS, df)

    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(result.to_string(index=False))
    result.to_csv("h1c_walkforward_result.csv", index=False)
