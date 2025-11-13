# Instapaper Bookmark Creator

Create Instapaper bookmarks in bulk from the command line.  The tool supports
CSV, JSON, and plain-text inputs, offers interactive or environment-based
credential management, and provides a dry-run mode for verification.

## Features

- **Multiple input formats** – parse CSV, JSON, or newline-delimited text files.
- **Environment aware** – pick up credentials from environment variables or
  prompt interactively when needed.
- **Dry run mode** – validate inputs without touching the Instapaper API.
- **Verbose reporting** – optional logging of each bookmark that gets created.

## Installation

1. Create a virtual environment (recommended) and install dependencies:

   ```bash
   cd create-instapaper
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Obtain Instapaper API credentials (consumer key/secret) and ensure that your
   Instapaper account has API access enabled.

## Usage

### Environment variables

The CLI looks for the following environment variables:

- `INSTAPAPER_API_KEY`
- `INSTAPAPER_API_SECRET`
- `INSTAPAPER_USERNAME`
- `INSTAPAPER_PASSWORD`

If they are not set the tool prompts for missing values (unless `--no-prompt`
was passed).

### Adding URLs from files

You can pass multiple files at once, mixing formats freely:

```bash
python -m create_instapaper.cli urls.csv list.json reading-list.txt
```

Supported formats:

- **CSV** – requires a `url` column and accepts optional `title`, `description`,
  and `folder_id` columns.
- **JSON** – either an array of objects or an object with an `items` array. Each
  item should contain at least a `url` field.
- **Text** – one URL per line; optionally append `|title|description|folder_id`.
  Lines starting with `#` are ignored.

### Adding ad-hoc URLs

You can also add single URLs without a file:

```bash
python -m create_instapaper.cli --url https://example.com --title "Example"
```

Use `--folder-id` to target a specific Instapaper folder and `--description` to
include a summary.

### Dry run and verbose output

`--dry-run` prints a summary of what would be created without calling the API.
Combine with `--verbose` to log each response when actually creating bookmarks.

```bash
python -m create_instapaper.cli urls.csv --dry-run
python -m create_instapaper.cli urls.csv --verbose
```

### Non-interactive environments

Use `--no-prompt` to fail fast when credentials are missing, which is useful in
CI pipelines.

```bash
python -m create_instapaper.cli urls.csv --no-prompt
```

## Error handling

The CLI validates file formats and gives actionable errors for missing columns,
invalid JSON, or rows without URLs.  API errors propagate as helpful messages so
that you can correct credentials or retry later.

## Development

Run the tests with `pytest`:

```bash
python -m pip install -r requirements-dev.txt
pytest
```

The test suite focuses on data loading and credential handling.  Network calls
are deliberately avoided so the tests remain fast and deterministic.
