"""Command line interface for adding URLs to Instapaper."""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional

from .client import BookmarkRequest, InstapaperClient, InstapaperError, add_urls
from .io_utils import BookmarkLoadError, load_from_path

ENV_VARS = {
    "consumer_key": "INSTAPAPER_API_KEY",
    "consumer_secret": "INSTAPAPER_API_SECRET",
    "username": "INSTAPAPER_USERNAME",
    "password": "INSTAPAPER_PASSWORD",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bulk create Instapaper bookmarks from files or URLs.",
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Input files containing URLs (CSV, JSON, TXT). If omitted, URLs must be provided via --url.",
    )
    parser.add_argument(
        "--url",
        dest="urls",
        action="append",
        help="URL to add to Instapaper. Can be specified multiple times.",
    )
    parser.add_argument(
        "--title",
        dest="title",
        help="Title to use when --url is provided without a file.",
    )
    parser.add_argument(
        "--description",
        dest="description",
        help="Description to use when --url is provided without a file.",
    )
    parser.add_argument(
        "--folder-id",
        dest="folder_id",
        help="Optional folder ID for URLs supplied via --url.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse inputs and report the actions without calling the API.",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Fail if credentials are missing instead of prompting interactively.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print URLs as they are processed.",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        requests = list(_collect_requests(args))
    except BookmarkLoadError as exc:  # pragma: no cover - defensive
        parser.error(str(exc))

    if not requests:
        parser.error("No URLs were provided.")

    if args.dry_run:
        _print_dry_run(requests)
        return 0

    client = _create_client(no_prompt=args.no_prompt)
    try:
        responses = add_urls(client, requests)
    except InstapaperError as exc:
        parser.error(str(exc))

    if args.verbose:
        for request, response in zip(requests, responses):
            print(f"Added {request.url}: {response}")

    return 0


def _collect_requests(args: argparse.Namespace) -> Iterable[BookmarkRequest]:
    for input_path in args.inputs:
        path = Path(input_path)
        if not path.exists():
            raise BookmarkLoadError(f"Input file '{input_path}' does not exist.")
        for request in load_from_path(path):
            yield request

    for url in args.urls or []:
        yield BookmarkRequest(
            url=url,
            title=args.title,
            description=args.description,
            folder_id=args.folder_id,
        )


def _create_client(*, no_prompt: bool) -> InstapaperClient:
    credentials = {}
    missing = []
    for field, env_var in ENV_VARS.items():
        value = os.getenv(env_var)
        if value:
            credentials[field] = value
        else:
            missing.append(field)

    if missing:
        if no_prompt:
            raise SystemExit(
                "Missing credentials. Set the environment variables or run without --no-prompt."
            )
        _prompt_for_credentials(credentials, missing)

    try:
        return InstapaperClient(**credentials)
    except RuntimeError as exc:  # pragma: no cover - dependency errors
        raise SystemExit(str(exc))


def _prompt_for_credentials(credentials: dict, missing: List[str]) -> None:
    prompt_map = {
        "consumer_key": "Instapaper API key",
        "consumer_secret": "Instapaper API secret",
        "username": "Instapaper username",
        "password": "Instapaper password",
    }

    for field in missing:
        prompt = prompt_map[field]
        if field == "password":
            value = getpass.getpass(f"{prompt}: ")
        else:
            value = input(f"{prompt}: ")
        if not value:
            raise SystemExit(f"{prompt} is required to continue.")
        credentials[field] = value


def _print_dry_run(requests: Iterable[BookmarkRequest]) -> None:
    print("Dry run: the following URLs would be added to Instapaper:")
    for request in requests:
        line = f"- {request.url}"
        if request.title:
            line += f" (title: {request.title})"
        if request.folder_id:
            line += f" [folder: {request.folder_id}]"
        print(line)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
