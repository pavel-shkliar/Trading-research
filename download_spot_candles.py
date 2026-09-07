"""
Скачивает дневные СПОТОВЫЕ свечи (не фьючерсные) с Binance - нужны для
расчёта базиса (разницы между фьючерсной и спотовой ценой), см. H13
в HYPOTHESES.md.

Спотовый и фьючерсный API Binance - это РАЗНЫЕ эндпоинты с разным базовым
адресом (spot: api.binance.com, futures: fapi.binance.com), хотя формат
ответа одинаковый.

Сохраняем в отдельную таблицу spot_candles (не смешиваем с candles,
которая для фьючерсов).

Запуск:
    python download_spot_candles.py --symbol BTCUSDT --days 2600
"""

import argparse
import time
from datetime import datetime, timedelta, timezone

import requests

from db import get_connection, get_saved_range, upsert_rows

SPOT_BASE_URL = "https://api.binance.com"
INTERVAL = "1d"
LIMIT = 1000


def create_table():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS spot_candles (
                    symbol TEXT NOT NULL,
                    open_time TIMESTAMPTZ NOT NULL,
                    close DOUBLE PRECISION NOT NULL,
                    UNIQUE (symbol, open_time)
                );
            """)
        conn.commit()
    finally:
        conn.close()


def fetch_klines(symbol: str, start_ms: int, end_ms: int) -> list:
    response = requests.get(SPOT_BASE_URL + "/api/v3/klines", params={
        "symbol": symbol, "interval": INTERVAL,
        "startTime": start_ms, "endTime": end_ms, "limit": LIMIT,
    }, timeout=10)
    response.raise_for_status()
    return response.json()


def _download_period(symbol: str, start_ms: int, end_ms: int) -> int:
    total = 0
    current_start = start_ms
    while current_start < end_ms:
        batch = fetch_klines(symbol, current_start, end_ms)
        if not batch:
            break
        rows = [(symbol, datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc), float(c[4])) for c in batch]
        total += upsert_rows("spot_candles", ["symbol", "open_time", "close"], rows, ["symbol", "open_time"])
        current_start = batch[-1][0] + 1
        if len(batch) < LIMIT:
            break
        time.sleep(0.2)
    return total


def download(symbol: str, days_back: int) -> int:
    end_dt = datetime.now(timezone.utc)
    requested_start = end_dt - timedelta(days=days_back)
    existing_min, existing_max = get_saved_range("spot_candles", "open_time", "symbol", symbol)

    total = 0
    if existing_min is None:
        total += _download_period(symbol, int(requested_start.timestamp() * 1000), int(end_dt.timestamp() * 1000))
    else:
        if requested_start < existing_min:
            total += _download_period(symbol, int(requested_start.timestamp() * 1000), int(existing_min.timestamp() * 1000))
        if existing_max < end_dt:
            gap_start = existing_max + timedelta(milliseconds=1)
            total += _download_period(symbol, int(gap_start.timestamp() * 1000), int(end_dt.timestamp() * 1000))
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--days", type=int, default=2600)
    args = parser.parse_args()

    create_table()
    print(f"Скачиваю спотовые свечи {args.symbol} за последние {args.days} дней...")
    saved = download(args.symbol, args.days)
    print(f"Готово: обработано {saved} свечей.")
