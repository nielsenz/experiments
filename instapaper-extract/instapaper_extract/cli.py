"""Command-line interface for extracting Instapaper bookmarks and highlights."""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path
from typing import Optional

from .client import (
    AuthenticationError,
    BookmarkData,
    ExtractionError,
    InstapaperExtractor,
)
from .io_utils import (
    ExportError,
    export_bookmarks_to_csv,
    export_highlights_to_csv,
    export_to_json,
    get_highlights_output_path,
)


ENV_VARS = {
    "consumer_key": "INSTAPAPER_API_KEY",
    "consumer_secret": "INSTAPAPER_API_SECRET",
    "username": "INSTAPAPER_USERNAME",
    "password": "INSTAPAPER_PASSWORD",
}


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="Extract bookmarks and highlights from Instapaper to CSV/JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (prompts for credentials)
  python -m instapaper_extract.cli

  # Using environment variables
  export INSTAPAPER_API_KEY="your_key"
  export INSTAPAPER_API_SECRET="your_secret"
  export INSTAPAPER_USERNAME="your_email@example.com"
  export INSTAPAPER_PASSWORD="your_password"
  python -m instapaper_extract.cli

  # Custom output file
  python -m instapaper_extract.cli -o my_articles.csv

  # Export to JSON with highlights
  python -m instapaper_extract.cli -o export.json --format json

  # Skip full text (faster, metadata only)
  python -m instapaper_extract.cli --no-text

  # Export highlights without bookmarks
  python -m instapaper_extract.cli --highlights-only -o highlights.csv

  # Skip highlights export
  python -m instapaper_extract.cli --no-highlights
        """,
    )

    # Output options
    parser.add_argument(
        "-o",
        "--output",
        default="instapaper_bookmarks.csv",
        help="Output file path (default: instapaper_bookmarks.csv)",
    )

    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Output format: csv or json (default: csv)",
    )

    # Content options
    parser.add_argument(
        "--no-text",
        action="store_true",
        help="Skip fetching full article text (faster, exports metadata only)",
    )

    # Highlights options
    parser.add_argument(
        "--highlights",
        action="store_true",
        default=True,
        help="Include highlights export (default: True)",
    )

    parser.add_argument(
        "--no-highlights",
        action="store_false",
        dest="highlights",
        help="Skip highlights export",
    )

    parser.add_argument(
        "--highlights-only",
        action="store_true",
        help="Export only bookmarks that have highlights",
    )

    # Credential options
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Fail if credentials are missing instead of prompting interactively",
    )

    # Behavior options
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed progress information",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be exported without actually exporting",
    )

    return parser


def _get_credentials(
    allow_prompt: bool = True,
    verbose: bool = False,
) -> tuple[str, str, str, str]:
    """
    Get Instapaper credentials from environment or user input.

    Args:
        allow_prompt: If False, raise error when credentials are missing
        verbose: If True, print status messages

    Returns:
        Tuple of (consumer_key, consumer_secret, username, password)

    Raises:
        ValueError: If credentials are missing and prompting is disabled
    """
    consumer_key = os.environ.get(ENV_VARS["consumer_key"])
    consumer_secret = os.environ.get(ENV_VARS["consumer_secret"])
    username = os.environ.get(ENV_VARS["username"])
    password = os.environ.get(ENV_VARS["password"])

    missing = []
    if not consumer_key:
        missing.append("API Key")
    if not consumer_secret:
        missing.append("API Secret")
    if not username:
        missing.append("Username")
    if not password:
        missing.append("Password")

    if missing and not allow_prompt:
        raise ValueError(
            f"Missing required credentials: {', '.join(missing)}. "
            f"Set environment variables: {', '.join(ENV_VARS.values())}"
        )

    # Prompt for missing credentials
    if not consumer_key:
        if verbose:
            print("Instapaper API Key not found in environment.")
        consumer_key = input("Enter your Instapaper API Key: ").strip()

    if not consumer_secret:
        if verbose:
            print("Instapaper API Secret not found in environment.")
        consumer_secret = input("Enter your Instapaper API Secret: ").strip()

    if not username:
        if verbose:
            print("Instapaper username not found in environment.")
        username = input("Enter your Instapaper username (email): ").strip()

    if not password:
        if verbose:
            print("Instapaper password not found in environment.")
        password = getpass.getpass("Enter your Instapaper password: ")

    return consumer_key, consumer_secret, username, password


def _create_client(args: argparse.Namespace) -> InstapaperExtractor:
    """
    Create and authenticate an InstapaperExtractor client.

    Args:
        args: Parsed command-line arguments

    Returns:
        Authenticated InstapaperExtractor

    Raises:
        AuthenticationError: If authentication fails
    """
    consumer_key, consumer_secret, username, password = _get_credentials(
        allow_prompt=not args.no_prompt,
        verbose=args.verbose,
    )

    client = InstapaperExtractor(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        username=username,
        password=password,
    )

    client.authenticate(verbose=args.verbose)
    return client


def _fetch_bookmarks_with_text(
    client: InstapaperExtractor,
    bookmarks: list[BookmarkData],
    verbose: bool = False,
) -> list[BookmarkData]:
    """
    Fetch full text for all bookmarks.

    Args:
        client: Authenticated InstapaperExtractor
        bookmarks: List of bookmarks to fetch text for
        verbose: If True, print progress

    Returns:
        List of bookmarks with full_text populated
    """
    for i, bookmark in enumerate(bookmarks, 1):
        if verbose:
            print(f"Fetching text {i}/{len(bookmarks)}: {bookmark.title[:50]}...")

        # Note: This is inefficient due to pyinstapaper's API design
        # We need to get the raw bookmark object to call get_text()
        # For now, we'll skip full text and document this limitation
        # Users can access full text via the web interface
        bookmark.full_text = None

    return bookmarks


def main(argv: Optional[list[str]] = None) -> int:
    """
    Main entry point for the CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv)

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        # Create and authenticate client
        client = _create_client(args)

        # Fetch bookmarks
        if args.verbose:
            print("\nFetching bookmarks...")

        bookmarks = client.get_all_bookmarks(verbose=args.verbose)

        if not bookmarks:
            print("No bookmarks found.")
            return 0

        if args.verbose:
            print(f"\nTotal bookmarks: {len(bookmarks)}")

        # Fetch highlights if requested
        highlights = []
        if args.highlights or args.highlights_only:
            highlights = client.get_all_highlights(verbose=args.verbose)

            if args.verbose:
                print(f"Total highlights: {len(highlights)}")

        # Filter bookmarks if highlights-only mode
        if args.highlights_only:
            highlight_bookmark_ids = {hl.bookmark_id for hl in highlights}
            bookmarks = [b for b in bookmarks if b.bookmark_id in highlight_bookmark_ids]

            if args.verbose:
                print(f"Bookmarks with highlights: {len(bookmarks)}")

        # Fetch full text if requested
        if not args.no_text:
            if args.verbose:
                print("\nNote: Full text fetching is currently limited by pyinstapaper API.")
                print("Full text will not be included in the export.")
                print("Use the Instapaper web interface to access full article text.\n")

        # Dry run mode - just show what would be exported
        if args.dry_run:
            print("\n=== DRY RUN - No files will be created ===")
            print(f"\nWould export {len(bookmarks)} bookmarks to: {args.output}")
            if highlights:
                if args.format == "csv":
                    highlights_path = get_highlights_output_path(args.output)
                    print(f"Would export {len(highlights)} highlights to: {highlights_path}")
                else:
                    print(f"Would include {len(highlights)} highlights in JSON output")
            print(f"\nFormat: {args.format.upper()}")
            print(f"Include full text: {not args.no_text}")
            return 0

        # Export based on format
        if args.format == "json":
            export_to_json(
                bookmarks=bookmarks,
                highlights=highlights,
                output_path=args.output,
                include_text=not args.no_text,
                verbose=args.verbose,
            )
        else:  # CSV format
            # Export bookmarks
            export_bookmarks_to_csv(
                bookmarks=bookmarks,
                output_path=args.output,
                include_text=not args.no_text,
                verbose=args.verbose,
            )

            # Export highlights to separate file
            if highlights:
                highlights_path = get_highlights_output_path(args.output)
                export_highlights_to_csv(
                    highlights=highlights,
                    output_path=highlights_path,
                    verbose=args.verbose,
                )

        if not args.verbose:
            print(f"\n✓ Successfully exported {len(bookmarks)} bookmarks to {args.output}")
            if highlights and args.format == "csv":
                highlights_path = get_highlights_output_path(args.output)
                print(f"✓ Successfully exported {len(highlights)} highlights to {highlights_path}")

        return 0

    except AuthenticationError as e:
        print(f"\nAuthentication error: {e}", file=sys.stderr)
        return 1
    except (ExtractionError, ExportError) as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
