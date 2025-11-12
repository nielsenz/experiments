# Instapaper Article Extractor

A Python script that exports your Instapaper articles (links and full text) to CSV format for analysis.

## Features

- Exports all your Instapaper articles to CSV
- Includes article metadata: title, URL, description, timestamp, reading progress, starred status
- Optionally fetches full article text content
- Supports environment variables and interactive credential input
- Handles unread, archived, and starred articles

## Prerequisites

### 1. Python 3.6+

Make sure you have Python 3.6 or higher installed.

### 2. Instapaper API Credentials

You need to obtain API credentials from Instapaper:

1. Go to [https://www.instapaper.com/main/request_oauth_consumer_token](https://www.instapaper.com/main/request_oauth_consumer_token)
2. Fill out the form to request API access
3. Wait for approval (usually quick)
4. You'll receive a **Consumer Key** (API Key) and **Consumer Secret** (API Secret)

### 3. Your Instapaper Account

You'll need your Instapaper account credentials:
- **Username**: Usually your email address
- **Password**: Your Instapaper password

## Installation

1. Clone or navigate to this directory:
```bash
cd /home/user/experiments/instapaper-extract
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Option 1: Interactive Mode (Recommended for First-Time Users)

Simply run the script and it will prompt you for credentials:

```bash
python extract_articles.py
```

You'll be prompted to enter:
- Instapaper API Key
- Instapaper API Secret
- Instapaper username (email)
- Instapaper password

### Option 2: Using Environment Variables (Recommended for Repeated Use)

Set your credentials as environment variables:

```bash
export INSTAPAPER_API_KEY="your_api_key_here"
export INSTAPAPER_API_SECRET="your_api_secret_here"
export INSTAPAPER_USERNAME="your_email@example.com"
export INSTAPAPER_PASSWORD="your_password_here"

python extract_articles.py
```

To make these permanent, add them to your `~/.bashrc` or `~/.zshrc` file.

### Command-Line Options

#### Custom Output File

```bash
python extract_articles.py -o my_articles.csv
```

#### Skip Full Text (Faster, Metadata Only)

If you only need article URLs and metadata without the full text content:

```bash
python extract_articles.py --no-text
```

This is significantly faster as it doesn't need to fetch each article's content.

#### Combined Options

```bash
python extract_articles.py -o articles_2024.csv --no-text
```

## Output Format

The script generates a CSV file with the following columns:

| Column | Description |
|--------|-------------|
| `bookmark_id` | Unique Instapaper bookmark ID |
| `title` | Article title |
| `url` | Original article URL |
| `description` | Article description/summary |
| `time_added` | Timestamp when article was saved |
| `progress` | Reading progress (0.0 to 1.0) |
| `starred` | Whether article is starred (1 or 0) |
| `full_text` | Full article text content (if `--no-text` not used) |

## Examples

### Basic export with full text:
```bash
python extract_articles.py
```
Output: `instapaper_articles.csv` (includes full article text)

### Fast export (metadata only):
```bash
python extract_articles.py --no-text -o metadata.csv
```
Output: `metadata.csv` (URLs and metadata only)

### Export to custom location:
```bash
python extract_articles.py -o ~/Documents/reading_list.csv
```

## Analysis Ideas

Once you have your CSV, you can:

1. **Import into Excel/Google Sheets** for sorting and filtering
2. **Use pandas** for data analysis:
   ```python
   import pandas as pd
   df = pd.read_csv('instapaper_articles.csv')

   # Most common domains
   df['domain'] = df['url'].str.extract(r'https?://([^/]+)')
   print(df['domain'].value_counts().head(10))

   # Search for specific topics
   tech_articles = df[df['full_text'].str.contains('machine learning', case=False, na=False)]
   ```

3. **Text analysis** (word frequency, sentiment analysis, topic modeling)
4. **Export to other formats** (JSON, SQLite, etc.)

## Troubleshooting

### Authentication Failed
- Double-check your API credentials
- Verify your username and password are correct
- Ensure you've been approved for API access by Instapaper

### Rate Limiting
The Instapaper API has rate limits. If you have many articles (>500), the script might take a while. Be patient and let it complete.

### Missing Articles
The script fetches up to 500 articles from each category (unread, archive, starred). If you have more than 500 articles in any category, some might not be included. The script can be modified to handle pagination if needed.

### HTML in Text
Some articles may have residual HTML entities or formatting. The script includes basic HTML cleaning, but complex articles might need additional processing.

## Security Note

Keep your API credentials secure:
- Don't commit them to version control
- Use environment variables or a `.env` file (add `.env` to `.gitignore`)
- Consider using a secrets manager for production use

## License

This script is provided as-is for personal use.
