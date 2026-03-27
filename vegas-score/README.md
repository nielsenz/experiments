# 🎰 Las Vegas Health Score CLI

A dual-index CLI tool tracking **environmental** and **economic** health for the Las Vegas valley, focused on the Seven Hills / Henderson area.

## Quick Start

```bash
# Install dependencies
uv sync

# Demo mode (no API calls needed)
uv run python vegas_score.py --demo

# Live data
uv run python vegas_score.py

# Verbose (show raw API responses)
uv run python vegas_score.py --verbose

# JSON output (for piping to other tools)
uv run python vegas_score.py --json

# Single index
uv run python vegas_score.py --env-only
uv run python vegas_score.py --econ-only

# Save each run to local history
uv run python vegas_score.py --save-history

# Show score trend from saved history
uv run python vegas_score.py --trend

# Save + show trend in one run
uv run python vegas_score.py --save-history --trend
```

## Requirements

Python 3.13+ with [uv](https://docs.astral.sh/uv/) for dependency management. Dependencies are declared in `pyproject.toml`.

## Data Sources

### Environmental (all free, no API keys)

| Source | API | Data | Key? |
|--------|-----|------|------|
| **NWS** | api.weather.gov | Temperature, wind, forecast, alerts | No |
| **AirNow** | airnow.gov/rest/cb | AQI, PM2.5, ozone | No |
| **EPA Envirofacts** | data.epa.gov | UV index by ZIP | No |
| **USGS Water** | waterservices.usgs.gov | Colorado River discharge | No |
| **USBR RISE** | data.usbr.gov | Lake Mead elevation | No |
| **US Drought Monitor** | usdm.unl.edu/api | Drought severity by county | No |

### Economic

| Source | API | Data | Key? |
|--------|-----|------|------|
| **BLS v1** | api.bls.gov | Unemployment, employment by sector, CPI | No (25 req/day) |
| **Census Bureau** | api.census.gov | Population, median home value, rent | No |
| **EIA** | api.eia.gov | Regional gas prices | DEMO_KEY works; free registration for more |
| **FRED** | api.stlouisfed.org | 30-yr mortgage rate | **Yes** (free at fred.stlouisfed.org) |

### Setting API Keys

```bash
# Optional: for higher BLS rate limits (500/day vs 25/day)
# Register at https://data.bls.gov/registrationEngine/

# Required for FRED mortgage data
export FRED_API_KEY="your_key_here"
# Get one free: https://fred.stlouisfed.org/docs/api/api_key.html

# Optional: for EIA beyond DEMO_KEY limits
export EIA_API_KEY="your_key_here"
# Register: https://www.eia.gov/opendata/register.php
```

## Scoring

Each indicator is normalized to **0–100**:

| Grade | Score | Meaning |
|-------|-------|---------|
| A | 90–100 | Excellent |
| B | 75–89 | Good |
| C | 60–74 | Fair |
| D | 40–59 | Below average |
| F | 0–39 | Poor / Critical |

### Environmental Weights

| Indicator | Weight | Scoring Logic |
|-----------|--------|---------------|
| Air Quality | 25% | AQI 0→100pts, 150→10pts |
| Heat/Comfort | 20% | 65-80°F→100pts, drops above 100°F |
| Water Supply | 20% | Lake Mead % of capacity |
| UV Exposure | 15% | UV 0-2→100pts, 11+→5pts |
| Drought | 10% | 100 minus % area in drought |
| Alerts | 10% | 100 minus 15pts per active alert |

### Economic Weights

| Indicator | Weight | Scoring Logic |
|-----------|--------|---------------|
| Unemployment | 20% | 3%→100pts, 10%→0pts |
| Job Growth | 20% | +30K YoY→100pts, 0→50pts, -30K→0pts |
| Hospitality | 15% | L&H jobs as % of pre-pandemic peak |
| Cost of Living | 15% | CPI relative to national avg |
| Housing | 15% | Median home $250K→100, $600K→20 |
| Gas Prices | 5% | $3/gal→100, $5/gal→0 |
| Mortgage Rate | 10% | 5%→100, 8%→10 |

### Composite Score

```
Composite = 50% Environmental + 50% Economic
```

## Project Structure

```
vegas_health_score/
├── vegas_score.py          # CLI entry point
├── fetchers/
│   ├── environmental.py    # NWS, AirNow, EPA, USGS, USBR, Drought
│   └── economic.py         # BLS, Census, EIA, FRED
├── scoring.py              # 0-100 normalization engine
├── display.py              # Terminal output formatting
└── README.md
```

## Current API Status (Feb 2026)

Several free API endpoints have changed or are returning errors. The following work without keys:

| Source | Status | Notes |
|--------|--------|-------|
| NWS (weather, alerts) | **Working** | Temperature, forecast, alerts |
| BLS (employment, CPI) | **Partially working** | Employment + CPI OK; unemployment parsing broken |
| Census (housing) | **Working** | Median home value + rent |
| EIA (gas prices) | **Working** | Uses DEMO_KEY by default |
| AirNow (AQI) | **Broken** | 404 — endpoint may have changed |
| EPA (UV index) | **Broken** | 404 — endpoint may have changed |
| USBR (Lake Mead) | **Broken** | Returns None for elevation |
| USGS (river flow) | **Broken** | No data returned |
| Drought Monitor | **Broken** | Connection timeout |
| Census (population) | **Broken** | 404 |
| FRED (mortgage rate) | **Needs key** | Set `FRED_API_KEY` env var |

## Ideas for Extension

- **Cron + SQLite**: Run daily, store history, track trends
- **LVCVA tourism data**: Scrape visitor volume reports
- **Zillow/Redfin**: Real-time home price feeds for Seven Hills specifically
- **NV Secretary of State**: New business filing counts
- **Sports economy**: Raiders/F1/Golden Knights event revenue proxies
- **Seasonal weighting**: Increase heat weight in summer, tourism weight during CES/conventions

## Trend Tracking

`vegas_score.py` can persist snapshots over time in a JSONL history file (default: `.vegas_score_history.jsonl`).

```bash
# collect one point
uv run python vegas_score.py --save-history

# display trend from all saved points
uv run python vegas_score.py --trend

# custom history location
uv run python vegas_score.py --save-history --trend --history-file data/vegas_history.jsonl
```

Use cron (daily or hourly) with `--save-history` to build the trend line over time.
