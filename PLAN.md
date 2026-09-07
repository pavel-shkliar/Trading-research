# Project: Analytical Agent for the Futures Market

## Context and goals

This is a learning pet project. The main goal is to build real
programming, data, and agent-building skills. Trading / finding market
patterns is the subject area for practice, not a goal to make money. The
end goal is to package the project into a GitHub portfolio piece + a
LinkedIn post, showcasing data engineering, automation, and AI-agent skills.

## System idea

The system looks for patterns in futures and options market data (open
interest, funding rate, long/short ratio, liquidations, options-market
metrics as a risk indicator), tests hypotheses against historical data,
and measures how often and how strongly they held up. The focus is
deliberately NOT classic indicators (RSI, MACD, etc. - well known and
therefore of limited value on their own), but derivatives-specific
mechanics: moments where an overheated crowd position (long or short)
builds up, and a reversal/squeeze has historically followed.

Known indicators (RSI, etc.) aren't off-limits - they're computed too,
just without expecting an edge from them alone (too well-known, likely
already arbitraged away). The value is more likely in combinations
(e.g., an RSI extreme coinciding with a funding-rate extreme) and in
derivatives metrics that are less commonly used systematically.

## Methodology for finding and validating patterns

- **Self-calibrated thresholds, not textbook ones.** We don't take
  "RSI > 70 = overbought" as given - textbook norms were calibrated on
  other markets and are widely known (if they ever worked, the effect
  is likely arbitraged away). Instead, thresholds are computed from our
  own data (e.g., "funding rate above the 95th percentile of ITS OWN history").
- **Walk-forward validation instead of a single in-sample/out-of-sample
  split.** Reason: crypto has multi-year cycles (bull/bear regimes), and
  a single fixed split risks catching a pattern specific to one regime.
  Instead: take a window (e.g. 12 months) -> search/calibrate the
  hypothesis -> freeze the parameters -> test on the next
  non-overlapping chunk (e.g. 3 months) -> slide the window forward ->
  repeat. This produces a series of independent checks across different
  parts of history instead of one.
- **Normalized metrics instead of absolute thresholds** - so
  observations from different coins (BTC, ETH, ...) can later be
  pooled into one statistic and the sample size grown, instead of
  treating each coin in complete isolation. If a pattern holds across
  several assets at once, that's an extra check that it isn't noise
  from one thin market.
- **Code parameterized by symbol from the start** - currently working
  with BTCUSDT only (to debug the whole pipeline on one asset), but
  functions don't hardcode the symbol, so adding other coins later is trivial.
- On news/fundamental events (FOMC, CPI, etc.) - deliberately NOT
  modeled automatically in v1 (a separate NLP project). Practice: flag
  known event dates and manually check "failed" signals against them
  during backtest review. Automating this is a candidate for step 8
  (an agent that reads the news itself).

## Data sources

- **Binance Futures API**:
  - Candles (OHLCV) - full history since contract launch
  - Funding rate - full history
  - Open Interest, Top Trader Long/Short Ratio (Positions, by
    volume/notional, NOT by account count), Taker Buy/Sell Volume -
    **Binance limitation: these three endpoints only return roughly the
    last 30 days of history**, regardless of the requested parameters.
    No ready-made long history exists here - we fetch what's available
    now and accumulate our own history going forward (see step 7 -
    automation)
  - Liquidations - no REST history at all. Plan: collect our own going
    forward via the `!forceOrder@arr` websocket stream (free, real-time).
    For historical data - use a proxy signal (a sharp OI drop + volume spike)
- **Deribit API** - options metrics, used as ready-made aggregated
  indicators, NOT building our own options pricing model (deliberate -
  too complex for the project's goals):
  - DVOL (implied volatility index) - good history available, prioritized
  - Put/Call ratio, 25-delta skew - harder to get in one request (needs
    aggregation across the option chain), deferred
- (Later, optional) on-chain data - Glassnode/Arkham/similar

## Storage - Postgres (not SQLite)

Decided to use Postgres from the start instead of the SQLite in the
original plan: more useful as a portfolio skill, easier to move to a
VPS later (same Docker image), better suited to concurrent writes (the
agent layer, step 8). Running locally in a Docker container
(`trading-research-db`), data on disk via a volume, credentials in
`.env` (not committed).

Incremental updates: before downloading, a script asks the database for
the latest saved date and requests only what's missing from the API.
Extra protection against duplicates - a `UNIQUE` constraint on
(symbol, time) in every table + `INSERT ... ON CONFLICT DO NOTHING`.

**Datasets are not committed to git** - only script code. Data lives in
Postgres (locally) - reproducibility comes from running the script, not
from a file stored in the repository.

## Architecture (9 stages, in order)

1. **First contact with the environment** - setup and a first test
   script (DONE)
2. **Data collection** - scripts to download candles, funding rate,
   open interest, long/short ratio, taker volume from Binance Futures +
   DVOL from Deribit
3. **Storage** - Postgres in Docker, incremental updates without duplicates
4. **Indicators** - RSI, Bollinger Bands, VWAP (baseline) + funding rate
   extremes (percentile), price/OI divergence, signs of liquidation
   clusters (the project's focus)
5. **Visualization** - price + indicator charts, signal markers
6. **Backtest** - walk-forward hypothesis testing against history +
   statistics (hit frequency, average result, confidence interval)
7. **Automation** - a scheduler (cron) for continuous data collection
   (especially OI/ratio/liquidations, where history is short and only
   accumulates going forward), then migration to a VPS (a cheap one:
   DigitalOcean/Hetzner/Linode, $5-10/mo) to run 24/7
8. **AI agent layer** - via the Claude API/Agent SDK: an agent that
   formulates new hypotheses from past results, writes code to test
   them, runs it, and analyzes the outcome - the most "agentic" and
   portfolio-interesting part. Candidate for extension: the agent
   classifies news/event days itself
9. **Portfolio packaging** - a README with an architecture diagram on
   GitHub, example findings (including negative results - that's fine
   too), a LinkedIn post

## Agreements / principles throughout

- Every step should end with something working and verifiable
- Commit to Git after every working step (code only, not datasets)
- Don't be afraid to ask for line-by-line code explanations
- Honestly record negative hypothesis results - that's valuable too
- Test on a short sample before downloading the full period

## Status (as of 2026-09-07)

Steps 1-6 are done for BTC and, for the funding-rate-based hypothesis,
across a 20-coin universe. 16 hypotheses have been tested; see
[HYPOTHESES.md](HYPOTHESES.md) for the full log. The project's leading
finding is H6b (DVOL complacency -> sustained underperformance,
confirmed on both BTC and ETH). Steps 7-9 (continuous automation beyond
the current daily task, the AI agent layer, and portfolio packaging) are
in progress or upcoming.
