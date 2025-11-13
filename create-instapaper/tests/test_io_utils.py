import json
from pathlib import Path

import pytest

from create_instapaper.io_utils import BookmarkLoadError, load_from_path


def write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_load_from_csv(tmp_path: Path):
    path = write(
        tmp_path / "bookmarks.csv",
        "url,title,description\nhttps://example.com,Example,Description\n",
    )

    requests = load_from_path(path)
    assert len(requests) == 1
    request = requests[0]
    assert request.url == "https://example.com"
    assert request.title == "Example"
    assert request.description == "Description"


def test_load_from_text(tmp_path: Path):
    path = write(
        tmp_path / "list.txt",
        "# comment\nhttps://example.com|Title|Desc|123\n",
    )

    requests = load_from_path(path)
    assert len(requests) == 1
    request = requests[0]
    assert request.folder_id == "123"


def test_load_from_json(tmp_path: Path):
    path = tmp_path / "bookmarks.json"
    path.write_text(
        json.dumps({"items": [{"url": "https://example.com", "title": "Ex"}]}),
        encoding="utf-8",
    )

    requests = load_from_path(path)
    assert requests[0].title == "Ex"


def test_invalid_format(tmp_path: Path):
    path = write(tmp_path / "bookmarks.xml", "<xml />")
    with pytest.raises(BookmarkLoadError):
        load_from_path(path)
