# Gate-closure clean test — VERDICT: the demand "edge" is not real alpha

Ran the cheapest sufficient form: no new data, split our error and CAISO's error
by (a) gate-cleanliness of our weather feature and (b) local hour. Truth = OASIS
ACTUAL. Model = day-ahead-honest (no lag24), single 70/30 expanding split.

## The latency map (why the split matters)

Our `previous_day1` weather feature for a target at local hour h is issued ~h
o'clock on D-1. CAISO's DAM gate closes ~10:00 PT on D-1. So our feature is:
- gate-CLEAN for target hours 00–10 local (issued at/before gate)
- LEAKING for target hours 11–23 local (issued AFTER gate, up to +13h fresher),
  worst in the evening ramp.

## MAPE by local hour (test set, vs OASIS ACTUAL) — robust to PT offset

| local hr | ours | CAISO | edge | note |
|---|---|---|---|---|
| 00–06 (clean, overnight) | ~2.6% | ~2.6% | ≈ 0 | **no edge where it's clean** |
| 07–10 (clean→gate) | 3–7% | 5–22% | + | CAISO degrading into solar |
| 09–15 (LEAK, solar) | 6–9% | 18–27% | +10 to +18 | contaminated + solar miss |
| 17–21 (LEAK, evening ramp) | 3.3% | **1.7–2.3%** | **−1 to −1.5** | **CAISO BEATS us** |

## Verdict

1. **No edge in the clean overnight hours.** Where our feature is honestly
   pre-gate and the problem is easy, we MATCH CAISO (edge ≈ 0, sometimes slightly
   negative). Correct null — no fake alpha manufactured where there shouldn't be.

2. **The aggregate "2.2-pt edge" is CAISO's midday solar miss.** CAISO is
   excellent (1.5–3.5%) everywhere except the 09–15 solar window, where it hits
   18–27%. Our whole edge is that window — and it's exactly where our feature
   leaks, so it's partly a latency artifact AND lands in hours that don't set the
   evening price.

3. **In the evening ramp (17–21) — the ONLY hours the thesis cares about —
   CAISO forecasts to ~1.7% and WE CANNOT BEAT IT**, despite our feature being
   maximally leaked (freshest) there. If latency were carrying us we'd win here;
   we lose by ~1.3 pts.

**Conclusion: link zero (competitive day-ahead forecast that matters for price)
does NOT hold in the price-relevant hours.** The demand-forecast "edge" was a
combination of (a) CAISO's solar underprediction in non-ramp hours and (b) our
own latency leak. This is the "better to know now" result.

## What this does and does NOT kill

- It KILLS the claim "we forecast demand better than CAISO in a way that could
  matter for price." We don't, in the ramp.
- It does NOT kill the project's core empirical fact: CAISO systematically
  underpredicts GROSS load midday (solar), which is a real net-load signature.
  But CAISO's EVENING forecast is already very good, so the tradeable question
  shrinks to: is there residual net-load surprise in the ramp that CAISO (and
  therefore the market) has NOT already priced? Base rate: probably not, since
  CAISO's evening MAPE is ~1.7%.

## Implication for steps 2 (net load) and 3 (price)

Still worth doing, but with lowered priors and a sharper question:
- NET LOAD: the interesting residual is whatever CAISO's ~1.7% evening error
  still contains. Subtract CAISO's OWN wind/solar forecast to form CAISO-implied
  net load, and ask whether OUR net-load estimate diverges from it in the ramp in
  a way that later verifies. Do NOT just rebuild our model on a net-load target
  and admire a MAPE — that repeats the mistake.
- PRICE: the honest test is whether CAISO's (small) evening net-load error, or
  our divergence from CAISO-implied net load, correlates with DA→RT spread. If
  CAISO's evening forecast is ~1.7% and the market prices it, expect ~0. Better
  to confirm ~0 than to assume signal.
