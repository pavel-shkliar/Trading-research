"""
H13: экстремальный базис (разница фьючерс/спот) -> схлопывание разрыва.

Свежий, но классический деривативный угол с настоящей экономической
причиной (в отличие от H8): базис = (цена фьючерса - цена спота) / цена
спота. В теории арбитраж должен держать эту разницу маленькой - если
фьючерс дороже спота намного (contango), выгодно продавать фьючерс
и покупать спот (cash-and-carry), что толкает базис обратно к нулю.

Гипотеза: экстремально высокий базис (фьючерс намного дороже спота,
percentile>0.95) -> ждём, что фьючерсная цена НЕДОперформит спот
впоследствии (базис схлопывается через отставание фьючерса, а не только
через рост спота).

Считаем через доходность ФЬЮЧЕРСА (то, чем мы торгуем) относительно
своей же истории - как и везде, база = все дни.

Горизонт 60 дней. Полная рутина: percentile 90д, эпизоды, walk-forward,
тесты значимости.

Запуск:
    python backtest_h13_basis.py
"""

import pandas as pd
from scipy import stats

from db import read_df
from walkforward_common import PERIODS, collapse_to_episodes, forward_return, summarize

BASIS_HIGH = 0.95
BASIS_LOW = 0.05
HORIZON = 60
SYMBOLS = ["BTCUSDT", "ETHUSDT"]


def load_data(symbol: str) -> pd.DataFrame:
    futures = read_df(
        "SELECT open_time AS date, close FROM candles WHERE symbol = %(s)s ORDER BY open_time",
        params={"s": symbol},
    )
    spot = read_df(
        "SELECT open_time AS date, close AS spot_close FROM spot_candles WHERE symbol = %(s)s ORDER BY open_time",
        params={"s": symbol},
    )
    futures["date"] = pd.to_datetime(futures["date"], utc=True)
    spot["date"] = pd.to_datetime(spot["date"], utc=True)

    df = futures.merge(spot, on="date").reset_index(drop=True)
    df["basis"] = (df["close"] - df["spot_close"]) / df["spot_close"] * 100
    df["basis_pct"] = df["basis"].rolling(90).apply(lambda x: x.rank(pct=True).iloc[-1], raw=False)
    return df


if __name__ == "__main__":
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")

    for symbol in SYMBOLS:
        df = load_data(symbol)
        high_basis = collapse_to_episodes(df["basis_pct"] > BASIS_HIGH)
        low_basis = collapse_to_episodes(df["basis_pct"] < BASIS_LOW)

        fwd = forward_return(df["close"], HORIZON)
        baseline = summarize(fwd)

        print(f"=== {symbol} (горизонт {HORIZON} дней) ===")
        for label, mask in [
            ("Базис высокий (фьючерс дорогой, ждём недоперформанса)", high_basis),
            ("Базис низкий (фьючерс дешёвый, ждём переперформанса)", low_basis),
        ]:
            s = summarize(fwd[mask])
            if s["mean"] is None or s["n"] < 5:
                print(f"  {label}: n={s['n']} - недостаточно данных")
                continue
            edge = s["mean"] - baseline["mean"]
            episode_returns = fwd[mask].dropna()
            t, p_ttest = stats.ttest_ind(episode_returns, fwd.dropna(), equal_var=False)
            print(f"  {label}: n={s['n']}, доходность={s['mean']:.2f}%, база={baseline['mean']:.2f}%, эдж={edge:.2f}, p={p_ttest:.4f}")

        print("  Walk-forward (базис высокий):")
        for start, end, label in PERIODS:
            mask = (df["date"] >= pd.Timestamp(start, tz="UTC")) & (df["date"] < pd.Timestamp(end, tz="UTC"))
            sig = fwd[mask & high_basis].dropna()
            base = fwd[mask].dropna()
            if len(sig) < 3:
                print(f"    {label}: n={len(sig)} - мало данных")
                continue
            print(f"    {label}: n={len(sig)}, доходность={sig.mean():.2f}%, база={base.mean():.2f}%, эдж={sig.mean()-base.mean():.2f}")
        print()
