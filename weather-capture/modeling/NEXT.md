# What this project is actually testing — and what's proven vs assumed

Read this before adding another demand-forecast decimal.

## The real thesis (not "forecast demand well")

Forecasting CAISO demand better than CAISO is worth ~nothing by itself. CAISO's
forecast is an operational input, not a price; you can't trade against it. The
only path to signal is:

> Does a **net-load surprise** (demand − wind − solar), computed with **strictly
> gate-closure information**, predict the **DA→RT price spread** in the ramp
> hours, **incrementally over the market's own implied forecast**, by enough to
> survive costs?

Four conjunctions. Each can independently kill the project. Demand accuracy is
**necessary, wildly insufficient**, and already ~done.

## Status of each link

| # | Link in the chain | Status |
|---|---|---|
| 0 | Forecast gross demand competitively | ✅ done — see `iso_benchmark_summary.md` |
| 1 | **Clean gate-closure test** — does the edge survive when NO feature is fresher than CAISO's DAM gate (~10:00 day-ahead)? | ✅ DONE — `gate_clean_test.md`. VERDICT: edge is NOT real alpha. In the evening ramp (the price-relevant hours) CAISO beats us (~1.7%); our aggregate "edge" was CAISO's midday solar miss + our own latency leak. |
| 2 | Net-load target (demand − wind − solar), not gross | ✅ DONE — `netload_diagnostic.py`, `netload_basis.md`. Solar error compounds MIDDAY (45–54% MAPE) not in the ramp; evening net forecast is CAISO's strong zone (~2.2%, near-zero bias). |
| 3 | Does net-load surprise predict DA→RT spread in ramp hours? | ✅ DONE — `price_spread_verdict.md`. VERDICT: real, economically-correct, monotonic signal (+$6.22/MWh Q5−Q1 ramp) BUT placebo (overnight) captures 72% of it → mostly generic volatility; clean increment ~$1.76 vs $25 spread noise; sign-agreement ~0.56. **No exploitable edge net of costs.** |
| 4 | ...incrementally over the market's implied forecast? | ⛔ moot — signal too small/non-specific to reach this test. |
| 5 | ...net of bid-ask, congestion, crowding, execution? | ⛔ moot — nothing to cost out. |

## OVERALL VERDICT (2026-07-26): chain ran end-to-end, no tradeable edge

The full thesis was tested in order and the honest conclusion is **negative**:
the market prices the evening net-load expectation about as well as CAISO
forecasts it (~2.2%), and the residual surprise→spread signal is too small and
too non-specific (placebo-confirmed) to trade net of costs. This is a *clean*
negative — reached with every link tested rather than assumed. The pipeline,
data, and diagnostics are all reusable if a sharper question (below) is worth
pursuing.

## What could still change the verdict (not started, lower priority)

- **Node-level prices** (not the SP15 hub) where congestion makes spreads larger
  and less efficient — the hub is the most-arbitraged point.
- **Tail/event conditioning**: the mechanism may only pay in rare high-surprise
  ramp events (heatwaves), not on average. Condition on |surprise| > threshold.
- An **ex-ante surprise forecast that beats CAISO in the ramp** — the gate-clean
  test says we don't have one; this would be the prerequisite for any real trade.

---

## (historical) original required order — all three now complete


## Required order (cheapest-highest-info first)

1. **Gate-closure clean test** (an afternoon). Re-run the day-ahead-honest model
   aligning every feature to CAISO's DAM gate timestamp: weather = the forecast
   *vintage issued before gate*, load history = most recent actual available at
   gate (~28h stale for late operating hours, not 24h). If the 2.2-pt edge over
   DAM survives → real. If it collapses → the "edge" was latency. **You cannot
   tell which world you're in from current numbers.** Do this before believing
   anything downstream.

2. **Net load.** Only meaningful if (1) holds. Rebuild the target as
   demand − wind − solar using CAISO renewable forecasts + actuals. Expect the
   error to concentrate hard in the evening ramp (solar forecast error
   compounding onto demand error) — that concentration IS the signal, or its
   absence kills the thesis.

3. **Price, last.** DA→RT spread. Ask whether net-load surprise predicts spread
   sign/magnitude in ramp hours, *after* removing what the DA price already
   implies about expected net load. This is the only step that can produce
   "alpha," and it's the one most likely to be zero.

## Honest self-assessment (2026-07-26)

The pipeline is real and the instincts are right, but the work so far proves the
**necessary** condition (can build the machine, forecast demand competitively)
and has NOT touched the **sufficient** ones (gate-clean edge, net-load, price,
market-relative, cost-net). The ISO benchmark was the correct first increment —
it saved us from building on the fake "we're 3x better than CAISO" headline. The
next correct increment is the gate-closure clean test, NOT more demand tuning and
NOT jumping to price.
