#!/usr/bin/env python3
"""
Fetch CAISO hourly electricity demand from the EIA API v2 and store it as
gzipped raw JSON, one file per month, mirroring the weather-capture archive style.

WHY EIA (not CAISO OASIS): EIA v2 serves clean hourly CAISO demand as JSON in a
few paginated calls covering years at a time. OASIS requires per-day ZIP
downloads and XML parsing. Same underlying data; EIA is far cheaper to maintain.

Series: electricity/rto/region-data, respondent=CISO (CAISO), type=D (demand).
Values are hourly, in megawatthours, timestamped in UTC.

Needs EIA_API_KEY in the environment. Free key: https://www.eia.gov/opendata/

Raw bytes are stored verbatim (like the weather capture). Nothing is reshaped;
each response is json.loads'd once to confirm it is well-formed before writing.

  energy/data/caiso_demand/<YYYY-MM>.json.gz
  energy/data/caiso_demand/_manifest.json
"""
import os, sys, json, gzip, time, argparse, datetime as dt

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "data", "caiso_demand")

EIA_ENDPOINT = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
RESPONDENT = "CISO"      # CAISO
DEMAND_TYPE = "D"        # actual demand
# Window: align to the CAISO series start referenced in weather-capture/history.
DEFAULT_START = "2023-05-01"

MAX_ATTEMPTS = 4
BACKOFF_BASE = 4
SLEEP_BETWEEN = 0.8
PAGE_LENGTH = 5000       # EIA max rows per call


def month_iter(start_ym, end_ym):
    """Yield (YYYY-MM, first_hour, last_hour_exclusive) per month in [start,end]."""
    y, m = int(start_ym[:4]), int(start_ym[5:7])
    ey, em = int(end_ym[:4]), int(end_ym[5:7])
    while (y, m) <= (ey, em):
        first = f"{y:04d}-{m:02d}-01T00"
        if m == 12:
            ny, nm = y + 1, 1
        else:
            ny, nm = y, m + 1
        nxt = f"{ny:04d}-{nm:02d}-01T00"
        yield f"{y:04d}-{m:02d}", first, nxt
        y, m = ny, nm


def fetch_month(api_key, first_hour, next_hour):
    """One month of hourly CAISO demand. Paginates. Returns the full parsed EIA response
    with all rows merged into response['response']['data']."""
    all_rows = []
    offset = 0
    base_params = {
        "api_key": api_key,
        "frequency": "hourly",
        "data[0]": "value",
        "facets[respondent][]": RESPONDENT,
        "facets[type][]": DEMAND_TYPE,
        "start": first_hour,
        "end": next_hour,
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": PAGE_LENGTH,
    }
    total = None
    while True:
        params = dict(base_params, offset=offset)
        j = _get_json(params)
        resp = j["response"]
        rows = resp.get("data", [])
        all_rows.extend(rows)
        if total is None:
            total = int(resp.get("total", len(rows)))
        offset += len(rows)
        if len(rows) == 0 or offset >= total:
            break
        time.sleep(SLEEP_BETWEEN)
    # rebuild a single response object carrying every row
    merged = {"request_start": first_hour, "request_end": next_hour,
              "respondent": RESPONDENT, "type": DEMAND_TYPE,
              "total": total, "data": all_rows}
    return merged


def _get_json(params):
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = requests.get(EIA_ENDPOINT, params=params, timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (403,) and "API_KEY" in r.text:
                raise SystemExit("EIA rejected the API key. Check $EIA_API_KEY.")
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except requests.RequestException as e:
            last = str(e)
        if attempt < MAX_ATTEMPTS:
            time.sleep(BACKOFF_BASE * attempt)
    raise RuntimeError(f"giving up after {MAX_ATTEMPTS} attempts: {last}")


def main():
    ap = argparse.ArgumentParser(description="Fetch CAISO hourly demand from EIA into gzipped monthly JSON.")
    ap.add_argument("--start", default=DEFAULT_START, help="YYYY-MM-DD (default 2023-05-01)")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--force", action="store_true", help="refetch months already present")
    args = ap.parse_args()

    api_key = os.environ.get("EIA_API_KEY")
    if not api_key:
        sys.exit("EIA_API_KEY not set. Get a free key at https://www.eia.gov/opendata/ "
                 "and add it as an environment variable.")

    end = args.end or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    start_ym, end_ym = args.start[:7], end[:7]
    os.makedirs(OUTDIR, exist_ok=True)

    manifest = {}
    mpath = os.path.join(OUTDIR, "_manifest.json")
    if os.path.exists(mpath):
        manifest = json.load(open(mpath))

    fetched = present = failed = 0
    for ym, first, nxt in month_iter(start_ym, end_ym):
        out = os.path.join(OUTDIR, f"{ym}.json.gz")
        if os.path.exists(out) and not args.force:
            present += 1
            print(f"  {ym}  already present")
            continue
        try:
            merged = fetch_month(api_key, first, nxt)
            n = len(merged["data"])
            with gzip.open(out, "wt") as fh:
                json.dump(merged, fh)
            manifest[ym] = {"rows": n, "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                            "start": first, "end": nxt}
            json.dump(manifest, open(mpath, "w"), indent=2, sort_keys=True)
            fetched += 1
            print(f"  {ym}  ok ({n} hours)")
        except Exception as e:
            failed += 1
            print(f"  {ym}  FAILED: {e}")
        time.sleep(SLEEP_BETWEEN)

    print(f"\nsummary: {fetched} fetched, {present} present, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
