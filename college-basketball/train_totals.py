"""
Train a totals (over/under) regression model for 2026 NCAA Tournament betting.

Target: total points scored (home_score + away_score)
Features: pre-game season-average team stats only
"""
import json, pickle, warnings
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import cross_val_score, KFold
from sklearn.metrics import mean_absolute_error

warnings.filterwarnings('ignore')

from config import SEASON_PBP, TEAM_STATS, MODELS_DIR, LEAGUE_AVG_PPG, LEAGUE_AVG_OPP_PPG, LEAGUE_AVG_PACE

MODELS_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = [
    'home_ppg', 'away_ppg',
    'home_opp_ppg', 'away_opp_ppg',
    'total_ppg',       # home_ppg + away_ppg — primary pace signal
    'home_net',        # home net rating
    'away_net',        # away net rating
    'avg_net',         # (home_net + away_net) / 2 — combined quality
    'def_strength',    # (home_opp_ppg + away_opp_ppg) / 2 — how stingy both defenses are
]

# ── Load team stats ────────────────────────────────────────────────────────────
print("Loading team stats...")
team_stats_df = pd.read_csv(TEAM_STATS)
stats_by_id = {str(row['team_id']): row for _, row in team_stats_df.iterrows()}

def get_stats(team_id):
    s = stats_by_id.get(str(team_id))
    if s is not None:
        return float(s['avg_pts']), float(s['avg_opp_pts']), float(s['avg_pace'])
    return LEAGUE_AVG_PPG, LEAGUE_AVG_OPP_PPG, LEAGUE_AVG_PACE

def compute_features(h_ppg, a_ppg, h_opp, a_opp):
    return {
        'home_ppg': h_ppg,
        'away_ppg': a_ppg,
        'home_opp_ppg': h_opp,
        'away_opp_ppg': a_opp,
        'total_ppg': h_ppg + a_ppg,
        'home_net': h_ppg - h_opp,
        'away_net': a_ppg - a_opp,
        'avg_net': ((h_ppg - h_opp) + (a_ppg - a_opp)) / 2,
        'def_strength': (h_opp + a_opp) / 2,
    }

# ── Load PBP and extract final scores ─────────────────────────────────────────
print("Loading season PBP...")
with open(SEASON_PBP) as f:
    all_games = json.load(f)
print(f"Loaded {len(all_games)} games")

X_rows, y_totals, y_margins = [], [], []
missing = 0

for gid, game in all_games.items():
    plays = game.get('plays', [])
    if not plays:
        continue

    # Get final score from last scoring play
    scored = [p for p in plays if p.get('scoringPlay')]
    if not scored:
        continue
    last = scored[-1]
    home_score = last.get('homeScore', 0)
    away_score = last.get('awayScore', 0)
    if home_score == 0 and away_score == 0:
        continue
    total = home_score + away_score
    margin = home_score - away_score  # positive = home win

    # Skip blowouts and incomplete games (likely data issues)
    if total < 80 or total > 220:
        continue

    # Get team IDs
    box = game.get('boxscore', {})
    teams = box.get('teams', [])
    if len(teams) != 2:
        continue
    home_id = away_id = None
    for t in teams:
        tid = str(t.get('team', {}).get('id', ''))
        if t.get('homeAway') == 'home':
            home_id = tid
        elif t.get('homeAway') == 'away':
            away_id = tid
    if not home_id or not away_id:
        continue

    h_ppg, h_opp, _ = get_stats(home_id)
    a_ppg, a_opp, _ = get_stats(away_id)

    if h_ppg == LEAGUE_AVG_PPG or a_ppg == LEAGUE_AVG_PPG:
        missing += 1

    feats = compute_features(h_ppg, a_ppg, h_opp, a_opp)
    X_rows.append([feats[c] for c in FEATURE_COLS])
    y_totals.append(total)
    y_margins.append(margin)

X = np.array(X_rows)
y_tot = np.array(y_totals)
y_mar = np.array(y_margins)

print(f"Training samples: {len(X)} ({missing} used league avg fallback)")
print(f"Total points — mean: {y_tot.mean():.1f}, std: {y_tot.std():.1f}, range: [{y_tot.min():.0f}, {y_tot.max():.0f}]")
print(f"Margin      — mean: {y_mar.mean():+.1f}, std: {y_mar.std():.1f}")

# ── Train totals model ─────────────────────────────────────────────────────────
print("\n--- TOTALS MODEL ---")
cv = KFold(n_splits=5, shuffle=True, random_state=42)

# Ridge baseline
ridge = Ridge(alpha=1.0)
cv_mae_ridge = -cross_val_score(ridge, X, y_tot, cv=cv, scoring='neg_mean_absolute_error')
print(f"Ridge  CV MAE: {cv_mae_ridge.mean():.2f} ± {cv_mae_ridge.std():.2f} pts")

# GBM
gbm_tot = GradientBoostingRegressor(
    n_estimators=200, max_depth=3, min_samples_leaf=20,
    learning_rate=0.05, subsample=0.8, random_state=42
)
cv_mae_gbm = -cross_val_score(gbm_tot, X, y_tot, cv=cv, scoring='neg_mean_absolute_error')
print(f"GBM    CV MAE: {cv_mae_gbm.mean():.2f} ± {cv_mae_gbm.std():.2f} pts")

gbm_tot.fit(X, y_tot)
in_sample_mae = mean_absolute_error(y_tot, gbm_tot.predict(X))
print(f"In-sample MAE: {in_sample_mae:.2f} pts")

print("\nFeature importances (totals):")
for feat, imp in sorted(zip(FEATURE_COLS, gbm_tot.feature_importances_), key=lambda x: -x[1]):
    print(f"  {feat:<20}: {imp:.4f}")

# ── Train spread model ─────────────────────────────────────────────────────────
print("\n--- SPREAD MODEL ---")
gbm_spr = GradientBoostingRegressor(
    n_estimators=200, max_depth=3, min_samples_leaf=20,
    learning_rate=0.05, subsample=0.8, random_state=42
)
cv_mae_spr = -cross_val_score(gbm_spr, X, y_mar, cv=cv, scoring='neg_mean_absolute_error')
print(f"GBM    CV MAE: {cv_mae_spr.mean():.2f} ± {cv_mae_spr.std():.2f} pts")

gbm_spr.fit(X, y_mar)
in_sample_mae_spr = mean_absolute_error(y_mar, gbm_spr.predict(X))
print(f"In-sample MAE: {in_sample_mae_spr:.2f} pts")

print("\nFeature importances (spread):")
for feat, imp in sorted(zip(FEATURE_COLS, gbm_spr.feature_importances_), key=lambda x: -x[1]):
    print(f"  {feat:<20}: {imp:.4f}")

# ── Save both models ───────────────────────────────────────────────────────────
artifacts = {
    'totals_model': gbm_tot,
    'spread_model': gbm_spr,
    'features': FEATURE_COLS,
    'trained_on': len(X),
    'totals_cv_mae': float(cv_mae_gbm.mean()),
    'spread_cv_mae': float(cv_mae_spr.mean()),
    'avg_total': float(y_tot.mean()),
    'avg_margin': float(y_mar.mean()),
}

out = MODELS_DIR / 'totals_spread_model.pkl'
with open(out, 'wb') as f:
    pickle.dump(artifacts, f)
print(f"\nModels saved → {out}")
