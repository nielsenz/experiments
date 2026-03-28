"""
Train a no-leakage first-to-10 model for 2026 NCAA Tournament betting.

Features: season-average team stats only (pre-game info, no actual game scores)
Model: GradientBoostingClassifier trained on 1138 regular season games
"""
import json, pickle, warnings
import numpy as np
import pandas as pd
from collections import defaultdict
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.calibration import CalibratedClassifierCV

warnings.filterwarnings('ignore')

from config import SEASON_PBP, TEAM_STATS, TEAM_TEMPO, MODEL_PATH, MODELS_DIR, LEAGUE_AVG_PPG, LEAGUE_AVG_OPP_PPG, LEAGUE_AVG_PACE
from features import compute_features, FEATURE_COLS, LEAGUE_NEUTRAL_P10

MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ── Step 1: Load PBP and extract first-to-10 labels ───────────────────────────
print("Loading season PBP data...")
with open(SEASON_PBP) as f:
    all_games = json.load(f)
print(f"Loaded {len(all_games)} games")

def extract_first_to_10(plays):
    """Extract which team reached 10 first using scoring play sequence."""
    scored = [p for p in plays if p.get('scoringPlay')]
    for p in scored:
        away = p.get('awayScore', 0)
        home = p.get('homeScore', 0)
        pts = p.get('scoreValue', 0)
        if away >= 10 and (away - pts) < 10:
            return 'away'
        if home >= 10 and (home - pts) < 10:
            return 'home'
    return None

# ── Step 2: Build team stats + tempo lookups ───────────────────────────────────
print("Loading team stats...")
team_stats_df = pd.read_csv(TEAM_STATS)
stats_by_id = {}
for _, row in team_stats_df.iterrows():
    stats_by_id[str(row['team_id'])] = {
        'name': row['team_name'],
        'avg_pts': float(row['avg_pts']),
        'avg_opp_pts': float(row['avg_opp_pts']),
        'avg_pace': float(row['avg_pace']),
    }
print(f"Team stats loaded for {len(stats_by_id)} teams")

print("Loading tempo stats...")
tempo_by_id = {}
if TEAM_TEMPO.exists():
    tempo_df = pd.read_csv(TEAM_TEMPO)
    for _, row in tempo_df.iterrows():
        tempo_by_id[str(row['team_id'])] = float(row['neutral_p10'])
    print(f"Tempo stats loaded for {len(tempo_by_id)} teams")
else:
    print("  Warning: team_tempo_2026.csv not found — run ingest/build_tempo_stats.py")

def get_stats(team_id):
    """Return (avg_pts, avg_opp_pts, avg_pace, neutral_p10, stats_source) for a team_id."""
    sid = str(team_id)
    if sid in stats_by_id:
        s = stats_by_id[sid]
        tempo = tempo_by_id.get(sid, LEAGUE_NEUTRAL_P10)
        return s['avg_pts'], s['avg_opp_pts'], s['avg_pace'], tempo, 'team_stats_2026'
    return LEAGUE_AVG_PPG, LEAGUE_AVG_OPP_PPG, LEAGUE_AVG_PACE, LEAGUE_NEUTRAL_P10, 'league_avg'

# ── Step 3: Build training set ─────────────────────────────────────────────────
print("Building training set from PBP...")
X_rows = []
y_labels = []
missing_teams = set()

for gid, game in all_games.items():
    plays = game.get('plays', [])
    if not plays:
        continue

    # Extract first-to-10 label
    f10 = extract_first_to_10(plays)
    if not f10:
        continue

    # Get team IDs from boxscore
    box = game.get('boxscore', {})
    teams = box.get('teams', [])
    if len(teams) != 2:
        continue

    home_id = away_id = None
    for t in teams:
        ha = t.get('homeAway', '')
        tid = str(t.get('team', {}).get('id', ''))
        if ha == 'home':
            home_id = tid
        elif ha == 'away':
            away_id = tid

    if not home_id or not away_id:
        continue

    # Look up season-average stats (NO game scores — no leakage)
    h_ppg, h_opp, h_pace, h_tempo, h_src = get_stats(home_id)
    a_ppg, a_opp, a_pace, a_tempo, a_src = get_stats(away_id)

    if h_src == 'league_avg':
        missing_teams.add(home_id)
    if a_src == 'league_avg':
        missing_teams.add(away_id)

    feats = compute_features(h_ppg, a_ppg, h_opp, a_opp, h_pace, a_pace, h_tempo, a_tempo)
    X_rows.append([feats[c] for c in FEATURE_COLS])
    y_labels.append(1 if f10 == 'home' else 0)

X_orig = np.array(X_rows)
y_orig = np.array(y_labels)

# ── Symmetrize: add a mirrored copy of every game with home/away swapped ───────
# This removes the home-court bias baked in from regular-season training data.
# Tournament games are neutral-site; the model should be indifferent to the
# arbitrary home/away label in the schedule.
#
# FEATURE_COLS order:
#   home_ppg, away_ppg, home_opp_ppg, away_opp_ppg, pace_ratio,
#   ppg_diff, total_ppg, home_net, away_net, home_tempo, away_tempo, tempo_diff
_idx = {c: i for i, c in enumerate(FEATURE_COLS)}
mirrored_rows = []
for row in X_orig:
    m = row.copy()
    m[_idx['home_ppg']]     = row[_idx['away_ppg']]
    m[_idx['away_ppg']]     = row[_idx['home_ppg']]
    m[_idx['home_opp_ppg']] = row[_idx['away_opp_ppg']]
    m[_idx['away_opp_ppg']] = row[_idx['home_opp_ppg']]
    m[_idx['pace_ratio']]   = 1.0 - row[_idx['pace_ratio']]
    m[_idx['ppg_diff']]     = -row[_idx['ppg_diff']]
    m[_idx['home_net']]     = row[_idx['away_net']]
    m[_idx['away_net']]     = row[_idx['home_net']]
    m[_idx['home_tempo']]   = row[_idx['away_tempo']]
    m[_idx['away_tempo']]   = row[_idx['home_tempo']]
    m[_idx['tempo_diff']]   = -row[_idx['tempo_diff']]
    # total_ppg is symmetric — no change needed
    mirrored_rows.append(m)

X = np.vstack([X_orig, np.array(mirrored_rows)])
y = np.concatenate([y_orig, 1 - y_orig])

if missing_teams:
    print(f"  Warning: {len(missing_teams)} team IDs used league avg fallback")

print(f"Training samples: {len(X_orig)} original → {len(X)} after symmetrization")
print(f"Home first-to-10 base rate (original): {y_orig.mean():.1%}")
print(f"Home first-to-10 base rate (symmetrized): {y.mean():.1%}  (should be ~50%)")

# ── Step 4: Train GBM ──────────────────────────────────────────────────────────
print("\nTraining GradientBoostingClassifier...")
gbm = GradientBoostingClassifier(
    n_estimators=200,
    max_depth=3,
    min_samples_leaf=20,
    learning_rate=0.05,
    subsample=0.8,
    random_state=42,
)

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_auc = cross_val_score(gbm, X, y, cv=cv, scoring='roc_auc')
cv_brier = cross_val_score(gbm, X, y, cv=cv, scoring='neg_brier_score')

print(f"CV AUC:   {cv_auc.mean():.4f} ± {cv_auc.std():.4f}")
print(f"CV Brier: {(-cv_brier).mean():.4f} ± {(-cv_brier).std():.4f}")

gbm.fit(X, y)
in_sample_auc = roc_auc_score(y, gbm.predict_proba(X)[:, 1])
print(f"In-sample AUC: {in_sample_auc:.4f}")

# Calibration
probs_is = gbm.predict_proba(X)[:, 1]
cal_error = abs(probs_is.mean() - y.mean())
print(f"Calibration error (mean prob vs base rate): {cal_error:.4f}")

print("\nFeature importances:")
for feat, imp in sorted(zip(FEATURE_COLS, gbm.feature_importances_), key=lambda x: -x[1]):
    print(f"  {feat:<20}: {imp:.4f}")

# ── Step 5: Save model ─────────────────────────────────────────────────────────
artifacts = {
    'model': gbm,
    'features': FEATURE_COLS,
    'trained_on': len(X),
    'home_f10_base_rate': float(y.mean()),
    'cv_auc_mean': float(cv_auc.mean()),
    'cv_auc_std': float(cv_auc.std()),
}

with open(MODEL_PATH, 'wb') as f:
    pickle.dump(artifacts, f)
print(f"\nModel saved → {MODEL_PATH}")

if cv_auc.mean() < 0.52:
    print("\n⚠️  WARNING: CV AUC < 0.52 — model has limited predictive edge.")
    print(f"   Consider using the base rate ({y.mean():.1%} home F10) directly for betting.")
