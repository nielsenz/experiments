# history/ — one-shot backfill

Historical data pulled once by `../backfill_history.py`. **Not** produced or
touched by the daily capture workflow, and not scanned by `check_gaps.py` — the
daily gate only looks at `weather-capture/data/`. A bug in the backfill cannot
turn that gate red, which is the entire reason this lives in its own tree.

```
history/
├── features/                        SAFE as model inputs
│   ├── previous_runs_ifs_hres/      ECMWF IFS HRES, as issued
│   └── ensemble_mean/               ensemble mean/spread (pending)
└── verification/                    ACTUALS — never a feature
    └── historical_forecast_actuals/
```

Each series directory holds one gzipped raw JSON file per calendar month
(`2024-03.json.gz`) plus a `_manifest.json`. Bytes are stored verbatim.

## The firewall

**`verification/` must never enter the feature set.**

Open-Meteo's Historical Forecast API stitches together the first few hours of
each successive model run. That makes the result close to analysis — effectively
observations. It is *not* a lower-fidelity forecast, and it is not "what the
model knew a day ahead."

Using it as a day-ahead feature is **leakage**. A model fed that series would
score beautifully in backtest by reading something close to the answer, and then
fall over in production, where the actual day-ahead input is a real forecast with
real error. This is why there are two trees instead of one tree and a decision
deferred to modeling time.

- `features/` — as-issued forecasts. What the model predicted *before* the
  target hour. These are legitimate day-ahead inputs.
- `verification/` — actuals. Use for labels, error metrics, and verification.
  Never as an input.

The split is structural, not a convention: every source declares a `role` in
`../history_sources.json`, the role determines which tree it writes to, and

```bash
python weather-capture/backfill_history.py --verify-firewall
```

asserts the two agree. It also runs automatically at the end of every backfill.

## Windows, and why they differ

| | from | why |
|---|---|---|
| CAISO spreads | 2023-05-01 | the window start |
| `historical_forecast_actuals` | 2023-05-01 | matches CAISO, for descriptive work |
| **modeling window** | **2024-01-01** | Previous Runs API does not go back further |
| `previous_runs_ifs_hres` | 2024-01-01 | the binding constraint |
| `ensemble_mean` | 2026-03-01 | earliest available |

The modeling window is **2024-01-01**, set by the Previous Runs floor. That
gives 2+ years of deterministic as-issued forecasts against the CAISO series.

May–December 2023 has actuals and CAISO but no as-issued forecasts. Don't try to
train on it. It is there for the descriptive work that needs no weather at all —
hour × month spread heatmaps and similar.

Ensemble members from the daily capture arrive as a later refinement, once the
cron has been running a while.

## Running it

Always start with a dry run. It prints exact URLs and makes no requests:

```bash
python weather-capture/backfill_history.py --dry-run
```

Curl one of those URLs by hand and confirm the response looks right **before**
committing to a full run — see the caveat below. Then:

```bash
# one source at a time is easiest to babysit
python weather-capture/backfill_history.py --source previous_runs_ifs_hres --limit 5
python weather-capture/backfill_history.py --source previous_runs_ifs_hres
python weather-capture/backfill_history.py --source historical_forecast_actuals
```

Safe to stop and re-run at any point: completed chunks are skipped, so a re-run
picks up where it left off. Requests are paced against a rolling per-minute
budget counted in **request units**, since ensemble calls bill as roughly 4 units
each on the free tier. There is also a per-run unit ceiling; hitting it stops the
run cleanly and tells you to re-run.

## ⚠️ None of this is verified against the live API

Every `open-meteo.com` host was blocked from the environment where this was
written, so the endpoints, the variable names, and the date floors in
`../history_sources.json` are **unconfirmed**. They are all isolated in that one
config file so fixing them means editing JSON, not code.

Two specifics to check first:

- `_previous_day1` as the as-issued variable suffix on the Previous Runs API.
- The 2024-01-01 Previous Runs floor.

`ensemble_mean` ships **disabled** pending its endpoint spec — host and path are
confirmed as the same ones the daily capture uses, but the mean/spread variable
names are not yet filled in. Add them to `hourly`, flip `enabled` to `true`, and
dry-run it.
