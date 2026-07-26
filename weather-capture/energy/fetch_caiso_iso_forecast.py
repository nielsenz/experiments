#!/usr/bin/env python3
"""
Fetch CAISO's OFFICIAL day-ahead demand forecast (and the matching actual load)
from CAISO OASIS, for use as an INCUMBENT BENCHMARK against our own model.

Why this exists
---------------
Our demand model reports MAE ~890 MWh (~3.3% MAPE). That number is meaningless
without a denominator: how good is CAISO's *own* published day-ahead forecast on
the same hours? If the ISO does ~1.5%, our 3.3% is mediocre; if it does ~3-4%,
we're at parity with a hand-rolled GBM. This fetcher gets the number that tells
us which world we live in.

What it pulls (OASIS SingleZip, queryname=SLD_FCST, TAC_AREA_NAME='CA ISO-TAC')
  - market_run_id=DAM     -> SYS_FCST_DA_MW  "Demand Forecast Day Ahead"  (the incumbent forecast)
  - market_run_id=ACTUAL  -> SYS_FCST_ACT_MW "Total Actual Hourly Integrated Load" (its own truth)

IMPORTANT (apples-to-apples): the DAM forecast MUST be scored against the OASIS
ACTUAL on the SAME 'CA ISO-TAC' footprint, NOT against EIA's CISO series -- the
two footprints differ ~3.35% systematically (see energy/README.md). We pull both
here so the ISO benchmark is judged against its own actuals, and so our model can
optionally be re-scored against the same OASIS truth for a fair comparison.

Storage (raw CSV rows, gzipped, one file per market x month):
  energy/data/caiso_iso_forecast/<DAM|ACTUAL>_<YYYY-MM>.json.gz
  energy/data/caiso_iso_forecast/_manifest.json

No API key needed. OASIS is keyless but rate-limited; we chunk ~30 days/call and
sleep politely between calls. Resumable (skips files already present).
"""
import os, sys, io, csv, json, gzip, time, zipfile, argparse
import datetime as dt
import urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "data", "caiso_iso_forecast")

OASIS = "http://oasis.caiso.com/oasisapi/SingleZip"
TAC = "CA ISO-TAC"
# OASIS caps a SLD_FCST request near ~31 days; use 30 to stay safe.
CHUNK_DAYS = 30
MAX_ATTEMPTS = 4
BACKOFF_BASE = 6
SLEEP_BETWEEN = 5.0          # OASIS is strict; be polite
DEFAULT_START = "2023-05-01"

MARKETS = {
    "DAM":    "SYS_FCST_DA_MW",
    "ACTUAL": "SYS_FCST_ACT_MW",
}


def month_chunks(start_ym, end_date):
    """Yield (YYYY-MM, chunk_start_date, chunk_end_date_exclusive) covering whole
    months but split so no single OASIS call exceeds CHUNK_DAYS. A month <= 31
    days becomes one or two chunks; we key the output file by month and append
    chunks into it."""
    y, m = int(start_ym[:4]), int(start_ym[5:7])
    ey, em = int(end_date[:4]), int(end_date[5:7])
    while (y, m) <= (ey, em):
        first = dt.date(y, m, 1)
        nm = dt.date(y + (m == 12), (m % 12) + 1, 1)  # first of next month
        # sub-chunk the month
        cur = first
        chunks = []
        while cur < nm:
            nxt = min(cur + dt.timedelta(days=CHUNK_DAYS), nm)
            chunks.append((cur, nxt))
            cur = nxt
        yield f"{y:04d}-{m:02d}", chunks
        y, m = nm.year, nm.month


def _fetch_zip(market, s_date, e_date):
    """One OASIS SLD_FCST call. Returns list of CA ISO-TAC rows (dicts)."""
    params = {
        "queryname": "SLD_FCST",
        "market_run_id": market,
        "startdatetime": s_date.strftime("%Y%m%d") + "T00:00-0000",
        "enddatetime":   e_date.strftime("%Y%m%d") + "T00:00-0000",
        "version": "1",
        "resultformat": "6",   # CSV
    }
    url = OASIS + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research; weather-capture)"})
            raw = urllib.request.urlopen(req, timeout=90).read()
            # OASIS returns a ZIP; a non-zip body usually means throttling/error
            try:
                zf = zipfile.ZipFile(io.BytesIO(raw))
            except zipfile.BadZipFile:
                snippet = raw[:200].decode("utf-8", "replace")
                raise RuntimeError(f"non-zip response (throttled?): {snippet}")
            name = zf.namelist()[0]
            txt = zf.read(name).decode()
            rows = list(csv.DictReader(io.StringIO(txt)))
            keep = [r for r in rows if r.get("TAC_AREA_NAME") == TAC]
            return keep
        except Exception as e:
            last = str(e)
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_BASE * attempt)
    raise RuntimeError(f"giving up after {MAX_ATTEMPTS} attempts: {last}")


def main():
    ap = argparse.ArgumentParser(description="Fetch CAISO OASIS day-ahead demand forecast + actual (ISO benchmark).")
    ap.add_argument("--start", default=DEFAULT_START, help="YYYY-MM-DD (default 2023-05-01)")
    ap.add_argument("--end", default=None, help="YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--markets", default="DAM,ACTUAL", help="comma list subset of DAM,ACTUAL")
    ap.add_argument("--force", action="store_true", help="refetch files already present")
    args = ap.parse_args()

    end = args.end or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    markets = [m.strip() for m in args.markets.split(",") if m.strip() in MARKETS]
    os.makedirs(OUTDIR, exist_ok=True)

    mpath = os.path.join(OUTDIR, "_manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}

    fetched = present = failed = 0
    for market in markets:
        item = MARKETS[market]
        for ym, chunks in month_chunks(args.start[:7], end):
            out = os.path.join(OUTDIR, f"{market}_{ym}.json.gz")
            if os.path.exists(out) and not args.force:
                present += 1
                print(f"  {market} {ym}  already present")
                continue
            try:
                rows = []
                for (cs, ce) in chunks:
                    rows.extend(_fetch_zip(market, cs, ce))
                    time.sleep(SLEEP_BETWEEN)
                # keep only the fields we need, tidy + small
                slim = [{
                    "start_gmt": r["INTERVALSTARTTIME_GMT"],
                    "opr_dt":    r["OPR_DT"],
                    "opr_hr":    r["OPR_HR"],
                    "mw":        r["MW"],
                    "item":      r["XML_DATA_ITEM"],
                } for r in rows if r.get("XML_DATA_ITEM") == item]
                merged = {"market": market, "tac": TAC, "item": item,
                          "month": ym, "rows": slim}
                with gzip.open(out, "wt") as fh:
                    json.dump(merged, fh)
                manifest[f"{market}_{ym}"] = {
                    "rows": len(slim),
                    "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                }
                json.dump(manifest, open(mpath, "w"), indent=2, sort_keys=True)
                fetched += 1
                print(f"  {market} {ym}  ok ({len(slim)} hours)")
            except Exception as e:
                failed += 1
                print(f"  {market} {ym}  FAILED: {e}")
            time.sleep(SLEEP_BETWEEN)

    print(f"\nsummary: {fetched} fetched, {present} present, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
