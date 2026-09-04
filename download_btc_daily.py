"""
Скрипт скачивает дневные свечи (candlesticks) BTC/USDT с Binance Futures
за последние 2 года и сохраняет их в файл btc_daily.csv.

Свеча (candle) — это данные о цене за один период времени (у нас — за день):
цена открытия (open), максимум (high), минимум (low), цена закрытия (close)
и объём торгов (volume).

Это шаг 2 из плана проекта (см. PLAN.md) — "Сбор данных".
"""

import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

# Базовый адрес публичного API Binance Futures (не требует ключей/регистрации
# для получения исторических свечей — это открытые рыночные данные).
BASE_URL = "https://fapi.binance.com"
ENDPOINT = "/fapi/v1/klines"

SYMBOL = "BTCUSDT"
INTERVAL = "1d"  # "1d" = дневная свеча
DAYS_BACK = 365 * 2  # 2 года

# Binance отдаёт максимум 1500 свечей за один запрос. Для дневных свечей
# за 2 года это ~730 штук, так что в теории хватило бы одного запроса,
# но мы всё равно делаем скрипт пригодным на будущее (для интервалов
# покороче, где данных за тот же период гораздо больше) — с постраничной
# загрузкой (пагинацией) через параметр startTime.
LIMIT = 1500


def fetch_klines(symbol: str, interval: str, start_time_ms: int, end_time_ms: int) -> list:
    """
    Делает один запрос к Binance Futures API и возвращает список свечей
    в "сыром" виде — так, как их отдаёт API (список списков).

    start_time_ms / end_time_ms — границы периода в миллисекундах
    (так требует Binance API).
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_time_ms,
        "endTime": end_time_ms,
        "limit": LIMIT,
    }
    response = requests.get(BASE_URL + ENDPOINT, params=params, timeout=10)
    # Если Binance вернул ошибку (например, неверные параметры или бан по
    # частоте запросов) — response.raise_for_status() выбросит исключение
    # с понятным сообщением, вместо того чтобы молча продолжать с мусорными
    # данными.
    response.raise_for_status()
    return response.json()


def download_all_klines(symbol: str, interval: str, days_back: int) -> pd.DataFrame:
    """
    Скачивает все свечи за период [сейчас - days_back дней; сейчас],
    постранично (несколькими запросами, если период не помещается в один).
    Возвращает готовый pandas DataFrame.
    """
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=days_back)

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    all_rows = []
    current_start = start_ms

    while current_start < end_ms:
        batch = fetch_klines(symbol, interval, current_start, end_ms)

        if not batch:
            # Пустой ответ значит, что данных больше нет — выходим из цикла.
            break

        all_rows.extend(batch)

        # Каждая свеча — это список, где элемент [0] — время открытия свечи
        # в миллисекундах. Следующий запрос начинаем через 1 мс после
        # времени открытия последней полученной свечи, чтобы не скачать
        # одну и ту же свечу дважды.
        last_open_time = batch[-1][0]
        current_start = last_open_time + 1

        # Если получили меньше свечей, чем максимум за запрос — значит,
        # это была последняя порция данных.
        if len(batch) < LIMIT:
            break

        # Небольшая пауза между запросами, чтобы не превысить лимит частоты
        # запросов Binance API (rate limit) и не получить временный бан.
        time.sleep(0.2)

    # Каждая "сырая" свеча от Binance — это список из 12 значений в строго
    # заданном порядке (так документировано в Binance API). Даём столбцам
    # понятные имена.
    columns = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ]
    df = pd.DataFrame(all_rows, columns=columns)

    # Оставляем только те столбцы, которые реально нужны для дальнейшей
    # работы, и приводим типы данных к правильным (изначально всё приходит
    # как строки или "сырые" числа).
    df = df[["open_time", "open", "high", "low", "close", "volume", "trades"]].copy()

    # open_time приходит в миллисекундах с 1970 года — переводим в
    # читаемую дату.
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)

    # Цены и объём приходят как строки — переводим в float, чтобы можно
    # было считать индикаторы (RSI, скользящие средние и т.д.) в будущем.
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    # На случай, если какие-то свечи всё же продублировались между
    # запросами — убираем дубликаты по времени открытия.
    df = df.drop_duplicates(subset="open_time").sort_values("open_time")

    return df.reset_index(drop=True)


if __name__ == "__main__":
    print(f"Скачиваю {SYMBOL} {INTERVAL} свечи за последние {DAYS_BACK} дней...")
    df = download_all_klines(SYMBOL, INTERVAL, DAYS_BACK)

    output_file = "btc_daily.csv"
    df.to_csv(output_file, index=False)

    print(f"Готово: {len(df)} свечей сохранено в {output_file}")
    print(f"Период: с {df['open_time'].min()} по {df['open_time'].max()}")
