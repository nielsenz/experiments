#!/usr/bin/env python3
"""One-shot historical backfill. Run by hand; never by the capture workflow.

This is deliberately kept separate from fetch_ensemble.py, and deliberately does
not import from it. Different failure profile: the daily capture races a ~3 day
retention window and its gate must go red the moment it misses. This job has no
deadline, and a bug in it must never turn that gate red. The cost of that
isolation is some duplicated retry logic, which is the right trade here.

Three sources, in two firewalled trees (see history/README.md):

  history/features/      as-issued forecasts -- safe as model inputs
  history/verification/  actuals -- must never enter the feature set

Everything about endpoints and variable names lives in history_sources.json.
Start with --dry-run.
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import gzip
import hashlib
import json
import os
import random
import sys
import time
from urllib.parse import urlencode

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(HERE, "history_sources.json")
DEFAULT_ROOT = os.path.join(HERE, "history")

USER_AGENT = "weather-capture-backfill/1.0 (github; one-shot historical backfill)"
MANIFEST_NAME = "_manifest.json"
GZIP_MAGIC = b"\x1f\x8b"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
VALID_ROLES = ("feature", "verification")
ROLE_DIRS = {"feature": "features", "verification": "verification"}


def log(message: str = "") -> None:
    print(message, flush=True)


# ---------------------------------------------------------------------------
# Config and chunking
# ---------------------------------------------------------------------------

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def parse_date(value: str, today: dt.date) -> dt.date:
    if value == "today":
        return today
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def month_chunks(start: dt.date, end: dt.date) -> list[tuple[str, dt.date, dt.date]]:
    """Split [start, end] into calendar-month chunks, clipped to the range.

    Returns (label, chunk_start, chunk_end). The historical endpoints accept a
    long date range in a single call, so a month per call keeps responses a
    sane size while keeping the total call count low.
    """
    if end < start:
        raise ValueError(f"end date {end} is before start date {start}")
    chunks = []
    year, month = start.year, start.month
    while True:
        first = dt.date(year, month, 1)
        last = dt.date(year, month, calendar.monthrange(year, month)[1])
        chunk_start = max(first, start)
        chunk_end = min(last, end)
        if chunk_start > chunk_end:
            break
        chunks.append((f"{year:04d}-{month:02d}", chunk_start, chunk_end))
        if last >= end:
            break
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return chunks


def source_dir(root: str, source_name: str, source: dict) -> str:
    return os.path.join(root, ROLE_DIRS[source["role"]], source_name)


def series_dir(root: str, source_name: str, source: dict, location_slug: str,
               model: str | None) -> str:
    leaf = location_slug if not model else f"{location_slug}_{model}"
    return os.path.join(source_dir(root, source_name, source), leaf)


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class RateLimiter:
    """Rolling one-minute budget in request units.

    Ensemble calls bill as several units each on the free tier, so the budget is
    counted in units rather than calls. Boring on purpose: we would much rather
    be slow than get thrown a 429 storm halfway through a long backfill.
    """

    def __init__(self, units_per_minute: int, units_per_run: int, sleep_between: float):
        self.units_per_minute = units_per_minute
        self.units_per_run = units_per_run
        self.sleep_between = sleep_between
        self.window: list[tuple[float, int]] = []
        self.spent = 0
        self._first_call = True

    def budget_remaining(self) -> int:
        return self.units_per_run - self.spent

    def would_exceed_run_budget(self, units: int) -> bool:
        return self.spent + units > self.units_per_run

    def acquire(self, units: int) -> None:
        if self._first_call:
            self._first_call = False
        elif self.sleep_between > 0:
            time.sleep(self.sleep_between)

        now = time.monotonic()
        self.window = [(ts, u) for ts, u in self.window if now - ts < 60.0]
        used = sum(u for _, u in self.window)
        if used + units > self.units_per_minute and self.window:
            wait = 60.0 - (now - self.window[0][0]) + 0.5
            if wait > 0:
                log(f"    rate limit: pausing {wait:.0f}s "
                    f"({used}/{self.units_per_minute} units used this minute)")
                time.sleep(wait)
                now = time.monotonic()
                self.window = [(ts, u) for ts, u in self.window if now - ts < 60.0]

        self.window.append((time.monotonic(), units))
        self.spent += units

    def charge(self, units: int) -> None:
        """Bill units already spent, without pausing.

        Retries are real requests and count against the API's limits, but the
        backoff has already slowed us down by the time we know how many there
        were. Charging after the fact keeps the accounting honest without
        double-sleeping -- otherwise a degraded API makes us undercount at
        exactly the moment the limit matters most.
        """
        if units <= 0:
            return
        self.window.append((time.monotonic(), units))
        self.spent += units


# ---------------------------------------------------------------------------
# Fetch and store
# ---------------------------------------------------------------------------

def existing_file_is_usable(path: str) -> bool:
    """True if `path` is a complete, readable chunk we can skip.

    Full decompress, not a magic-byte check. A truncated file has valid magic
    bytes, and skipping one forever would leave a permanent hole in a backfill
    that reports itself as finished.
    """
    try:
        if os.path.getsize(path) <= 0:
            return False
        with open(path, "rb") as handle:
            if handle.read(2) != GZIP_MAGIC:
                return False
        with gzip.open(path, "rb") as handle:
            json.loads(handle.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - any failure means "re-fetch"
        return False
    return True


def build_params(source: dict, job: dict) -> dict:
    """Parameters for one chunk.

    Two shapes, because the endpoints differ. The dated historical endpoints
    take start_date/end_date. The ensemble archive is reached with past_days
    instead, which always anchors to today, so that source pulls its whole
    window in a single call rather than by month.
    """
    params = {
        "latitude": job["location"]["latitude"],
        "longitude": job["location"]["longitude"],
        "hourly": ",".join(source["hourly"]),
    }
    if job.get("past_days") is not None:
        params["past_days"] = job["past_days"]
        if source.get("forecast_days") is not None:
            params["forecast_days"] = source["forecast_days"]
    else:
        params["start_date"] = job["chunk_start"].isoformat()
        params["end_date"] = job["chunk_end"].isoformat()
    if job["model"]:
        params["models"] = job["model"]
    return params


def fetch_chunk(source: dict, params: dict, session: requests.Session,
                request_cfg: dict) -> dict:
    """Fetch one chunk. Never raises."""
    max_attempts = int(request_cfg.get("max_attempts", 4))
    backoff_base = float(request_cfg.get("backoff_base_seconds", 10))
    timeout = (
        float(request_cfg.get("connect_timeout_seconds", 15)),
        float(request_cfg.get("read_timeout_seconds", 300)),
    )
    errors: list[str] = []

    for attempt in range(1, max_attempts + 1):
        try:
            response = session.get(source["endpoint"], params=params, timeout=timeout,
                                   headers={"User-Agent": USER_AGENT})
        except requests.RequestException as exc:
            errors.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
            _sleep_before_retry(attempt, max_attempts, backoff_base, None)
            continue

        if response.status_code == 200:
            body = response.content
            try:
                json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"attempt {attempt}: 200 but body is not valid JSON: {exc}")
                _sleep_before_retry(attempt, max_attempts, backoff_base, None)
                continue
            return {"status": "ok", "body": body, "attempts": attempt, "errors": errors}

        detail = response.text[:300].replace("\n", " ")
        errors.append(f"attempt {attempt}: HTTP {response.status_code}: {detail}")
        if response.status_code not in RETRYABLE_STATUS:
            break
        _sleep_before_retry(attempt, max_attempts, backoff_base, response)

    return {"status": "failed", "body": None,
            "attempts": len(errors) or 1, "errors": errors}


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
    delay += random.uniform(0, 2)
    log(f"    retrying in {delay:.1f}s")
    time.sleep(delay)


def write_gzip(path: str, body: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            gz.write(body)
        raw.flush()
        os.fsync(raw.fileno())
    os.replace(tmp_path, path)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(directory: str, source_name: str, source: dict) -> dict:
    path = os.path.join(directory, MANIFEST_NAME)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)
            manifest.setdefault("entries", {})
            return manifest
        except (OSError, json.JSONDecodeError):
            log(f"  manifest at {path} unreadable, rebuilding")
    return {
        "schema_version": 1,
        "source": source_name,
        "role": source["role"],
        "provenance": source.get("provenance"),
        "endpoint": source["endpoint"],
        "models": source.get("models", []),
        "hourly": source["hourly"],
        "entries": {},
    }


def write_manifest(directory: str, manifest: dict) -> None:
    entries = manifest.get("entries", {})
    manifest["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest["ok"] = sum(1 for e in entries.values() if e.get("status") == "ok")
    manifest["failed"] = sum(1 for e in entries.values() if e.get("status") == "failed")
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, MANIFEST_NAME)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(tmp_path, path)


# ---------------------------------------------------------------------------
# Planning and running
# ---------------------------------------------------------------------------

def plan_source(config: dict, root: str, source_name: str, source: dict,
                today: dt.date) -> list[dict]:
    """Every chunk this source wants, whether or not it already exists."""
    start = parse_date(source["start_date"], today)
    end = parse_date(source["end_date"], today)
    models = source.get("models") or [None]
    units = int(source.get("request_units_per_call", 1))
    past_days_mode = source.get("chunk") == "past_days"

    if past_days_mode:
        # past_days always anchors to today, so an arbitrary past window cannot
        # be selected -- one call per series covers the whole thing.
        if end < start:
            raise ValueError(f"end date {end} is before start date {start}")
        past_days = (today - start).days
        chunks = [("archive", start, end, past_days)]
    else:
        chunks = [(label, s, e, None) for label, s, e in month_chunks(start, end)]

    jobs = []
    for location in config["locations"]:
        for model in models:
            directory = series_dir(root, source_name, source, location["slug"], model)
            for label, chunk_start, chunk_end, past_days in chunks:
                jobs.append({
                    "source": source_name,
                    "role": source["role"],
                    "provenance": source.get("provenance"),
                    "location": location,
                    "model": model,
                    "label": label,
                    "chunk_start": chunk_start,
                    "chunk_end": chunk_end,
                    "past_days": past_days,
                    "directory": directory,
                    "path": os.path.join(directory, f"{label}.json.gz"),
                    "units": units,
                })
    return jobs


def selected_sources(config: dict, only: list[str] | None,
                     include_disabled: bool) -> list[tuple[str, dict]]:
    chosen = []
    for name, source in config["sources"].items():
        if only and name not in only:
            continue
        if not source.get("enabled", False) and not include_disabled:
            reason = source.get("_disabled_reason", "disabled in config")
            log(f"skipping source '{name}': {reason}")
            continue
        if source["role"] not in VALID_ROLES:
            raise ValueError(f"source '{name}' has unknown role {source['role']!r}")
        if not source.get("hourly"):
            log(f"skipping source '{name}': no hourly variables configured")
            continue
        chosen.append((name, source))
    return chosen


def run(config: dict, root: str, args: argparse.Namespace, today: dt.date) -> int:
    only = args.source or None
    sources = selected_sources(config, only, args.include_disabled)
    if not sources:
        log("nothing to do")
        return 0

    request_cfg = config.get("request", {})
    limiter = RateLimiter(
        units_per_minute=int(request_cfg.get("max_request_units_per_minute", 250)),
        units_per_run=int(request_cfg.get("max_request_units_per_run", 8000)),
        sleep_between=float(request_cfg.get("sleep_between_calls_seconds", 3.0)),
    )

    session = requests.Session()
    totals = {"ok": 0, "skipped": 0, "failed": 0, "planned": 0}
    stopped_early = False

    for source_name, source in sources:
        jobs = plan_source(config, root, source_name, source, today)
        todo = [job for job in jobs if not existing_file_is_usable(job["path"])]
        totals["planned"] += len(jobs)
        totals["skipped"] += len(jobs) - len(todo)

        log("")
        log(f"=== {source_name} [{source['role']}] ===")
        log(f"    {source['start_date']} .. {source['end_date']}  "
            f"{len(jobs)} chunks, {len(jobs) - len(todo)} already present, {len(todo)} to fetch")
        log(f"    {len(todo) * int(source.get('request_units_per_call', 1))} request units")

        if args.dry_run:
            for job in todo[: args.dry_run_examples]:
                params = build_params(source, job)
                log(f"    GET {source['endpoint']}?{urlencode(params)}")
                log(f"        -> {os.path.relpath(job['path'], root)}")
            if len(todo) > args.dry_run_examples:
                log(f"    ... and {len(todo) - args.dry_run_examples} more")
            continue

        manifests: dict[str, dict] = {}
        for job in todo:
            if args.limit and totals["ok"] + totals["failed"] >= args.limit:
                log(f"    stopping: --limit {args.limit} reached")
                stopped_early = True
                break
            if limiter.would_exceed_run_budget(job["units"]):
                log(f"    stopping: run budget of {limiter.units_per_run} units exhausted. "
                    f"Re-run to continue -- completed chunks are skipped.")
                stopped_early = True
                break

            directory = job["directory"]
            if directory not in manifests:
                manifests[directory] = load_manifest(directory, source_name, source)
            manifest = manifests[directory]

            params = build_params(source, job)
            label = f"{job['location']['slug']}" + (f"/{job['model']}" if job["model"] else "")
            log(f"  {label} {job['label']}")

            limiter.acquire(job["units"])
            result = fetch_chunk(source, params, session, request_cfg)
            # Each retry was another real request against the API's budget.
            limiter.charge(job["units"] * (result["attempts"] - 1))

            entry = {
                "status": result["status"],
                "attempts": result["attempts"],
                "role": source["role"],
                # Recorded on every entry so the statistic's origin travels with
                # the data. Archive ensemble mean/spread and mean/spread derived
                # from captured members are different statistics and must not be
                # joined into one continuous feature -- see history/README.md.
                "provenance": job.get("provenance"),
                "location": job["location"]["slug"],
                "model": job["model"],
                "start_date": job["chunk_start"].isoformat(),
                "end_date": job["chunk_end"].isoformat(),
                "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            if job.get("past_days") is not None:
                entry["past_days"] = job["past_days"]
                entry["as_of"] = today.isoformat()
            if result["status"] == "ok":
                try:
                    write_gzip(job["path"], result["body"])
                except OSError as exc:
                    entry["status"] = "failed"
                    entry["error"] = f"write failed: {exc}"
                    totals["failed"] += 1
                    log(f"    WRITE FAILED: {exc}")
                else:
                    entry["bytes"] = os.path.getsize(job["path"])
                    entry["raw_bytes"] = len(result["body"])
                    entry["sha256"] = sha256_file(job["path"])
                    totals["ok"] += 1
                    log(f"    ok ({entry['bytes']} bytes gzipped)")
            else:
                entry["error"] = result["errors"][-1] if result["errors"] else "unknown"
                entry["all_errors"] = result["errors"]
                totals["failed"] += 1
                log(f"    FAILED: {entry['error']}")

            manifest["entries"][f"{job['label']}.json.gz"] = entry
            write_manifest(directory, manifest)

        for directory, manifest in manifests.items():
            write_manifest(directory, manifest)
        if stopped_early:
            break

    log("")
    log("summary:")
    log(f"  planned {totals['planned']} chunks")
    log(f"  {totals['ok']} fetched, {totals['skipped']} already present, {totals['failed']} failed")
    if not args.dry_run:
        log(f"  {limiter.spent} request units spent")
    if stopped_early:
        log("  stopped early -- re-run to continue where it left off")

    problems = verify_firewall(config, root)
    if problems:
        log("")
        log("FIREWALL VIOLATION:")
        for problem in problems:
            log(f"  - {problem}")
        return 2

    return 1 if totals["failed"] else 0


# ---------------------------------------------------------------------------
# Firewall
# ---------------------------------------------------------------------------

def verify_firewall(config: dict, root: str) -> list[str]:
    """Check that no verification data has leaked into the feature tree.

    The whole point of two trees is that the split is structural rather than a
    note in a README, so it is worth asserting mechanically. Cheap enough to run
    at the end of every backfill.
    """
    problems = []
    expected: dict[str, str] = {}
    for name, source in config["sources"].items():
        role = source.get("role")
        if role not in VALID_ROLES:
            problems.append(f"source '{name}' has unknown role {role!r}")
            continue
        expected[name] = ROLE_DIRS[role]

    for role, dirname in ROLE_DIRS.items():
        role_root = os.path.join(root, dirname)
        if not os.path.isdir(role_root):
            continue
        for entry in sorted(os.listdir(role_root)):
            path = os.path.join(role_root, entry)
            if not os.path.isdir(path):
                continue
            if entry not in expected:
                problems.append(
                    f"{dirname}/{entry} does not correspond to any configured source")
            elif expected[entry] != dirname:
                problems.append(
                    f"source '{entry}' has role '{role}' but data is under {dirname}/ "
                    f"(expected {expected[entry]}/)")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--root", default=DEFAULT_ROOT,
                        help="output tree (default: weather-capture/history)")
    parser.add_argument("--source", action="append",
                        help="only this source; repeatable")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be fetched, make no requests")
    parser.add_argument("--dry-run-examples", type=int, default=5,
                        help="how many example URLs to print per source (default: 5)")
    parser.add_argument("--limit", type=int, default=0,
                        help="stop after this many fetches; 0 means no limit")
    parser.add_argument("--include-disabled", action="store_true",
                        help="also run sources marked enabled:false")
    parser.add_argument("--verify-firewall", action="store_true",
                        help="only check the feature/verification split, fetch nothing")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    today = dt.datetime.now(dt.timezone.utc).date()

    if args.verify_firewall:
        problems = verify_firewall(config, args.root)
        if problems:
            log("FIREWALL VIOLATION:")
            for problem in problems:
                log(f"  - {problem}")
            return 2
        log("firewall ok: feature and verification trees are correctly separated")
        return 0

    try:
        return run(config, args.root, args, today)
    except ValueError as exc:
        log(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
