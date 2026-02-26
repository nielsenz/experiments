"""Instapaper API client wrapper for extracting bookmarks and highlights."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import sys

from pyinstapaper import Instapaper


class InstapaperError(RuntimeError):
    """Base exception for Instapaper API errors."""
    pass


class AuthenticationError(InstapaperError):
    """Raised when authentication fails."""
    pass


class ExtractionError(InstapaperError):
    """Raised when extraction operations fail."""
    pass


@dataclass
class BookmarkData:
    """Represents a bookmark with its metadata."""
    bookmark_id: int
    title: str
    url: str
    description: str
    time_added: int
    progress: float
    starred: bool
    full_text: Optional[str] = None


@dataclass
class HighlightData:
    """Represents a highlight/annotation on a bookmark."""
    highlight_id: int
    bookmark_id: int
    text: str
    note: Optional[str]
    time: int
    position: int


class InstapaperExtractor:
    """
    Wrapper around pyinstapaper for extracting bookmarks and highlights.

    This client provides a clean interface for fetching bookmarks and their
    associated highlights from the Instapaper API.
    """

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        username: str,
        password: str,
    ):
        """
        Initialize the Instapaper extractor.

        Args:
            consumer_key: Instapaper API consumer key
            consumer_secret: Instapaper API consumer secret
            username: Instapaper account username/email
            password: Instapaper account password
        """
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.username = username
        self.password = password
        self._client: Optional[Instapaper] = None

    def authenticate(self, verbose: bool = False) -> None:
        """
        Authenticate with the Instapaper API.

        Args:
            verbose: If True, print status messages

        Raises:
            AuthenticationError: If authentication fails
        """
        if verbose:
            print("Authenticating with Instapaper...")

        try:
            self._client = Instapaper(self.consumer_key, self.consumer_secret)
            self._client.login(self.username, self.password)
            if verbose:
                print("Authentication successful!")
        except Exception as e:
            raise AuthenticationError(f"Authentication failed: {e}") from e

    @property
    def client(self) -> Instapaper:
        """Get the authenticated client, authenticating if needed."""
        if self._client is None:
            self.authenticate()
        return self._client

    def get_all_bookmarks(self, verbose: bool = False) -> List[BookmarkData]:
        """
        Fetch all bookmarks from all folders (unread, archive, starred).

        Args:
            verbose: If True, print progress messages

        Returns:
            List of BookmarkData objects

        Raises:
            ExtractionError: If fetching bookmarks fails
        """
        if verbose:
            print("Fetching bookmarks...")

        raw_bookmarks = []

        # Fetch unread bookmarks
        try:
            unread = self.client.get_bookmarks('unread', limit=500)
            raw_bookmarks.extend(unread)
            if verbose:
                print(f"Found {len(unread)} unread articles")
        except Exception as e:
            if verbose:
                print(f"Warning: Error fetching unread bookmarks: {e}", file=sys.stderr)

        # Fetch archive
        try:
            archive = self.client.get_bookmarks('archive', limit=500)
            raw_bookmarks.extend(archive)
            if verbose:
                print(f"Found {len(archive)} archived articles")
        except Exception as e:
            if verbose:
                print(f"Warning: Error fetching archived bookmarks: {e}", file=sys.stderr)

        # Fetch starred (deduplicate)
        try:
            starred = self.client.get_bookmarks('starred', limit=500)
            existing_ids = {b.bookmark_id for b in raw_bookmarks}
            new_starred = [b for b in starred if b.bookmark_id not in existing_ids]
            raw_bookmarks.extend(new_starred)
            if verbose:
                print(f"Found {len(new_starred)} additional starred articles")
        except Exception as e:
            if verbose:
                print(f"Warning: Error fetching starred bookmarks: {e}", file=sys.stderr)

        if not raw_bookmarks:
            return []

        # Convert to BookmarkData objects
        bookmarks = []
        for bookmark in raw_bookmarks:
            bookmarks.append(BookmarkData(
                bookmark_id=bookmark.bookmark_id,
                title=bookmark.title or '',
                url=bookmark.url or '',
                description=bookmark.description or '',
                time_added=bookmark.time if hasattr(bookmark, 'time') else 0,
                progress=bookmark.progress if hasattr(bookmark, 'progress') else 0.0,
                starred=bool(hasattr(bookmark, 'starred') and bookmark.starred),
            ))

        return bookmarks

    def get_bookmark_text(self, bookmark_id: int, verbose: bool = False) -> str:
        """
        Fetch the full text content of a bookmark.

        Args:
            bookmark_id: The bookmark ID to fetch text for
            verbose: If True, print error messages

        Returns:
            Full text content (may be HTML)
        """
        try:
            # We need to get the bookmark object to call get_text()
            # This is a bit inefficient but matches pyinstapaper's API
            bookmarks = self.client.get_bookmarks('unread', limit=500)
            bookmarks.extend(self.client.get_bookmarks('archive', limit=500))
            bookmarks.extend(self.client.get_bookmarks('starred', limit=500))

            for bookmark in bookmarks:
                if bookmark.bookmark_id == bookmark_id:
                    return bookmark.get_text()

            return ''
        except Exception as e:
            if verbose:
                print(f"Warning: Could not fetch text for bookmark {bookmark_id}: {e}",
                      file=sys.stderr)
            return ''

    def get_bookmark_highlights(
        self,
        bookmark_obj,
        verbose: bool = False
    ) -> List[HighlightData]:
        """
        Fetch all highlights for a bookmark.

        Args:
            bookmark_obj: The pyinstapaper Bookmark object
            verbose: If True, print error messages

        Returns:
            List of HighlightData objects
        """
        try:
            raw_highlights = bookmark_obj.get_highlights()

            highlights = []
            for hl in raw_highlights:
                highlights.append(HighlightData(
                    highlight_id=hl.highlight_id,
                    bookmark_id=hl.bookmark_id,
                    text=hl.text or '',
                    note=hl.note if hasattr(hl, 'note') else None,
                    time=hl.time if hasattr(hl, 'time') else 0,
                    position=hl.position if hasattr(hl, 'position') else 0,
                ))

            return highlights
        except Exception as e:
            if verbose:
                print(f"Warning: Could not fetch highlights for bookmark {bookmark_obj.bookmark_id}: {e}",
                      file=sys.stderr)
            return []

    def get_all_highlights(self, verbose: bool = False) -> List[HighlightData]:
        """
        Fetch all highlights from all bookmarks.

        Args:
            verbose: If True, print progress messages

        Returns:
            List of HighlightData objects
        """
        if verbose:
            print("Fetching highlights...")

        # Get raw bookmark objects from pyinstapaper
        raw_bookmarks = []
        try:
            raw_bookmarks.extend(self.client.get_bookmarks('unread', limit=500))
        except Exception:
            pass

        try:
            raw_bookmarks.extend(self.client.get_bookmarks('archive', limit=500))
        except Exception:
            pass

        try:
            raw_bookmarks.extend(self.client.get_bookmarks('starred', limit=500))
        except Exception:
            pass

        # Deduplicate bookmarks
        seen = set()
        unique_bookmarks = []
        for b in raw_bookmarks:
            if b.bookmark_id not in seen:
                seen.add(b.bookmark_id)
                unique_bookmarks.append(b)

        # Fetch highlights for each bookmark
        all_highlights = []
        for bookmark in unique_bookmarks:
            highlights = self.get_bookmark_highlights(bookmark, verbose=False)
            all_highlights.extend(highlights)

        if verbose:
            print(f"Found {len(all_highlights)} total highlights")

        return all_highlights
