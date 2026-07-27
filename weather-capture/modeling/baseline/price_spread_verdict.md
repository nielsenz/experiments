# Step 3 — does net-load surprise predict the DA→RT spread? VERDICT

Pulled SP15 hub prices (DA hourly PRC_LMP, RT 5-min PRC_INTVL_LMP → hourly),
2025-01 → 2026-07, 13,695 hours aligned with net-load. Tested whether net-load
surprise (net_ACT − net_DAM, + = more net load than the DA market forecast)
predicts the spread (RT − DA).

## Result: a real but small, and largely NON-specific, signal

**By-hour Pearson r** (surprise vs spread): positive and strongest in the evening
ramp — hr19 r=+0.34, hr20 +0.17, hr21 +0.24, sign-agreement rising to 0.58. The
direction is economically correct (under-forecast net load → RT above DA).

**Quintile monotonicity (ramp 17–21):** clean and monotonic —

| surprise quintile | mean surprise | mean spread |
|---|---|---|
| Q1 (over-forecast −874 MWh) | −874 | −$5.07 |
| Q3 | +164 | −$1.20 |
| Q5 (under-forecast +1246 MWh) | +1246 | +$1.15 |

Q5−Q1 = **+$6.22/MWh**. The mechanism holds.

## Why this does NOT clear the bar

1. **Placebo fails.** The SAME quintile analysis on OVERNIGHT hours (0–5), where
   there is no ramp mechanism, gives Q5−Q1 = **+$4.46/MWh** — 72% as large as the
   ramp effect. So most of the "signal" is generic co-movement: volatile net-load
   hours are volatile-spread hours, ramp or not. The ramp-SPECIFIC increment is
   only ~$1.76/MWh.

2. **Signal ≪ noise.** Ramp spread has **std $24.63** (mean −$2.13, P10 −$12.1,
   P90 +$6.9). A $6 quintile swing — let alone a $1.76 clean increment — lives
   deep inside ±$25 of per-hour noise. Sign-agreement ~0.56 is barely above a
   coin flip.

3. **Not net of costs or crowding.** This is CAISO's OWN forecast miss vs the
   realized spread — the most generous possible version (perfect hindsight of the
   surprise). A tradeable version needs to FORECAST the surprise ex-ante (the
   gate-clean test showed we don't beat CAISO in the ramp, so we can't), then
   survive bid-ask, the DA/RT commitment, congestion, and the fact that this is
   the single most-studied trade on this grid.

## Overall project verdict (the honest close)

- The empirical facts are real: CAISO systematically under-forecasts midday gross
  load (BTM solar), net-load error compounds hardest MIDDAY not in the ramp, and
  net-load surprise does co-move with the DA→RT spread in the economically
  correct direction.
- BUT: the ramp — the only place a retail-scale trade could live — is where CAISO
  already forecasts net load to ~2.2%, the surprise→spread signal is mostly
  generic volatility (placebo-confirmed), and the clean increment ($1.76) is tiny
  vs $25 spread noise.
- **Conclusion: no exploitable edge demonstrated.** The market prices the evening
  net-load expectation about as well as CAISO forecasts it, and the residual is
  too small and too non-specific to trade net of costs. This is the "if it's no,
  that's also the finding, and better to know now" outcome — reached with the
  chain intact rather than assumed.

## What WOULD change the verdict (honest next steps, not started)

- Node-level (not hub) prices where congestion makes spreads larger and less
  efficient — the hub is the most-arbitraged point.
- Tail focus: the mechanism may only pay in the rare high-surprise ramp events
  (heatwave stress), not on average. Condition on |surprise| > threshold and
  measure spread capture in those events only.
- A genuinely ex-ante surprise forecast that beats CAISO in the ramp — which the
  gate-clean test says we do not currently have.
