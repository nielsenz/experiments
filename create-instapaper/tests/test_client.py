from types import SimpleNamespace

import pytest

from create_instapaper.client import (
    BookmarkRequest,
    InstapaperClient,
    InstapaperError,
)


class DummyResponse:
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


class DummySession:
    def __init__(self, responses):
        self._responses = responses
        self.posts = []

    def post(self, url, data=None):
        self.posts.append((url, data))
        if not self._responses:
            raise AssertionError("No more responses configured for DummySession")
        return self._responses.pop(0)


def make_session_factory(responses):
    shared = list(responses)

    def factory(*args, **kwargs):
        return DummySession(shared)

    return factory


def test_authentication_parses_tokens():
    responses = [DummyResponse(text="oauth_token=a&oauth_token_secret=b")]
    client = InstapaperClient(
        "key",
        "secret",
        "user",
        "pass",
        session_factory=make_session_factory(responses),
    )
    client.authenticate()
    assert client._access_token == "a"
    assert client._access_token_secret == "b"


def test_add_bookmark_raises_on_error():
    responses = [
        DummyResponse(text="oauth_token=a&oauth_token_secret=b"),
        DummyResponse(status_code=400, text="bad request"),
    ]
    client = InstapaperClient(
        "key",
        "secret",
        "user",
        "pass",
        session_factory=make_session_factory(responses),
    )

    with pytest.raises(InstapaperError):
        client.add_bookmark(BookmarkRequest(url="https://example.com"))


def test_bulk_add_returns_responses():
    responses = [
        DummyResponse(text="oauth_token=a&oauth_token_secret=b"),
        DummyResponse(json_data={"bookmark_id": 1}),
        DummyResponse(json_data={"bookmark_id": 2}),
    ]
    client = InstapaperClient(
        "key",
        "secret",
        "user",
        "pass",
        session_factory=make_session_factory(responses),
    )

    results = client.bulk_add(
        [
            BookmarkRequest(url="https://example.com/1"),
            BookmarkRequest(url="https://example.com/2"),
        ]
    )
    assert results == [{"bookmark_id": 1}, {"bookmark_id": 2}]
