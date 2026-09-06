"""
Скачивает дневные свечи (OHLCV) с Binance Futures и сохраняет в таблицу
candles в Postgres. Инкрементально — качает только то, чего ещё нет.

Запуск:
    python download_candles.py --days 5     (короткий тест)
    python download_candles.py --days 730   (полная история за 2 года)
"""

import argparse
import time
from datetime import datetime, timedelta, timezone

from binance_api import get
from db import get_saved_range, upsert_rows

SYMBOL = "BTCUSDT"
INTERVAL = "1d"
LIMIT = 1500  # максимум свечей за один запрос к Binance


def fetch_klines(symbol: str, start_ms: int, end_ms: int) -> list:
    return get("/fapi/v1/klines", {
        "symbol": symbol,
        "interval": INTERVAL,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": LIMIT,
    })


def _download_period(symbol: str, start_ms: int, end_ms: int) -> int:
    """Качает и сохраняет один непрерывный период [start_ms, end_ms],
    постранично (несколько запросов, если период большой)."""
    total = 0
    current_start = start_ms
    while current_start < end_ms:
        batch = fetch_klines(symbol, current_start, end_ms)
        if not batch:
            break

        rows = [
            (
                symbol,
                datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc),
                float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5]),
                int(c[8]),
            )
            for c in batch
        ]
        total += upsert_rows(
            "candles",
            ["symbol", "open_time", "open", "high", "low", "close", "volume", "trades"],
            rows,
            ["symbol", "open_time"],
        )

        current_start = batch[-1][0] + 1
        if len(batch) < LIMIT:
            break
        time.sleep(0.2)

    return total


def download(symbol: str, days_back: int) -> int:
    end_dt = datetime.now(timezone.utc)
    requested_start = end_dt - timedelta(days=days_back)

    # Смотрим, что уже есть в базе, и докачиваем ОБА недостающих куска:
    # более старую историю (если раньше скачали только недавний тестовый
    # кусок) и более новую (обычное инкрементальное обновление). Без этого
    # разделения, если один раз скачать только "последние 5 дней" для теста,
    # а потом попросить "последние 730 дней" — старая история за пределами
    # уже сохранённого окна никогда не докачается, потому что код будет
    # смотреть только "после последней сохранённой даты".
    existing_min, existing_max = get_saved_range("candles", "open_time", "symbol", symbol)

    total = 0
    if existing_min is None:
        # Данных вообще нет - качаем весь запрошенный период целиком.
        total += _download_period(symbol, int(requested_start.timestamp() * 1000), int(end_dt.timestamp() * 1000))
    else:
        if requested_start < existing_min:
            total += _download_period(
                symbol,
                int(requested_start.timestamp() * 1000),
                int(existing_min.timestamp() * 1000),
            )
        if existing_max < end_dt:
            gap_start = existing_max + timedelta(milliseconds=1)
            total += _download_period(symbol, int(gap_start.timestamp() * 1000), int(end_dt.timestamp() * 1000))

    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--symbol", default=SYMBOL)
    args = parser.parse_args()

    print(f"Скачиваю свечи {args.symbol} за последние {args.days} дней...")
    saved = download(args.symbol, args.days)
    print(f"Готово: обработано {saved} свечей.")
