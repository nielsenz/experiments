# College Basketball Betting Models — 2026 NCAA Tournament

## Overview
Three betting models for the 2026 March Madness tournament:
1. **First-to-10** — which team scores 10 points first (race-to-10 prop market)
2. **Totals** — predicted total points scored (over/under)
3. **Spread** — predicted point differential (against the spread)

All models use pre-game season-average stats only — no game-score leakage.

## Stack
- **Python via `uv`** — always run scripts with `uv run python <script>`
- **scikit-learn** — GBM for first-to-10/spread, Ridge for totals
- **pandas / numpy** — data wrangling
- **ESPN public API** — data source (no auth required)

## Directory Structure
```
college-basketball/
├── config.py              # All path constants — import this, never hardcode paths
├── features.py            # Canonical first-to-10 feature computation
├── train.py               # Train first-to-10 GBM model
├── predict.py             # Generate first-to-10 predictions + American odds
├── train_totals.py        # Train totals + spread regression models (both in one file)
├── predict_totals.py      # Generate totals/spread predictions vs book lines
├── fetch_results.py       # Fetch final scores from ESPN API, update tracking CSVs
├── data/
│   ├── raw/               # Large JSON PBP files — gitignored
│   │   ├── season_pbp_2026.json          # 1138 regular season games
│   │   └── tournament_pbp_2026_raw.json  # tournament games
│   ├── processed/         # CSVs — tracked in git
│   │   ├── team_stats_2026.csv                # 151 teams, season averages
│   │   ├── first_to_10_results.csv            # Completed tournament F10 outcomes
│   │   ├── predictions_2026.csv               # F10 predictions for all tourney games
│   │   ├── totals_predictions_2026.csv        # Totals/spread predictions
│   │   ├── betting_lines_sweet16.csv          # Sweet 16 F10 bets: book odds, stakes, results
│   │   └── sweet16_totals_spread_lines.csv    # Sweet 16 O/U and spread book lines vs model
│   └── models/            # Trained model PKL files
│       ├── first_to_10_model_clean.pkl   # GBM classifier, CV AUC=0.604
│       └── totals_spread_model.pkl       # GBM regressors, totals CV MAE=12.8, spread CV MAE=11.6
├── ingest/                # Data fetching scripts
│   ├── scrape_pbp_parallel.py   # Fetch regular season PBP (uses game_ids_2026.txt)
│   └── scrape_tournament.py     # Fetch tournament PBP (broken: uses sportsdataverse)
└── source/                # Source data files — tracked in git
    ├── tournament_schedule_2026_updated.csv  # Live tournament schedule/results
    ├── tournament_schedule_2026.csv          # Original (stale, use _updated)
    └── game_ids_2026.txt                     # 11,580 regular season game IDs
```

## Common Commands
```bash
# Train first-to-10 model
uv run python train.py

# Generate first-to-10 predictions + odds
uv run python predict.py

# Train totals + spread models
uv run python train_totals.py

# Generate totals/spread predictions
uv run python predict_totals.py

# Fetch final scores and update result tracking CSVs
uv run python fetch_results.py

# Re-fetch tournament schedule (run before predict.py when bracket advances)
uv run python3 -c "
import requests, csv
from config import SOURCE_DIR
# ... see scrape_pbp_parallel.py for ESPN scoreboard fetch pattern
"
```

## Models

### First-to-10 (train.py / predict.py)
- **Algorithm**: GradientBoostingClassifier
- **Training data**: 1137 regular season games (season_pbp_2026.json)
- **Features** (from features.py): `home_ppg`, `away_ppg`, `home_opp_ppg`, `away_opp_ppg`, `pace_ratio`, `ppg_diff`, `total_ppg`, `home_net`, `away_net`
- **CV AUC**: 0.604 | **Tournament accuracy**: 70% (R2), 68% (R1)
- **Known limitation**: Trained on regular season where home court is real. Tournament games are neutral site — model over-inflates "home" team probability. Trust picks where model's favored team is listed as *away*.

### Totals (train_totals.py / predict_totals.py)
- **Target**: total points scored (home_score + away_score)
- **Algorithm**: GradientBoostingRegressor (Ridge CV MAE slightly better at 12.46 vs GBM 12.84 — consider switching)
- **Training data**: 1137 regular season games, filtered 80 < total < 220
- **CV MAE**: ±12.8 pts | **Season avg total**: 151.3 pts
- **Features**: `home_ppg`, `away_ppg`, `home_opp_ppg`, `away_opp_ppg`, `total_ppg`, `home_net`, `away_net`, `avg_net`, `def_strength`
- **Top features**: `def_strength` (0.376), `total_ppg` (0.340)
- **Use**: compare predicted total vs book's over/under; only act on edges >5 pts given MAE

### Spread (train_totals.py / predict_totals.py)
- **Target**: home_score - away_score (positive = home wins)
- **Algorithm**: GradientBoostingRegressor
- **CV MAE**: ±11.6 pts
- **Top features**: `away_net` (0.336), `home_net` (0.315)
- **Known limitation**: Same neutral-site bias as F10 model — consistently makes favorites look more dominant than book. Don't rely on spread model for tournament predictions.

## Feature Definitions (canonical — from features.py)
All inputs are **pre-game season averages** from `team_stats_2026.csv`:
- `pace_ratio`: `home_pace / (home_pace + away_pace)` — home share of pace (~0.5 neutral site)
- `ppg_diff`: `home_ppg - away_ppg`
- `total_ppg`: `home_ppg + away_ppg`
- `home_net` / `away_net`: `ppg - opp_ppg` (net rating proxy)
- `avg_net`: `(home_net + away_net) / 2` — combined quality signal
- `def_strength`: `(home_opp_ppg + away_opp_ppg) / 2` — how stingy both defenses are

Note: `features.py` is canonical for first-to-10 (includes `pace_ratio`). `train_totals.py` defines its own `compute_features` (no pace, adds `avg_net` and `def_strength`) — **do not pickle this function**, define it inline in predict scripts instead.

## Data Pipeline
```
ESPN API → scrape_pbp_parallel.py → data/raw/season_pbp_2026.json
                                  → team stats (avg_pts, avg_opp_pts, avg_pace)
                                  → first-to-10 labels (from play sequences)
                                  → final scores (for totals/spread training)

ESPN API → tournament schedule    → source/tournament_schedule_2026_updated.csv
         → tournament PBP         → data/raw/tournament_pbp_2026_raw.json
```

## Betting Tracking

### F10 Bets — `data/processed/betting_lines_sweet16.csv`
Tracks all Sweet 16 F10 bets placed:
- Book odds, model probability, edge, EV per $100
- T1 bets ($11 stake): Iowa F10, Illinois F10
- T2 bets ($6 stake): Purdue F10, Arizona F10, Michigan F10, UConn F10
- Total staked: $46 across 6 bets
- Fill in `actual_f10_winner` and `bet_correct` after games complete

### Totals/Spread Lines — `data/processed/sweet16_totals_spread_lines.csv`
Records pregame book lines alongside model predictions for all 8 Sweet 16 games:
- Columns: `book_spread`, `book_total`, `model_pred_total`, `model_pred_spread`, `total_edge_dir`, `total_edge_pts`
- Fill in `actual_total`, `actual_home_score`, `actual_away_score`, `actual_spread` via `fetch_results.py`

## Known Issues / Notes
- `ingest/scrape_tournament.py` uses `sportsdataverse` which is broken on Python 3.13 (`pkg_resources` missing). Use the direct ESPN API fetch pattern from `scrape_pbp_parallel.py` instead.
- Team name "Illinois" in `team_stats_2026.csv` matches id=356 (Fighting Illini, 85 PPG). `E Illinois` is id=2197 (59 PPG). Always look up by `team_id`, never by name string search.
- Tournament schedule: use `source/tournament_schedule_2026_updated.csv` (fetched March 25). The original `tournament_schedule_2026.csv` has stale statuses.
- When bracket advances (Elite 8, Final Four), re-fetch the schedule CSV via ESPN scoreboard API before running predict scripts.
- Do not pickle `compute_features` from `train_totals.py` — it can't be unpickled cross-module. Define it inline in predict scripts instead.
