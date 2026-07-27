# Net-load investigation — resolving the "is DAM gross or net?" question

Pulled CAISO SLD_REN_FCST (Solar+Wind, DAM forecast + ACTUAL, summed over hubs
NP15/SP15/ZP26) and checked it against the demand series, full day 2026-06-02.

## The decisive check: does DAM demand match ACTUAL demand at night (solar≈0)?

At PDT 00–05 (GMT 07–12), solar ≈ 0:
  DAM demand ≈ ACTUAL demand (e.g. 24,347 vs 25,243; 21,539 vs 22,497).
At PDT 11–14 (solar peak):
  DAM demand ≈ 19,800 but ACTUAL demand ≈ 27,900 — an ~8 GW gap.

## Conclusion (this SETTLES the earlier confusion, and confirms the benchmark)

- **DAM `SYS_FCST_DA_MW` IS a gross-load day-ahead forecast** (it equals gross
  ACTUAL at night). So the ISO benchmark comparison (DAM vs ACTUAL, both gross)
  was VALID — NOT apples-to-oranges. The 6.51% MAPE stands.
- **The ~8 GW midday DAM-vs-ACTUAL gap is REAL** and solar-shaped. CAISO's
  day-ahead GROSS load forecast systematically under-predicts the gross load that
  actually materializes at solar peak. This is the behind-the-meter (BTM) solar
  surprise: as utility-scale solar ramps, BTM solar behavior shifts gross load in
  ways the day-ahead forecast misses.
- `RENEW_FCST` solar is CAISO's UTILITY-scale dispatched solar (peaks ~19 GW),
  NOT total solar including BTM. So `gross_demand − RENEW_solar` is NOT a clean
  net load and should not be used naively (it hits implausible lows midday).

## What "net load" should mean here (for step 2)

CAISO's operational net load = gross load − (wind + utility solar). We have all
three as DAM forecast and ACTUAL:
  net_DAM = SYS_FCST_DA_MW  − RENEW_FCST_DA(Solar+Wind)
  net_ACT = SYS_FCST_ACT_MW − RENEW_FCST_ACT(Solar+Wind)
Both consistent-basis (each subtracts its own market's renewables), so
net_DAM vs net_ACT is a valid net-load forecast-error measure — apples-to-apples.

The diagnostic question (per user): rebuild net load and watch the EVENING-RAMP
residual. Does solar-forecast error COMPOUND onto demand error in the ramp
(net error > demand error), or is CAISO's evening net forecast already tight
(gate-clean test showed CAISO's evening GROSS forecast is ~1.7%)?

## Caveat carried forward

The gate-clean test verdict is unchanged: in the EVENING ramp (17–21 local),
CAISO's gross forecast is excellent (~1.7%) and we don't beat it. The midday
gap is real but midday is not where evening price is set. Net load lets us ask
whether the RAMP specifically hides residual surprise.
