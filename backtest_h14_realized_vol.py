"""
H14: низкая РЕАЛИЗОВАННАЯ волатильность (не подразумеваемая DVOL)
-> недоперформанс, та же механика что H6b, но доступна для ВСЕХ монет
(не только BTC/ETH, у которых есть DVOL от Deribit).

Реализованная волатильность = скользящее стандартное отклонение дневных
доходностей за 90 дней - считается прямо из цены, никаких дополнительных
данных не нужно. Идея та же: аномально спокойный рынок (по факту цены,
не по опционам) может означать недооценку риска, а не устойчивое затишье.

Горизонт 60 дней (якорь). Монеты с историей < 400 дней исключены (как
и в H1b multi-symbol). Тестируем И по каждой монете, И объединённым пулом.

Запуск:
    python backtest_h14_realized_vol.py
"""

import numpy as np
import pandas as pd
from scipy import stats

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return, summarize

VOL_WINDOW = 90
VOL_LOW = 0.05
HORIZON = 60
MIN_HISTORY_DAYS = 400

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "ZECUSDT", "SOLUSDT", "XRPUSDT",
    "HYPEUSDT", "DOGEUSDT", "ARBUSDT", "BNBUSDT",
    "RAYSOLUSDT", "SUIUSDT", "NEARUSDT", "TAOUSDT", "LINKUSDT",
    "WLDUSDT", "UNIUSDT", "PUMPUSDT", "ADAUSDT", "LTCUSDT", "AVAXUSDT",
]


def load_data(symbol: str) -> pd.DataFrame:
    df = read_df(
        "SELECT open_time AS date, close FROM candles WHERE symbol = %(symbol)s ORDER BY open_time",
        params={"symbol": symbol},
    )
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)

    per_symbol_rows = []
    all_excess_returns = []

    for symbol in SYMBOLS:
        df = load_data(symbol)
        if len(df) < MIN_HISTORY_DAYS:
            continue

        daily_return = df["close"].pct_change() * 100
        realized_vol = daily_return.rolling(VOL_WINDOW).std()
        vol_pct = realized_vol.rolling(VOL_WINDOW).apply(lambda x: x.rank(pct=True).iloc[-1], raw=False)

        low_vol = collapse_to_episodes(vol_pct < VOL_LOW)
        fwd = forward_return(df["close"], HORIZON)

        signal_stats = summarize(fwd[low_vol])
        baseline_stats = summarize(fwd)
        if signal_stats["mean"] is None:
            continue

        edge = signal_stats["mean"] - baseline_stats["mean"]
        episode_returns = fwd[low_vol].dropna()
        excess = (episode_returns - baseline_stats["mean"]).tolist()
        all_excess_returns.extend(excess)

        per_symbol_rows.append({
            "symbol": symbol, "n_episodes": signal_stats["n"],
            "signal_mean": signal_stats["mean"], "baseline_mean": baseline_stats["mean"], "edge": edge,
        })

    result = pd.DataFrame(per_symbol_rows).sort_values("edge")
    print(result.to_string(index=False))

    all_excess = np.array(all_excess_returns)
    n_total = len(all_excess)
    mean_excess = all_excess.mean()
    se = all_excess.std() / np.sqrt(n_total)
    ci_low, ci_high = mean_excess - 1.96 * se, mean_excess + 1.96 * se
    t_stat, p_value = stats.ttest_1samp(all_excess, 0)

    print(f"\n=== Объединённый пул ===")
    print(f"Всего эпизодов: {n_total}")
    print(f"Средняя избыточная доходность: {mean_excess:.2f}%")
    print(f"95% ДИ: [{ci_low:.2f}%, {ci_high:.2f}%]")
    print(f"t-test против нуля: t={t_stat:.2f}, p={p_value:.4f}")
