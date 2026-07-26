# history/ — one-shot backfill

Historical data pulled once by `../backfill_history.py`. **Not** produced or
touched by the daily capture workflow, and not scanned by `check_gaps.py` — the
daily gate only looks at `weather-capture/data/`. A bug in the backfill cannot
turn that gate red, which is the entire reason this lives in its own tree.

```
history/
├── features/                        SAFE as model inputs
│   ├── previous_runs_ifs_hres/      ECMWF IFS HRES, as issued
│   └── ensemble_mean/               ensemble mean/spread (archive)
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

## The seam: archive mean/spread ≠ mean/spread from captured members

There are two sources of ensemble mean and spread in this repo, and **they are
different statistics. Do not join them into one continuous feature.**

| | where | what it is |
|---|---|---|
| `archive_ensemble_mean` | `features/ensemble_mean/` | mean/spread as published by the `*_ensemble_mean_*` models |
| `captured_ensemble_members` | `../data/` | individual members captured daily; any mean/spread is something *you* compute |

They differ in generating process, member count, and derivation. Concatenating
them produces a feature with a discontinuity at the changeover date — around when
the daily cron started — that a model will happily fit as if it were signal. The
break is invisible in the values themselves, which is what makes it dangerous.

Every manifest on both sides carries a `provenance` field
(`archive_ensemble_mean` vs `captured_ensemble_members`) so the origin travels
with the data rather than living in someone's memory. **Keep it as a feature
column, or keep the two as separate features.** Do not drop it in a join.

The daily members capture is the higher-fidelity source and is what the eventual
model should lean on; the archive mean/spread covers the period before the cron
existed. Treating them as one series is the tempting shortcut and the wrong one.

## Windows, and why they differ

| | from | why |
|---|---|---|
| CAISO spreads | 2023-05-01 | the window start |
| `historical_forecast_actuals` | 2023-05-01 | matches CAISO, for descriptive work |
| **modeling window** | **2024-01-01** | Previous Runs API does not go back further |
| `previous_runs_ifs_hres` | 2024-01-01 | the binding constraint |
| `ensemble_mean` | 2026-04-25 | **93-day archive cap** (see below) |

The modeling window is **2024-01-01**, set by the Previous Runs floor. That
gives 2+ years of deterministic as-issued forecasts against the CAISO series.

`ensemble_mean` has the shortest window and it is not a choice: the ensemble
archive is reached with `past_days`, which the API caps at **93** ('Allowed range
0 to 93'). Anything older 400s. So `start_date` must stay within ~93 days of
today, and mean/spread older than that window is simply not retrievable. **Re-run
this source periodically** to keep pushing coverage forward — it is a rolling
window, not a one-shot deep backfill like the other two.

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

## ✅ Verified against the live API (2026-07-26)

The first full backfill ran successfully against Open-Meteo. The endpoints,
variable names, and date floors in `../history_sources.json` — previously
unconfirmed because every `open-meteo.com` host was blocked from the authoring
environment — are now confirmed by real fetches, with these findings:

- **`previous_runs_ifs_hres`** — confirmed. The `_previous_day1` variable suffix
  and the 2024-01-01 floor both work; all four variables (including
  `shortwave_radiation` and `wind_speed_100m`, previously flagged as maybe
  unavailable) returned data. 155/155 monthly chunks captured.
- **`historical_forecast_actuals`** — confirmed. 195/195 monthly chunks captured
  back to 2023-05-01.
- **`ensemble_mean`** — confirmed shape, with one correction: the ensemble host
  caps `past_days` at **93** (`"Allowed range 0 to 93"`). The original
  `start_date: 2026-03-01` (≈147 past_days) 400'd on every call; it is now
  `2026-04-25`. All 5 location archives captured for each of **three** confirmed
  models: `dwd_icon_eps_ensemble_mean_seamless` (DWD ICON),
  `ncep_gefs025_ensemble_mean` (GFS), and `ecmwf_ifs025_ensemble_mean` (ECMWF).
  Note the naming is not uniform — the DWD id ends in `_seamless`, the GFS and
  ECMWF ids do not. Invalid ids return HTTP 400 ("Cannot initialize MultiDomains
  from invalid String value"), which is the cheap way to probe new candidates.

Because `past_days` anchors to today, `ensemble_mean` pulls its whole window in a
single call per location+model, written as `archive.json.gz`, with the effective
`past_days` and `as_of` date recorded in the manifest. Its 93-day window is a
rolling one — re-run it periodically to extend coverage forward.

### Not an option: Previous Runs for ensembles

Recorded here so it isn't re-investigated. The Previous Runs API covers
**deterministic models only**, with a limited variable set. There is no ensemble
equivalent — it would be roughly 2 TB for barely three months. Ensemble
mean/spread history comes from the ensemble archive above. `history_sources.json`
carries a disabled stub with the same note.
