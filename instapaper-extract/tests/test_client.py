"""Tests for client module."""
import pytest

from instapaper_extract.client import (
    AuthenticationError,
    BookmarkData,
    HighlightData,
    InstapaperExtractor,
)


class TestBookmarkData:
    """Tests for BookmarkData dataclass."""

    def test_create_bookmark(self):
        """Should create BookmarkData instance."""
        bookmark = BookmarkData(
            bookmark_id=123,
            title="Test",
            url="https://example.com",
            description="Test desc",
            time_added=1638360000,
            progress=0.5,
            starred=True,
        )

        assert bookmark.bookmark_id == 123
        assert bookmark.title == "Test"
        assert bookmark.starred is True
        assert bookmark.full_text is None


class TestHighlightData:
    """Tests for HighlightData dataclass."""

    def test_create_highlight(self):
        """Should create HighlightData instance."""
        highlight = HighlightData(
            highlight_id=456,
            bookmark_id=123,
            text="Important passage",
            note="My note",
            time=1638360100,
            position=42,
        )

        assert highlight.highlight_id == 456
        assert highlight.bookmark_id == 123
        assert highlight.text == "Important passage"
        assert highlight.note == "My note"


class TestInstapaperExtractor:
    """Tests for InstapaperExtractor class."""

    def test_create_extractor(self):
        """Should create extractor instance."""
        extractor = InstapaperExtractor(
            consumer_key="key",
            consumer_secret="secret",
            username="user",
            password="pass",
        )

        assert extractor.consumer_key == "key"
        assert extractor.consumer_secret == "secret"
        assert extractor.username == "user"
        assert extractor.password == "pass"
        assert extractor._client is None

    # Note: Integration tests with real API would require mocking pyinstapaper
    # For now, we keep tests simple and focused on structure
