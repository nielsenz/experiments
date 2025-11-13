"""Utilities for loading bookmark payloads from different file formats."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List, Optional

from .client import BookmarkRequest


@dataclass
class LoadedBookmark:
    """Data structure returned by :func:`load_from_path`."""

    request: BookmarkRequest
    source: Path
    line_number: Optional[int] = None


class BookmarkLoadError(ValueError):
    """Raised when a bookmark cannot be parsed from an input file."""


def load_from_path(path: Path) -> List[BookmarkRequest]:
    """Load bookmark requests from a path.

    Parameters
    ----------
    path:
        Path to a CSV, JSON, or newline-delimited text file.  The loader infers
        the format from the file extension.
    """

    loader = _loader_for_suffix(path.suffix.lower())
    return [entry.request for entry in loader(path)]


def _loader_for_suffix(suffix: str):
    if suffix in {".csv"}:
        return _load_from_csv
    if suffix in {".json"}:
        return _load_from_json
    if suffix in {".txt", ""}:
        return _load_from_text
    raise BookmarkLoadError(
        f"Unsupported input format '{suffix or 'plain text'}'."
    )


def _load_from_csv(path: Path) -> Iterator[LoadedBookmark]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if "url" not in reader.fieldnames:
            raise BookmarkLoadError("CSV input must contain a 'url' column.")
        for index, row in enumerate(reader, start=2):
            request = _bookmark_from_row(row)
            yield LoadedBookmark(request=request, source=path, line_number=index)


def _bookmark_from_row(row: dict) -> BookmarkRequest:
    url = (row.get("url") or "").strip()
    if not url:
        raise BookmarkLoadError("Encountered a row without a URL.")

    return BookmarkRequest(
        url=url,
        title=_clean(row.get("title")),
        description=_clean(row.get("description")),
        folder_id=_clean(row.get("folder_id")),
    )


def _load_from_json(path: Path) -> Iterator[LoadedBookmark]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, dict):
        items = payload.get("items")
    else:
        items = payload

    if not isinstance(items, Iterable):
        raise BookmarkLoadError("JSON input must be an iterable of items.")

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise BookmarkLoadError(
                "JSON items must be objects containing at least a 'url' field."
            )
        request = _bookmark_from_row(item)
        yield LoadedBookmark(request=request, source=path, line_number=index)


def _load_from_text(path: Path) -> Iterator[LoadedBookmark]:
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            segments = [segment.strip() for segment in line.split("|")]
            url = segments[0]
            if not url:
                raise BookmarkLoadError(
                    f"Missing URL on line {index} of {path.name}."
                )
            title = segments[1] if len(segments) > 1 else None
            description = segments[2] if len(segments) > 2 else None
            folder_id = segments[3] if len(segments) > 3 else None
            request = BookmarkRequest(
                url=url,
                title=_clean(title),
                description=_clean(description),
                folder_id=_clean(folder_id),
            )
            yield LoadedBookmark(
                request=request,
                source=path,
                line_number=index,
            )


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None
