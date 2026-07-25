#!/usr/bin/env python3
"""Scan the capture archive and report missing or incomplete dates.

This is the thing that turns a silent failure into a red X. The capture job runs
it last; if the required trailing window is not complete, it exits non-zero and
the workflow fails loudly.

Two modes:

  default    Check the trailing --days window (ending today UTC) against the
             *current* config. This is the pass/fail gate.
  --all      Report on every date directory in the archive. Each date is checked
             against the file list recorded in its own _manifest.json, so
             adding a location later does not retroactively mark years of good
             history as incomplete. Reporting only; never fails on its own.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "locations.json")
DEFAULT_DATA_DIR = os.path.join(HERE, "data")

MANIFEST_NAME = "_manifest.json"
DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GZIP_MAGIC = b"\x1f\x8b"


def log(message: str) -> None:
    print(message, flush=True)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def utc_today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def expected_filenames(config: dict) -> list[str]:
    names = []
    for location in config["locations"]:
        for model in config["models"]:
            names.append(f"{location['slug']}_{model}.json.gz")
    return sorted(names)


def read_manifest(date_dir: str) -> dict | None:
    path = os.path.join(date_dir, MANIFEST_NAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def file_problem(path: str, deep: bool) -> str | None:
    """Return a description of what is wrong with `path`, or None if it is fine."""
    if not os.path.exists(path):
        return "missing"
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        return f"unreadable ({exc})"
    if size <= 0:
        return "empty"
    try:
        with open(path, "rb") as handle:
            if handle.read(2) != GZIP_MAGIC:
                return "not a gzip file"
    except OSError as exc:
        return f"unreadable ({exc})"

    if deep:
        # Decompress and confirm it parses as JSON. This is an integrity check
        # only -- nothing is extracted, kept, or derived from the contents.
        try:
            with gzip.open(path, "rb") as handle:
                json.loads(handle.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - any failure here means corrupt
            return f"corrupt ({type(exc).__name__}: {exc})"
    return None


def check_date(data_dir: str, date_str: str, expected: list[str], deep: bool) -> dict:
    """Check one date directory. Returns a result dict; never raises."""
    date_dir = os.path.join(data_dir, date_str)
    result = {
        "date": date_str,
        "complete": False,
        "present": 0,
        "expected": len(expected),
        "problems": [],
        "late": False,
        "manifest_failures": [],
    }

    if not os.path.isdir(date_dir):
        result["problems"].append("date directory does not exist")
        return result

    manifest = read_manifest(date_dir)
    if manifest is None:
        result["problems"].append(f"{MANIFEST_NAME} is missing or unreadable")
    else:
        entries = manifest.get("entries", {})
        result["late"] = any(entry.get("late") for entry in entries.values())
        result["manifest_failures"] = sorted(
            name for name, entry in entries.items() if entry.get("status") == "failed"
        )

    for filename in expected:
        problem = file_problem(os.path.join(date_dir, filename), deep)
        if problem is None:
            result["present"] += 1
        else:
            result["problems"].append(f"{filename}: {problem}")

    result["complete"] = result["present"] == result["expected"] and not result["problems"]
    return result


def known_dates(data_dir: str) -> list[str]:
    if not os.path.isdir(data_dir):
        return []
    return sorted(
        name for name in os.listdir(data_dir)
        if DATE_DIR_RE.match(name) and os.path.isdir(os.path.join(data_dir, name))
    )


def report(results: list[dict], header: str) -> None:
    log(header)
    for result in results:
        status = "OK      " if result["complete"] else "INCOMPLETE"
        marker = " [late]" if result["late"] else ""
        log(f"  {status} {result['date']}{marker}  {result['present']}/{result['expected']} files")
        for problem in result["problems"]:
            log(f"      - {problem}")
        for failure in result["manifest_failures"]:
            if not any(failure in p for p in result["problems"]):
                log(f"      - {failure}: recorded as failed in {MANIFEST_NAME}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--days", type=int, default=3,
                        help="size of the trailing window that must be complete (default: 3)")
    parser.add_argument("--all", action="store_true",
                        help="report on every date in the archive (reporting only, never fails)")
    parser.add_argument("--deep", action="store_true",
                        help="also decompress each file to confirm it is valid JSON")
    args = parser.parse_args(argv)

    config = load_config(args.config)

    if args.all:
        dates = known_dates(args.data_dir)
        if not dates:
            log(f"no date directories found under {args.data_dir}")
            return 0
        results = []
        for date_str in dates:
            manifest = read_manifest(os.path.join(args.data_dir, date_str))
            # Judge historical dates by what was expected when they were captured.
            expected = sorted((manifest or {}).get("expected_files") or expected_filenames(config))
            results.append(check_date(args.data_dir, date_str, expected, args.deep))
        report(results, f"archive report ({len(results)} dates):")
        incomplete = [r for r in results if not r["complete"]]
        log("")
        log(f"{len(results) - len(incomplete)} complete, {len(incomplete)} incomplete")
        if incomplete:
            log("incomplete dates: " + ", ".join(r["date"] for r in incomplete))
        return 0

    today = utc_today()
    window = [(today - dt.timedelta(days=offset)).isoformat()
              for offset in range(args.days - 1, -1, -1)]
    expected = expected_filenames(config)
    results = [check_date(args.data_dir, date_str, expected, args.deep) for date_str in window]

    report(results, f"checking the last {args.days} day(s) (today is {today.isoformat()} UTC):")

    incomplete = [r for r in results if not r["complete"]]
    log("")
    if incomplete:
        log("=" * 62)
        log(f"GAP DETECTED: {len(incomplete)} of the last {args.days} day(s) are incomplete.")
        for result in incomplete:
            log(f"  {result['date']}: {result['present']}/{result['expected']} files present")
        log("")
        log("Ensemble members are retained by Open-Meteo for only ~3 days.")
        log("Data older than that cannot be recovered. Investigate now.")
        log("=" * 62)
        return 1

    log(f"all {args.days} day(s) complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
