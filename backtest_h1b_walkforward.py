"""
Walk-forward проверка H1b (см. HYPOTHESES.md): перегруженные шорты -> рост.

Логика разбивки на периоды и расчёта статистики - в walkforward_common.py
(общий код для H1b и H1c, чтобы не дублировать).

Запуск:
    python backtest_h1b_walkforward.py
"""

import pandas as pd

from walkforward_common import load_data, run_walkforward

SYMBOL = "BTCUSDT"
SHORT_THRESHOLD = 0.05
HORIZONS = [30, 90]


if __name__ == "__main__":
    df = load_data(SYMBOL)
    short_crowded = df["funding_percentile_90d"] < SHORT_THRESHOLD

    result = run_walkforward(SYMBOL, short_crowded, HORIZONS, df)

    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(result.to_string(index=False))
    result.to_csv("h1b_walkforward_result.csv", index=False)
