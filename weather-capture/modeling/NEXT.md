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
| 1 | **Clean gate-closure test** — does the edge survive when NO feature is fresher than CAISO's DAM gate (~10:00 day-ahead)? | ❌ REQUIRED NEXT. Current "day-ahead" model uses `previous_runs` temp + 168h lag, plausibly fresher than gate. If edge collapses here it was information latency = fake alpha. |
| 2 | Net-load target (demand − wind − solar), not gross | ❌ not started. Pull CAISO wind/solar forecast + actual (OASIS SLD_REN_FCST / renewables). |
| 3 | Is net-load *surprise* correlated with DA→RT spread in ramp hours? | ❌ not started. Pull DA (PRC_LMP DAM) + RT (PRC_INTVL_LMP / RTM) prices. |
| 4 | ...incrementally over the market's implied forecast? | ❌ not started. Market already prices consensus demand. Must beat the *implied* net-load forecast, not CAISO's. |
| 5 | ...net of bid-ask, congestion, crowding, execution? | ❌ the gap between a backtested spread edge and a tradeable one. |

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
