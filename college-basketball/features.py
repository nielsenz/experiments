"""
Canonical feature computation for the first-to-10 model.

All inputs MUST be pre-game season averages — no actual game scores allowed.
This is the single source of truth used by train.py and predict.py.

Tempo features (new):
  home_tempo / away_tempo: median plays for each team to reach 10 pts at a
  neutral site, estimated as (home_game_p10 + away_game_p10) / 2.
  Lower = faster scorer. Derived from team_tempo_2026.csv.

  tempo_diff: away_tempo - home_tempo
    Positive → away team takes more plays (home scores faster → home favored)
    Negative → home team takes more plays (away scores faster → away favored)
"""

LEAGUE_NEUTRAL_P10 = 53.0  # league-wide median plays-to-10 (fallback)

FEATURE_COLS = [
    'home_ppg',
    'away_ppg',
    'home_opp_ppg',
    'away_opp_ppg',
    'pace_ratio',    # home_pace / (home_pace + away_pace), ~0.5 for neutral-site
    'ppg_diff',      # home_ppg - away_ppg
    'total_ppg',     # home_ppg + away_ppg (game pace proxy)
    'home_net',      # home_ppg - home_opp_ppg (net rating proxy)
    'away_net',      # away_ppg - away_opp_ppg
    'home_tempo',    # median plays-to-10 at neutral site (lower = faster)
    'away_tempo',    # same for away team
    'tempo_diff',    # away_tempo - home_tempo (positive = home is relatively faster)
]


def compute_features(home_ppg: float, away_ppg: float,
                     home_opp_ppg: float, away_opp_ppg: float,
                     home_pace: float, away_pace: float,
                     home_tempo: float = LEAGUE_NEUTRAL_P10,
                     away_tempo: float = LEAGUE_NEUTRAL_P10) -> dict:
    """
    Compute canonical features from season-average team stats.

    Args:
        home_ppg:     home team avg points scored per game
        away_ppg:     away team avg points scored per game
        home_opp_ppg: home team avg points allowed per game
        away_opp_ppg: away team avg points allowed per game
        home_pace:    home team avg pace (total pts per game, proxy)
        away_pace:    away team avg pace
        home_tempo:   home team's neutral-site plays-to-10 (from team_tempo_2026.csv)
        away_tempo:   away team's neutral-site plays-to-10

    Returns:
        dict with keys matching FEATURE_COLS
    """
    total_pace = home_pace + away_pace
    return {
        'home_ppg':    home_ppg,
        'away_ppg':    away_ppg,
        'home_opp_ppg': home_opp_ppg,
        'away_opp_ppg': away_opp_ppg,
        'pace_ratio':  home_pace / total_pace if total_pace > 0 else 0.5,
        'ppg_diff':    home_ppg - away_ppg,
        'total_ppg':   home_ppg + away_ppg,
        'home_net':    home_ppg - home_opp_ppg,
        'away_net':    away_ppg - away_opp_ppg,
        'home_tempo':  home_tempo,
        'away_tempo':  away_tempo,
        'tempo_diff':  away_tempo - home_tempo,
    }
