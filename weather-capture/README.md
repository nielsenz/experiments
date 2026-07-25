# weather-capture

Daily capture of Open-Meteo **ensemble** forecasts for five locations in
California and Nevada, committed to this repo as gzipped raw JSON.

Open-Meteo retains individual ensemble members for only about three days. This
job accumulates a forecast history that cannot be bought or backfilled after the
fact. **A missed day is gone permanently**, so everything here is built around
capturing something and failing loudly when it doesn't.

## What gets captured

| | |
|---|---|
| Endpoint | `https://ensemble-api.open-meteo.com/v1/ensemble` |
| Locations | Fresno CA, Sacramento CA, Los Angeles CA, Las Vegas NV, Henderson NV |
| Models | `gfs025`, `ecmwf_ifs025`, `icon_seamless` |
| Hourly variables | `temperature_2m`, `shortwave_radiation`, `cloud_cover`, `wind_speed_100m` |
| Horizon | `forecast_days=7`, plus `past_days=3` of trailing hours |
| Schedule | 06:00 and 18:00 UTC, plus manual dispatch |

15 files per day (5 locations × 3 models), one HTTP request each.

```
weather-capture/data/2026-07-25/
├── _manifest.json                     # what succeeded, what failed, and why
├── fresno-ca_gfs025.json.gz
├── fresno-ca_ecmwf_ifs025.json.gz
└── ...                                # 15 files
```

The response bytes are written through **untouched**. Nothing is parsed,
reshaped, or modelled. (Each response is run through `json.loads` once to
confirm it is well-formed — an HTML error page must never land in the archive
looking like data — but what gets stored is always the original bytes.)

## How each run works

1. For each of the last **3 days**, check whether each of the 15 files already
   exists and is intact. Skip it if so, fetch it if not. This is what makes a
   skipped or delayed run self-healing, and it's why the 18:00 job normally does
   nothing: on a healthy day, the 06:00 job already got everything.
2. Each fetch is isolated. One bad response never aborts the other fourteen.
   Failures retry 3× with exponential backoff and jitter; calls are spaced ~2s
   apart to stay polite.
3. Results are recorded in the date's `_manifest.json` after **every** fetch, so
   a job killed mid-run still leaves an accurate record.
4. Whatever was captured is committed and pushed.
5. `check_gaps.py` runs last. If the last 3 days aren't complete, **the workflow
   fails** — that's the red X.

The gap check runs *after* the commit on purpose: a failing check must never
cost you the data the run did manage to capture.

## Verifying the first run

The first run performs the backlog fill on its own — it fetches the whole
trailing 3-day window, which is the entire backlog that exists, since members
older than that are already gone upstream.

1. **Actions → weather-capture → Run workflow** (leave both date inputs blank).
2. Watch the log. You want to see 15 `ok` lines and a summary like
   `2026-07-25: 15 fetched, 0 already present, 0 failed`.
3. Confirm the final step prints `all 3 day(s) complete.` and the job is green.
4. Check the commit landed: `weather-capture/data/` should have three dated
   directories with 15 files plus a `_manifest.json` each.
5. Spot-check that a file is real data:

   ```bash
   gzip -dc weather-capture/data/$(date -u +%F)/fresno-ca_gfs025.json.gz | head -c 400
   ```

   You should see `latitude`, `hourly_units`, and `temperature_2m_member01`,
   `..._member02`, and so on. Many members per variable is the whole point — if
   you only see one series per variable, the ensemble request isn't doing what
   it should.

6. Then just confirm the next scheduled run goes green on its own.

To audit the whole archive at any time:

```bash
python weather-capture/check_gaps.py --all          # report on every date
python weather-capture/check_gaps.py --days 3 --deep # the gate the workflow runs
```

`--deep` decompresses every file to prove it isn't truncated. `--all` is a
report and never fails; the default windowed mode is the one that fails a build.

## Manual backfill

**Actions → weather-capture → Run workflow**, and set `start_date` /
`end_date` (`YYYY-MM-DD`, UTC, inclusive). Or locally:

```bash
pip install -r weather-capture/requirements.txt
python weather-capture/fetch_ensemble.py --start-date 2026-07-20 --end-date 2026-07-22
```

Existing intact files are skipped, so re-running a range is safe and cheap.

### What backfill can and cannot recover

This matters, so it's worth being blunt about it.

The endpoint always serves the **current** model run. If you backfill
2026-07-20 on 2026-07-25, you do **not** get the forecast that was issued on
07-20 — that artifact is gone and nothing can bring it back. You get today's
run, whose `past_days=3` window happens to cover some of those valid hours.

So a late capture recovers *coverage of past valid hours*, never *the run as it
was issued*. Files captured late are flagged `"late": true` in the manifest and
show as `[late]` in the gap report, so they're never silently mistaken for an
on-time capture. This is also why gaps are worth chasing the same day: within
about three days a gap is genuinely repairable, and after that it isn't.

## ⚠️ GitHub disables scheduled workflows in inactive public repos

**GitHub automatically disables `schedule` triggers in a public repository after
60 days with no commit activity.** You get an email when it happens, and it is
easy to miss. If this repo goes quiet, the capture stops silently — which is the
one failure mode the gap check cannot catch, because a job that never runs
cannot fail.

This job commits on most days, which itself counts as activity, so in normal
operation the 60-day clock never runs down. The risk is a long outage: if
fetching breaks for two months, the workflow gets disabled on top of it, and
fixing the fetch alone won't bring it back.

If it happens: **Actions → weather-capture → Enable workflow**, then dispatch a
run manually. Worth checking the Actions tab occasionally to confirm runs are
still happening at all.

## Storage

Roughly 30–60 KB gzipped per file, ~700 KB/day, so on the order of **250 MB per
year**. Files are written once and never modified, so git deltas don't compound,
but expect the repo to be around a gigabyte after four years.

## Tests

Standard library `unittest`, with the API mocked. No network access, no test
dependencies:

```bash
python -m unittest discover -s weather-capture/tests -t weather-capture/tests -v
```

Covers retry and backoff behaviour, skip-if-exists (including refusing to skip
empty, non-gzip, or truncated files), per-fetch isolation, manifest contents,
late labelling, and gap detection.

They deliberately do **not** run in the capture workflow — a test failure must
never block a capture. Run them when you change something.

## Configuration

Everything tunable lives in `locations.json`: coordinates, models, variables,
horizon, timeouts, retry counts, and inter-request delay.

Adding a location or model changes what *future* runs fetch. It does not
retroactively invalidate history: each date's `_manifest.json` records the file
list expected when it was captured, and `--all` judges each date against its own
manifest. The windowed gate uses the current config, so a config change is
expected to be reflected within the next few days.

## Dependencies and secrets

`requests`, and otherwise the standard library. That's the whole list.

There are no secrets, tokens, or credentials in any file here, and none are
needed. The workflow authenticates using the ephemeral `GITHUB_TOKEN` that
Actions injects at runtime, scoped with `permissions: contents: write`. Nothing
is ever written to disk that shouldn't be in a public repo — the API requires no
authentication.
