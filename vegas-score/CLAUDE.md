# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Las Vegas Health Score CLI — a dual-index tool that fetches live data from public APIs and scores environmental + economic health for the Seven Hills / Henderson, NV area on a 0–100 scale.

## Setup & Running

```bash
# Install dependencies (uses uv for project management)
uv sync

# Demo mode (no API calls, uses hardcoded sample data)
uv run python vegas_score.py --demo

# Live data (requires internet; FRED_API_KEY env var needed for mortgage data)
uv run python vegas_score.py

# JSON output
uv run python vegas_score.py --json
```

## Architecture

The data pipeline flows: **Fetchers → ScoreEngine → Display**

- `vegas_score.py` — CLI entry point, wires together fetchers, scoring, and display
- `fetchers/environmental.py` — `EnvironmentalFetcher` class that hits 6 free APIs (NWS, AirNow, EPA, USGS, USBR, Drought Monitor). Each method returns a dict; `fetch_all()` aggregates them
- `fetchers/economic.py` — `EconomicFetcher` class that hits 4 APIs (BLS, Census, EIA, FRED). BLS series IDs for the Las Vegas MSA are defined at module level
- `scoring.py` — `ScoreEngine` normalizes raw data to 0–100 per indicator using Vegas-calibrated thresholds, then computes weighted averages. Weights are defined as class constants (`ENV_WEIGHTS`, `ECON_WEIGHTS`)
- `display.py` — Terminal rendering with ANSI color-coded grade bars (A/B/C/D/F)

## Key design details

- All API endpoints are free/no-key except FRED (requires `FRED_API_KEY` env var) and optionally EIA (`EIA_API_KEY`, falls back to `DEMO_KEY`)
- Both fetcher classes support `demo=True` mode that returns hardcoded sample data without making network calls
- Composite score = 50% environmental + 50% economic
- `ScoreEngine._weighted_avg` gracefully skips indicators with `None` scores and re-normalizes weights
