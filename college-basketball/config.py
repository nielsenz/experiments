from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = DATA_DIR / "models"
SOURCE_DIR = BASE_DIR / "source"

TEAM_STATS  = PROCESSED_DIR / "team_stats_2026.csv"
TEAM_TEMPO  = PROCESSED_DIR / "team_tempo_2026.csv"
RESULTS = PROCESSED_DIR / "first_to_10_results.csv"
SCHEDULE = SOURCE_DIR / "tournament_schedule_2026_updated.csv"
MODEL_PATH = MODELS_DIR / "first_to_10_model_clean.pkl"
PREDICTIONS_OUT = PROCESSED_DIR / "predictions_2026.csv"

SEASON_PBP = RAW_DIR / "season_pbp_2026.json"
TOURNAMENT_PBP = RAW_DIR / "tournament_pbp_2026_raw.json"

# Legacy model paths (moved from root)
MODEL_2025 = MODELS_DIR / "first_to_10_model_2025.pkl"
MODEL_2026 = MODELS_DIR / "first_to_10_model_2026.pkl"

# Fallbacks for teams missing from team_stats
LEAGUE_AVG_PPG = 75.5
LEAGUE_AVG_OPP_PPG = 75.5
LEAGUE_AVG_PACE = 151.0
