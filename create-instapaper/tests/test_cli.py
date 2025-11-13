import os
from pathlib import Path
from unittest import mock

import pytest

from create_instapaper import cli
from create_instapaper.client import InstapaperError


def write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_dry_run_outputs_urls(tmp_path, capsys):
    csv_path = write(
        tmp_path / "urls.csv",
        "url\nhttps://example.com\n",
    )

    exit_code = cli.main([str(csv_path), "--dry-run"])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "https://example.com" in output


def test_no_prompt_requires_env(monkeypatch):
    monkeypatch.delenv("INSTAPAPER_API_KEY", raising=False)
    monkeypatch.delenv("INSTAPAPER_API_SECRET", raising=False)
    monkeypatch.delenv("INSTAPAPER_USERNAME", raising=False)
    monkeypatch.delenv("INSTAPAPER_PASSWORD", raising=False)

    with pytest.raises(SystemExit):
        cli._create_client(no_prompt=True)


def test_main_calls_add_urls(monkeypatch, tmp_path):
    text_path = write(tmp_path / "urls.txt", "https://example.com\n")

    fake_response = {"bookmark_id": 1}
    add_urls = mock.Mock(return_value=[fake_response])
    monkeypatch.setattr(cli, "add_urls", add_urls)

    def fake_client(**kwargs):
        class _FakeClient:
            pass

        return _FakeClient()

    monkeypatch.setattr(cli, "InstapaperClient", fake_client)
    monkeypatch.setitem(os.environ, "INSTAPAPER_API_KEY", "key")
    monkeypatch.setitem(os.environ, "INSTAPAPER_API_SECRET", "secret")
    monkeypatch.setitem(os.environ, "INSTAPAPER_USERNAME", "user")
    monkeypatch.setitem(os.environ, "INSTAPAPER_PASSWORD", "pass")

    exit_code = cli.main([str(text_path)])
    assert exit_code == 0
    assert add_urls.called


def test_main_handles_api_error(monkeypatch, tmp_path):
    text_path = write(tmp_path / "urls.txt", "https://example.com\n")

    def fake_client(**kwargs):
        class _FakeClient:
            def bulk_add(self, requests):
                raise InstapaperError("boom")

        return _FakeClient()

    monkeypatch.setattr(cli, "InstapaperClient", fake_client)
    monkeypatch.setitem(os.environ, "INSTAPAPER_API_KEY", "key")
    monkeypatch.setitem(os.environ, "INSTAPAPER_API_SECRET", "secret")
    monkeypatch.setitem(os.environ, "INSTAPAPER_USERNAME", "user")
    monkeypatch.setitem(os.environ, "INSTAPAPER_PASSWORD", "pass")

    with pytest.raises(SystemExit):
        cli.main([str(text_path)])
