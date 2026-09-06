"""
Запускает скачивание всех источников данных проекта по очереди
и сохраняет результат в Postgres.

Использование:
    python download_all.py --days 5      # короткий тест конвейера
    python download_all.py --days 730    # полная история (где доступна)

Для Open Interest / Long-Short Ratio / Taker Volume Binance всё равно
не отдаст больше ~30 дней (ограничение самого API) — скрипт сам
подрезает days для этих трёх источников, даже если попросить больше.
"""

import argparse

import download_candles
import download_funding_rate
import download_open_interest
import download_long_short_ratio
import download_taker_volume
import download_dvol

SYMBOL = "BTCUSDT"
CURRENCY = "BTC"
BINANCE_SHORT_HISTORY_LIMIT = 30  # OI/ratio/taker-volume эндпоинты Binance


def main(days: int):
    print(f"=== Свечи ({days} дн.) ===")
    print(download_candles.download(SYMBOL, days), "записей")

    print(f"=== Funding rate ({days} дн.) ===")
    print(download_funding_rate.download(SYMBOL, days), "записей")

    short_days = min(days, BINANCE_SHORT_HISTORY_LIMIT)

    print(f"=== Open Interest ({short_days} дн., лимит Binance) ===")
    print(download_open_interest.download(SYMBOL, short_days), "записей")

    print(f"=== Top Trader Long/Short Ratio ({short_days} дн., лимит Binance) ===")
    print(download_long_short_ratio.download(SYMBOL, short_days), "записей")

    print(f"=== Taker Buy/Sell Volume ({short_days} дн., лимит Binance) ===")
    print(download_taker_volume.download(SYMBOL, short_days), "записей")

    print(f"=== DVOL ({days} дн.) ===")
    print(download_dvol.download(CURRENCY, days), "записей")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=730)
    args = parser.parse_args()
    main(args.days)
