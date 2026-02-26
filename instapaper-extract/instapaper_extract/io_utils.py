"""Utilities for exporting bookmarks and highlights to various formats."""
from __future__ import annotations

import csv
import json
import re
from html import unescape
from pathlib import Path
from typing import List, Optional

from .client import BookmarkData, HighlightData


class ExportError(RuntimeError):
    """Raised when export operations fail."""
    pass


def clean_html(html_text: str) -> str:
    """
    Remove HTML tags and clean up text content.

    Args:
        html_text: Text potentially containing HTML

    Returns:
        Cleaned plain text
    """
    if not html_text:
        return ""

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', html_text)
    # Unescape HTML entities
    text = unescape(text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def export_bookmarks_to_csv(
    bookmarks: List[BookmarkData],
    output_path: str,
    include_text: bool = True,
    verbose: bool = False,
) -> None:
    """
    Export bookmarks to CSV format.

    Args:
        bookmarks: List of BookmarkData objects
        output_path: Path to output CSV file
        include_text: Whether to include full_text column
        verbose: If True, print progress messages

    Raises:
        ExportError: If export fails
    """
    if not bookmarks:
        if verbose:
            print("No bookmarks to export")
        return

    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'bookmark_id',
                'title',
                'url',
                'description',
                'time_added',
                'progress',
                'starred'
            ]

            if include_text:
                fieldnames.append('full_text')

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for bookmark in bookmarks:
                row = {
                    'bookmark_id': bookmark.bookmark_id,
                    'title': bookmark.title,
                    'url': bookmark.url,
                    'description': bookmark.description,
                    'time_added': bookmark.time_added,
                    'progress': bookmark.progress,
                    'starred': '1' if bookmark.starred else '0',
                }

                if include_text:
                    row['full_text'] = clean_html(bookmark.full_text or '')

                writer.writerow(row)

        if verbose:
            print(f"✓ Exported {len(bookmarks)} bookmarks to {output_path}")

    except Exception as e:
        raise ExportError(f"Failed to export bookmarks to CSV: {e}") from e


def export_highlights_to_csv(
    highlights: List[HighlightData],
    output_path: str,
    verbose: bool = False,
) -> None:
    """
    Export highlights to CSV format.

    Args:
        highlights: List of HighlightData objects
        output_path: Path to output CSV file
        verbose: If True, print progress messages

    Raises:
        ExportError: If export fails
    """
    if not highlights:
        if verbose:
            print("No highlights to export")
        return

    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'bookmark_id',
                'highlight_id',
                'text',
                'note',
                'time',
                'position'
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for highlight in highlights:
                row = {
                    'bookmark_id': highlight.bookmark_id,
                    'highlight_id': highlight.highlight_id,
                    'text': clean_html(highlight.text),
                    'note': clean_html(highlight.note) if highlight.note else '',
                    'time': highlight.time,
                    'position': highlight.position,
                }
                writer.writerow(row)

        if verbose:
            print(f"✓ Exported {len(highlights)} highlights to {output_path}")

    except Exception as e:
        raise ExportError(f"Failed to export highlights to CSV: {e}") from e


def export_to_json(
    bookmarks: List[BookmarkData],
    highlights: List[HighlightData],
    output_path: str,
    include_text: bool = True,
    verbose: bool = False,
) -> None:
    """
    Export bookmarks and highlights to JSON format.

    Args:
        bookmarks: List of BookmarkData objects
        highlights: List of HighlightData objects
        output_path: Path to output JSON file
        include_text: Whether to include full text
        verbose: If True, print progress messages

    Raises:
        ExportError: If export fails
    """
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Group highlights by bookmark_id
        highlights_by_bookmark = {}
        for hl in highlights:
            if hl.bookmark_id not in highlights_by_bookmark:
                highlights_by_bookmark[hl.bookmark_id] = []
            highlights_by_bookmark[hl.bookmark_id].append({
                'highlight_id': hl.highlight_id,
                'text': clean_html(hl.text),
                'note': clean_html(hl.note) if hl.note else None,
                'time': hl.time,
                'position': hl.position,
            })

        # Build bookmarks array with nested highlights
        bookmarks_data = []
        for bookmark in bookmarks:
            bookmark_dict = {
                'bookmark_id': bookmark.bookmark_id,
                'title': bookmark.title,
                'url': bookmark.url,
                'description': bookmark.description,
                'time_added': bookmark.time_added,
                'progress': bookmark.progress,
                'starred': bookmark.starred,
            }

            if include_text:
                bookmark_dict['full_text'] = clean_html(bookmark.full_text or '')

            # Add highlights if present
            if bookmark.bookmark_id in highlights_by_bookmark:
                bookmark_dict['highlights'] = highlights_by_bookmark[bookmark.bookmark_id]
            else:
                bookmark_dict['highlights'] = []

            bookmarks_data.append(bookmark_dict)

        # Create the output structure
        output_data = {
            'total_bookmarks': len(bookmarks),
            'total_highlights': len(highlights),
            'bookmarks': bookmarks_data,
        }

        with open(output_file, 'w', encoding='utf-8') as jsonfile:
            json.dump(output_data, jsonfile, indent=2, ensure_ascii=False)

        if verbose:
            print(f"✓ Exported {len(bookmarks)} bookmarks and {len(highlights)} highlights to {output_path}")

    except Exception as e:
        raise ExportError(f"Failed to export to JSON: {e}") from e


def get_highlights_output_path(bookmarks_path: str) -> str:
    """
    Generate the highlights CSV path from the bookmarks path.

    Args:
        bookmarks_path: Path to the bookmarks output file

    Returns:
        Path for highlights CSV (same directory, with _highlights suffix)

    Example:
        'articles.csv' -> 'articles_highlights.csv'
        'data/export.csv' -> 'data/export_highlights.csv'
    """
    path = Path(bookmarks_path)
    stem = path.stem
    suffix = path.suffix

    highlights_name = f"{stem}_highlights{suffix}"
    return str(path.parent / highlights_name)
