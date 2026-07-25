"""Tests for check_gaps.py -- the thing that has to turn silence into a red X.

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

import check_gaps  # noqa: E402


TODAY = dt.date(2026, 7, 25)
SAMPLE_BODY = json.dumps({"hourly": {"time": [], "temperature_2m_member01": []}}).encode("utf-8")

LOCATIONS = ["fresno-ca", "sacramento-ca", "los-angeles-ca", "las-vegas-nv", "henderson-nv"]
MODELS = ["gfs025", "ecmwf_ifs025", "icon_seamless"]


class GapDetectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_dir = os.path.join(self.tmp.name, "data")
        self.config_path = os.path.join(self.tmp.name, "locations.json")
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump({
                "endpoint": "https://example.invalid",
                "models": MODELS,
                "hourly": ["temperature_2m"],
                "forecast_days": 7,
                "locations": [
                    {"slug": slug, "name": slug, "latitude": 0.0, "longitude": 0.0}
                    for slug in LOCATIONS
                ],
            }, handle)

        patcher = mock.patch.object(check_gaps, "utc_today", return_value=TODAY)
        patcher.start()
        self.addCleanup(patcher.stop)

    # -- helpers ---------------------------------------------------------

    def expected_files(self) -> list[str]:
        return sorted(f"{slug}_{model}.json.gz" for slug in LOCATIONS for model in MODELS)

    def make_complete_date(self, date: dt.date, omit: list[str] | None = None,
                           late: bool = False) -> str:
        omit = omit or []
        date_dir = os.path.join(self.data_dir, date.isoformat())
        os.makedirs(date_dir, exist_ok=True)
        entries = {}
        for filename in self.expected_files():
            if filename in omit:
                continue
            with gzip.open(os.path.join(date_dir, filename), "wb") as handle:
                handle.write(SAMPLE_BODY)
            entries[filename] = {"status": "ok", "late": late}
        with open(os.path.join(date_dir, "_manifest.json"), "w", encoding="utf-8") as handle:
            json.dump({
                "schema_version": 1,
                "date": date.isoformat(),
                "expected_files": self.expected_files(),
                "entries": entries,
            }, handle)
        return date_dir

    def make_full_window(self, days: int = 3, **kwargs) -> None:
        for offset in range(days):
            self.make_complete_date(TODAY - dt.timedelta(days=offset), **kwargs)

    def run_check(self, *extra) -> int:
        return check_gaps.main(
            ["--config", self.config_path, "--data-dir", self.data_dir, *extra])

    # -- the happy path --------------------------------------------------

    def test_complete_window_passes(self):
        self.make_full_window()
        self.assertEqual(self.run_check("--days", "3"), 0)

    def test_complete_window_passes_deep_check(self):
        self.make_full_window()
        self.assertEqual(self.run_check("--days", "3", "--deep"), 0)

    def test_extra_history_does_not_affect_the_window(self):
        self.make_full_window()
        self.make_complete_date(TODAY - dt.timedelta(days=9), omit=["fresno-ca_gfs025.json.gz"])
        self.assertEqual(self.run_check("--days", "3"), 0,
                         "an old incomplete date must not fail the trailing window")

    # -- the failures that matter ---------------------------------------

    def test_missing_date_directory_fails(self):
        self.make_complete_date(TODAY)
        self.make_complete_date(TODAY - dt.timedelta(days=1))
        # TODAY-2 never captured.
        self.assertEqual(self.run_check("--days", "3"), 1)

    def test_empty_archive_fails(self):
        self.assertEqual(self.run_check("--days", "3"), 1)

    def test_single_missing_file_fails(self):
        self.make_full_window()
        os.remove(os.path.join(
            self.data_dir, TODAY.isoformat(), "henderson-nv_icon_seamless.json.gz"))
        self.assertEqual(self.run_check("--days", "3"), 1,
                         "14 of 15 files is an incomplete day")

    def test_zero_byte_file_fails(self):
        self.make_full_window()
        path = os.path.join(self.data_dir, TODAY.isoformat(), "fresno-ca_gfs025.json.gz")
        open(path, "wb").close()
        self.assertEqual(self.run_check("--days", "3"), 1)

    def test_non_gzip_file_fails(self):
        self.make_full_window()
        path = os.path.join(self.data_dir, TODAY.isoformat(), "fresno-ca_gfs025.json.gz")
        with open(path, "wb") as handle:
            handle.write(b"<html>rate limited</html>")
        self.assertEqual(self.run_check("--days", "3"), 1)

    def test_corrupt_gzip_body_is_caught_by_deep_check(self):
        self.make_full_window()
        path = os.path.join(self.data_dir, TODAY.isoformat(), "fresno-ca_gfs025.json.gz")
        with open(path, "rb") as handle:
            good = handle.read()
        with open(path, "wb") as handle:
            handle.write(good[: len(good) // 2])  # valid magic bytes, truncated body

        self.assertEqual(self.run_check("--days", "3", "--deep"), 1)

    def test_missing_manifest_fails(self):
        self.make_full_window()
        os.remove(os.path.join(self.data_dir, TODAY.isoformat(), "_manifest.json"))
        self.assertEqual(self.run_check("--days", "3"), 1)

    def test_window_size_is_respected(self):
        self.make_complete_date(TODAY)
        self.assertEqual(self.run_check("--days", "1"), 0)
        self.assertEqual(self.run_check("--days", "3"), 1)

    # -- reporting -------------------------------------------------------

    def test_late_capture_is_reported_but_still_counts_as_present(self):
        self.make_full_window(late=True)
        self.assertEqual(self.run_check("--days", "3"), 0)
        results = [check_gaps.check_date(
            self.data_dir, TODAY.isoformat(), self.expected_files(), False)]
        self.assertTrue(results[0]["late"])
        self.assertTrue(results[0]["complete"])

    def test_check_date_lists_each_problem(self):
        self.make_complete_date(
            TODAY, omit=["fresno-ca_gfs025.json.gz", "las-vegas-nv_icon_seamless.json.gz"])
        result = check_gaps.check_date(
            self.data_dir, TODAY.isoformat(), self.expected_files(), False)

        self.assertFalse(result["complete"])
        self.assertEqual(result["present"], 13)
        self.assertEqual(result["expected"], 15)
        self.assertEqual(len(result["problems"]), 2)
        self.assertTrue(all("missing" in problem for problem in result["problems"]))

    def test_all_mode_never_fails_the_build(self):
        self.make_complete_date(TODAY - dt.timedelta(days=30), omit=["fresno-ca_gfs025.json.gz"])
        self.assertEqual(self.run_check("--all"), 0,
                         "--all is a report, not a gate")

    def test_all_mode_judges_history_by_its_own_manifest(self):
        """Adding a location later must not retroactively invalidate good history."""
        date = TODAY - dt.timedelta(days=40)
        date_dir = os.path.join(self.data_dir, date.isoformat())
        os.makedirs(date_dir, exist_ok=True)

        # This date was captured when only two locations were configured.
        historical = sorted(
            f"{slug}_{model}.json.gz" for slug in LOCATIONS[:2] for model in MODELS)
        for filename in historical:
            with gzip.open(os.path.join(date_dir, filename), "wb") as handle:
                handle.write(SAMPLE_BODY)
        with open(os.path.join(date_dir, "_manifest.json"), "w", encoding="utf-8") as handle:
            json.dump({
                "schema_version": 1,
                "date": date.isoformat(),
                "expected_files": historical,
                "entries": {name: {"status": "ok"} for name in historical},
            }, handle)

        result = check_gaps.check_date(self.data_dir, date.isoformat(), historical, False)
        self.assertTrue(result["complete"])
        self.assertEqual(result["expected"], 6)

        # And against the current 5-location config it would look incomplete,
        # which is exactly why --all uses the recorded list.
        against_current = check_gaps.check_date(
            self.data_dir, date.isoformat(), self.expected_files(), False)
        self.assertFalse(against_current["complete"])

    def test_manifest_recorded_failure_is_surfaced(self):
        date_dir = self.make_complete_date(TODAY, omit=["fresno-ca_gfs025.json.gz"])
        manifest_path = os.path.join(date_dir, "_manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        manifest["entries"]["fresno-ca_gfs025.json.gz"] = {
            "status": "failed", "error": "HTTP 500"}
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle)

        result = check_gaps.check_date(
            self.data_dir, TODAY.isoformat(), self.expected_files(), False)
        self.assertIn("fresno-ca_gfs025.json.gz", result["manifest_failures"])


if __name__ == "__main__":
    unittest.main()
