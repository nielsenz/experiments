# energy/ — CAISO demand (the prediction target)

The energy series this whole project exists to predict. Weather (from
`../data/` and `../history/`) is the feature side; CAISO hourly demand is the
label side.

## Source

`fetch_caiso_demand.py` pulls **CAISO hourly electricity demand** from the
**EIA API v2** (`electricity/rto/region-data`, respondent `CISO`, type `D`),
stored as gzipped raw JSON, one file per month:

```
energy/data/caiso_demand/<YYYY-MM>.json.gz
energy/data/caiso_demand/_manifest.json
```

Raw bytes are written verbatim — same discipline as the weather capture. Values
are hourly megawatthours, timestamped UTC. Default window starts **2023-05-01**
to match the CAISO window referenced in `../history/README.md`.

## Why EIA over CAISO OASIS

Both serve "CAISO system demand," but they are **different products of the same
grid, not copies of one number.** EIA's `type=D` is demand for the EIA-defined
CISO balancing-authority region (timezone-normalized, gap-imputed, periodically
revised); OASIS `SLD_FCST` / `CA ISO-TAC` is CAISO's actual hourly integrated
load for the TAC-area footprint (settlement-grade, raw).

**Measured difference** (72 hrs, 2026-07-20→22, `CA ISO-TAC` vs EIA `CISO`):

| metric | value |
|---|---|
| mean \|diff\| | ~1,106 MWh (3.35%) |
| max \|diff\| | ~3,454 MWh |
| pattern | systematic, not noise — largest overnight (up to ~7%), ~0 midday |

The gap is a **boundary + integration-method difference** (which sub-areas /
imports each footprint includes — e.g. LADWP is a separate TAC area in OASIS),
not measurement error. It's a level/shape offset, not a distortion of the
demand-vs-weather *response*, which is what this project learns.

**EIA is chosen because:**
1. Consistency matters more than absolute boundary "correctness" for modeling
   demand as a function of weather — EIA is uniformly processed across its whole
   history.
2. One JSON call covers years. OASIS needs per-request ZIP+CSV, 37 TAC areas to
   filter, a ~31-day-per-call limit, and stricter rate limits.
3. The ~3% offset is harmless for a weather→demand model.

Use OASIS instead only if you need settlement-grade load, sub-LSE breakdowns
(SCE / PGE / SDGE), or CAISO's official operational record. A keyless OASIS
fallback can be added if the EIA dependency ever becomes a problem.

## Running it

Needs a **free** EIA API key (email registration, instant):
https://www.eia.gov/opendata/register.php — then set `EIA_API_KEY` in the
environment.

```bash
# from repo root
export EIA_API_KEY=...            # or set it in Minis env vars
python3 weather-capture/energy/fetch_caiso_demand.py            # 2023-05 -> today
python3 weather-capture/energy/fetch_caiso_demand.py --start 2024-01-01
```

Resumable: months already on disk are skipped unless `--force`. Retries 4× with
backoff; paginates the EIA response (5000 rows/call).

## Status

Fetcher scaffolded and validated (compiles, `--help` works, missing-key guard
fires). **Not yet run** — waiting on an `EIA_API_KEY`. Once demand data lands,
the next step is a `load_caiso()` in `../modeling/EDA/loaders.py` and a
demand-vs-weather join (demand–temperature response curve, hour/season profiles).

## Firewall note

Demand is a **label**. The same discipline as the weather firewall applies: do
not leak future demand into features. Align on UTC timestamps at join time
(convert to local for any CAISO/energy interpretation — the daily demand cycle
is a local-time phenomenon).
