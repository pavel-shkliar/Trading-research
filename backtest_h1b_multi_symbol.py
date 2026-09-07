"""
H1b на нескольких монетах (не только BTC) - проверка идеи из чата: если
закономерность реальна (механика деривативов), она должна проявляться
не только на одном активе. Используем НОРМАЛИЗОВАННЫЙ порог
(funding_percentile_90d - свой для каждой монеты, не абсолютное число) -
это и позволяет сравнивать/объединять разные монеты (см. обсуждение
в PLAN.md/чате про нормализацию вместо абсолютных порогов).

Монеты с историей короче ~400 дней исключены - недостаточно данных для
осмысленного расчёта (см. download_universe.py - MARSCOINUSDT всего
7 дней, бесполезно).

Горизонт 90 дней - наш единственный walk-forward-подтверждённый горизонт
для H1b.

Для каждой монеты - своя база (свой рынок, свои условия). Для объединённого
результата - "избыточная доходность" (episode_return - своя база монеты)
собирается со всех монет в один общий пул, чтобы увеличить выборку, не
смешивая монеты с разным общим уровнем доходности напрямую.

Запуск:
    python backtest_h1b_multi_symbol.py
"""

import numpy as np
import pandas as pd
from scipy import stats

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return, summarize

SHORT_THRESHOLD = 0.05
HORIZON = 90
MIN_HISTORY_DAYS = 400

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "ZECUSDT", "SOLUSDT", "XRPUSDT",
    "HYPEUSDT", "DOGEUSDT", "ARBUSDT", "SNDKUSDT", "BNBUSDT",
    "RAYSOLUSDT", "SUIUSDT", "NEARUSDT", "TAOUSDT", "LINKUSDT",
    "WLDUSDT", "UNIUSDT", "PUMPUSDT", "BZUSDT", "MARSCOINUSDT",
]


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
    per_symbol_rows = []
    all_excess_returns = []

    for symbol in SYMBOLS:
        df = load_data(symbol)
        if len(df) < MIN_HISTORY_DAYS:
            print(f"{symbol}: пропущена, история {len(df)} дней < {MIN_HISTORY_DAYS}")
            continue

        short_crowded = collapse_to_episodes(df["funding_percentile_90d"] < SHORT_THRESHOLD)
        fwd = forward_return(df["close"], HORIZON)

        signal_stats = summarize(fwd[short_crowded])
        baseline_stats = summarize(fwd)

        if signal_stats["mean"] is None or baseline_stats["mean"] is None:
            print(f"{symbol}: недостаточно сигнальных дней для горизонта {HORIZON}")
            continue

        edge_mean = signal_stats["mean"] - baseline_stats["mean"]

        # Избыточная доходность каждого эпизода этой монеты - для объединённого пула
        episode_returns = fwd[short_crowded].dropna()
        excess = (episode_returns - baseline_stats["mean"]).tolist()
        all_excess_returns.extend(excess)

        per_symbol_rows.append({
            "symbol": symbol,
            "history_days": len(df),
            "n_episodes": signal_stats["n"],
            "signal_mean": signal_stats["mean"],
            "baseline_mean": baseline_stats["mean"],
            "edge_mean": edge_mean,
        })

    result = pd.DataFrame(per_symbol_rows).sort_values("edge_mean", ascending=False)
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    pd.set_option("display.width", 200)
    print(result.to_string(index=False))
    result.to_csv("h1b_multi_symbol_result.csv", index=False)

    print(f"\n=== Объединённый пул (все монеты вместе) ===")
    all_excess = np.array(all_excess_returns)
    n_total = len(all_excess)
    mean_excess = all_excess.mean()
    se = all_excess.std() / np.sqrt(n_total)
    ci_low, ci_high = mean_excess - 1.96 * se, mean_excess + 1.96 * se
    t_stat, p_value = stats.ttest_1samp(all_excess, 0)

    print(f"Всего эпизодов по всем монетам: {n_total}")
    print(f"Средняя избыточная доходность (сигнал минус своя база): {mean_excess:.2f}%")
    print(f"95% доверительный интервал: [{ci_low:.2f}%, {ci_high:.2f}%]")
    print(f"t-test против нуля: t={t_stat:.2f}, p-value={p_value:.4f}")
