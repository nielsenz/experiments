#!/usr/bin/env python3
"""Capture Open-Meteo ensemble forecasts and write them to disk as gzipped raw JSON.

Design notes, because this is meant to run unattended for years:

* One HTTP request per (location, model) pair. The response bytes are written
  through untouched, so we never depend on the API's multi-model response shape.
* Every fetch is isolated. One failure never aborts the others.
* Existing, structurally-sound files are skipped, so re-running is cheap and safe.
* Everything that happened is recorded in a per-date _manifest.json so that gaps
  are machine-detectable after the fact.

We `json.loads` each response *only* to confirm it is well-formed JSON (an HTML
error page must never be written into the archive as if it were data). What gets
stored is always the original raw bytes, gzipped. Nothing is parsed, reshaped,
or modelled.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import random
import sys
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "locations.json")
DEFAULT_DATA_DIR = os.path.join(HERE, "data")

USER_AGENT = "weather-capture/1.0 (github actions; open-meteo ensemble archive)"

MANIFEST_NAME = "_manifest.json"
MANIFEST_SCHEMA_VERSION = 1

# Retried: transport errors, server errors, and rate limiting. A 4xx other than
# 429 means we asked for something wrong, and asking again will not fix it.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

GZIP_MAGIC = b"\x1f\x8b"


def log(message: str) -> None:
    print(message, flush=True)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def utc_today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def date_range(start: dt.date, end: dt.date) -> list[dt.date]:
    if end < start:
        raise ValueError(f"end date {end} is before start date {start}")
    days = (end - start).days
    return [start + dt.timedelta(days=offset) for offset in range(days + 1)]


def target_dates(args: argparse.Namespace) -> list[dt.date]:
    """Dates to ensure data exists for.

    Default is the trailing `--days` window ending today (UTC), which is what
    makes a skipped or delayed run self-healing: a run that finds yesterday
    missing will go and get it.
    """
    if args.start_date or args.end_date:
        today = utc_today()
        start = parse_date(args.start_date) if args.start_date else today
        end = parse_date(args.end_date) if args.end_date else today
        return date_range(start, end)

    today = utc_today()
    return [today - dt.timedelta(days=offset) for offset in range(args.days - 1, -1, -1)]


def output_filename(location_slug: str, model: str) -> str:
    return f"{location_slug}_{model}.json.gz"


def expected_filenames(config: dict) -> list[str]:
    names = []
    for location in config["locations"]:
        for model in config["models"]:
            names.append(output_filename(location["slug"], model))
    return sorted(names)


def existing_file_is_usable(path: str) -> bool:
    """True if `path` is a complete, readable capture that we can safely skip.

    This must apply the *same* standard as check_gaps.py --deep. If the skip
    test were any weaker, a file that check_gaps rejects would be skipped by
    every future run: the gap check fails forever while the fetcher never
    repairs it, and a file that was still inside the ~3 day retention window is
    lost permanently. A truncated file has valid gzip magic bytes, so checking
    the header is not enough -- we have to decompress it.

    The decompressed bytes are used only to confirm the file is intact. Nothing
    is parsed out of them or kept.
    """
    try:
        if os.path.getsize(path) <= 0:
            return False
        with open(path, "rb") as handle:
            if handle.read(2) != GZIP_MAGIC:
                return False
        with gzip.open(path, "rb") as handle:
            json.loads(handle.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - any failure means "not usable, re-fetch"
        return False
    return True


def build_params(config: dict, location: dict, model: str, past_days: int) -> dict:
    params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "models": model,
        "hourly": ",".join(config["hourly"]),
        "forecast_days": config["forecast_days"],
    }
    if past_days > 0:
        params["past_days"] = past_days
    return params


def fetch_one(config: dict, location: dict, model: str, session: requests.Session) -> dict:
    """Fetch a single (location, model) pair. Never raises.

    Returns a result dict that always has a "status" of "ok" or "failed", and on
    success carries the raw response bytes under "body".
    """
    request_cfg = config.get("request", {})
    max_attempts = int(request_cfg.get("max_attempts", 3))
    backoff_base = float(request_cfg.get("backoff_base_seconds", 4))
    timeout = (
        float(request_cfg.get("connect_timeout_seconds", 15)),
        float(request_cfg.get("read_timeout_seconds", 120)),
    )

    past_days = int(config.get("past_days", 0))
    errors: list[str] = []

    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        params = build_params(config, location, model, past_days)
        try:
            response = session.get(
                config["endpoint"], params=params, timeout=timeout,
                headers={"User-Agent": USER_AGENT},
            )
        except requests.RequestException as exc:
            errors.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
            _sleep_before_retry(attempt, max_attempts, backoff_base, None)
            continue

        if response.status_code == 200:
            body = response.content
            try:
                json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                # A 200 that is not JSON is a proxy/error page, not data.
                errors.append(f"attempt {attempt}: 200 but body is not valid JSON: {exc}")
                _sleep_before_retry(attempt, max_attempts, backoff_base, None)
                continue

            return {
                "status": "ok",
                "body": body,
                "attempts": attempt,
                "past_days_used": past_days,
                "errors": errors,
            }

        detail = response.text[:300].replace("\n", " ")
        errors.append(f"attempt {attempt}: HTTP {response.status_code}: {detail}")

        # If the endpoint rejects past_days, drop it and keep going rather than
        # losing the capture entirely. Recorded in the manifest so it is visible.
        if response.status_code == 400 and past_days > 0:
            log(f"    past_days={past_days} rejected, retrying forecast-only")
            past_days = 0
            attempt -= 1  # this degrade does not consume a retry
            continue

        if response.status_code not in RETRYABLE_STATUS:
            break

        _sleep_before_retry(attempt, max_attempts, backoff_base, response)

    return {
        "status": "failed",
        "body": None,
        "attempts": attempt,
        "past_days_used": past_days,
        "errors": errors,
    }


def _sleep_before_retry(attempt: int, max_attempts: int, base: float, response) -> None:
    if attempt >= max_attempts:
        return
    delay = base * (2 ** (attempt - 1))
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                pass
    delay += random.uniform(0, 1)  # jitter, so 15 fetches do not retry in lockstep
    log(f"    retrying in {delay:.1f}s")
    time.sleep(delay)


def write_gzip(path: str, body: bytes) -> None:
    """Write `body` gzipped to `path` atomically."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    # mtime=0 keeps the bytes deterministic, so an identical capture does not
    # produce a spurious diff.
    with open(tmp_path, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            gz.write(body)
        raw.flush()
        os.fsync(raw.fileno())
    os.replace(tmp_path, path)


def load_manifest(date_dir: str, date_str: str, config: dict) -> dict:
    path = os.path.join(date_dir, MANIFEST_NAME)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            manifest.setdefault("entries", {})
            return manifest
        except (OSError, json.JSONDecodeError):
            log(f"  existing manifest at {path} is unreadable, rebuilding it")

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "date": date_str,
        "expected_files": expected_filenames(config),
        "entries": {},
    }


def write_manifest(date_dir: str, manifest: dict) -> None:
    entries = manifest.get("entries", {})
    manifest["schema_version"] = MANIFEST_SCHEMA_VERSION
    manifest["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest["expected"] = len(manifest.get("expected_files", []))
    manifest["ok"] = sum(1 for e in entries.values() if e.get("status") == "ok")
    manifest["failed"] = sum(1 for e in entries.values() if e.get("status") == "failed")
    manifest["complete"] = (
        manifest["failed"] == 0
        and sorted(k for k, e in entries.items() if e.get("status") == "ok")
        == sorted(manifest.get("expected_files", []))
    )

    os.makedirs(date_dir, exist_ok=True)
    path = os.path.join(date_dir, MANIFEST_NAME)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp_path, path)


def capture_date(config: dict, data_dir: str, date: dt.date, session: requests.Session,
                 today: dt.date) -> dict:
    """Ensure every expected file exists for `date`. Returns a small summary."""
    date_str = date.isoformat()
    date_dir = os.path.join(data_dir, date_str)
    manifest = load_manifest(date_dir, date_str, config)

    # A capture for any date other than today cannot be the run that was issued
    # that day -- the endpoint only serves the current model run. We still take
    # it (it carries trailing hours that cover the gap), but it is labelled so
    # it is never mistaken for an on-time capture.
    late = date != today
    if late:
        log(f"  note: {date_str} is a late capture; the model run issued that day is not recoverable")

    sleep_between = float(config.get("request", {}).get("sleep_between_fetches_seconds", 2.0))
    summary = {"date": date_str, "ok": 0, "failed": 0, "skipped": 0, "late": late}
    first_fetch = True

    for location in config["locations"]:
        for model in config["models"]:
            filename = output_filename(location["slug"], model)
            path = os.path.join(date_dir, filename)

            if existing_file_is_usable(path):
                summary["skipped"] += 1
                entry = manifest["entries"].get(filename)
                if not entry or entry.get("status") != "ok":
                    # File is on disk but the manifest disagrees. Trust the disk
                    # and repair the manifest.
                    manifest["entries"][filename] = {
                        "status": "ok",
                        "note": "present on disk; manifest repaired",
                        "bytes": os.path.getsize(path),
                        "sha256": sha256_file(path),
                    }
                continue

            # Be polite: space out calls, but do not pay the delay before the
            # first real fetch of the run.
            if not first_fetch and sleep_between > 0:
                time.sleep(sleep_between)
            first_fetch = False

            log(f"  fetching {date_str} {location['slug']} {model}")
            result = fetch_one(config, location, model, session)

            entry = {
                "status": result["status"],
                "attempts": result["attempts"],
                "past_days_used": result["past_days_used"],
                "late": late,
                "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "location": location["slug"],
                "model": model,
            }

            if result["status"] == "ok":
                try:
                    write_gzip(path, result["body"])
                except OSError as exc:
                    entry["status"] = "failed"
                    entry["error"] = f"write failed: {exc}"
                    summary["failed"] += 1
                    log(f"    WRITE FAILED: {exc}")
                else:
                    entry["bytes"] = os.path.getsize(path)
                    entry["raw_bytes"] = len(result["body"])
                    entry["sha256"] = sha256_file(path)
                    summary["ok"] += 1
                    log(f"    ok ({entry['bytes']} bytes gzipped)")
            else:
                entry["error"] = result["errors"][-1] if result["errors"] else "unknown"
                entry["all_errors"] = result["errors"]
                summary["failed"] += 1
                log(f"    FAILED after {result['attempts']} attempt(s): {entry['error']}")

            manifest["entries"][filename] = entry
            # Written after every fetch, so a job killed mid-run still leaves an
            # accurate record of what it managed to get.
            write_manifest(date_dir, manifest)

    write_manifest(date_dir, manifest)
    return summary


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--days", type=int, default=3,
                        help="size of the trailing window to ensure, ending today UTC (default: 3)")
    parser.add_argument("--start-date", help="YYYY-MM-DD; overrides --days")
    parser.add_argument("--end-date", help="YYYY-MM-DD; overrides --days")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    today = utc_today()

    try:
        dates = target_dates(args)
    except ValueError as exc:
        log(f"ERROR: {exc}")
        return 2

    log(f"capture window: {dates[0].isoformat()} .. {dates[-1].isoformat()} (today is {today.isoformat()} UTC)")

    session = requests.Session()
    summaries = []
    for date in dates:
        log(f"{date.isoformat()}:")
        summaries.append(capture_date(config, args.data_dir, date, session, today))

    log("")
    log("summary:")
    total_failed = 0
    for summary in summaries:
        marker = " [late]" if summary["late"] else ""
        log(f"  {summary['date']}{marker}: {summary['ok']} fetched, "
            f"{summary['skipped']} already present, {summary['failed']} failed")
        total_failed += summary["failed"]

    # A non-zero exit here is informational. The workflow commits whatever was
    # captured regardless, and check_gaps.py is what decides pass/fail.
    if total_failed:
        log(f"\n{total_failed} fetch(es) failed; see the per-date {MANIFEST_NAME} files")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
