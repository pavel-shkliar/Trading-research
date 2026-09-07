"""
Bulk downloader for the 20-asset cross-validation universe (the top
crypto perpetuals by 24h volume, excluding tokenized traditional assets
Binance also lists on the same engine - gold, stocks, ETFs).

Only candles + funding rate (full history) - OI/ratio/taker are skipped
(30-day limited, not needed here) and DVOL isn't fetched for altcoins
(Deribit only publishes it for BTC and ETH).

Usage:
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

DAYS = 2600  # max available history - the download scripts fetch less for younger coins


if __name__ == "__main__":
    for symbol in SYMBOLS:
        print(f"=== {symbol} ===")
        try:
            n_candles = download_candles.download(symbol, DAYS)
            n_funding = download_funding_rate.download(symbol, DAYS)
            print(f"  candles: {n_candles}, funding: {n_funding}")

            df = compute_indicators.build_indicators(symbol)
            n_saved = compute_indicators.save_indicators(df)
            print(f"  indicators: {n_saved} rows ({df['date'].min().date()} - {df['date'].max().date()})")
        except Exception as e:
            print(f"  ERROR for {symbol}: {e}")

        time.sleep(0.5)  # avoid hammering the API between symbols
