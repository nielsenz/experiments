#!/usr/bin/env python3
"""
Instapaper Article Extractor

This script authenticates with Instapaper, retrieves all saved articles,
and exports them to a CSV file containing article links and text content.
"""

import argparse
import csv
import os
import sys
from getpass import getpass
from typing import List, Dict
from pyinstapaper import Instapaper
from html import unescape
import re


def clean_html(html_text: str) -> str:
    """Remove HTML tags and clean up text content."""
    if not html_text:
        return ""

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', html_text)
    # Unescape HTML entities
    text = unescape(text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_credentials() -> tuple:
    """
    Get Instapaper credentials from environment variables or user input.

    Returns:
        tuple: (api_key, api_secret, username, password)
    """
    # Try to get from environment variables first
    api_key = os.environ.get('INSTAPAPER_API_KEY')
    api_secret = os.environ.get('INSTAPAPER_API_SECRET')
    username = os.environ.get('INSTAPAPER_USERNAME')
    password = os.environ.get('INSTAPAPER_PASSWORD')

    # Prompt for missing credentials
    if not api_key:
        print("Instapaper API Key not found in environment.")
        api_key = input("Enter your Instapaper API Key: ").strip()

    if not api_secret:
        print("Instapaper API Secret not found in environment.")
        api_secret = input("Enter your Instapaper API Secret: ").strip()

    if not username:
        print("Instapaper username not found in environment.")
        username = input("Enter your Instapaper username (email): ").strip()

    if not password:
        print("Instapaper password not found in environment.")
        password = getpass("Enter your Instapaper password: ")

    return api_key, api_secret, username, password


def fetch_all_bookmarks(instapaper: Instapaper) -> List:
    """
    Fetch all bookmarks from Instapaper.

    Args:
        instapaper: Authenticated Instapaper instance

    Returns:
        List of bookmark objects
    """
    print("Fetching bookmarks...")
    bookmarks = []

    # Fetch unread bookmarks
    try:
        unread = instapaper.get_bookmarks('unread', limit=500)
        bookmarks.extend(unread)
        print(f"Found {len(unread)} unread articles")
    except Exception as e:
        print(f"Error fetching unread bookmarks: {e}")

    # Fetch archive
    try:
        archive = instapaper.get_bookmarks('archive', limit=500)
        bookmarks.extend(archive)
        print(f"Found {len(archive)} archived articles")
    except Exception as e:
        print(f"Error fetching archived bookmarks: {e}")

    # Fetch starred
    try:
        starred = instapaper.get_bookmarks('starred', limit=500)
        # Remove duplicates (starred items might be in unread or archive)
        starred_ids = {b.bookmark_id for b in bookmarks}
        new_starred = [b for b in starred if b.bookmark_id not in starred_ids]
        bookmarks.extend(new_starred)
        print(f"Found {len(new_starred)} additional starred articles")
    except Exception as e:
        print(f"Error fetching starred bookmarks: {e}")

    return bookmarks


def extract_articles_to_csv(api_key: str, api_secret: str, username: str,
                            password: str, output_file: str,
                            include_text: bool = True) -> None:
    """
    Extract all articles from Instapaper and save to CSV.

    Args:
        api_key: Instapaper API consumer key
        api_secret: Instapaper API consumer secret
        username: Instapaper account username/email
        password: Instapaper account password
        output_file: Path to output CSV file
        include_text: Whether to fetch full article text (slower)
    """
    # Initialize and authenticate
    print("Authenticating with Instapaper...")
    try:
        instapaper = Instapaper(api_key, api_secret)
        instapaper.login(username, password)
        print("Authentication successful!")
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

    # Fetch all bookmarks
    bookmarks = fetch_all_bookmarks(instapaper)

    if not bookmarks:
        print("No bookmarks found.")
        return

    print(f"\nTotal bookmarks: {len(bookmarks)}")

    # Export to CSV
    print(f"\nExporting to {output_file}...")

    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['bookmark_id', 'title', 'url', 'description',
                     'time_added', 'progress', 'starred']

        if include_text:
            fieldnames.append('full_text')

        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for i, bookmark in enumerate(bookmarks, 1):
            print(f"Processing {i}/{len(bookmarks)}: {bookmark.title[:50]}...")

            row = {
                'bookmark_id': bookmark.bookmark_id,
                'title': bookmark.title or '',
                'url': bookmark.url or '',
                'description': bookmark.description or '',
                'time_added': bookmark.time if hasattr(bookmark, 'time') else '',
                'progress': bookmark.progress if hasattr(bookmark, 'progress') else '',
                'starred': '1' if (hasattr(bookmark, 'starred') and bookmark.starred) else '0'
            }

            # Fetch full text if requested
            if include_text:
                try:
                    html_text = bookmark.get_text()
                    row['full_text'] = clean_html(html_text)
                except Exception as e:
                    print(f"  Warning: Could not fetch text for '{bookmark.title}': {e}")
                    row['full_text'] = ''

            writer.writerow(row)

    print(f"\n✓ Successfully exported {len(bookmarks)} articles to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Extract articles from Instapaper to CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (prompts for credentials)
  python extract_articles.py

  # Using environment variables
  export INSTAPAPER_API_KEY="your_key"
  export INSTAPAPER_API_SECRET="your_secret"
  export INSTAPAPER_USERNAME="your_email@example.com"
  export INSTAPAPER_PASSWORD="your_password"
  python extract_articles.py

  # Custom output file
  python extract_articles.py -o my_articles.csv

  # Skip fetching full text (faster, metadata only)
  python extract_articles.py --no-text
        """
    )

    parser.add_argument(
        '-o', '--output',
        default='instapaper_articles.csv',
        help='Output CSV file path (default: instapaper_articles.csv)'
    )

    parser.add_argument(
        '--no-text',
        action='store_true',
        help='Skip fetching full article text (faster, exports metadata only)'
    )

    args = parser.parse_args()

    # Get credentials
    api_key, api_secret, username, password = get_credentials()

    # Extract articles
    extract_articles_to_csv(
        api_key=api_key,
        api_secret=api_secret,
        username=username,
        password=password,
        output_file=args.output,
        include_text=not args.no_text
    )


if __name__ == '__main__':
    main()
