"""Shared test fixtures for instapaper_extract tests."""
import pytest

from instapaper_extract.client import BookmarkData, HighlightData


@pytest.fixture
def sample_bookmarks():
    """Sample bookmark data for testing."""
    return [
        BookmarkData(
            bookmark_id=1,
            title="Test Article 1",
            url="https://example.com/article1",
            description="First test article",
            time_added=1638360000,
            progress=0.5,
            starred=True,
            full_text="This is the full text of article 1",
        ),
        BookmarkData(
            bookmark_id=2,
            title="Test Article 2",
            url="https://example.com/article2",
            description="Second test article",
            time_added=1638360100,
            progress=0.0,
            starred=False,
            full_text=None,
        ),
    ]


@pytest.fixture
def sample_highlights():
    """Sample highlight data for testing."""
    return [
        HighlightData(
            highlight_id=101,
            bookmark_id=1,
            text="Important passage from article 1",
            note="My annotation",
            time=1638360050,
            position=42,
        ),
        HighlightData(
            highlight_id=102,
            bookmark_id=1,
            text="Another highlight from article 1",
            note=None,
            time=1638360060,
            position=100,
        ),
    ]
