"""Tests for fetch_ensemble.py. The API is mocked; nothing here touches the network.

Run with:  python -m unittest discover -s weather-capture/tests -v
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

import fetch_ensemble  # noqa: E402


SAMPLE_BODY = json.dumps({
    "latitude": 36.75,
    "longitude": -119.75,
    "hourly": {"time": ["2026-07-25T00:00"], "temperature_2m_member01": [21.4]},
}).encode("utf-8")


def make_config(tmpdir: str, locations: int = 1, models: int = 1) -> dict:
    all_locations = [
        {"slug": "fresno-ca", "name": "Fresno", "latitude": 36.7378, "longitude": -119.7871},
        {"slug": "sacramento-ca", "name": "Sacramento", "latitude": 38.5816, "longitude": -121.4944},
        {"slug": "los-angeles-ca", "name": "Los Angeles", "latitude": 34.0522, "longitude": -118.2437},
        {"slug": "las-vegas-nv", "name": "Las Vegas", "latitude": 36.1699, "longitude": -115.1398},
        {"slug": "henderson-nv", "name": "Henderson", "latitude": 36.0395, "longitude": -114.9817},
    ]
    all_models = ["gfs025", "ecmwf_ifs025", "icon_seamless"]
    return {
        "endpoint": "https://ensemble-api.example.invalid/v1/ensemble",
        "models": all_models[:models],
        "hourly": ["temperature_2m", "shortwave_radiation", "cloud_cover", "wind_speed_100m"],
        "forecast_days": 7,
        "past_days": 3,
        "request": {
            "connect_timeout_seconds": 1,
            "read_timeout_seconds": 1,
            "max_attempts": 3,
            "backoff_base_seconds": 0.01,
            "sleep_between_fetches_seconds": 0,
        },
        "locations": all_locations[:locations],
    }


class FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"", headers: dict | None = None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class FakeSession:
    """Returns queued responses in order. A queued Exception is raised instead."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append({"url": url, "params": params})
        if not self.responses:
            raise AssertionError("FakeSession ran out of queued responses")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class ScriptedSession:
    """Chooses a response per (location, model) using a callable."""

    def __init__(self, responder):
        self.responder = responder
        self.calls = []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append({"url": url, "params": params})
        result = self.responder(params)
        if isinstance(result, Exception):
            raise result
        return result


class RetryTests(unittest.TestCase):
    """Retry with exponential backoff, and the limits on what gets retried."""

    def setUp(self):
        patcher = mock.patch.object(fetch_ensemble.time, "sleep")
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = make_config(self.tmp.name)

    def test_retries_server_error_then_succeeds(self):
        session = FakeSession([
            FakeResponse(500, b"upstream boom"),
            FakeResponse(503, b"still boom"),
            FakeResponse(200, SAMPLE_BODY),
        ])
        result = fetch_ensemble.fetch_one(
            self.config, self.config["locations"][0], "gfs025", session)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(result["body"], SAMPLE_BODY)
        self.assertEqual(len(session.calls), 3)

    def test_backoff_is_exponential(self):
        # A base of 10 keeps the doubling well clear of the 0-1s jitter, so the
        # assertion cannot flake. Sleep is mocked, so this costs no real time.
        config = dict(self.config)
        config["request"] = dict(self.config["request"], backoff_base_seconds=10)

        session = FakeSession([FakeResponse(500)] * 3)
        fetch_ensemble.fetch_one(config, config["locations"][0], "gfs025", session)

        # Two sleeps for three attempts, each roughly double the last.
        delays = [call.args[0] for call in self.sleep.call_args_list]
        self.assertEqual(len(delays), 2)
        self.assertGreaterEqual(delays[0], 10)
        self.assertGreaterEqual(delays[1], 20)
        self.assertGreater(delays[1], delays[0])

    def test_gives_up_after_max_attempts(self):
        session = FakeSession([FakeResponse(500, b"boom")] * 3)
        result = fetch_ensemble.fetch_one(
            self.config, self.config["locations"][0], "gfs025", session)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(len(result["errors"]), 3)

    def test_retries_transport_errors(self):
        session = FakeSession([
            requests.ConnectionError("connection reset"),
            requests.Timeout("read timed out"),
            FakeResponse(200, SAMPLE_BODY),
        ])
        result = fetch_ensemble.fetch_one(
            self.config, self.config["locations"][0], "gfs025", session)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["attempts"], 3)

    def test_does_not_retry_client_errors(self):
        session = FakeSession([FakeResponse(404, b"no such thing")])
        result = fetch_ensemble.fetch_one(
            self.config, self.config["locations"][0], "gfs025", session)

        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(session.calls), 1, "a 404 must not be retried")

    def test_honours_retry_after_on_429(self):
        session = FakeSession([
            FakeResponse(429, b"slow down", headers={"Retry-After": "30"}),
            FakeResponse(200, SAMPLE_BODY),
        ])
        result = fetch_ensemble.fetch_one(
            self.config, self.config["locations"][0], "gfs025", session)

        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(self.sleep.call_args_list[0].args[0], 30)

    def test_rejects_200_that_is_not_json(self):
        session = FakeSession([
            FakeResponse(200, b"<html>gateway error</html>"),
            FakeResponse(200, SAMPLE_BODY),
        ])
        result = fetch_ensemble.fetch_one(
            self.config, self.config["locations"][0], "gfs025", session)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["body"], SAMPLE_BODY)
        self.assertEqual(result["attempts"], 2, "an HTML error page must not count as data")

    def test_degrades_when_past_days_is_rejected(self):
        session = FakeSession([
            FakeResponse(400, b"past_days is out of range"),
            FakeResponse(200, SAMPLE_BODY),
        ])
        result = fetch_ensemble.fetch_one(
            self.config, self.config["locations"][0], "gfs025", session)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["past_days_used"], 0)
        self.assertIn("past_days", session.calls[0]["params"])
        self.assertNotIn("past_days", session.calls[1]["params"])

    def test_requests_expected_parameters(self):
        session = FakeSession([FakeResponse(200, SAMPLE_BODY)])
        fetch_ensemble.fetch_one(
            self.config, self.config["locations"][0], "gfs025", session)

        params = session.calls[0]["params"]
        self.assertEqual(params["models"], "gfs025")
        self.assertEqual(params["forecast_days"], 7)
        self.assertEqual(params["past_days"], 3)
        self.assertEqual(params["latitude"], 36.7378)
        self.assertEqual(
            params["hourly"],
            "temperature_2m,shortwave_radiation,cloud_cover,wind_speed_100m")


class SkipIfExistsTests(unittest.TestCase):
    """A file already on disk must not be fetched again -- unless it is unusable."""

    def setUp(self):
        patcher = mock.patch.object(fetch_ensemble.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = os.path.join(self.tmp.name, "data")
        self.today = dt.date(2026, 7, 25)
        self.config = make_config(self.tmp.name, locations=1, models=1)

    def write_existing(self, filename: str, body: bytes = SAMPLE_BODY) -> str:
        date_dir = os.path.join(self.data_dir, self.today.isoformat())
        os.makedirs(date_dir, exist_ok=True)
        path = os.path.join(date_dir, filename)
        with gzip.open(path, "wb") as handle:
            handle.write(body)
        return path

    def test_skips_existing_file_without_fetching(self):
        self.write_existing("fresno-ca_gfs025.json.gz")
        session = FakeSession([])  # any call raises

        summary = fetch_ensemble.capture_date(
            self.config, self.data_dir, self.today, session, self.today)

        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(summary["ok"], 0)
        self.assertEqual(len(session.calls), 0, "no HTTP call may be made for an existing file")

    def test_skips_only_the_files_that_exist(self):
        config = make_config(self.tmp.name, locations=1, models=3)
        self.write_existing("fresno-ca_gfs025.json.gz")
        session = FakeSession([FakeResponse(200, SAMPLE_BODY)] * 2)

        summary = fetch_ensemble.capture_date(
            config, self.data_dir, self.today, session, self.today)

        self.assertEqual(summary["skipped"], 1)
        self.assertEqual(summary["ok"], 2)
        self.assertEqual(len(session.calls), 2)

    def test_refetches_empty_file(self):
        date_dir = os.path.join(self.data_dir, self.today.isoformat())
        os.makedirs(date_dir, exist_ok=True)
        open(os.path.join(date_dir, "fresno-ca_gfs025.json.gz"), "wb").close()
        session = FakeSession([FakeResponse(200, SAMPLE_BODY)])

        summary = fetch_ensemble.capture_date(
            self.config, self.data_dir, self.today, session, self.today)

        self.assertEqual(summary["ok"], 1)
        self.assertEqual(summary["skipped"], 0, "a zero-byte file is not a capture")

    def test_refetches_truncated_file(self):
        date_dir = os.path.join(self.data_dir, self.today.isoformat())
        os.makedirs(date_dir, exist_ok=True)
        with open(os.path.join(date_dir, "fresno-ca_gfs025.json.gz"), "wb") as handle:
            handle.write(b"not gzip at all")
        session = FakeSession([FakeResponse(200, SAMPLE_BODY)])

        summary = fetch_ensemble.capture_date(
            self.config, self.data_dir, self.today, session, self.today)

        self.assertEqual(summary["ok"], 1)
        self.assertEqual(summary["skipped"], 0)

    def test_refetches_truncated_gzip_body(self):
        """A file with valid gzip magic bytes but a truncated body must be re-fetched.

        Regression test. If this is skipped, check_gaps --deep rejects the file
        on every run while the fetcher never repairs it, and the capture is lost
        once it falls outside the retention window.
        """
        path = self.write_existing("fresno-ca_gfs025.json.gz")
        with open(path, "rb") as handle:
            good = handle.read()
        with open(path, "wb") as handle:
            handle.write(good[: len(good) // 2])

        self.assertEqual(good[:2], b"\x1f\x8b")
        self.assertFalse(fetch_ensemble.existing_file_is_usable(path))

        session = FakeSession([FakeResponse(200, SAMPLE_BODY)])
        summary = fetch_ensemble.capture_date(
            self.config, self.data_dir, self.today, session, self.today)

        self.assertEqual(summary["ok"], 1)
        self.assertEqual(summary["skipped"], 0)
        with gzip.open(path, "rb") as handle:
            self.assertEqual(handle.read(), SAMPLE_BODY)

    def test_refetches_gzip_containing_non_json(self):
        path = self.write_existing("fresno-ca_gfs025.json.gz", body=b"<html>rate limited</html>")
        self.assertFalse(fetch_ensemble.existing_file_is_usable(path))

        session = FakeSession([FakeResponse(200, SAMPLE_BODY)])
        summary = fetch_ensemble.capture_date(
            self.config, self.data_dir, self.today, session, self.today)
        self.assertEqual(summary["ok"], 1)

    def test_stored_bytes_round_trip_unchanged(self):
        session = FakeSession([FakeResponse(200, SAMPLE_BODY)])
        fetch_ensemble.capture_date(
            self.config, self.data_dir, self.today, session, self.today)

        path = os.path.join(self.data_dir, self.today.isoformat(), "fresno-ca_gfs025.json.gz")
        with gzip.open(path, "rb") as handle:
            self.assertEqual(handle.read(), SAMPLE_BODY, "raw response bytes must be stored verbatim")


class IsolationAndManifestTests(unittest.TestCase):
    """One bad response must not cost us the other fourteen."""

    def setUp(self):
        patcher = mock.patch.object(fetch_ensemble.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = os.path.join(self.tmp.name, "data")
        self.today = dt.date(2026, 7, 25)

    def read_manifest(self, date: dt.date) -> dict:
        path = os.path.join(self.data_dir, date.isoformat(), "_manifest.json")
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def test_one_failing_pair_does_not_abort_the_rest(self):
        config = make_config(self.tmp.name, locations=5, models=3)

        def responder(params):
            if params["models"] == "ecmwf_ifs025" and params["latitude"] == 34.0522:
                return FakeResponse(500, b"this one is cursed")
            return FakeResponse(200, SAMPLE_BODY)

        session = ScriptedSession(responder)
        summary = fetch_ensemble.capture_date(
            config, self.data_dir, self.today, session, self.today)

        self.assertEqual(summary["ok"], 14)
        self.assertEqual(summary["failed"], 1)

        manifest = self.read_manifest(self.today)
        self.assertEqual(manifest["ok"], 14)
        self.assertEqual(manifest["failed"], 1)
        self.assertFalse(manifest["complete"])
        self.assertEqual(
            manifest["entries"]["los-angeles-ca_ecmwf_ifs025.json.gz"]["status"], "failed")

    def test_a_raising_session_still_lets_others_through(self):
        config = make_config(self.tmp.name, locations=2, models=1)

        def responder(params):
            if params["latitude"] == 38.5816:
                return requests.ConnectionError("network went away")
            return FakeResponse(200, SAMPLE_BODY)

        session = ScriptedSession(responder)
        summary = fetch_ensemble.capture_date(
            config, self.data_dir, self.today, session, self.today)

        self.assertEqual(summary["ok"], 1)
        self.assertEqual(summary["failed"], 1)

    def test_manifest_records_success_detail(self):
        config = make_config(self.tmp.name, locations=1, models=1)
        session = FakeSession([FakeResponse(200, SAMPLE_BODY)])
        fetch_ensemble.capture_date(config, self.data_dir, self.today, session, self.today)

        manifest = self.read_manifest(self.today)
        entry = manifest["entries"]["fresno-ca_gfs025.json.gz"]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["raw_bytes"], len(SAMPLE_BODY))
        self.assertEqual(len(entry["sha256"]), 64)
        self.assertTrue(manifest["complete"])
        self.assertEqual(manifest["expected_files"], ["fresno-ca_gfs025.json.gz"])

    def test_late_capture_is_labelled(self):
        config = make_config(self.tmp.name, locations=1, models=1)
        two_days_ago = self.today - dt.timedelta(days=2)
        session = FakeSession([FakeResponse(200, SAMPLE_BODY)])

        summary = fetch_ensemble.capture_date(
            config, self.data_dir, two_days_ago, session, self.today)

        self.assertTrue(summary["late"])
        manifest = self.read_manifest(two_days_ago)
        self.assertTrue(manifest["entries"]["fresno-ca_gfs025.json.gz"]["late"],
                        "a backfilled date is not the run issued that day and must say so")

    def test_same_day_capture_is_not_late(self):
        config = make_config(self.tmp.name, locations=1, models=1)
        session = FakeSession([FakeResponse(200, SAMPLE_BODY)])
        fetch_ensemble.capture_date(config, self.data_dir, self.today, session, self.today)

        manifest = self.read_manifest(self.today)
        self.assertFalse(manifest["entries"]["fresno-ca_gfs025.json.gz"]["late"])

    def test_rerun_repairs_a_previous_failure(self):
        config = make_config(self.tmp.name, locations=1, models=2)

        failing = ScriptedSession(
            lambda params: FakeResponse(200, SAMPLE_BODY)
            if params["models"] == "gfs025" else FakeResponse(500, b"boom"))
        fetch_ensemble.capture_date(config, self.data_dir, self.today, failing, self.today)
        self.assertEqual(self.read_manifest(self.today)["failed"], 1)

        # The 18:00 run: only the missing file is fetched, and the manifest heals.
        recovering = FakeSession([FakeResponse(200, SAMPLE_BODY)])
        summary = fetch_ensemble.capture_date(
            config, self.data_dir, self.today, recovering, self.today)

        self.assertEqual(summary["ok"], 1)
        self.assertEqual(summary["skipped"], 1)
        manifest = self.read_manifest(self.today)
        self.assertEqual(manifest["failed"], 0)
        self.assertTrue(manifest["complete"])


class TargetDateTests(unittest.TestCase):
    def test_default_window_is_trailing_three_days(self):
        args = argparse_namespace(days=3, start_date=None, end_date=None)
        with mock.patch.object(fetch_ensemble, "utc_today", return_value=dt.date(2026, 7, 25)):
            dates = fetch_ensemble.target_dates(args)
        self.assertEqual(
            [d.isoformat() for d in dates], ["2026-07-23", "2026-07-24", "2026-07-25"])

    def test_explicit_range_is_inclusive(self):
        args = argparse_namespace(days=3, start_date="2026-07-20", end_date="2026-07-22")
        with mock.patch.object(fetch_ensemble, "utc_today", return_value=dt.date(2026, 7, 25)):
            dates = fetch_ensemble.target_dates(args)
        self.assertEqual(
            [d.isoformat() for d in dates], ["2026-07-20", "2026-07-21", "2026-07-22"])

    def test_reversed_range_is_rejected(self):
        args = argparse_namespace(days=3, start_date="2026-07-22", end_date="2026-07-20")
        with mock.patch.object(fetch_ensemble, "utc_today", return_value=dt.date(2026, 7, 25)):
            with self.assertRaises(ValueError):
                fetch_ensemble.target_dates(args)


def argparse_namespace(**kwargs):
    import argparse
    return argparse.Namespace(**kwargs)


if __name__ == "__main__":
    unittest.main()
