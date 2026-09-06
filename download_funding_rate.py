"""
Скачивает funding rate (ставку финансирования перпетуального фьючерса,
платится раз в 8 часов) с Binance Futures в таблицу funding_rate.

Экстремальные значения (относительно СВОЕЙ ЖЕ истории — это считается
на шаге индикаторов, не здесь) — признак перегретой позиции толпы.

Запуск:
    python download_funding_rate.py --days 5
    python download_funding_rate.py --days 2600  (максимум истории, с 2019 года)
"""

import argparse
import time
from datetime import datetime, timedelta, timezone

from binance_api import get
from db import get_saved_range, upsert_rows

SYMBOL = "BTCUSDT"
LIMIT = 1000


def fetch_funding(symbol: str, start_ms: int, end_ms: int) -> list:
    return get("/fapi/v1/fundingRate", {
        "symbol": symbol,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": LIMIT,
    })


def _download_period(symbol: str, start_ms: int, end_ms: int) -> int:
    total = 0
    current_start = start_ms
    while current_start < end_ms:
        batch = fetch_funding(symbol, current_start, end_ms)
        if not batch:
            break

        rows = [
            (symbol, datetime.fromtimestamp(f["fundingTime"] / 1000, tz=timezone.utc), float(f["fundingRate"]))
            for f in batch
        ]
        total += upsert_rows(
            "funding_rate",
            ["symbol", "funding_time", "funding_rate"],
            rows,
            ["symbol", "funding_time"],
        )

        current_start = batch[-1]["fundingTime"] + 1
        if len(batch) < LIMIT:
            break
        time.sleep(0.2)

    return total


def download(symbol: str, days_back: int) -> int:
    end_dt = datetime.now(timezone.utc)
    requested_start = end_dt - timedelta(days=days_back)

    # См. подробный комментарий в download_candles.py - докачиваем и более
    # старую историю (если раньше был только тестовый кусок), и более новую.
    existing_min, existing_max = get_saved_range("funding_rate", "funding_time", "symbol", symbol)

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
    parser.add_argument("--days", type=int, default=2600)
    parser.add_argument("--symbol", default=SYMBOL)
    args = parser.parse_args()

    print(f"Скачиваю funding rate {args.symbol} за последние {args.days} дней...")
    saved = download(args.symbol, args.days)
    print(f"Готово: обработано {saved} записей funding rate.")
