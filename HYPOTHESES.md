# Hypothesis Log

Every hypothesis tested goes here, with its result (including negative
ones - see PLAN.md's commitment to honestly recording failures). Check
this list before proposing a new idea, to avoid re-testing the same
thing twice.

Statuses: `proposed` (formulated, not yet tested) -> `testing` ->
`confirmed` / `rejected` / `inconclusive` (not enough data for a verdict).

## Checklist before recording a new hypothesis's result

(added 2026-09-07 after catching an in-sample/out-of-sample gap - a
written plan doesn't enforce itself, hence an explicit checklist)

- [ ] n = independent episodes (via `collapse_to_episodes`), not raw
      overlapping days
- [ ] Walk-forward across all 6 periods (not a single split) - the
      primary robustness bar now that strict out-of-sample was made
      non-blocking (see the note below)
- [ ] (optional, every month or two) re-check previously frozen
      hypotheses against fresh data from the auto-collector - doesn't
      block new tests
- [ ] Absolute numbers shown (return, frequency), not just "the edge"
- [ ] Hypothesis counter updated in the multiple-comparisons note below
- [ ] Extra caution if horizon = 30 days - three prior hypotheses were
      unstable there

## H14 - Low REALIZED volatility -> underperformance (H6b analog across 20 coins)

**Status**: inconclusive - the impressive pool did NOT survive
year-by-year walk-forward, the effect is concentrated in 2021-2022 (2026-09-07)

**Formulation**: the same mechanism as H6b (complacency ->
underperformance), but via REALIZED price volatility (rolling 90-day std
of daily returns) instead of implied DVOL - available for all 20
universe coins, not just BTC/ETH.

**Exploratory result across 20 coins (60-day horizon)** looked
excellent: 17 of 20 coins with a negative edge, a pooled sample of 848
episodes gave a mean excess return of **-10.12%**, 95% CI
[-14.44%, -5.80%], **t-test p=0.0000**.

**Year-by-year walk-forward (pooled) shattered the first impression**:

| Period | n | Mean excess return | p-value |
|---|---|---|---|
| 2019-2020 | 33 | +48.92% (contradicts) | 0.0347 |
| 2021 | 141 | -46.19% | 0.0000 |
| 2022 (Luna/FTX collapse) | 119 | -14.58% | 0.0000 |
| 2023 | 133 | +9.31% (contradicts) | 0.0528 |
| 2024 | 128 | -2.95% (not significant) | 0.5388 |
| 2025-2026 | 294 | +1.17% (not significant) | 0.6928 |

**Conclusion**: the effect is almost entirely explained by two specific
turbulent years (2021, 2022 - the most volatile in our history), not a
persistent pattern. In both of the most recent periods (2024, 2025-2026
- 400+ episodes) there is no effect at all. The impressive overall
p-value (0.0000) is a textbook case of pooling data without a time
breakdown masking regime-dependence. Not confirmed as a working finding
- but a valuable illustration of why the full walk-forward process
exists: without it, this hypothesis would have looked like the best
result of the project.

---

## H13 - Extreme futures/spot basis -> gap convergence

**Status**: rejected (2026-09-07)

**Formulation**: basis = (futures price - spot price)/spot. In theory,
arbitrage should keep the gap small - extreme high basis (expensive
futures) -> expect futures underperformance afterward. Downloaded spot
candles separately for this (`download_spot_candles.py`, `spot_candles`
table) - not done before.

**Result** (60-day horizon): BTC edge -1.71 (p=0.56), ETH edge +6.22
(p=0.11) - both not significant, and the BTC/ETH signs are OPPOSITE.
Walk-forward is also inconsistent by year.

**Conclusion**: no effect. A plausible explanation - the basis on
perpetuals is already continuously trimmed by funding rate (paid every
8 hours) - the gap doesn't have time to build into an independent
multi-day signal beyond what funding rate itself already covers
(H1/H1b/H1c). Rejected.

---

## H12 - ETH/BTC ratio extreme -> reversal of relative strength

**Status**: inconclusive - the impressive raw result did NOT survive
episode collapsing/walk-forward (2026-09-07)

**Formulation**: a fresh angle - cross-asset rotation, not derivatives
or calendar. Extreme "alt season" (ETH/BTC ratio percentile > 0.95) ->
expect BTC to subsequently outperform ETH (reversal of relative
strength). The other side (BTC dominance -> ETH catches up) did not
hold up in the exploratory pass (p=0.89); only the working half was tested.

**Looked strong on raw days**: n=181, p=0.0001.

**After collapsing into independent episodes**: n dropped to **35**
(181 raw days averaged ~5 days per episode - very strong
autocorrelation). t-test p=0.31 - NOT significant. Mann-Whitney p=0.055
- borderline, also fails the threshold.

**Walk-forward**: 4 of 5 periods with data confirm the direction, but
the most recent period (2025-2026) **reverses** (+10.37 instead of the
expected negative, n=9).

**Conclusion**: a good methodology lesson, not a finding - the raw
p-value was dramatically inflated by autocorrelation (181 -> 35 upon
collapsing), exactly what this project's procedure exists to catch. Not
logged as a working hypothesis, but valuable as a demonstration of why
the full validation chain matters.

---

## H11 - High/low trading volume -> next-day return

**Status**: rejected (2026-09-07)

**Formulation**: independent of day of week - does volume itself (top/
bottom decile relative to a rolling 90 days) predict the next day's return?

**Result**: BTC p=0.4810, ETH p=0.1742 - both not significant.
Year-by-year walk-forward shows inconsistent signs, including a clear
reversal on both assets in 2025-2026 (BTC -0.461, ETH -0.685, while
prior periods were mostly positive).

**Conclusion**: no effect. Rejected.

---

## H10 - DVOL complacency: after a rally vs without one (refines H6b)

**Status**: confirmed as a refinement - both subgroups confirm H6b,
"without a rally" is stronger (2026-09-07)

**Formulation**: among H6b's signal days (DVOL low), does the effect
differ depending on whether it was PRECEDED by a rally (positive 90-day
return) or not?

**Result** (60-day horizon):

| Coin | After rally (n) | Edge | Without rally (n) | Edge |
|---|---|---|---|---|
| BTC | 55 | -8.25 | 47 | **-10.43** |
| ETH | 47 | -5.27 | 34 | **-20.41** |

**Conclusion**: both subgroups confirm H6b's direction (both negative),
but "complacency WITHOUT a preceding rally" is a meaningfully stronger
signal, especially on ETH (-20.41 vs -5.27). Plausible explanation:
calm after a rally is partly a normal reaction (people are content with
their gains), while calm WITHOUT a rally is more unusual - a genuine
sign of risk underpricing. Refines H6b, doesn't contradict it.

---

## H8 - Calendar effects (day of week)

**Status**: interesting finding, but WITHOUT a causal explanation -
held with caution (2026-09-07)

**Formulation**: not derivatives, but time - does intraday return
(open->close) differ by day of week? A completely different dimension
from everything before it.

**Result**: "overnight" return (close -> next open) is structurally
always ~0 - crypto trades 24/7, this is a data limitation, not a finding.

Intraday return on Wednesdays is meaningfully higher than other days on
BOTH assets:

| | Wednesday | Other days | p-value |
|---|---|---|---|
| BTC | +0.463% | +0.078% | 0.0459 |
| ETH | +0.665% | +0.130% | 0.0432 |

Year-by-year walk-forward: BTC - 5 of 6 periods positive (2022 ~ zero),
ETH - **6 of 6** positive.

**Important caveat**: this hypothesis was found by SCANNING all 7
weekdays (a textbook multiple-comparisons situation - see the note
below). The statistics are robust and cross-asset, but the lack of a
causal mechanism is a real reason for caution. No trading decisions are
built on this without independent confirmation on future data.

**Signal direction (clarification)**: a positive Wednesday intraday
return means "go/stay long from Wednesday's open to its close" - i.e.
the signal says "buy," not "sell."

**Outlier vs broad-based check (2026-09-07)**: the median (not just the
mean) is also meaningfully higher on Wednesdays (BTC 0.072% vs 0.020%,
ETH 0.199% vs 0.091%), and trimming the 6 most extreme Wednesdays
(3 from each tail) does NOT reduce the effect - it even grows slightly -
meaning this isn't a couple of outliers but a broad, recurring pattern.

**Cause investigation - FOMC (Fed meetings)**: FOMC is announced 8 times
a year, almost always on a Wednesday - a logical candidate cause. But
across 7 years we have 365 Wednesdays (~52/year), and FOMC Wednesdays
are only 8 of 52 (~15%). Since the effect is broad (holding on nearly
every Wednesday, not just outliers), FOMC physically cannot be the sole
cause - too small a share of Wednesdays are meeting days. Other
candidates considered and ruled out: Deribit's weekly options expiry
(Fridays, not Wednesday), technical-analysis "weekly candle" conventions
(usually Monday-anchored).

**Final conclusion**: no cause found. A statistically robust, broad,
cross-asset effect with no explanation - comparable to the historically
documented "Monday effect" in equities, also well-documented but not
fully explained after decades of research. Logged honestly as a real
but low-priority-for-practical-use finding.

---

## H7 - Funding rate velocity (refinement of the already-dead H1b)

**Status**: rejected - doesn't rescue H1b (2026-09-07)

**Formulation**: a sudden flip into crowded positioning (not crowded 14
days ago) vs a chronic state (crowded 14 days ago too) - does speed
matter more than level?

**Result** (60-day horizon): BTC - sudden flip edge +4.11, chronic
-4.04. ETH - the OPPOSITE: sudden flip -5.17, chronic +17.80.

**Conclusion**: directions disagree between assets in the same way as
the underlying H1b - velocity doesn't rescue an already-rejected
hypothesis. Not pursued further.

---

## H2 - RSI extreme alone -> reversal

**Status**: rejected - works the OPPOSITE of the textbook assumption (2026-09-07)

**Formulation**: a classic control. RSI<30 (oversold) -> expect a rally,
RSI>70 (overbought) -> expect a drop. Standard textbook threshold 30/70,
not our own percentile - the goal here is specifically to test the
well-known indicator as-is.

**Result** (`backtest_h2_rsi.py`, episodes, all 7 horizons):

| Horizon | RSI>70 (expect drop) Delta | RSI<30 (expect rally) Delta |
|---|---|---|
| 30 days | +2.25 | -0.33 |
| 60 days | +0.58 | -1.71 |
| 90 days | +7.39 | -4.74 |
| 180 days | +3.87 | -16.54 |

**Conclusion**: "overbought" on BTC has historically preceded CONTINUED
gains (momentum), not a reversal. "Oversold" at medium-long horizons has
preceded CONTINUED losses (a "falling knife"), not a bounce. Both are
the reverse of the textbook assumption. An expected and useful control
result: confirms the method honestly finds "no edge (or reversed edge)"
exactly where PLAN.md predicted it would, rather than manufacturing a
pattern out of anything.

---

## H4 - Bollinger Bands -> reversion to the mean

**Status**: rejected - same momentum pattern as H2/RSI (2026-09-07)

**Formulation**: lower band touch -> expect a rally to the midline,
upper band touch -> expect a drop to the midline. Classic control.

**Result** (`backtest_h4_bollinger.py`):

| Horizon | Lower (expect rally) Delta | Upper (expect drop) Delta |
|---|---|---|
| 90 days | -5.85 | +4.88 |
| 180 days | -16.63 | +8.15 |

**Conclusion**: the same pattern as H2 (RSI) - momentum, not
mean-reversion. Expected, since both indicators are computed from price
- a good cross-confirmation that this isn't an artifact of one specific
indicator's formula but a property of the market itself in this period.

---

## H6 - DVOL extremes on their own (not tied to funding)

**Status**: split - H6a rejected, H6b promising (walk-forward passed at
60 days, the best result of any hypothesis so far - see below) (2026-09-07)

**H6a: DVOL high (percentile>0.95) -> expect a bounce** (VIX-style
analogy on traditional markets). Result was weak/near zero at every
horizon (return delta from -0.55 to +4.44, no clear direction). Rejected.

**H6b: DVOL low (percentile<0.05, "complacency") -> expect
underperformance AND more frequent large drops** ("calm before the
storm").

| Horizon | Return Delta | Large-drop-frequency Delta |
|---|---|---|
| 7 days | -2.11 | +6.70 pp |
| 14 days | -3.30 | +13.82 pp |
| 30 days | -3.37 | +9.78 pp |
| 60 days | -6.83 | +18.21 pp |
| 90 days | -6.80 | +4.97 pp |

Return is negative on 6 of 7 horizons, large-drop frequency exceeds
baseline on 5 of 7 (especially at 7-60 days). The first new idea
INDEPENDENT of funding rate with a consistent picture across several
horizons at once - a candidate for walk-forward (`backtest_h6_dvol.py`,
data only from 2021-06-21).

**Walk-forward for H6b (`backtest_h6b_walkforward.py`, horizons
30/60/90, n = episodes)** - IMPORTANT on sign: the hypothesis predicts
UNDERperformance, so a negative edge_mean = confirmation, not the reverse:

60-day horizon (the best result of any hypothesis to date):

| Period | n | Return Delta | Confirms? |
|---|---|---|---|
| 2019-2020 | 0 | - (DVOL didn't exist) | - |
| 2021 | 6 | -26.19 | Yes |
| 2022 | 19 | -0.91 | Yes (weakly) |
| 2023 | 11 | -10.90 | Yes |
| 2024 | 13 | -3.97 | Yes (weakly) |
| 2025-2026 | 36 | -0.73 | Yes (weakly) |

**All 5 available periods confirm** - even more consistent than H1b (5
of 6). Weaker at 90 days (3 of 5 clearly confirm, 2 neutral/
contradicting, including the most recent period). Mixed at 30 days.

**Status updated**: H6b is the most consistent walk-forward result of
any hypothesis tested, at the 60-day horizon.

**Statistical significance check (2026-09-07, 60-day horizon, n=85
episodes)**:
- Welch t-test (vs baseline): **p=0.0086** - significant
- Mann-Whitney U: **p=0.0017** - significant

Unlike H1b (where the t-test and Mann-Whitney disagreed), here **both
tests agree** - a more reliable result. The signal group's own 95% CI
[-7.04%, +2.70%] crosses zero (can't firmly claim "guaranteed loss"),
but the comparison against baseline is significant at the <1% level on
both tests - the signal group is significantly worse than the general
market.

**H6b's overall status**: our most statistically reliable result to
date - walk-forward (5 of 5 periods) plus both significance tests agree.
Still not "proven" in an absolute sense (see the multiple-comparisons
counter - this is already the 9th hypothesis tested), but noticeably
stronger than H1b.

**Check on ETH (2026-09-07, `backtest_h6b_eth_check.py`)** - Deribit
only publishes DVOL for BTC and ETH, nowhere further to extend, but this
is the first hypothesis that actually held up on a SECOND independent asset:

| Coin | n | Edge | t-test | Mann-Whitney |
|---|---|---|---|---|
| BTCUSDT | 85 | -6.83 | p=0.0086 | p=0.0017 |
| ETHUSDT | 71 | **-10.06** | p=0.0114 | p=0.0016 |

The effect is even stronger on ETH than BTC, and both tests agree there
too. Unlike H1b (which failed the 20-coin test), H6b passes on every
asset it can actually be tested on. The best, most validated hypothesis
of the project so far - not generalized to "any asset" (there's no data
for that beyond BTC/ETH), but no longer looking like BTC-specific noise
either.

**Year-by-year walk-forward for BOTH assets (2026-09-07,
`backtest_h6b_walkforward.py`, horizons 30/60/90)**:

| Horizon | BTC periods confirming | ETH periods confirming |
|---|---|---|
| 30 days | 4 of 5 | 4 of 5 |
| 60 days | **5 of 5** | **5 of 5** |
| 90 days | 3 of 5 | **5 of 5** |

**26 of 30 asset x period x horizon combinations confirm the hypothesis
(87%)**. At the 60-day horizon - a perfect result on both assets, no
exceptions:

| Period | BTC Return Delta (60d) | ETH Return Delta (60d) |
|---|---|---|
| 2021 | -26.19 | -3.82 |
| 2022 (Luna/FTX collapse) | -0.91 | -13.26 |
| 2023 | -10.90 | -10.53 |
| 2024 | -3.97 | -7.20 |
| 2025-2026 | -0.73 | -7.30 |

Telling detail: in 2022, BTC confirmed weakly while ETH confirmed
noticeably more strongly. Different assets weathered the same crisis
differently, yet both ultimately confirmed the pattern - an argument
that this isn't a coincidence of one asset in one regime.

**Summary**: H6b at the 60-day horizon is the most consistent result of
the entire project (5/5 walk-forward on TWO assets, plus both
significance tests passing on both). Its generalization limits are
known and honestly stated: nothing further to test beyond BTC/ETH (a
Deribit limitation), but within those bounds the result is as complete
as our data can make it.

**Mechanism (deeper dive, 2026-09-07, `backtest_h6b_mechanism.py`)** -
a CORRECTION to the original framing: H6b was initially described as
"calm before the storm" (implying a sharp crash). Built the full
day-by-day return trajectory (not just the endpoint at day 60) - the
picture is different:

- The gap between the signal group and the baseline **widens gradually
  and steadily** across the full 60 days, not in one sharp move on a
  specific day
- BTC: the signal group treads water while the baseline steadily rises
  (general market uptrend) - "fails to keep pace," not "crashes"
- ETH: the signal group itself gradually declines (from -1.6% on day 5
  to -6% on day 60) against a rising baseline
- The worst point reached within the window (max drawdown) for the
  signal group is only modestly deeper than baseline (BTC -14.83% vs
  -12.12%, ETH -22.89% vs -16.52%) - not a sharp crash, but steadily
  somewhat worse throughout

**Revised formulation of H6b**: DVOL complacency precedes not a "sudden
crash" but a **period of sustained underperformance**, building over
roughly 2 months after the signal.

---

## H5 - RSI oversold as additional confirmation for H1b

**Status**: inconclusive / not useful at the 90-day horizon (2026-09-07)

**Formulation**: among H1b's signal days, is the effect stronger when
RSI(14) ALSO shows oversold (<30, textbook threshold) at the same time
as funding rate? Two independent indicators (from different data: price/
volume vs funding rate) confirming each other.

**Result** (`backtest_h5_rsi_funding.py`, exploration across all 7 horizons):

| Horizon | Group | n | Return Delta | Large-rally-frequency Delta |
|---|---|---|---|---|
| 14 days | Both indicators | **11** | +6.71 | +12.42 pp |
| 14 days | Funding only | 87 | +0.81 | +1.45 pp |
| 90 days | Both indicators | **11** | +4.74 | +13.13 pp |
| 90 days | Funding only | 87 | +6.32 | +8.11 pp |
| 180 days | Both indicators | **11** | **-7.54** | +3.43 pp |
| 180 days | Funding only | 86 | **+9.42** | +10.73 pp |

**Critical caveat**: the "both indicators" group is only **11 episodes**
across 7 years - an extremely small sample, individual numbers are unreliable.

**Conclusion**: at short horizons (3-14 days) the combination looks
stronger than funding alone - but trust in results there is already low
(30-day instability seen in prior hypotheses, plus n=11). At our only
horizon actually confirmed by walk-forward (90 days), adding RSI does
NOT improve the result (worse than funding alone), and at 180 days the
combination goes negative outright. Not complicating H1b with this
combination - no clear improvement where the effect is already confirmed.

---

## H3 - DVOL as a filter/confirmation for H1b

**Status**: mixed - confirms at 90 days, contradicts at 30 (2026-09-07)

**Formulation**: among days with H1b's signal (crowded shorts), is the
effect stronger when DVOL (options volatility) is ALSO elevated (above
its own 90-day median) compared to when DVOL is calm? A direct test of
PLAN.md's original idea - options as a "smart money" filter. Data
constraint: only available from 2021-06-21 (DVOL exists from 2021-03-24
+ 90 days for the percentile) - less data than the original H1b.

**Result** (`backtest_h3_dvol_filter.py`, n = independent episodes):

| Horizon | Group | n (episodes) | Return Delta | Large-rally-frequency Delta |
|---|---|---|---|---|
| 90 days | DVOL also stressed | 35 | **+14.43** | **+17.68 pp** |
| 90 days | DVOL calm | 53 | +3.42 | +3.88 pp |
| 30 days | DVOL also stressed | 35 | +0.93 | -6.86 pp |
| 30 days | DVOL calm | 53 | +2.41 | +5.10 pp |

**Conclusion**: at 90 days the hypothesis is confirmed even more
strongly than on raw days (the effect is now ~4x higher in the
options-confirmed group, was 2-3x before). At 30 days it remains
unstable/ambiguous (one of the two metrics flipped sign after
recomputing on episodes). This is now the third case (after H1a, H1b)
where the 30-day horizon gives an unstable/contradictory result - looks
like a systematic property of this horizon in the data (perhaps a
squeeze needs more time to unwind), not a coincidence of one hypothesis.
Not testing further at 30 days without a dedicated investigation of
this quirk.

---

## Methodological note: we don't yet have a true out-of-sample test (2026-09-07)

Honest admission: everything done so far (exploratory pass + year-by-
year walk-forward) used the ENTIRE history at once, including the most
recent data - a robustness-over-time check, not the blind out-of-sample
test PLAN.md promised from the start. "Future" data has already been
seen - retroactively declaring some past chunk "out-of-sample" would be
dishonest.

**Protocol going forward** - using real future data that doesn't exist yet:

Hypotheses **frozen** as of 2026-09-07, exact parameters:
- **H1b**: funding_percentile_90d < 0.05, 90-day horizon
- **H3**: same + DVOL_percentile_90d > 0.5 ("options also stressed" filter)

**Update (2026-09-07)**: decided not to make this a blocking requirement
(too slow for the project's pace, and walk-forward across 6 distinct
market regimes already provides a meaningful robustness check). Instead
of a strict requirement - a light, free habit: re-run these same frozen
tests on new data every month or two (the auto-collector runs in the
background anyway) and log the result here as an optional extra check.
Not a guarantee against fitting a hypothesis to the data, but better
than nothing and costs no real time.

## Methodological note: multiple comparisons (2026-09-07)

The more hypotheses we test, the higher the chance of stumbling on a
"pattern" that isn't real - simple probability: testing 20 random ideas
at a "significant at 5%" threshold will turn up a couple of hits even
with zero real effect anywhere. This is exactly what PLAN.md warned
about from the start (overfitting/data snooping).

**Tested-hypothesis counter** (to calibrate trust in new "findings" -
the longer the list, the more skeptical to be):
1. H1a - rejected
2. H1c - rejected
3. H1b - promising, but not rigorously proven (see its section - the
   significance tests disagree)
4. H3 - mixed (confirms at 90d, contradicts at 30d)
5. H5 - inconclusive/not useful (doesn't improve H1b at 90d, unreliable
   sample at short horizons)
6. H2 - rejected (RSI works opposite the textbook assumption)
7. H6a - rejected (DVOL panic -> bounce, no effect)
8. H6b - **best result**, walk-forward 5/5 + both significance tests
   (DVOL complacency -> drops), tested only on BTC so far
9. H4 - rejected (Bollinger, same momentum picture as H2)

**Update (2026-09-07)**: H1b rejected as a universal pattern across 20
coins (p=0.0019, sign negative). H6b confirmed on ETH (the second
available asset) and in its mechanism - the project's best, most
validated result to date.

10. H7 - rejected (funding rate velocity, directions disagree between
    assets the same way the dead H1b did)
11. H8 - interesting but WITHOUT a causal explanation (the Wednesday
    effect, held with caution, no decisions built on it without confirmation)
12. H10 - confirmed as a refinement of H6b (without a rally - stronger
    than after one)
13. H11 - rejected (trading volume doesn't predict the next day)
14. H12 - inconclusive (ETH/BTC ratio - an impressive raw p-value that
    didn't survive episodes/walk-forward, a methodology lesson)
15. H13 - rejected (futures/spot basis, likely redundant with funding
    rate, which already "trims" basis every 8 hours)
16. H14 - inconclusive (realized volatility across 20 coins - an
    impressive pool (p=0.0000) that didn't survive walk-forward, the
    effect concentrated in 2021-2022, absent in 2024-2026)

At 16 hypotheses tested - 8 rejected (H1a, H1c, H2, H4, H6a, H7, H11,
H13), plus H12 and H14 inconclusive after scrutiny (both cases where an
impressive raw result didn't survive the routine of episodes/walk-
forward), H1b rejected as a universal pattern (alive only on BTC/a
handful of coins), H6b our leading, most-validated result (plus H10 as
its refinement), H3/H5 are refinements of the already-dead H1b (not
retroactively revised, just not built upon further), H8 a statistically
robust but unexplained finding in its own caution category. A normal
ratio for this many tests. If 8 of the next 10 hypotheses suddenly turn
out "significant," that's a reason to suspect a methodology error, not
to celebrate.

---

## H1 - Extreme funding rate -> price reversal

**Status**: split - see H1a (rejected) and H1b (promising, needs walk-forward)

**Formulation (original)**: when funding rate sits at an extreme
relative to its own 90-day history (percentile > 95 - the crowd is
crowded long, or < 5 - crowded short), price moves against the crowded
side with elevated probability and magnitude over the following N days.

**Data**: `funding_percentile_90d` (`indicators` table) + price
(`candles`). Full 2019-2026 history.

**Test method** (`backtest_h1.py`, exploratory pass over the entire
history at once, NOT walk-forward):
- The two sides are scored separately, never blended into one number
- For each signal day and horizon N in {3,7,14,30,60,90,180}: the
  actual price return over N days (not a binary right/wrong)
- Compared against the mean/median return across ALL days of history at
  the same horizon (baseline - controls for the market's general drift)
- Separately: the frequency of LARGE moves (>=5%) in the expected
  direction, signal vs baseline
- Caveat: signal days aren't independent (funding stays extreme for
  several consecutive days), and windows overlap heavily at longer
  horizons - this is exploration, not final confirmation

**Result (2026-09-07, BTCUSDT, n~154-178 signals per horizon)**: the
original symmetric hypothesis split into two very different halves -
see H1a and H1b below.

**Conclusion**: the hypothesis in its original (symmetric) form is
rejected. Split into two separate hypotheses for further work.

---

## H1a - Crowded LONGS -> reversal down

**Status**: inconclusive, needs walk-forward (updated 2026-09-07, a
methodology error was fixed - see below)

**First attempt (flawed)**: originally only checked "did large-drop
frequency fall below baseline" and concluded "rejected." This was
premature - one narrow metric can't distinguish "will rally," "will
just have a smoother decline" (same direction, without sharp crashes),
and "volatility simply dropped in both directions." Recomputed
symmetrically: mean, median, volatility (std), and large-move frequency
UP/DOWN separately, each against its own baseline.

**Result v2 - the effect is horizon-dependent**:
- 7-30 days: volatility BELOW baseline, large moves rarer in both
  directions - looks like general calm, not a reversal
- 60-90 days: volatility unchanged, but large RALLIES noticeably more
  frequent than baseline (+6.6...+10.0 pp), large drops noticeably rarer
  (-5.4...-11.1 pp) - looks more like continued gains than just "calmer"
- 180 days: a sharp jump in the BASELINE's volatility (44.75 -> 87.32) -
  likely distorted by one or two large market moves at the end of the
  dataset (2025-2026). This horizon isn't trusted yet

**Conclusion**: there's an effect, but it's horizon-dependent and
possibly distorted by a small number of independent periods (the same
window-overlap and low-independence risk as H1b). See H1c below - this
idea was carried through to a full walk-forward test.

**Additional check (2026-09-07) - absolute, not just relative, return**:
an important methodological point from the discussion - "signal beats
baseline" (an edge) does NOT equal "the trade is profitable." Checked
`mean_return` ON ITS OWN (without subtracting baseline) for the trade
H1a's original hypothesis implies - shorting after the signal: price
return was POSITIVE at all 7 horizons (0.99% at 3 days -> 26.83% at
180). So an actual short after this signal would have LOST money on
average over this period, despite some relative "edge" in large-drop
frequency. Confirms the inconclusive verdict / not testing this as a
"short hypothesis" in its original form - whatever is there, it isn't
about shorting.

For comparison - H1b (buying after the "crowded shorts" signal):
`mean_return` is also positive at every horizon AND beats baseline at
every one without exception - this is what separates H1b from H1a:
there, the trade isn't just non-lossy, it outpaces the general market
uptrend, not merely "loses less than a random trade."

---

## H1c - Crowded LONGS -> buy (follow the crowd)

**Status**: rejected/no edge (2026-09-07)

**Formulation**: since returns after the "crowded longs" signal are
often positive (see H1a), maybe that's not an absence of effect but a
BUY signal (follow the crowd rather than fade it)? Proposed in
discussion - tested with the same rigor (walk-forward) as H1b rather
than by eye.

**Walk-forward, 90-day horizon** (n = independent episodes, not raw
days, 4-18 per period):

| Period | n (episodes) | Return Delta | Large-rally-frequency Delta |
|---|---|---|---|
| 2019-2020 | 18 | **-4.34** | **-22.56 pp** |
| 2021 | 14 | **-5.13** | +3.42 pp |
| 2022 | **4** | +28.97 | +26.71 pp |
| 2023 | 9 | +3.56 | +4.63 pp |
| 2024 | 12 | +1.14 | +3.69 pp |
| 2025-2026 | 12 | +3.36 | -8.33 pp |

**30-day horizon**: similarly unstable, signs jump around by period.

**Conclusion**: unlike H1b, the signs are unstable across periods (on
episodes the picture became even more clearly "noisy" than on raw days
- 2019-2020 and 2021 flipped from weakly positive to negative), metrics
within a period sometimes contradict each other, and 2022 has only 4
independent episodes - not enough for a conclusion. Looks like noise,
not a pattern. The "positive return after the signal" in the exploratory
pass was explained by the market's general uptrend (the baseline is
almost always positive too), not a real signal effect. Not pursued further.

---

## H1b - Crowded SHORTS -> rally up

**Status**: rejected as a universal pattern - across 20 coins the pooled
result is statistically significantly NEGATIVE (see the check at the
end of this section). Possibly works only on BTC/a handful of large
coins, doesn't generalize (updated 2026-09-07)

**Result**: both the mean return and the frequency of large (>=5%)
upward moves beat the baseline at almost every horizon (except a small
negative in large-move frequency at 30 days), with the large-move-
frequency edge GROWING with horizon (+3.2 pp at 3 days -> +8.6 pp at 90
days -> +8.0 pp at 180 days).

**Next step**: run through full walk-forward (not a single pass over
the whole history) - check the effect is stable across different market
regimes (bull and bear periods separately), not carried by one lucky
stretch of history.

**Walk-forward, 90-day horizon (`backtest_h1b_walkforward.py`)**: the
baseline is computed separately for each period (over all days in that
period, not just signal days), to avoid confusing the signal's effect
with "just a good year for the market." n = number of INDEPENDENT
EPISODES (adjacent signal days collapsed into one event, see the
autocorrelation note), not raw days:

| Period | n (episodes) | edge_mean | edge_big_up_freq |
|---|---|---|---|
| 2019-2020 (COVID crash) | 7 | +52.46 | +13.16 pp |
| 2021 (bull -> correction) | 10 | +37.54 | +43.42 pp |
| 2022 (bear, Luna/FTX collapse) | 15 | -5.63 | -3.29 pp |
| 2023 (recovery) | 15 | +5.82 | +6.85 pp |
| 2024 (ETF rally) | 19 | +11.50 | +8.51 pp |
| 2025-2026 | 26 | +4.89 | +12.82 pp |

5 of 6 periods show a positive edge, across different regimes (not just
bull markets). The single exception (2022) is substantively explainable:
that crash was driven by fundamental news (bankruptcies), not purely
technical overheated positioning - the signal wasn't expected to work
there (on episodes, 2022's edge became slightly more clearly negative
than on raw days, but the overall conclusion doesn't change). This is
the first real confirmation of the effect, not just an average over one
lucky period.

**Walk-forward, 30-day horizon** - far less stable: the sign of the
large-rally-frequency edge swings by period (2021: -7.49 pp, 2023: -3.59
pp), and in the most recent period (2025-2026) the effect REVERSES
notably negative (edge_mean -3.38, edge_big_up -18.65 pp).

**Conclusion**: H1b at the 90-day horizon looks like a real, consistent
pattern (not a perfect one - the per-period n is small, more checks
needed). At the 30-day horizon it's unreliable, including a worrying
reversal in the most recent period. Practical takeaway: if using H1b as
a signal, anchor to the medium-term (90-day) rather than short-term
(30-day) horizon.

**Statistical significance check (2026-09-07, 90-day horizon)**: 159
"raw" signal days collapsed into **92 independent episodes** (adjacent
days with extreme funding count as one event, not several) - the
numbers barely changed (mean 21.52% vs 22.36% on raw days), so the
effect isn't just double-counting one event.

The formal tests disagree:
- t-test (compares means, sensitive to outliers): **p=0.134** - not
  significant at 5%
- Mann-Whitney U (compares rank distributions, robust to outliers):
  **p=0.018** - significant at 5%

95% CI for the signal group's mean return: [12.76%, 30.27%] - not zero,
but overlaps the baseline (14.64%).

The disagreement between tests is explained by heavy tails (a couple of
very high-return episodes swing the mean without affecting the more
robust rank test). **Honest overall status: probably a real effect, but
not rock-solid proof** - not "confirmed," but "promising, needs more
data/episodes for a confident conclusion."

**Downgrade after testing on 17 coins, then 20 (2026-09-07,
`backtest_h1b_multi_symbol.py`, 90-day horizon)**: downloaded history
for the top 20 crypto perpetuals on Binance (excluding tokenized
traditional assets like gold/stocks). 3 coins younger than ~400 days
were swapped for long-established ones (ADAUSDT, LTCUSDT, AVAXUSDT) -
20 coins total with sufficient history.

Only **8 of 20** coins show a positive edge, and BTC itself (+6.87) is
more modest than several others (SOL +28.29, BNB +22.67). All 3 new
coins (ADA -28.28, LTC -14.10, AVAX -44.47) came out negative.

Pooled sample (**1186 episodes across 20 coins**, each episode's excess
return relative to its OWN coin's baseline): mean excess return
**-10.46%**, 95% CI **[-17.03%, -3.89%]** - entirely negative, doesn't
cross zero. **t-test p=0.0019 - significant**.

**Final conclusion**: across the broader crypto market, H1b works
statistically significantly in the OPPOSITE direction from the original
hypothesis - not just "unconfirmed," but significantly negative when
pooled across assets. Status: **rejected as a universal pattern**. What
looked like "derivatives mechanics" is more likely a BTC-specific
quirk (possibly shared with SOL/BNB) in this period rather than a
fundamental crowded-positioning effect on any asset. DOGE showed an
extremely negative edge (-50.80) - likely a distorting one-off period,
not investigated further.

Additional process note: the hypothesis was first seen as promising
(exploratory pass + walk-forward), and only then tested for formal
significance - this isn't a fully blind check, closer to the data-
snooping PLAN.md warns against.
