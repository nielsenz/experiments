# Instapaper Extractor

Export your Instapaper bookmarks and highlights to CSV or JSON format for analysis and backup.

## Features

- **Extract all bookmarks** from unread, archive, and starred folders
- **Export highlights** separately with annotations and notes
- **Multiple output formats** - CSV or JSON
- **Flexible filtering** - Export all bookmarks, or only those with highlights
- **Environment-aware credentials** - Use environment variables or interactive prompts
- **Dry-run mode** - Preview what will be exported without creating files
- **Comprehensive metadata** - Title, URL, description, timestamp, reading progress, starred status
- **Clean architecture** - Well-tested, modular Python package

## Prerequisites

### Python 3.7+

Make sure you have Python 3.7 or higher installed.

### Instapaper API Credentials

You need to obtain API credentials from Instapaper:

1. Go to [https://www.instapaper.com/main/request_oauth_consumer_token](https://www.instapaper.com/main/request_oauth_consumer_token)
2. Fill out the form to request API access
3. Wait for approval (usually quick)
4. You'll receive a **Consumer Key** (API Key) and **Consumer Secret** (API Secret)

### Your Instapaper Account

You'll need your Instapaper account credentials:
- **Username**: Usually your email address
- **Password**: Your Instapaper password

## Installation

1. Navigate to the project directory:
   ```bash
   cd instapaper-extract
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Usage

Run the extractor in interactive mode (prompts for credentials):

```bash
python -m instapaper_extract.cli
```

### Environment Variables (Recommended)

Set your credentials as environment variables:

```bash
export INSTAPAPER_API_KEY="your_api_key_here"
export INSTAPAPER_API_SECRET="your_api_secret_here"
export INSTAPAPER_USERNAME="your_email@example.com"
export INSTAPAPER_PASSWORD="your_password_here"

python -m instapaper_extract.cli
```

To make these permanent, add them to your `~/.bashrc` or `~/.zshrc` file.

### Command-Line Options

#### Output Options

```bash
# Custom output file
python -m instapaper_extract.cli -o my_bookmarks.csv

# Export to JSON
python -m instapaper_extract.cli -o export.json --format json
```

#### Content Options

```bash
# Skip full text (faster, metadata only)
python -m instapaper_extract.cli --no-text

# Skip highlights export
python -m instapaper_extract.cli --no-highlights

# Export only bookmarks that have highlights
python -m instapaper_extract.cli --highlights-only
```

#### Utility Options

```bash
# Verbose output (show progress)
python -m instapaper_extract.cli --verbose

# Dry run (preview without creating files)
python -m instapaper_extract.cli --dry-run

# Fail if credentials missing (useful for CI/scripts)
python -m instapaper_extract.cli --no-prompt
```

## Output Formats

### CSV Format (Default)

When using CSV format, two files are created:

**Bookmarks CSV** (`instapaper_bookmarks.csv`):
| Column | Description |
|--------|-------------|
| `bookmark_id` | Unique Instapaper bookmark ID |
| `title` | Article title |
| `url` | Original article URL |
| `description` | Article description/summary |
| `time_added` | Unix timestamp when article was saved |
| `progress` | Reading progress (0.0 to 1.0) |
| `starred` | Whether article is starred (1 or 0) |
| `full_text` | Full article text (if `--no-text` not used) |

**Highlights CSV** (`instapaper_bookmarks_highlights.csv`):
| Column | Description |
|--------|-------------|
| `bookmark_id` | Associated bookmark ID |
| `highlight_id` | Unique highlight ID |
| `text` | Highlighted text |
| `note` | Optional annotation/note |
| `time` | Unix timestamp of highlight creation |
| `position` | Position in article (0-indexed) |

### JSON Format

When using JSON format, a single file contains bookmarks with nested highlights:

```json
{
  "total_bookmarks": 150,
  "total_highlights": 42,
  "bookmarks": [
    {
      "bookmark_id": 12345,
      "title": "Article Title",
      "url": "https://example.com/article",
      "description": "Article description",
      "time_added": 1638360000,
      "progress": 0.75,
      "starred": true,
      "full_text": "Full article content...",
      "highlights": [
        {
          "highlight_id": 67890,
          "text": "Important passage",
          "note": "My annotation",
          "time": 1638360100,
          "position": 42
        }
      ]
    }
  ]
}
```

## Examples

### Export everything to CSV (default)
```bash
python -m instapaper_extract.cli
```
Output: `instapaper_bookmarks.csv` + `instapaper_bookmarks_highlights.csv`

### Export to JSON with highlights
```bash
python -m instapaper_extract.cli -o backup.json --format json --verbose
```
Output: `backup.json` (includes bookmarks and highlights)

### Fast metadata-only export
```bash
python -m instapaper_extract.cli --no-text --no-highlights -o metadata.csv
```
Output: `metadata.csv` (bookmarks only, no full text or highlights)

### Export only bookmarks with highlights
```bash
python -m instapaper_extract.cli --highlights-only -o highlighted.csv
```
Output: `highlighted.csv` + `highlighted_highlights.csv`

### Preview what will be exported
```bash
python -m instapaper_extract.cli --dry-run --verbose
```
Output: Shows what would be exported without creating files

## Analysis Ideas

Once you have your data, you can:

1. **Import into Excel/Google Sheets** for sorting and filtering
2. **Use pandas for analysis**:
   ```python
   import pandas as pd

   # Load bookmarks
   bookmarks = pd.read_csv('instapaper_bookmarks.csv')
   highlights = pd.read_csv('instapaper_bookmarks_highlights.csv')

   # Most common domains
   bookmarks['domain'] = bookmarks['url'].str.extract(r'https?://([^/]+)')
   print(bookmarks['domain'].value_counts().head(10))

   # Bookmarks with most highlights
   highlight_counts = highlights.groupby('bookmark_id').size()
   top_highlighted = bookmarks[bookmarks['bookmark_id'].isin(highlight_counts.index)]
   ```

3. **Text analysis** - Word frequency, sentiment analysis, topic modeling
4. **Knowledge graph** - Build connections between articles and highlights
5. **Backup and migration** - Archive your Instapaper data

## Development

### Running Tests

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run the test suite:

```bash
pytest
```

Run tests with coverage:

```bash
pytest --cov=instapaper_extract --cov-report=html
```

### Project Structure

```
instapaper-extract/
├── instapaper_extract/
│   ├── __init__.py       # Package exports
│   ├── cli.py            # Command-line interface
│   ├── client.py         # API wrapper
│   └── io_utils.py       # Export utilities
├── tests/
│   ├── conftest.py       # Test fixtures
│   ├── test_cli.py       # CLI tests
│   ├── test_client.py    # Client tests
│   └── test_io_utils.py  # Export tests
├── requirements.txt      # Production dependencies
├── requirements-dev.txt  # Development dependencies
└── README.md
```

## Troubleshooting

### Authentication Failed
- Double-check your API credentials
- Verify your username and password are correct
- Ensure you've been approved for API access by Instapaper

### Rate Limiting
The Instapaper API has rate limits. If you have many bookmarks (>500), the script might take a while. Be patient and let it complete.

### Missing Bookmarks
The script fetches up to 500 bookmarks from each category (unread, archive, starred). If you have more than 500 bookmarks in any category, some might not be included. This is a limitation of the current implementation.

### Highlights Limit
Non-subscribers are limited to 5 highlights per month by Instapaper. If you see fewer highlights than expected, check your subscription status.

### Full Text Not Included
Due to limitations in the pyinstapaper library's API design, full text fetching is currently not fully implemented. The script will note this when run. Use the Instapaper web interface to access full article text.

## Security Note

Keep your API credentials secure:
- Don't commit them to version control
- Use environment variables or a `.env` file (add `.env` to `.gitignore`)
- Consider using a secrets manager for production use
- Never share your API credentials publicly

## License

This tool is provided as-is for personal use.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.
