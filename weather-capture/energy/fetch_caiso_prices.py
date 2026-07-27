#!/usr/bin/env python3
"""
Fetch CAISO LMP prices (SP15 trading hub) to test whether net-load forecast error
predicts the DA->RT spread.

  DA price : PRC_LMP / DAM,  LMP_PRC, hourly           ($/MWh)
  RT price : PRC_INTVL_LMP / RTM, LMP_PRC, 5-min -> averaged to hourly
  spread   : RT_hourly_mean - DA        (+ = RT settled above DA)

Node: TH_SP15_GEN-APND (SP15 hub, the big SoCal load zone; where evening ramp
scarcity shows up). Keyless OASIS, ~30-day chunks, resumable.

Storage: energy/data/caiso_prices/<DA|RT>_<YYYY-MM>.json.gz
"""
import os, sys, io, csv, json, gzip, time, zipfile, argparse
import datetime as dt
import urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "data", "caiso_prices")
OASIS = "http://oasis.caiso.com/oasisapi/SingleZip"
NODE = "TH_SP15_GEN-APND"
CHUNK_DAYS = 30
MAX_ATTEMPTS = 4
BACKOFF_BASE = 6
SLEEP_BETWEEN = 5.0

SPEC = {
    "DA": {"queryname": "PRC_LMP", "market_run_id": "DAM"},
    "RT": {"queryname": "PRC_INTVL_LMP", "market_run_id": "RTM"},
}


def month_chunks(start_ym, end_date):
    y, m = int(start_ym[:4]), int(start_ym[5:7])
    ey, em = int(end_date[:4]), int(end_date[5:7])
    while (y, m) <= (ey, em):
        first = dt.date(y, m, 1)
        nm = dt.date(y + (m == 12), (m % 12) + 1, 1)
        cur = first; chunks = []
        while cur < nm:
            nxt = min(cur + dt.timedelta(days=CHUNK_DAYS), nm)
            chunks.append((cur, nxt)); cur = nxt
        yield f"{y:04d}-{m:02d}", chunks
        y, m = nm.year, nm.month


def _fetch(spec, s_date, e_date):
    params = {"queryname": spec["queryname"], "market_run_id": spec["market_run_id"],
              "startdatetime": s_date.strftime("%Y%m%d") + "T00:00-0000",
              "enddatetime": e_date.strftime("%Y%m%d") + "T00:00-0000",
              "version": "1", "resultformat": "6", "node": NODE}
    url = OASIS + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research; weather-capture)"})
            raw = urllib.request.urlopen(req, timeout=90).read()
            try:
                zf = zipfile.ZipFile(io.BytesIO(raw))
            except zipfile.BadZipFile:
                raise RuntimeError(f"non-zip (throttled?): {raw[:150].decode('utf-8','replace')}")
            rows = list(csv.DictReader(io.StringIO(zf.read(zf.namelist()[0]).decode())))
            # keep LMP_PRC only; average to hourly (RT 5-min collapses to the hour)
            hourly = {}
            for r in rows:
                if r.get("XML_DATA_ITEM") != "LMP_PRC":
                    continue
                k = r["INTERVALSTARTTIME_GMT"][:13]
                hourly.setdefault(k, []).append(float(r["MW"]))
            return {k: sum(v) / len(v) for k, v in hourly.items()}
        except Exception as e:
            last = str(e)
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_BASE * attempt)
    raise RuntimeError(f"giving up after {MAX_ATTEMPTS} attempts: {last}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--which", default="DA,RT")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    end = args.end or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    which = [w.strip() for w in args.which.split(",") if w.strip() in SPEC]
    os.makedirs(OUTDIR, exist_ok=True)

    fetched = present = failed = 0
    for w in which:
        for ym, chunks in month_chunks(args.start[:7], end):
            out = os.path.join(OUTDIR, f"{w}_{ym}.json.gz")
            if os.path.exists(out) and not args.force:
                present += 1; print(f"  {w} {ym}  present"); continue
            try:
                agg = {}
                for (cs, ce) in chunks:
                    agg.update(_fetch(SPEC[w], cs, ce))
                    time.sleep(SLEEP_BETWEEN)
                with gzip.open(out, "wt") as fh:
                    json.dump({"which": w, "node": NODE, "month": ym,
                               "rows": [{"start_gmt": k, "lmp": v} for k, v in sorted(agg.items())]}, fh)
                fetched += 1; print(f"  {w} {ym}  ok ({len(agg)} hours)")
            except Exception as e:
                failed += 1; print(f"  {w} {ym}  FAILED: {e}")
            time.sleep(SLEEP_BETWEEN)
    print(f"\nsummary: {fetched} fetched, {present} present, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
