"""
Массовая загрузка данных по топ-20 крипто-перпетуалам (не токенизированным
традиционным активам вроде золота/акций, которые тоже торгуются на Binance
Futures - их явно исключаем) - чтобы проверить, держится ли H1b на
нескольких монетах, а не только на BTC (см. обсуждение в чате про
нормализацию порогов вместо абсолютных значений, чтобы объединять монеты).

Качаем только свечи + funding rate (полная история) - OI/ratio/taker
пропускаем, они всё равно ограничены 30 днями и не нужны для H1b/H6b.
Не качаем DVOL для альткоинов - Deribit публикует DVOL только для BTC
и ETH, для остальных монет такого индекса физически не существует.

Запуск:
    python download_universe.py
"""

import time

import download_candles
import download_funding_rate
import compute_indicators

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "ZECUSDT", "SOLUSDT", "XRPUSDT",
    "HYPEUSDT", "DOGEUSDT", "ARBUSDT", "SNDKUSDT", "BNBUSDT",
    "RAYSOLUSDT", "SUIUSDT", "NEARUSDT", "TAOUSDT", "LINKUSDT",
    "WLDUSDT", "UNIUSDT", "PUMPUSDT", "BZUSDT", "MARSCOINUSDT",
]

DAYS = 2600  # максимум доступной истории - скрипт сам возьмёт меньше, если монета моложе


if __name__ == "__main__":
    for symbol in SYMBOLS:
        print(f"=== {symbol} ===")
        try:
            n_candles = download_candles.download(symbol, DAYS)
            n_funding = download_funding_rate.download(symbol, DAYS)
            print(f"  свечи: {n_candles}, funding: {n_funding}")

            df = compute_indicators.build_indicators(symbol)
            n_saved = compute_indicators.save_indicators(df)
            print(f"  индикаторы: {n_saved} строк ({df['date'].min().date()} - {df['date'].max().date()})")
        except Exception as e:
            print(f"  ОШИБКА для {symbol}: {e}")

        time.sleep(0.5)  # не долбить API слишком часто между монетами
