# Crypto Derivatives Signal Research

A systematic study of whether crowd positioning in crypto derivatives markets — funding rates, implied volatility, long/short extremes — predicts future price behavior, built with a walk-forward validation pipeline designed specifically to catch overfitting before it's mistaken for a discovery.

This is a learning project: the goal was to build real data engineering and quantitative research skills, not to produce a trading strategy. The most interesting result turned out to be about methodology as much as markets — see [Finding 3](#finding-3-the-process-caught-its-own-false-positives) below.

## Data

| Source | Metrics | Coverage |
|---|---|---|
| Binance Futures | Daily OHLCV candles, funding rate | Full history since Sept 2019, 20 assets |
| Binance Futures | Open interest, top-trader long/short ratio, taker buy/sell volume | Limited by the exchange to a rolling 30-day window; collected forward via a daily scheduled job |
| Deribit | DVOL (implied volatility index) | BTC and ETH only (the only two assets Deribit publishes it for), since March 2021 |
| Binance Spot | Daily close | Used to compute futures/spot basis |

All data lives in Postgres (Docker), with incremental, idempotent download scripts and a daily automated job that keeps the short-history metrics accumulating over time.

## Methodology

1. **Percentile-based, not textbook thresholds.** A metric's extremity is measured against its own trailing 90-day history, not a fixed cutoff — this is what makes it possible to compare BTC and a newly-listed altcoin on the same terms.
2. **Full-history exploratory pass** across seven horizons (3–180 days) before committing to any specific one.
3. **Episode collapsing.** A signal that persists for several consecutive days is one event, not several — treating each day separately inflates the sample size with heavily overlapping, non-independent return windows and produces artificially confident p-values.
4. **Walk-forward across six historical regimes** (2019–20 COVID crash/recovery, 2021 bull/correction, 2022 bear/Luna-FTX collapse, 2023 recovery, 2024 ETF rally, 2025–26) instead of a single in-sample/out-of-sample split — a real effect should show up in more than one kind of market.
5. **Formal significance testing** (Welch's t-test and Mann-Whitney U) on the resulting episodes, not just a comparison of averages.
6. **Cross-asset validation** — every promising result is rerun across up to 20 assets before being trusted.

## Findings

### Finding 1: DVOL complacency precedes sustained underperformance

When Deribit's DVOL (options-implied volatility) sits in the bottom 5% of its own 90-day range — the options market pricing in unusual calm — BTC and ETH both go on to underperform over the following 60 days, consistently across time and across both assets:

- **Walk-forward**: negative edge in all 5 testable historical periods, on *both* BTC and ETH (10/10)
- **Significance**: BTC t-test p=0.0086, Mann-Whitney p=0.0017; ETH t-test p=0.0114, Mann-Whitney p=0.0016
- **Mechanism**: the underperformance builds gradually across the full 60-day window rather than arriving as a single sharp move — the signal asset fails to keep pace with the broader market's drift rather than crashing outright

### Finding 2: an unexplained Wednesday effect

Buying at the open and selling at the close on Wednesdays produces a meaningfully higher return than any other day of the week, on both BTC (p=0.046) and ETH (p=0.043), holding up in walk-forward (5/6 and 6/6 periods respectively) and confirmed by the median as well as the mean — not a handful of outlier days.

No causal explanation was found. FOMC announcements land on Wednesdays but cover only ~15% of all Wednesdays in the sample, too small a share to account for a pattern this broad. Logged as a real but currently unexplained anomaly, in the same category as the historically documented (and still not fully explained) "Monday effect" in equities — flagged, not acted on.

### Finding 3: the process caught its own false positives

Twice, a hypothesis produced a spectacular pooled result and then failed once tested properly:

- One test's raw p-value of 0.0001 came from 181 "signal days" that collapsed to just **35 independent episodes** once consecutive days were merged — the headline number was an artifact of counting the same event repeatedly.
- Another produced p=0.0000 pooling 848 episodes across 20 coins — until a year-by-year breakdown showed the entire effect was carried by two unusually volatile years (2021, 2022), with literally no effect in the most recent two years of data.

Both are logged in [HYPOTHESES.md](HYPOTHESES.md) as `inconclusive`, not `confirmed`. Catching these before treating them as findings is the actual point of the walk-forward and episode-collapsing pipeline described above.

## What didn't hold up

16 hypotheses were tested in total; 8 were cleanly rejected, including two textbook technical indicators (RSI, Bollinger Bands) that turned out to work in the *opposite* direction from the standard assumption on this dataset — momentum rather than mean-reversion. A hypothesis about crowded futures positioning (funding rate extremes) looked promising on BTC alone but reversed sign and turned statistically significant *against* itself once tested across 20 assets. Full writeups, including the negative results, are in [HYPOTHESES.md](HYPOTHESES.md).

## Repository structure

```
db.py                       Postgres connection, schema, generic upsert helper
binance_api.py / deribit_api.py   Thin HTTP clients for the two exchanges
download_*.py                Incremental downloaders (candles, funding rate,
                              open interest, long/short ratio, taker volume,
                              DVOL, spot candles)
download_universe.py         Bulk downloader for the 20-asset cross-validation set
compute_indicators.py        RSI, Bollinger, VWAP, funding/DVOL percentiles,
                              price/OI divergence
walkforward_common.py        Shared walk-forward machinery: period splitting,
                              episode collapsing, forward-return statistics
backtest_h*.py                One script per hypothesis tested (see HYPOTHESES.md)
run_daily_download.bat + Windows Task Scheduler   Keeps the 30-day-limited
                              metrics accumulating history over time
PLAN.md                      Project plan and architecture decisions
HYPOTHESES.md                 Full hypothesis log, including every rejected idea
```

## Running it

Requires Python 3.12, Docker, and a Postgres container (see `PLAN.md` for setup).

```bash
pip install -r requirements.txt
python db.py                  # create tables
python download_all.py --days 2600
python compute_indicators.py
python backtest_h6b_walkforward.py   # the strongest result
```

## Stack

Python, pandas, scipy, PostgreSQL (Docker), Binance Futures & Spot APIs, Deribit API, Windows Task Scheduler for automated collection.
