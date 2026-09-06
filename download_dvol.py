"""
Скачивает DVOL (индекс подразумеваемой волатильности опционов на Deribit,
аналог VIX) в таблицу dvol.

DVOL — "фильтр умного рынка" (см. PLAN.md): если фьючерсный рынок выглядит
перегретым (funding rate экстремальный, OI растёт), а DVOL остаётся
спокойным — движение может быть менее устойчивым (чисто на плече, без
подтверждения опционным рынком).

Запуск:
    python download_dvol.py --days 5
    python download_dvol.py --days 730
"""

import argparse
from datetime import datetime, timedelta, timezone

from deribit_api import get
from db import get_saved_range, upsert_rows

CURRENCY = "BTC"
RESOLUTION = 86400  # размер свечи индекса в секундах (86400 = 1 день)
CHUNK_DAYS = 80      # запрашиваем историю кусками, чтобы не упереться в лимиты Deribit за один запрос


def fetch_chunk(currency: str, start_ms: int, end_ms: int) -> list:
    result = get("/public/get_volatility_index_data", {
        "currency": currency,
        "start_timestamp": start_ms,
        "end_timestamp": end_ms,
        "resolution": RESOLUTION,
    })
    return result["data"]


def _download_period(currency: str, period_start: datetime, period_end: datetime) -> int:
    """Качает один непрерывный период кусками по CHUNK_DAYS дней."""
    total = 0
    chunk_start = period_start
    while chunk_start < period_end:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS), period_end)

        data = fetch_chunk(
            currency,
            int(chunk_start.timestamp() * 1000),
            int(chunk_end.timestamp() * 1000),
        )

        # Каждая точка — [timestamp_ms, open, high, low, close]
        rows = [
            (
                currency,
                datetime.fromtimestamp(point[0] / 1000, tz=timezone.utc),
                float(point[1]), float(point[2]), float(point[3]), float(point[4]),
            )
            for point in data
        ]
        total += upsert_rows(
            "dvol",
            ["currency", "ts", "open", "high", "low", "close"],
            rows,
            ["currency", "ts"],
        )

        chunk_start = chunk_end

    return total


def download(currency: str, days_back: int) -> int:
    end_dt = datetime.now(timezone.utc)
    requested_start = end_dt - timedelta(days=days_back)

    # См. подробный комментарий в download_candles.py.
    existing_min, existing_max = get_saved_range("dvol", "ts", "currency", currency)

    total = 0
    if existing_min is None:
        total += _download_period(currency, requested_start, end_dt)
    else:
        if requested_start < existing_min:
            total += _download_period(currency, requested_start, existing_min)
        if existing_max < end_dt:
            gap_start = existing_max + timedelta(milliseconds=1)
            total += _download_period(currency, gap_start, end_dt)

    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=730)
    parser.add_argument("--currency", default=CURRENCY)
    args = parser.parse_args()

    print(f"Скачиваю DVOL {args.currency} за последние {args.days} дней...")
    saved = download(args.currency, args.days)
    print(f"Готово: обработано {saved} записей DVOL.")
