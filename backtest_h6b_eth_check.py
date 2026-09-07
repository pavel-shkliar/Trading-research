"""
Проверка H6b на ETH - единственной другой монете, для которой Deribit
вообще публикует DVOL (кроме BTC). Не полноценный walk-forward по всем
периодам (мало данных на одну монету), а быстрая проверка: держится ли
направление и порядок величины эффекта на втором активе.

Горизонт 60 дней - тот же, где H6b показала лучший результат на BTC.

Запуск:
    python backtest_h6b_eth_check.py
"""

import numpy as np
from scipy import stats

from db import read_df
from walkforward_common import collapse_to_episodes, forward_return

DVOL_LOW = 0.05
HORIZON = 60


def load_data(symbol: str):
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
    return df[df["dvol_percentile_90d"].notna()].reset_index(drop=True)


def check(symbol: str):
    df = load_data(symbol)
    dvol_low = df["dvol_percentile_90d"] < DVOL_LOW
    episode_mask = collapse_to_episodes(dvol_low)

    fwd = forward_return(df["close"], HORIZON)
    episode_returns = fwd[episode_mask].dropna()
    baseline_returns = fwd.dropna()

    n = len(episode_returns)
    mean = episode_returns.mean()
    baseline_mean = baseline_returns.mean()
    edge = mean - baseline_mean

    if n < 5:
        print(f"{symbol}: n={n} эпизодов - слишком мало для теста значимости")
        return

    t_stat, p_ttest = stats.ttest_ind(episode_returns, baseline_returns, equal_var=False)
    u_stat, p_mw = stats.mannwhitneyu(episode_returns, baseline_returns, alternative="less")

    print(f"{symbol}: n={n}, сигнал={mean:.2f}%, база={baseline_mean:.2f}%, эдж={edge:.2f}")
    print(f"  t-test p={p_ttest:.4f}, Mann-Whitney p={p_mw:.4f}")


if __name__ == "__main__":
    check("BTCUSDT")
    check("ETHUSDT")
