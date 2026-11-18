"""Download the City of Henderson DSC_Permits table to a gzipped CSV.

Source: the city's ArcGIS open data hub (table "DSC_Permits", refreshed daily).
The service returns at most 1,000 rows per request, so this pages through it by
ObjectId and retries on transient failures.

By default the output is "slim": property-owner names and addresses, the
permit's street address and parcel number, and free-text descriptions are left
out, because this repo is public and the analysis does not need them. Pass
--full to keep every column (write that somewhere private).
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

SERVICE = (
    "https://services2.arcgis.com/naGsY5NZWVbd6bwD/arcgis/rest/services/"
    "DSC_Permits/FeatureServer/0"
)
PAGE = 1000
DATE_FIELDS = {"ApplyDate", "ExpireDate", "IssueDate", "FinalizedDate"}
SLIM_FIELDS = [
    "ObjectId", "PermitNumber", "PermitType", "WorkClass", "Department",
    "Category", "PermitStatus", "SubmittalMethod",
    "ApplyDate", "ApplyDateFY", "IssueDate", "FinalizedDate", "ExpireDate",
    "WorkingDaysBetweenApplyDateAndIssueDate",
    "ValuationTotal", "ParcelAddressZip",
    "ProfessionalName", "ProfessionalStateLicNbr", "ProfessionalPhone",
]


def get(url: str, params: dict, tries: int = 6) -> dict:
    last = None
    for attempt in range(1, tries + 1):
        try:
            r = requests.get(url, params=params, timeout=120)
            r.raise_for_status()
            body = r.json()
            if "error" in body:
                raise RuntimeError(f"service error: {body['error']}")
            return body
        except Exception as exc:  # noqa: BLE001 - retry anything, report the last
            last = exc
            wait = min(60, 2 ** attempt)
            print(f"  attempt {attempt} failed ({exc}); retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"gave up after {tries} attempts: {last}")


def iso(ms) -> str:
    if ms in (None, ""):
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="henderson-permits/data/dsc_permits.csv.gz")
    ap.add_argument("--full", action="store_true", help="keep every column, including owner and address fields")
    ap.add_argument("--max-rows", type=int, default=0, help="stop early (for testing)")
    args = ap.parse_args()

    meta = get(SERVICE, {"f": "json"})
    all_fields = [f["name"] for f in meta["fields"]]
    fields = all_fields if args.full else [f for f in SLIM_FIELDS if f in all_fields]
    missing = [f for f in SLIM_FIELDS if f not in all_fields]
    if missing and not args.full:
        print(f"warning: service no longer has fields {missing}", file=sys.stderr)

    total = get(f"{SERVICE}/query", {"where": "1=1", "returnCountOnly": "true", "f": "json"})["count"]
    print(f"{total:,} rows in service; fetching {len(fields)} columns")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    written, last_oid = 0, -1
    with gzip.open(out, "wt", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(fields)
        while True:
            # Keyset paging on ObjectId: stable even if rows are added mid-run.
            body = get(f"{SERVICE}/query", {
                "where": f"ObjectId > {last_oid}",
                "outFields": ",".join(fields),
                "orderByFields": "ObjectId",
                "resultRecordCount": PAGE,
                "returnGeometry": "false",
                "f": "json",
            })
            feats = body.get("features", [])
            if not feats:
                break
            for feat in feats:
                a = feat["attributes"]
                row = []
                for f in fields:
                    v = a.get(f)
                    if f in DATE_FIELDS:
                        v = iso(v)
                    elif v is None:
                        v = ""
                    elif isinstance(v, str):
                        v = " ".join(v.split())
                    row.append(v)
                w.writerow(row)
            written += len(feats)
            last_oid = feats[-1]["attributes"]["ObjectId"]
            if written % 20000 < PAGE:
                print(f"  {written:,} / {total:,}")
            if args.max_rows and written >= args.max_rows:
                break

    manifest = {
        "source": SERVICE,
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows_in_service": total,
        "rows_written": written,
        "columns": fields,
        "slim": not args.full,
    }
    out.with_name("manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {written:,} rows to {out}")
    if not args.max_rows and written < total * 0.99:
        print("error: wrote noticeably fewer rows than the service reports", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
