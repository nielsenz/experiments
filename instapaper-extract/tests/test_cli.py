"""Tests for CLI module."""
import pytest

from instapaper_extract.cli import build_parser, _get_credentials, ENV_VARS


class TestBuildParser:
    """Tests for build_parser function."""

    def test_default_arguments(self):
        """Should use default values."""
        parser = build_parser()
        args = parser.parse_args([])

        assert args.output == "instapaper_bookmarks.csv"
        assert args.format == "csv"
        assert args.highlights is True
        assert args.no_text is False
        assert args.verbose is False
        assert args.dry_run is False

    def test_custom_output(self):
        """Should accept custom output path."""
        parser = build_parser()
        args = parser.parse_args(["-o", "custom.csv"])

        assert args.output == "custom.csv"

    def test_json_format(self):
        """Should accept JSON format."""
        parser = build_parser()
        args = parser.parse_args(["--format", "json"])

        assert args.format == "json"

    def test_no_highlights(self):
        """Should disable highlights."""
        parser = build_parser()
        args = parser.parse_args(["--no-highlights"])

        assert args.highlights is False

    def test_highlights_only(self):
        """Should enable highlights-only mode."""
        parser = build_parser()
        args = parser.parse_args(["--highlights-only"])

        assert args.highlights_only is True

    def test_verbose_flag(self):
        """Should enable verbose mode."""
        parser = build_parser()
        args = parser.parse_args(["--verbose"])

        assert args.verbose is True

    def test_dry_run_flag(self):
        """Should enable dry-run mode."""
        parser = build_parser()
        args = parser.parse_args(["--dry-run"])

        assert args.dry_run is True


class TestGetCredentials:
    """Tests for _get_credentials function."""

    def test_missing_credentials_no_prompt(self, monkeypatch):
        """Should raise error when credentials missing and no-prompt is set."""
        # Clear environment variables
        for var in ENV_VARS.values():
            monkeypatch.delenv(var, raising=False)

        with pytest.raises(ValueError, match="Missing required credentials"):
            _get_credentials(allow_prompt=False)

    def test_credentials_from_env(self, monkeypatch):
        """Should read credentials from environment."""
        monkeypatch.setenv("INSTAPAPER_API_KEY", "test_key")
        monkeypatch.setenv("INSTAPAPER_API_SECRET", "test_secret")
        monkeypatch.setenv("INSTAPAPER_USERNAME", "test_user")
        monkeypatch.setenv("INSTAPAPER_PASSWORD", "test_pass")

        key, secret, user, password = _get_credentials(allow_prompt=False)

        assert key == "test_key"
        assert secret == "test_secret"
        assert user == "test_user"
        assert password == "test_pass"
