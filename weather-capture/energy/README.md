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

Both serve the same underlying demand data. EIA returns years of clean hourly
JSON in a few paginated calls; OASIS requires per-day ZIP downloads and XML
parsing. EIA is far cheaper to maintain, so it is the primary source here. (A
keyless OASIS fallback can be added if the EIA dependency ever becomes a
problem.)

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
