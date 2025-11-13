"""Client helpers for interacting with the Instapaper API.

The module contains a thin wrapper around the handful of API calls that we
need for the CLI.  It purposely keeps the surface area small so that it can be
unit tested without network access.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional
from urllib.parse import parse_qs


__all__ = [
    "InstapaperClient",
    "InstapaperError",
    "BookmarkRequest",
]


class InstapaperError(RuntimeError):
    """Raised when the Instapaper API returns an error response."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class BookmarkRequest:
    """Represents a request to add a bookmark to Instapaper."""

    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    folder_id: Optional[str] = None

    def to_payload(self) -> dict[str, str]:
        payload: dict[str, str] = {"url": self.url}
        if self.title:
            payload["title"] = self.title
        if self.description:
            payload["description"] = self.description
        if self.folder_id:
            payload["folder_id"] = self.folder_id
        return payload


class InstapaperClient:
    """Minimal Instapaper API client.

    Parameters
    ----------
    consumer_key:
        Instapaper API consumer key.
    consumer_secret:
        Instapaper API consumer secret.
    username:
        Instapaper account username (usually the email address).
    password:
        Instapaper account password.
    session_factory:
        Optional callable used to construct :class:`OAuth1Session`.  This is
        primarily used by the tests to provide a fake in-memory session.
    """

    API_ROOT = "https://www.instapaper.com/api/1"

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        username: str,
        password: str,
        *,
        session_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        if not all([consumer_key, consumer_secret, username, password]):
            raise ValueError("All Instapaper credentials must be provided.")

        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.username = username
        self.password = password
        self._session_factory = session_factory or _load_session_factory()
        self._access_token: Optional[str] = None
        self._access_token_secret: Optional[str] = None

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------
    def authenticate(self) -> None:
        """Authenticate the client using xAuth.

        Instapaper issues access tokens via OAuth1's xAuth flow.  The response
        body is a URL encoded string which we parse into token and secret.
        """

        session = self._session_factory(
            self.consumer_key,
            client_secret=self.consumer_secret,
        )

        response = session.post(
            f"{self.API_ROOT}/oauth/access_token",
            data={
                "x_auth_username": self.username,
                "x_auth_password": self.password,
                "x_auth_mode": "client_auth",
            },
        )
        token, secret = self._parse_access_token_response(response)
        self._access_token = token
        self._access_token_secret = secret

    @staticmethod
    def _parse_access_token_response(response: Any) -> tuple[str, str]:
        if response.status_code != 200:
            raise InstapaperError(
                f"Authentication failed with status {response.status_code}: {response.text}",
                status_code=response.status_code,
            )

        parsed = parse_qs(response.text)
        try:
            token = parsed["oauth_token"][0]
            secret = parsed["oauth_token_secret"][0]
        except (KeyError, IndexError):
            raise InstapaperError(
                "Could not parse access token from Instapaper response.",
                status_code=response.status_code,
            ) from None
        return token, secret

    # ------------------------------------------------------------------
    # Bookmark helpers
    # ------------------------------------------------------------------
    def add_bookmark(self, request: BookmarkRequest) -> dict:
        """Add a bookmark to Instapaper.

        Parameters
        ----------
        request:
            The bookmark request to send to Instapaper.

        Returns
        -------
        dict
            Parsed JSON response from the API.
        """

        session = self._ensure_session()
        response = session.post(
            f"{self.API_ROOT}/bookmarks/add",
            data=request.to_payload(),
        )

        if response.status_code == 200:
            return response.json()

        raise InstapaperError(
            f"Failed to add bookmark: {response.status_code} {response.text}",
            status_code=response.status_code,
        )

    def bulk_add(self, requests_: Iterable[BookmarkRequest]) -> list[dict]:
        """Add multiple bookmarks and return their responses."""

        results = []
        for request in requests_:
            results.append(self.add_bookmark(request))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_session(self) -> OAuth1Session:
        if not (self._access_token and self._access_token_secret):
            self.authenticate()

        session = self._session_factory(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=self._access_token,
            resource_owner_secret=self._access_token_secret,
        )
        return session


def add_urls(
    client: InstapaperClient,
    urls: Iterable[BookmarkRequest],
) -> list[dict]:
    """Convenience helper used by the CLI to add many URLs."""

    return client.bulk_add(urls)


def _load_session_factory() -> Callable[..., Any]:
    try:
        from requests_oauthlib import OAuth1Session
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "requests-oauthlib is required to use InstapaperClient. Install the package via 'pip install requests-oauthlib'."
        ) from exc
    return OAuth1Session
