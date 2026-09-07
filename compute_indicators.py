"""
Шаг 4 плана — считает индикаторы на основе уже скачанных данных
и сохраняет результат в таблицу indicators.

Что считаем и зачем (см. PLAN.md):
- RSI(14), Bollinger Bands(20, 2 std), rolling VWAP(20) — классика,
  считаем их не потому что сами по себе дадут эдж, а как строительные
  блоки для будущих комбинаций
- Перцентиль funding rate за последние 90 дней — НЕ абсолютное значение,
  а "насколько текущий funding экстремален относительно своей же недавней
  истории" (см. обсуждение в PLAN.md про нормализацию вместо готовых
  учебниковых порогов)
- Дивергенция цена/Open Interest — 4 комбинации знака изменения цены
  и изменения OI (новые лонги / шорт-каверинг / новые шорты /
  закрытие-ликвидация лонгов). Доступно только там, где есть история OI
  (сейчас — последние ~30 дней, будет расти с каждым днём автосбора)

ВАЖНО про перцентиль funding rate — без забегания вперёд (look-ahead bias):
перцентиль на каждую дату считается ТОЛЬКО по предыдущим 90 дням
(rolling-окно), а не по всей истории целиком. Если бы мы взяли перцентиль
относительно всей истории сразу — на дату из 2020 года "просочилась" бы
информация о будущих (2024-2026) значениях funding rate, которых тогда
ещё не существовало. Это классическая ошибка при подготовке данных для
бэктеста — сигнал "видел бы будущее", результат бэктеста был бы обманчиво
хорошим и не воспроизводился бы в реальной торговле.

Запуск:
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
FUNDING_PERCENTILE_WINDOW = 90  # дней


def compute_rsi(close: pd.Series, period: int) -> pd.Series:
    """RSI по методу Уайлдера (Wilder's smoothing - экспоненциальное
    сглаживание с alpha = 1/period, стандарт для RSI)."""
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
    """Классический VWAP считается ВНУТРИ одного дня по тиковым сделкам.
    У нас только дневные свечи, поэтому используем адаптацию - "скользящий
    VWAP" за последние period дней: средняя цена, взвешенная по объёму
    за это окно, а не по количеству дней."""
    return (close * volume).rolling(period).sum() / volume.rolling(period).sum()


def compute_rolling_percentile(series: pd.Series, window: int) -> pd.Series:
    """Для каждого дня - на каком перцентиле относительно ПРЕДЫДУЩИХ
    `window` дней находится сегодняшнее значение. rank(pct=True) внутри
    rolling-окна даёт перцентиль последнего значения окна относительно
    самого окна - без заглядывания в данные позже текущей даты. Используется
    и для funding rate, и для DVOL - одна и та же логика нормализации."""
    return series.rolling(window).apply(lambda x: x.rank(pct=True).iloc[-1], raw=False)


def classify_price_oi_divergence(price_change: float, oi_change: float) -> str:
    """4 классических комбинации цена/OI - см. PLAN.md."""
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
    # --- Цена/объём -> RSI, Bollinger, VWAP ---
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

    # --- Funding rate -> дневное среднее + перцентиль ---
    funding = read_df(
        "SELECT funding_time, funding_rate FROM funding_rate WHERE symbol = %(symbol)s ORDER BY funding_time",
        params={"symbol": symbol},
    )
    funding["date"] = pd.to_datetime(funding["funding_time"], utc=True).dt.normalize()
    funding_daily = funding.groupby("date")["funding_rate"].mean()
    funding_percentile = compute_rolling_percentile(funding_daily, FUNDING_PERCENTILE_WINDOW)

    result = result.merge(
        funding_daily.rename("funding_rate_daily_avg"), on="date", how="left"
    )
    result = result.merge(
        funding_percentile.rename("funding_percentile_90d"), on="date", how="left"
    )

    # --- DVOL (Deribit) -> перцентиль той же логикой, что funding rate ---
    # DVOL - "температура" опционного рынка (см. PLAN.md, "фильтр умного
    # рынка"). История доступна только с 2021-03-24 (раньше индекс не
    # существовал) - для более ранних дат тут будут NULL, это ожидаемо,
    # не баг.
    dvol = read_df(
        "SELECT ts, close FROM dvol WHERE currency = 'BTC' ORDER BY ts",
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

    # --- Open Interest -> дивергенция с ценой (доступно только там, где есть история OI) ---
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

        result = result.merge(
            oi[["date", "oi_change_pct", "price_oi_divergence"]], on="date", how="left"
        )
    else:
        result["oi_change_pct"] = None
        result["price_oi_divergence"] = None

    result.insert(0, "symbol", symbol)
    return result


def _nan_to_none(value):
    """pandas хранит "пропуск" как float NaN даже в колонках, где мы явно
    просим None - float64-колонка в pandas физически не может держать
    Python None, он молча превращается обратно в NaN. Проблема в том, что
    psycopg2 отправит такой NaN в Postgres как ЗНАЧЕНИЕ 'NaN'::float8
    (Postgres умеет такое хранить!), а не как SQL NULL - это ломает
    COUNT()/AVG() и подобные запросы, которые должны эти дни игнорировать.
    Поэтому явно подменяем NaN на None в момент сборки строк для вставки,
    когда данные уже не в pandas, а в обычных Python-кортежах."""
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
    print(f"Считаю индикаторы для {SYMBOL}...")
    df = build_indicators(SYMBOL)
    saved = save_indicators(df)
    print(f"Готово: обработано {saved} строк индикаторов ({df['date'].min().date()} - {df['date'].max().date()}).")
