"""
Скачивает историю Open Interest (суммарный объём открытых позиций)
с Binance Futures в таблицу open_interest.

ВАЖНО (ограничение самого Binance API, не нашего кода): этот эндпоинт
отдаёт историю максимум примерно за 30 дней назад, сколько бы дней
назад ни попросить в startTime. Длинную историю тут получить нельзя —
вместо этого копим свою историю вперёд, регулярно перезапуская этот
скрипт (см. шаг 7 плана — автоматизация через cron).

Запуск:
    python download_open_interest.py --days 5
    python download_open_interest.py --days 30
"""

import argparse
import time
from datetime import datetime, timedelta, timezone

from binance_api import get
from db import get_saved_range, upsert_rows

SYMBOL = "BTCUSDT"
PERIOD = "1d"  # дневная агрегация - совпадает по частоте со свечами
LIMIT = 500


def fetch(symbol: str, start_ms: int, end_ms: int) -> list:
    return get("/futures/data/openInterestHist", {
        "symbol": symbol,
        "period": PERIOD,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": LIMIT,
    })


def _download_period(symbol: str, start_ms: int, end_ms: int) -> int:
    total = 0
    current_start = start_ms
    while current_start < end_ms:
        batch = fetch(symbol, current_start, end_ms)
        if not batch:
            break

        rows = [
            (
                symbol,
                datetime.fromtimestamp(r["timestamp"] / 1000, tz=timezone.utc),
                float(r["sumOpenInterest"]),
                float(r["sumOpenInterestValue"]),
            )
            for r in batch
        ]
        total += upsert_rows(
            "open_interest",
            ["symbol", "ts", "sum_open_interest", "sum_open_interest_value"],
            rows,
            ["symbol", "ts"],
        )

        current_start = batch[-1]["timestamp"] + 1
        if len(batch) < LIMIT:
            break
        time.sleep(0.2)

    return total


def download(symbol: str, days_back: int) -> int:
    end_dt = datetime.now(timezone.utc)
    requested_start = end_dt - timedelta(days=days_back)

    # См. подробный комментарий в download_candles.py.
    existing_min, existing_max = get_saved_range("open_interest", "ts", "symbol", symbol)

    total = 0
    if existing_min is None:
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
    parser.add_argument("--days", type=int, default=30, help="Binance хранит максимум ~30 дней для этого эндпоинта")
    parser.add_argument("--symbol", default=SYMBOL)
    args = parser.parse_args()

    print(f"Скачиваю Open Interest {args.symbol} за последние {args.days} дней...")
    saved = download(args.symbol, args.days)
    print(f"Готово: обработано {saved} записей Open Interest.")
