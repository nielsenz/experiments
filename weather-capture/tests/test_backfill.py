"""Tests for backfill_history.py. API mocked; nothing here touches the network.

Run with:  python -m unittest discover -s weather-capture/tests -t weather-capture/tests -v
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

import backfill_history as bh  # noqa: E402
import check_gaps  # noqa: E402

TODAY = dt.date(2026, 7, 25)
SAMPLE_BODY = json.dumps({"hourly": {"time": [], "temperature_2m_previous_day1": []}}).encode()


def make_config(sources: dict | None = None, locations: int = 1) -> dict:
    all_locations = [
        {"slug": "fresno-ca", "latitude": 36.7378, "longitude": -119.7871},
        {"slug": "sacramento-ca", "latitude": 38.5816, "longitude": -121.4944},
    ]
    if sources is None:
        sources = {
            "previous_runs_ifs_hres": {
                "enabled": True,
                "role": "feature",
                "endpoint": "https://previous-runs.example.invalid/v1/forecast",
                "models": ["ecmwf_ifs025"],
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
                "chunk": "month",
                "request_units_per_call": 1,
                "hourly": ["temperature_2m_previous_day1"],
            },
            "historical_forecast_actuals": {
                "enabled": True,
                "role": "verification",
                "endpoint": "https://historical-forecast.example.invalid/v1/forecast",
                "models": [],
                "start_date": "2024-01-01",
                "end_date": "2024-02-29",
                "chunk": "month",
                "request_units_per_call": 1,
                "hourly": ["temperature_2m"],
            },
        }
    return {
        "locations": all_locations[:locations],
        "request": {
            "connect_timeout_seconds": 1,
            "read_timeout_seconds": 1,
            "max_attempts": 3,
            "backoff_base_seconds": 0.01,
            "sleep_between_calls_seconds": 0,
            "max_request_units_per_minute": 10000,
            "max_request_units_per_run": 10000,
        },
        "sources": sources,
    }


class FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"", headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}

    @property
    def text(self):
        return self.content.decode("utf-8", errors="replace")


class FakeSession:
    def __init__(self, responder=None):
        self.responder = responder or (lambda params: FakeResponse(200, SAMPLE_BODY))
        self.calls = []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append({"url": url, "params": params})
        result = self.responder(params)
        if isinstance(result, Exception):
            raise result
        return result


def make_args(**overrides):
    import argparse
    defaults = dict(source=None, dry_run=False, dry_run_examples=5, limit=0,
                    include_disabled=False)
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class ChunkingTests(unittest.TestCase):
    def test_splits_into_calendar_months(self):
        chunks = bh.month_chunks(dt.date(2024, 1, 1), dt.date(2024, 3, 31))
        self.assertEqual([c[0] for c in chunks], ["2024-01", "2024-02", "2024-03"])
        self.assertEqual(chunks[0][1], dt.date(2024, 1, 1))
        self.assertEqual(chunks[0][2], dt.date(2024, 1, 31))

    def test_clips_partial_months_to_the_range(self):
        chunks = bh.month_chunks(dt.date(2023, 5, 17), dt.date(2023, 7, 9))
        self.assertEqual([c[0] for c in chunks], ["2023-05", "2023-06", "2023-07"])
        self.assertEqual(chunks[0][1], dt.date(2023, 5, 17), "first chunk starts at range start")
        self.assertEqual(chunks[-1][2], dt.date(2023, 7, 9), "last chunk ends at range end")

    def test_handles_leap_february(self):
        chunks = bh.month_chunks(dt.date(2024, 2, 1), dt.date(2024, 2, 29))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0][2], dt.date(2024, 2, 29))

    def test_single_day_range(self):
        chunks = bh.month_chunks(dt.date(2024, 6, 5), dt.date(2024, 6, 5))
        self.assertEqual(len(chunks), 1)

    def test_multi_year_span(self):
        chunks = bh.month_chunks(dt.date(2024, 1, 1), dt.date(2026, 7, 25))
        self.assertEqual(len(chunks), 31)
        self.assertEqual(chunks[-1][0], "2026-07")
        self.assertEqual(chunks[-1][2], dt.date(2026, 7, 25))

    def test_reversed_range_is_rejected(self):
        with self.assertRaises(ValueError):
            bh.month_chunks(dt.date(2024, 3, 1), dt.date(2024, 1, 1))

    def test_today_sentinel_resolves(self):
        self.assertEqual(bh.parse_date("today", TODAY), TODAY)
        self.assertEqual(bh.parse_date("2024-01-01", TODAY), dt.date(2024, 1, 1))


class RoutingTests(unittest.TestCase):
    """Role decides the tree. This is the firewall, so it is worth pinning down."""

    def test_feature_source_writes_under_features(self):
        config = make_config()
        source = config["sources"]["previous_runs_ifs_hres"]
        path = bh.series_dir("/root", "previous_runs_ifs_hres", source, "fresno-ca", "ecmwf_ifs025")
        self.assertEqual(path, "/root/features/previous_runs_ifs_hres/fresno-ca_ecmwf_ifs025")

    def test_verification_source_writes_under_verification(self):
        config = make_config()
        source = config["sources"]["historical_forecast_actuals"]
        path = bh.series_dir("/root", "historical_forecast_actuals", source, "fresno-ca", None)
        self.assertEqual(path, "/root/verification/historical_forecast_actuals/fresno-ca")

    def test_actuals_never_land_in_the_feature_tree(self):
        config = make_config()
        source = config["sources"]["historical_forecast_actuals"]
        path = bh.series_dir("/root", "historical_forecast_actuals", source, "fresno-ca", None)
        self.assertNotIn("/features/", path)


class FirewallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "history")
        self.config = make_config()

    def test_clean_tree_passes(self):
        os.makedirs(os.path.join(self.root, "features", "previous_runs_ifs_hres"))
        os.makedirs(os.path.join(self.root, "verification", "historical_forecast_actuals"))
        self.assertEqual(bh.verify_firewall(self.config, self.root), [])

    def test_empty_tree_passes(self):
        self.assertEqual(bh.verify_firewall(self.config, self.root), [])

    def test_verification_source_in_feature_tree_is_caught(self):
        os.makedirs(os.path.join(self.root, "features", "historical_forecast_actuals"))
        problems = bh.verify_firewall(self.config, self.root)
        self.assertTrue(problems)
        self.assertIn("historical_forecast_actuals", problems[0])
        self.assertIn("verification", problems[0])

    def test_unknown_directory_in_feature_tree_is_caught(self):
        os.makedirs(os.path.join(self.root, "features", "something_i_dropped_here"))
        problems = bh.verify_firewall(self.config, self.root)
        self.assertTrue(any("something_i_dropped_here" in p for p in problems))

    def test_unknown_role_in_config_is_caught(self):
        config = make_config(sources={
            "weird": {"enabled": True, "role": "whatever", "endpoint": "x",
                      "models": [], "start_date": "2024-01-01", "end_date": "2024-01-31",
                      "request_units_per_call": 1, "hourly": ["temperature_2m"]},
        })
        problems = bh.verify_firewall(config, self.root)
        self.assertTrue(any("unknown role" in p for p in problems))

    def test_verify_firewall_cli_exit_codes(self):
        config_path = os.path.join(self.tmp.name, "sources.json")
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(self.config, handle)

        os.makedirs(os.path.join(self.root, "features", "previous_runs_ifs_hres"))
        self.assertEqual(bh.main(
            ["--config", config_path, "--root", self.root, "--verify-firewall"]), 0)

        os.makedirs(os.path.join(self.root, "features", "historical_forecast_actuals"))
        self.assertEqual(bh.main(
            ["--config", config_path, "--root", self.root, "--verify-firewall"]), 2)


class RunTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(bh.time, "sleep")
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "history")

    def run_backfill(self, config, session, **arg_overrides) -> int:
        with mock.patch.object(bh.requests, "Session", return_value=session):
            return bh.run(config, self.root, make_args(**arg_overrides), TODAY)

    def test_fetches_every_chunk_and_writes_files(self):
        config = make_config()
        session = FakeSession()
        rc = self.run_backfill(config, session)

        self.assertEqual(rc, 0)
        # 3 months of previous-runs + 2 months of actuals, one location.
        self.assertEqual(len(session.calls), 5)
        self.assertTrue(os.path.exists(os.path.join(
            self.root, "features", "previous_runs_ifs_hres",
            "fresno-ca_ecmwf_ifs025", "2024-01.json.gz")))
        self.assertTrue(os.path.exists(os.path.join(
            self.root, "verification", "historical_forecast_actuals",
            "fresno-ca", "2024-02.json.gz")))

    def test_sends_expected_date_range_parameters(self):
        config = make_config(sources={
            "previous_runs_ifs_hres": dict(
                make_config()["sources"]["previous_runs_ifs_hres"], end_date="2024-01-31"),
        })
        session = FakeSession()
        self.run_backfill(config, session)

        params = session.calls[0]["params"]
        self.assertEqual(params["start_date"], "2024-01-01")
        self.assertEqual(params["end_date"], "2024-01-31")
        self.assertEqual(params["models"], "ecmwf_ifs025")
        self.assertEqual(params["hourly"], "temperature_2m_previous_day1")

    def test_omits_models_when_source_has_none(self):
        config = make_config(sources={
            "historical_forecast_actuals": dict(
                make_config()["sources"]["historical_forecast_actuals"],
                end_date="2024-01-31"),
        })
        session = FakeSession()
        self.run_backfill(config, session)
        self.assertNotIn("models", session.calls[0]["params"])

    def test_resumes_and_skips_completed_chunks(self):
        config = make_config()
        first = FakeSession()
        self.run_backfill(config, first)
        self.assertEqual(len(first.calls), 5)

        second = FakeSession()
        rc = self.run_backfill(config, second)
        self.assertEqual(rc, 0)
        self.assertEqual(len(second.calls), 0, "a completed backfill must re-fetch nothing")

    def test_resume_refetches_only_the_missing_chunk(self):
        config = make_config()
        self.run_backfill(config, FakeSession())
        os.remove(os.path.join(self.root, "features", "previous_runs_ifs_hres",
                               "fresno-ca_ecmwf_ifs025", "2024-02.json.gz"))

        session = FakeSession()
        self.run_backfill(config, session)
        self.assertEqual(len(session.calls), 1)
        self.assertEqual(session.calls[0]["params"]["start_date"], "2024-02-01")

    def test_truncated_chunk_is_refetched(self):
        config = make_config()
        self.run_backfill(config, FakeSession())
        path = os.path.join(self.root, "features", "previous_runs_ifs_hres",
                            "fresno-ca_ecmwf_ifs025", "2024-01.json.gz")
        with open(path, "rb") as handle:
            good = handle.read()
        with open(path, "wb") as handle:
            handle.write(good[: len(good) // 2])

        self.assertFalse(bh.existing_file_is_usable(path))
        session = FakeSession()
        self.run_backfill(config, session)
        self.assertEqual(len(session.calls), 1)

    def test_one_failing_chunk_does_not_abort_the_rest(self):
        config = make_config()

        def responder(params):
            if params["start_date"] == "2024-02-01":
                return FakeResponse(500, b"boom")
            return FakeResponse(200, SAMPLE_BODY)

        session = FakeSession(responder)
        rc = self.run_backfill(config, session)

        self.assertEqual(rc, 1, "a failed chunk should be reported in the exit code")
        manifest_path = os.path.join(self.root, "features", "previous_runs_ifs_hres",
                                     "fresno-ca_ecmwf_ifs025", "_manifest.json")
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        self.assertEqual(manifest["failed"], 1)
        self.assertEqual(manifest["ok"], 2)
        self.assertEqual(manifest["role"], "feature")

    def test_retries_then_succeeds(self):
        config = make_config(sources={
            "previous_runs_ifs_hres": dict(
                make_config()["sources"]["previous_runs_ifs_hres"], end_date="2024-01-31"),
        })
        attempts = {"n": 0}

        def responder(params):
            attempts["n"] += 1
            if attempts["n"] < 3:
                return FakeResponse(503, b"busy")
            return FakeResponse(200, SAMPLE_BODY)

        session = FakeSession(responder)
        rc = self.run_backfill(config, session)
        self.assertEqual(rc, 0)
        self.assertEqual(attempts["n"], 3)

    def test_dry_run_makes_no_requests_and_writes_nothing(self):
        config = make_config()
        session = FakeSession()
        rc = self.run_backfill(config, session, dry_run=True)

        self.assertEqual(rc, 0)
        self.assertEqual(len(session.calls), 0)
        self.assertFalse(os.path.exists(os.path.join(self.root, "features")))

    def test_limit_stops_early_and_is_resumable(self):
        config = make_config()
        session = FakeSession()
        self.run_backfill(config, session, limit=2)
        self.assertEqual(len(session.calls), 2)

        resumed = FakeSession()
        self.run_backfill(config, resumed)
        self.assertEqual(len(resumed.calls), 3, "the remaining chunks finish on a re-run")

    def test_disabled_source_is_skipped(self):
        config = make_config()
        config["sources"]["ensemble_mean"] = {
            "enabled": False, "role": "feature",
            "endpoint": "https://ensemble.example.invalid/v1/ensemble",
            "models": ["gfs025"], "start_date": "2026-03-01", "end_date": "2026-03-31",
            "request_units_per_call": 4, "hourly": [],
            "_disabled_reason": "awaiting spec",
        }
        session = FakeSession()
        self.run_backfill(config, session)
        self.assertEqual(len(session.calls), 5, "the disabled source contributes no calls")

    def test_source_with_no_variables_is_skipped_even_if_enabled(self):
        """Guards the half-configured ensemble_mean case from firing bad calls."""
        config = make_config(sources={
            "ensemble_mean": {
                "enabled": True, "role": "feature",
                "endpoint": "https://ensemble.example.invalid/v1/ensemble",
                "models": ["gfs025"], "start_date": "2026-03-01", "end_date": "2026-03-31",
                "request_units_per_call": 4, "hourly": [],
            },
        })
        session = FakeSession()
        self.run_backfill(config, session)
        self.assertEqual(len(session.calls), 0)

    def test_source_filter(self):
        config = make_config()
        session = FakeSession()
        self.run_backfill(config, session, source=["historical_forecast_actuals"])
        self.assertEqual(len(session.calls), 2)
        self.assertTrue(all("historical-forecast" in c["url"] for c in session.calls))

    def test_run_unit_budget_stops_cleanly(self):
        config = make_config()
        config["request"]["max_request_units_per_run"] = 2
        session = FakeSession()
        rc = self.run_backfill(config, session)

        self.assertEqual(len(session.calls), 2)
        self.assertEqual(rc, 0, "stopping on budget is not a failure")

    def test_stored_bytes_are_verbatim(self):
        config = make_config(sources={
            "previous_runs_ifs_hres": dict(
                make_config()["sources"]["previous_runs_ifs_hres"], end_date="2024-01-31"),
        })
        self.run_backfill(config, FakeSession())
        path = os.path.join(self.root, "features", "previous_runs_ifs_hres",
                            "fresno-ca_ecmwf_ifs025", "2024-01.json.gz")
        with gzip.open(path, "rb") as handle:
            self.assertEqual(handle.read(), SAMPLE_BODY)

    def test_transport_errors_are_retried_then_recorded(self):
        config = make_config(sources={
            "previous_runs_ifs_hres": dict(
                make_config()["sources"]["previous_runs_ifs_hres"], end_date="2024-01-31"),
        })
        session = FakeSession(lambda params: requests.ConnectionError("reset"))
        rc = self.run_backfill(config, session)
        self.assertEqual(rc, 1)
        self.assertEqual(len(session.calls), 3, "max_attempts is 3")


def ensemble_mean_source(**overrides):
    source = {
        "enabled": True,
        "role": "feature",
        "provenance": "archive_ensemble_mean",
        "endpoint": "https://ensemble.example.invalid/v1/ensemble",
        "models": ["dwd_icon_eps_ensemble_mean_seamless"],
        "start_date": "2026-03-01",
        "end_date": "today",
        "chunk": "past_days",
        "forecast_days": 7,
        "request_units_per_call": 4,
        "hourly": ["temperature_2m", "temperature_2m_spread"],
    }
    source.update(overrides)
    return source


class PastDaysArchiveTests(unittest.TestCase):
    """The ensemble archive is reached with past_days, not a date range."""

    def setUp(self):
        patcher = mock.patch.object(bh.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "history")
        self.config = make_config(sources={"ensemble_mean": ensemble_mean_source()},
                                  locations=2)

    def run_backfill(self, config=None, session=None, **overrides):
        session = session or FakeSession()
        with mock.patch.object(bh.requests, "Session", return_value=session):
            rc = bh.run(config or self.config, self.root, make_args(**overrides), TODAY)
        return rc, session

    def test_one_call_per_series_not_one_per_month(self):
        rc, session = self.run_backfill()
        self.assertEqual(rc, 0)
        self.assertEqual(len(session.calls), 2, "2 locations x 1 model = 2 calls total")

    def test_uses_past_days_and_not_a_date_range(self):
        _, session = self.run_backfill()
        params = session.calls[0]["params"]
        self.assertNotIn("start_date", params)
        self.assertNotIn("end_date", params)
        self.assertEqual(params["past_days"], (TODAY - dt.date(2026, 3, 1)).days)
        self.assertEqual(params["forecast_days"], 7)

    def test_requests_mean_and_spread_with_the_ensemble_mean_model(self):
        _, session = self.run_backfill()
        params = session.calls[0]["params"]
        self.assertEqual(params["models"], "dwd_icon_eps_ensemble_mean_seamless")
        self.assertEqual(params["hourly"], "temperature_2m,temperature_2m_spread")

    def test_writes_archive_file(self):
        self.run_backfill()
        self.assertTrue(os.path.exists(os.path.join(
            self.root, "features", "ensemble_mean",
            "fresno-ca_dwd_icon_eps_ensemble_mean_seamless", "archive.json.gz")))

    def test_records_past_days_and_as_of_in_the_manifest(self):
        self.run_backfill()
        path = os.path.join(self.root, "features", "ensemble_mean",
                            "fresno-ca_dwd_icon_eps_ensemble_mean_seamless", "_manifest.json")
        with open(path, encoding="utf-8") as handle:
            manifest = json.load(handle)
        entry = manifest["entries"]["archive.json.gz"]
        self.assertEqual(entry["as_of"], TODAY.isoformat())
        self.assertEqual(entry["past_days"], (TODAY - dt.date(2026, 3, 1)).days)

    def test_bills_four_units_per_ensemble_call(self):
        config = make_config(sources={"ensemble_mean": ensemble_mean_source()}, locations=2)
        config["request"]["max_request_units_per_run"] = 1000
        captured = {}
        real = bh.RateLimiter

        def spy(*a, **kw):
            captured["limiter"] = real(*a, **kw)
            return captured["limiter"]

        with mock.patch.object(bh, "RateLimiter", side_effect=spy):
            self.run_backfill(config)
        self.assertEqual(captured["limiter"].spent, 8, "2 calls x 4 units")

    def test_is_resumable(self):
        self.run_backfill()
        _, session = self.run_backfill()
        self.assertEqual(len(session.calls), 0)


class ProvenanceTests(unittest.TestCase):
    """The seam between archive mean/spread and captured members must stay visible."""

    def setUp(self):
        patcher = mock.patch.object(bh.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "history")

    def read_manifest(self, *parts):
        with open(os.path.join(self.root, *parts, "_manifest.json"), encoding="utf-8") as h:
            return json.load(h)

    def test_provenance_recorded_on_manifest_and_entries(self):
        config = make_config(sources={"ensemble_mean": ensemble_mean_source()}, locations=1)
        with mock.patch.object(bh.requests, "Session", return_value=FakeSession()):
            bh.run(config, self.root, make_args(), TODAY)

        manifest = self.read_manifest(
            "features", "ensemble_mean", "fresno-ca_dwd_icon_eps_ensemble_mean_seamless")
        self.assertEqual(manifest["provenance"], "archive_ensemble_mean")
        self.assertEqual(manifest["entries"]["archive.json.gz"]["provenance"],
                         "archive_ensemble_mean")

    def test_archive_and_captured_members_carry_different_provenance(self):
        """The two mean/spread sources must never be indistinguishable."""
        import fetch_ensemble

        config = make_config(sources={"ensemble_mean": ensemble_mean_source()}, locations=1)
        with mock.patch.object(bh.requests, "Session", return_value=FakeSession()):
            bh.run(config, self.root, make_args(), TODAY)
        archive = self.read_manifest(
            "features", "ensemble_mean", "fresno-ca_dwd_icon_eps_ensemble_mean_seamless")

        daily = fetch_ensemble.load_manifest(
            os.path.join(self.tmp.name, "nope"), "2026-07-25",
            {"locations": [{"slug": "fresno-ca"}], "models": ["gfs025"]})

        self.assertEqual(daily["provenance"], "captured_ensemble_members")
        self.assertNotEqual(archive["provenance"], daily["provenance"])

    def test_verification_source_provenance_is_distinct_too(self):
        config = make_config(locations=1)
        with mock.patch.object(bh.requests, "Session", return_value=FakeSession()):
            bh.run(config, self.root, make_args(), TODAY)
        manifest = self.read_manifest(
            "verification", "historical_forecast_actuals", "fresno-ca")
        self.assertIsNone(manifest["provenance"],
                          "test config sets none; the real config sets it")


class RealConfigTests(unittest.TestCase):
    """Sanity checks against the shipped history_sources.json."""

    def setUp(self):
        self.config = bh.load_config(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "history_sources.json"))

    def test_every_source_has_a_valid_role(self):
        for name, source in self.config["sources"].items():
            self.assertIn(source["role"], bh.VALID_ROLES, f"source {name}")

    def test_historical_forecast_is_verification_not_feature(self):
        self.assertEqual(
            self.config["sources"]["historical_forecast_actuals"]["role"], "verification",
            "the stitched-analysis series must never be classed as a feature")

    def test_enabled_sources_all_declare_provenance(self):
        for name, source in self.config["sources"].items():
            if source.get("enabled"):
                self.assertTrue(source.get("provenance"), f"source {name} needs provenance")

    def test_ensemble_mean_requests_spread_for_every_variable(self):
        hourly = self.config["sources"]["ensemble_mean"]["hourly"]
        base = [v for v in hourly if not v.endswith("_spread")]
        for variable in base:
            self.assertIn(f"{variable}_spread", hourly,
                          f"{variable} is requested without its spread")
        self.assertEqual(len(base), 4)

    def test_ensemble_mean_uses_an_ensemble_mean_model_id(self):
        for model in self.config["sources"]["ensemble_mean"]["models"]:
            self.assertIn("ensemble_mean", model)

    def test_rejected_previous_runs_stub_is_disabled(self):
        stub = self.config["sources"]["_rejected_previous_runs_for_ensembles"]
        self.assertFalse(stub["enabled"])
        self.assertFalse(stub["hourly"], "must have no variables so it can never run")

    def test_shipped_config_passes_the_firewall(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(bh.verify_firewall(self.config, tmp), [])


class RateLimiterTests(unittest.TestCase):
    def test_spends_units_per_call(self):
        limiter = bh.RateLimiter(units_per_minute=1000, units_per_run=100, sleep_between=0)
        limiter.acquire(4)
        limiter.acquire(4)
        self.assertEqual(limiter.spent, 8)
        self.assertEqual(limiter.budget_remaining(), 92)

    def test_detects_run_budget_exhaustion(self):
        limiter = bh.RateLimiter(units_per_minute=1000, units_per_run=10, sleep_between=0)
        limiter.acquire(8)
        self.assertFalse(limiter.would_exceed_run_budget(2))
        self.assertTrue(limiter.would_exceed_run_budget(4),
                        "an ensemble call at 4 units must not overrun the budget")

    def test_sleeps_when_the_minute_budget_is_hit(self):
        limiter = bh.RateLimiter(units_per_minute=8, units_per_run=1000, sleep_between=0)
        with mock.patch.object(bh.time, "sleep") as sleeper:
            for _ in range(3):
                limiter.acquire(4)
        self.assertTrue(sleeper.called, "exceeding the per-minute budget must pause")

    def test_charge_bills_without_sleeping(self):
        limiter = bh.RateLimiter(units_per_minute=4, units_per_run=1000, sleep_between=0)
        with mock.patch.object(bh.time, "sleep") as sleeper:
            limiter.acquire(4)
            limiter.charge(8)
            self.assertFalse(sleeper.called, "backoff already slept; do not sleep again")
        self.assertEqual(limiter.spent, 12)

    def test_charge_ignores_zero_and_negative(self):
        limiter = bh.RateLimiter(units_per_minute=100, units_per_run=100, sleep_between=0)
        limiter.charge(0)
        limiter.charge(-1)
        self.assertEqual(limiter.spent, 0)

    def test_retries_are_billed_against_the_budget(self):
        """A chunk that retries twice costs three requests, not one."""
        attempts = {"n": 0}

        def responder(params):
            attempts["n"] += 1
            if attempts["n"] < 3:
                return FakeResponse(503, b"busy")
            return FakeResponse(200, SAMPLE_BODY)

        config = make_config(sources={
            "previous_runs_ifs_hres": dict(
                make_config()["sources"]["previous_runs_ifs_hres"], end_date="2024-01-31"),
        })
        with tempfile.TemporaryDirectory() as tmp:
            session = FakeSession(responder)
            with mock.patch.object(bh.time, "sleep"):
                with mock.patch.object(bh.requests, "Session", return_value=session):
                    captured = {}
                    real_limiter = bh.RateLimiter

                    def spy(*a, **kw):
                        captured["limiter"] = real_limiter(*a, **kw)
                        return captured["limiter"]

                    with mock.patch.object(bh, "RateLimiter", side_effect=spy):
                        bh.run(config, os.path.join(tmp, "history"), make_args(), TODAY)

            self.assertEqual(len(session.calls), 3)
            self.assertEqual(captured["limiter"].spent, 3,
                             "all three HTTP attempts must be billed")

    def test_does_not_sleep_before_the_first_call(self):
        limiter = bh.RateLimiter(units_per_minute=1000, units_per_run=1000, sleep_between=5)
        with mock.patch.object(bh.time, "sleep") as sleeper:
            limiter.acquire(1)
            self.assertFalse(sleeper.called)
            limiter.acquire(1)
            self.assertTrue(sleeper.called)


class DailyGateIsolationTests(unittest.TestCase):
    """The backfill tree must be invisible to the daily capture's gate."""

    def test_check_gaps_ignores_the_history_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = os.path.join(tmp, "data")
            history_root = os.path.join(tmp, "history")
            os.makedirs(data_dir)

            config = make_config()
            session = FakeSession()
            with mock.patch.object(bh.requests, "Session", return_value=session):
                with mock.patch.object(bh.time, "sleep"):
                    bh.run(config, history_root, make_args(), TODAY)

            # The backfill wrote plenty of files, none of them under data/.
            self.assertTrue(os.path.isdir(history_root))
            self.assertEqual(check_gaps.known_dates(data_dir), [],
                             "backfill output must not appear as a capture date")

    def test_backfill_months_are_not_mistaken_for_capture_dates(self):
        """`2024-01` must not parse as a capture date directory."""
        self.assertIsNone(check_gaps.DATE_DIR_RE.match("2024-01"))
        self.assertIsNotNone(check_gaps.DATE_DIR_RE.match("2024-01-15"))


if __name__ == "__main__":
    unittest.main()
