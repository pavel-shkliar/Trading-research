"""
Computes indicators from already-downloaded data and stores them in the
indicators table:

- RSI(14), Bollinger Bands(20, 2 std), rolling VWAP(20) - classic
  price/volume indicators, kept as building blocks for combinations
  rather than expected to carry an edge on their own.
- 90-day rolling percentile of funding rate - NOT an absolute threshold,
  but how extreme the current value is relative to its own recent
  history (self-relative normalization, comparable across assets).
- Price/Open Interest divergence - the four sign combinations of price
  change vs OI change. Only available where OI history exists.

Percentile computation uses a TRAILING window only (never the full
history at once) to avoid look-ahead bias: a percentile computed against
the entire dataset would leak future values into past dates, producing
a backtest that looks good but wouldn't reproduce in live trading.

Usage:
    python compute_indicators.py
"""

import math

import pandas as pd

from db import read_df, upsert_rows

SYMBOL = "BTCUSDT"

RSI_PERIOD = 14
BB_PERIOD = 20
BB_STD = 2
VWAP_PERIOD = 20
FUNDING_PERCENTILE_WINDOW = 90


def compute_rsi(close: pd.Series, period: int) -> pd.Series:
    """Wilder's RSI (exponential smoothing with alpha = 1/period)."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_bollinger(close: pd.Series, period: int, num_std: float):
    mid = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return upper, mid, lower


def compute_vwap(close: pd.Series, volume: pd.Series, period: int) -> pd.Series:
    """Classic VWAP is intraday, tick-by-tick. With only daily candles we
    use a rolling adaptation instead: volume-weighted average price over
    the trailing `period` days."""
    return (close * volume).rolling(period).sum() / volume.rolling(period).sum()


def compute_rolling_percentile(series: pd.Series, window: int) -> pd.Series:
    """Percentile of each value relative to the PRECEDING `window`
    observations only - no look-ahead. Shared by funding rate and DVOL."""
    return series.rolling(window).apply(lambda x: x.rank(pct=True).iloc[-1], raw=False)


def classify_price_oi_divergence(price_change: float, oi_change: float) -> str:
    if pd.isna(price_change) or pd.isna(oi_change):
        return None
    if price_change > 0 and oi_change > 0:
        return "new_longs"
    if price_change > 0 and oi_change <= 0:
        return "short_covering"
    if price_change <= 0 and oi_change > 0:
        return "new_shorts"
    return "long_liquidation"


def build_indicators(symbol: str) -> pd.DataFrame:
    candles = read_df(
        "SELECT open_time AS date, close, volume FROM candles WHERE symbol = %(symbol)s ORDER BY open_time",
        params={"symbol": symbol},
    )
    candles["date"] = pd.to_datetime(candles["date"], utc=True).dt.normalize()

    result = pd.DataFrame({"date": candles["date"]})
    result["rsi_14"] = compute_rsi(candles["close"], RSI_PERIOD)
    result["bb_upper"], result["bb_mid"], result["bb_lower"] = compute_bollinger(
        candles["close"], BB_PERIOD, BB_STD
    )
    result["vwap_20"] = compute_vwap(candles["close"], candles["volume"], VWAP_PERIOD)

    funding = read_df(
        "SELECT funding_time, funding_rate FROM funding_rate WHERE symbol = %(symbol)s ORDER BY funding_time",
        params={"symbol": symbol},
    )
    funding["date"] = pd.to_datetime(funding["funding_time"], utc=True).dt.normalize()
    funding_daily = funding.groupby("date")["funding_rate"].mean()
    funding_percentile = compute_rolling_percentile(funding_daily, FUNDING_PERCENTILE_WINDOW)

    result = result.merge(funding_daily.rename("funding_rate_daily_avg"), on="date", how="left")
    result = result.merge(funding_percentile.rename("funding_percentile_90d"), on="date", how="left")

    # DVOL exists only from 2021-03-24 onward, and only for BTC and ETH on
    # Deribit - NULLs elsewhere are expected, not a bug.
    dvol_currency = symbol.replace("USDT", "")
    dvol = read_df(
        "SELECT ts, close FROM dvol WHERE currency = %(currency)s ORDER BY ts",
        params={"currency": dvol_currency},
    )
    if not dvol.empty:
        dvol["date"] = pd.to_datetime(dvol["ts"], utc=True).dt.normalize()
        dvol_daily = dvol.groupby("date")["close"].mean()
        dvol_percentile = compute_rolling_percentile(dvol_daily, FUNDING_PERCENTILE_WINDOW)

        result = result.merge(dvol_daily.rename("dvol_close"), on="date", how="left")
        result = result.merge(dvol_percentile.rename("dvol_percentile_90d"), on="date", how="left")
    else:
        result["dvol_close"] = None
        result["dvol_percentile_90d"] = None

    oi = read_df(
        "SELECT ts AS date, sum_open_interest FROM open_interest WHERE symbol = %(symbol)s ORDER BY ts",
        params={"symbol": symbol},
    )
    if not oi.empty:
        oi["date"] = pd.to_datetime(oi["date"], utc=True).dt.normalize()
        oi["oi_change_pct"] = oi["sum_open_interest"].pct_change() * 100

        price_by_date = candles.set_index(candles["date"])["close"]
        oi = oi.merge(
            price_by_date.pct_change().rename("price_change_pct") * 100,
            left_on="date", right_index=True, how="left",
        )
        oi["price_oi_divergence"] = [
            classify_price_oi_divergence(p, o)
            for p, o in zip(oi["price_change_pct"], oi["oi_change_pct"])
        ]

        result = result.merge(oi[["date", "oi_change_pct", "price_oi_divergence"]], on="date", how="left")
    else:
        result["oi_change_pct"] = None
        result["price_oi_divergence"] = None

    result.insert(0, "symbol", symbol)
    return result


def _nan_to_none(value):
    """pandas keeps a float64 column's gaps as NaN even when None is
    assigned - it silently coerces back. psycopg2 would then send that NaN
    to Postgres as the literal value 'NaN'::float8 (a valid float value
    there) rather than SQL NULL, breaking COUNT()/AVG() downstream. Convert
    at row-tuple assembly time, once pandas can no longer undo it."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def save_indicators(df: pd.DataFrame) -> int:
    columns = [
        "symbol", "date", "rsi_14", "bb_upper", "bb_mid", "bb_lower", "vwap_20",
        "funding_rate_daily_avg", "funding_percentile_90d",
        "dvol_close", "dvol_percentile_90d",
        "oi_change_pct", "price_oi_divergence",
    ]
    rows = [
        tuple(_nan_to_none(v) for v in row)
        for row in df[columns].itertuples(index=False, name=None)
    ]
    return upsert_rows("indicators", columns, rows, ["symbol", "date"])


if __name__ == "__main__":
    print(f"Computing indicators for {SYMBOL}...")
    df = build_indicators(SYMBOL)
    saved = save_indicators(df)
    print(f"Done: {saved} indicator rows processed ({df['date'].min().date()} - {df['date'].max().date()}).")
