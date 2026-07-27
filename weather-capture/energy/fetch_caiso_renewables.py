#!/usr/bin/env python3
"""
Fetch CAISO renewables (Solar + Wind) day-ahead forecast + actual from OASIS,
to construct NET LOAD = demand - (wind + utility solar).

queryname=SLD_REN_FCST, summed over trading hubs (NP15/SP15/ZP26) to a system
total, split by RENEWABLE_TYPE (Solar, Wind), for both markets:
  DAM     -> RENEW_FCST_DA_MW   (day-ahead renewable forecast)
  ACTUAL  -> RENEW_FCST_ACT_MW  (actual renewable generation)

Net load is formed consistently per market:
  net_DAM = SYS_FCST_DA_MW  - (Solar_DAM  + Wind_DAM)
  net_ACT = SYS_FCST_ACT_MW - (Solar_ACT  + Wind_ACT)
so net_DAM vs net_ACT is an apples-to-apples net-load forecast error.

NOTE: RENEW solar here is CAISO utility-scale dispatched solar, not total incl.
behind-the-meter. See modeling/baseline/netload_basis.md.

Storage (gzipped, per market x month):
  energy/data/caiso_renewables/<DAM|ACTUAL>_<YYYY-MM>.json.gz
  each file: {"market","month","rows":[{start_gmt,solar_mw,wind_mw}, ...]}
Keyless OASIS, ~30-day chunks, resumable, polite sleeps.
"""
import os, sys, io, csv, json, gzip, time, zipfile, argparse
import datetime as dt
import urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "data", "caiso_renewables")
OASIS = "http://oasis.caiso.com/oasisapi/SingleZip"
CHUNK_DAYS = 30
MAX_ATTEMPTS = 4
BACKOFF_BASE = 6
SLEEP_BETWEEN = 5.0
DEFAULT_START = "2023-05-01"
MARKETS = {"DAM": "RENEW_FCST_DA_MW", "ACTUAL": "RENEW_FCST_ACT_MW"}


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


def _fetch(market, item, s_date, e_date):
    params = {"queryname": "SLD_REN_FCST", "market_run_id": market,
              "startdatetime": s_date.strftime("%Y%m%d") + "T00:00-0000",
              "enddatetime": e_date.strftime("%Y%m%d") + "T00:00-0000",
              "version": "1", "resultformat": "6"}
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
            # sum hubs by hour and type, for our item only
            agg = {}
            for r in rows:
                if r.get("XML_DATA_ITEM") != item:
                    continue
                k = r["INTERVALSTARTTIME_GMT"][:13]
                agg.setdefault(k, {"Solar": 0.0, "Wind": 0.0})
                rt = r.get("RENEWABLE_TYPE")
                if rt in ("Solar", "Wind"):
                    agg[k][rt] += float(r["MW"])
            return agg
        except Exception as e:
            last = str(e)
            if attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_BASE * attempt)
    raise RuntimeError(f"giving up after {MAX_ATTEMPTS} attempts: {last}")


def main():
    ap = argparse.ArgumentParser(description="Fetch CAISO renewables DAM+ACTUAL for net load.")
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=None)
    ap.add_argument("--markets", default="DAM,ACTUAL")
    ap.add_argument("--force", action="store_true")
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
                present += 1; print(f"  {market} {ym}  already present"); continue
            try:
                agg = {}
                for (cs, ce) in chunks:
                    part = _fetch(market, item, cs, ce)
                    agg.update(part)
                    time.sleep(SLEEP_BETWEEN)
                rows = [{"start_gmt": k, "solar_mw": v["Solar"], "wind_mw": v["Wind"]}
                        for k, v in sorted(agg.items())]
                with gzip.open(out, "wt") as fh:
                    json.dump({"market": market, "month": ym, "rows": rows}, fh)
                manifest[f"{market}_{ym}"] = {"rows": len(rows),
                    "fetched_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
                json.dump(manifest, open(mpath, "w"), indent=2, sort_keys=True)
                fetched += 1; print(f"  {market} {ym}  ok ({len(rows)} hours)")
            except Exception as e:
                failed += 1; print(f"  {market} {ym}  FAILED: {e}")
            time.sleep(SLEEP_BETWEEN)

    print(f"\nsummary: {fetched} fetched, {present} present, {failed} failed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
