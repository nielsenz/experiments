# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Instapaper Extractor is a Python CLI tool that exports Instapaper bookmarks and highlights to CSV or JSON formats. It wraps the `pyinstapaper` library to provide a clean, user-friendly interface with multiple export options.

## Development Setup

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install -r requirements-dev.txt
```

## Running the Tool

```bash
# Basic usage (interactive credential prompt)
python -m instapaper_extract.cli

# With environment variables (recommended)
export INSTAPAPER_API_KEY="your_key"
export INSTAPAPER_API_SECRET="your_secret"
export INSTAPAPER_USERNAME="your_email"
export INSTAPAPER_PASSWORD="your_password"
python -m instapaper_extract.cli

# Common options
python -m instapaper_extract.cli -o output.json --format json --verbose
python -m instapaper_extract.cli --highlights-only
python -m instapaper_extract.cli --dry-run
```

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_client.py

# Run with coverage
pytest --cov=instapaper_extract --cov-report=html

# Run single test
pytest tests/test_io_utils.py::test_export_bookmarks_to_csv
```

## Architecture

The codebase follows a clean three-layer architecture:

### 1. API Client Layer (`client.py`)
- **`InstapaperExtractor`**: Main wrapper around `pyinstapaper` library
  - Handles authentication via OAuth
  - Fetches bookmarks from three folders: unread, archive, starred (limit 500 each)
  - Fetches highlights by iterating through raw bookmark objects
  - Deduplicates starred bookmarks that may appear in other folders
- **Data Models**: `BookmarkData` and `HighlightData` dataclasses normalize pyinstapaper's objects
- **Important limitation**: Full text fetching is not fully implemented due to pyinstapaper API design constraints

### 2. Export Layer (`io_utils.py`)
- **CSV Export**: Creates two separate files (bookmarks + highlights)
- **JSON Export**: Single file with nested structure (highlights grouped under bookmarks)
- **`clean_html()`**: Strips HTML tags and entities from text fields
- **`get_highlights_output_path()`**: Generates highlights filename by adding `_highlights` suffix

### 3. CLI Layer (`cli.py`)
- **Credential Management**:
  - Reads from environment variables (INSTAPAPER_API_KEY, INSTAPAPER_API_SECRET, INSTAPAPER_USERNAME, INSTAPAPER_PASSWORD)
  - Falls back to interactive prompts unless `--no-prompt` specified
- **Export Flow**:
  1. Authenticate client
  2. Fetch all bookmarks (from 3 folders)
  3. Optionally fetch highlights
  4. Filter to highlights-only if requested
  5. Export based on format (CSV creates 2 files, JSON creates 1)
- **Dry-run mode**: Shows what would be exported without creating files

## Key Design Patterns

### Credential Resolution Strategy
The CLI checks environment variables first, then prompts interactively. Use `--no-prompt` flag for CI/scripts to fail fast if credentials are missing.

### Bookmark Deduplication
Starred bookmarks can also appear in unread/archive folders. The client tracks `bookmark_id` in a set to avoid duplicates when fetching starred items.

### Highlight Association
Highlights are fetched by calling `get_highlights()` on raw pyinstapaper bookmark objects (not our BookmarkData wrapper). This requires maintaining references to original objects during the highlight fetching phase.

### Output Path Convention
CSV format always creates two files:
- User-specified path for bookmarks
- Auto-generated path with `_highlights` suffix for highlights

JSON format combines both into a single file with nested structure.

## Known Limitations

1. **Bookmark Limit**: API fetches max 500 bookmarks per folder (1500 total max)
2. **Full Text**: Not implemented due to pyinstapaper library limitations - use web interface for full article text
3. **Rate Limiting**: The API has rate limits; be patient with large collections
4. **Highlight Subscription**: Free accounts limited to 5 highlights/month by Instapaper

## Code Conventions

- Use `verbose` parameter for progress messages (don't print unless verbose=True or final success message)
- All exceptions inherit from base `InstapaperError`
- Return empty lists (not None) for zero-result queries
- Use dataclasses for data transfer objects (BookmarkData, HighlightData)
- Handle pyinstapaper exceptions gracefully with try/except and continue processing other items
