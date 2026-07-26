# ISO benchmark — the honest scorecard

**Question:** our demand model reported ~3.3% MAPE. Is that good? Meaningless
without a denominator — so we pulled CAISO's OWN day-ahead forecast and scored
everything against the SAME truth (OASIS `CA ISO-TAC` ACTUAL, SYS_FCST_ACT_MW),
over rolling-origin folds.

## The number that matters

| forecaster | MAPE (vs OASIS ACTUAL) | validation |
|---|---|---|
| CAISO day-ahead forecast (DAM) | **6.51%** | full history, 28,386 h |
| our model, lag-24 | **3.55% ± 0.20%** | 6-fold rolling |
| our model, day-ahead-honest (no lag-24) | **4.33% ± 0.20%** | 4-fold rolling |

Per-fold day-ahead MAPE: 4.37, 4.25, 4.09, 4.62% (Jan 2025 → Jul 2026). Tight.

## Reading it — carefully

- **The single-split fear is resolved.** The baseline's 3.3% was not a lucky
  Jan–Jul draw: rolling folds give 3.55% ± 0.20% across multiple seasons.
- **We appear competitive-to-better than the ISO's own forecast**, even after
  dropping the lag-24 crutch (4.33% vs 6.51%). Dropping lag-24 cost only 0.8
  points, so weather + week-ago-load + calendar carry most of the skill —
  autocorrelation was NOT the whole story.

## ⚠️ The caveat that outranks all the others (see modeling/NEXT.md)

This comparison is **NOT gate-closure clean.** Our "day-ahead" model uses a
`previous_runs` temperature vintage and a 168 h load lag that are plausibly
FRESHER than the information CAISO had at its DAM gate (~10:00 the prior day). So
4.33% vs 6.51% may be measuring **information latency, not skill** — the single
most common way energy backtests manufacture fake alpha.

**The 2.2-point edge is UNCONFIRMED until it survives a strict gate-closure
re-run.** If it survives, it's real. If it collapses toward zero, the "edge" was
look-ahead. We cannot tell which from these numbers. This is the required next
increment — NOT more demand tuning, NOT jumping to price.

## And even if the edge survives — "so what?"

Beating CAISO's demand forecast pays nothing (it's an operational input, not a
price). The project only matters if a **net-load surprise** predicts the
**DA→RT spread** in ramp hours, **incrementally over the market's implied
forecast**, **net of costs**. Demand accuracy is necessary and wildly
insufficient. Full chain and priority order in `modeling/NEXT.md`.

## Where the ISO's error lives (this is the thesis)

CAISO's day-ahead error is **solar-shaped**: ~2% overnight, peaking ~27% at
midday local (solar peak), cross-validated by EIA's own DF-vs-D at 8.8% for the
same month. Both forecasters under-predict gross load by ~8 GW when behind-the-
meter solar is highest. That midday/evening structure is the net-load surprise —
and the reason the next target is **net load**, not gross demand.

## Method notes

- Truth = OASIS `CA ISO-TAC` ACTUAL for every metric (not EIA), so the ISO
  forecast is judged against its own actuals — immune to the ~3.35% EIA/OASIS
  boundary offset documented in `energy/README.md`.
- Rolling-origin: expanding train window, next block as test, walk forward.
- Two model variants isolate how much skill came from load autocorrelation
  (lag-24) vs genuine day-ahead-available signal.
- Firewall respected: day-ahead `previous_runs` temperature; load lags ≥168 h
  (day-ahead variant) or ≥24 h (lag24 variant); never the target hour. But see
  the gate-closure caveat above — firewall ≠ gate-clean.
- Authoritative day-ahead fold numbers captured in `dayahead_folds.txt` (the
  in-repo `iso_benchmark.py` is compute-fragile in the mobile sandbox and may be
  OS-killed mid-run; per-fold subprocess runs produced the recorded figures).
