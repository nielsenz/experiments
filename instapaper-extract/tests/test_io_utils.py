"""Tests for io_utils module."""
import csv
import json
from pathlib import Path

import pytest

from instapaper_extract.io_utils import (
    clean_html,
    export_bookmarks_to_csv,
    export_highlights_to_csv,
    export_to_json,
    get_highlights_output_path,
)


class TestCleanHtml:
    """Tests for clean_html function."""

    def test_remove_html_tags(self):
        """Should remove HTML tags."""
        html = "<p>Hello <strong>world</strong></p>"
        assert clean_html(html) == "Hello world"

    def test_unescape_entities(self):
        """Should unescape HTML entities."""
        html = "Hello &amp; goodbye &lt;world&gt;"
        assert clean_html(html) == "Hello & goodbye <world>"

    def test_remove_extra_whitespace(self):
        """Should normalize whitespace."""
        html = "Hello    world\n\n\ntest"
        assert clean_html(html) == "Hello world test"

    def test_empty_string(self):
        """Should handle empty strings."""
        assert clean_html("") == ""
        assert clean_html(None) == ""


class TestExportBookmarksToCsv:
    """Tests for export_bookmarks_to_csv function."""

    def test_export_basic_bookmarks(self, sample_bookmarks, tmp_path):
        """Should export bookmarks to CSV."""
        output_file = tmp_path / "bookmarks.csv"
        export_bookmarks_to_csv(sample_bookmarks, str(output_file), include_text=False)

        assert output_file.exists()

        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]['bookmark_id'] == '1'
        assert rows[0]['title'] == 'Test Article 1'
        assert rows[0]['starred'] == '1'
        assert rows[1]['starred'] == '0'

    def test_export_with_text(self, sample_bookmarks, tmp_path):
        """Should include full_text when requested."""
        output_file = tmp_path / "bookmarks.csv"
        export_bookmarks_to_csv(sample_bookmarks, str(output_file), include_text=True)

        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert 'full_text' in rows[0]
        assert rows[0]['full_text'] == 'This is the full text of article 1'

    def test_empty_bookmarks(self, tmp_path):
        """Should handle empty bookmark list."""
        output_file = tmp_path / "empty.csv"
        export_bookmarks_to_csv([], str(output_file))
        # Should not create file or should create empty file
        # Current implementation doesn't create file for empty list


class TestExportHighlightsToCsv:
    """Tests for export_highlights_to_csv function."""

    def test_export_highlights(self, sample_highlights, tmp_path):
        """Should export highlights to CSV."""
        output_file = tmp_path / "highlights.csv"
        export_highlights_to_csv(sample_highlights, str(output_file))

        assert output_file.exists()

        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]['highlight_id'] == '101'
        assert rows[0]['bookmark_id'] == '1'
        assert rows[0]['text'] == 'Important passage from article 1'
        assert rows[0]['note'] == 'My annotation'
        assert rows[1]['note'] == ''


class TestExportToJson:
    """Tests for export_to_json function."""

    def test_export_json(self, sample_bookmarks, sample_highlights, tmp_path):
        """Should export bookmarks and highlights to JSON."""
        output_file = tmp_path / "export.json"
        export_to_json(
            sample_bookmarks,
            sample_highlights,
            str(output_file),
            include_text=True,
        )

        assert output_file.exists()

        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        assert data['total_bookmarks'] == 2
        assert data['total_highlights'] == 2
        assert len(data['bookmarks']) == 2

        # First bookmark should have 2 highlights
        bookmark1 = data['bookmarks'][0]
        assert bookmark1['bookmark_id'] == 1
        assert len(bookmark1['highlights']) == 2

        # Second bookmark should have no highlights
        bookmark2 = data['bookmarks'][1]
        assert bookmark2['bookmark_id'] == 2
        assert len(bookmark2['highlights']) == 0


class TestGetHighlightsOutputPath:
    """Tests for get_highlights_output_path function."""

    def test_simple_filename(self):
        """Should add _highlights suffix to simple filename."""
        result = get_highlights_output_path("articles.csv")
        assert result == "articles_highlights.csv"

    def test_with_directory(self):
        """Should preserve directory path."""
        result = get_highlights_output_path("data/export.csv")
        assert result == "data/export_highlights.csv"

    def test_different_extension(self):
        """Should work with different file extensions."""
        result = get_highlights_output_path("output.txt")
        assert result == "output_highlights.txt"
