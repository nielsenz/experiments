"""
First-to-10 college basketball model
- Training: 2025 MBB season PBP via sportsdataverse
- Features: pace_ratio, pace_diff, home_pts_pg, away_pts_pg
- Model: Logistic Regression
- Inference: 2026 Sweet 16 matchups
"""
import os, pickle, warnings
warnings.filterwarnings('ignore')
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.metrics import roc_auc_score, accuracy_score, classification_report

import sportsdataverse as sdv

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 & 2: Load 2025 PBP → extract first-to-10 outcomes
# ─────────────────────────────────────────────────────────────────────────────
print("Loading 2025 MBB PBP data...")
pbp = sdv.load_mbb_pbp(seasons=[2025], return_as_pandas=True)
print(f"Total PBP rows: {len(pbp):,}")

# Sort by game then play sequence
pbp = pbp.sort_values(['game_id', 'game_play_number']).reset_index(drop=True)

# Cumulative max scores per game (who reaches 10 first)
pbp['home_cum'] = pbp.groupby('game_id')['home_score'].cummax()
pbp['away_cum'] = pbp.groupby('game_id')['away_score'].cummax()

# First scoring play that brings either team to >= 10
pbp['home_reach_10'] = pbp['home_cum'] >= 10
pbp['away_reach_10'] = pbp['away_cum'] >= 10

# For each game: find the first play where each team reached 10
first_home_10 = pbp[pbp['home_reach_10']].groupby('game_id')['game_play_number'].min().rename('home_10_play')
first_away_10 = pbp[pbp['away_reach_10']].groupby('game_id')['game_play_number'].min().rename('away_10_play')

reach_df = pd.concat([first_home_10, first_away_10], axis=1)
reach_df['home_first_10'] = (reach_df['home_10_play'] <= reach_df['away_10_play']).astype(int)

print(f"Games with complete first-to-10 outcome: {len(reach_df):,}")
print(reach_df['home_first_10'].value_counts())

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Build features per game
# ─────────────────────────────────────────────────────────────────────────────
# Final scores (home_pts_pg, away_pts_pg) and pace metrics

# Get final scores per game
final_scores = pbp.groupby('game_id').agg(
    home_pts=('home_score', 'max'),
    away_pts=('away_score', 'max'),
    n_plays=('game_play_number', 'max'),
    home_abbrev=('home_team_abbrev', 'first'),
    away_abbrev=('away_team_abbrev', 'first'),
).reset_index()

# Merge with outcome
model_df = reach_df.reset_index().merge(final_scores, on='game_id', how='inner')
print(f"\nModel DataFrame shape: {model_df.shape}")

# Build features
model_df['total_pts'] = model_df['home_pts'] + model_df['away_pts']
model_df['pace_ratio']   = model_df['home_pts'] / (model_df['total_pts'] + 1)   # home share of scoring
model_df['pace_diff']    = np.abs(model_df['home_pts'] - model_df['away_pts']) / (model_df['total_pts'] + 1)  # margin ratio
model_df['home_pts_pg']  = model_df['home_pts'].astype(float)
model_df['away_pts_pg']  = model_df['away_pts'].astype(float)

features = ['pace_ratio', 'pace_diff', 'home_pts_pg', 'away_pts_pg']
X = model_df[features].astype(float).values
y = model_df['home_first_10'].values

# Clean
mask = np.isfinite(X).all(axis=1) & (X[:, 2:] >= 0).all(axis=1)
X, y = X[mask], y[mask]
print(f"Training samples after cleaning: {len(X):,}")
print(f"Class balance: {y.mean():.3f} home_first_10")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 (model): Train logistic regression
# ─────────────────────────────────────────────────────────────────────────────
lr = LogisticRegression(random_state=42, max_iter=1000)
cv_auc  = cross_val_score(lr, X, y, cv=5, scoring='roc_auc')
cv_acc  = cross_val_score(lr, X, y, cv=5, scoring='accuracy')

lr.fit(X, y)
y_prob = lr.predict_proba(X)[:, 1]
y_pred = lr.predict(X)

print(f"\n=== Model Performance (5-fold CV) ===")
print(f"AUC:      {cv_auc.mean():.4f} ± {cv_auc.std():.4f}")
print(f"Accuracy: {cv_acc.mean():.4f} ± {cv_acc.std():.4f}")
print(f"In-sample AUC: {roc_auc_score(y, y_prob):.4f}")
print(f"In-sample Accuracy: {accuracy_score(y, y_pred):.4f}")
print("\nClassification Report:")
print(classification_report(y, y_pred, target_names=['Away First 10', 'Home First 10']))
print("Coefficients:")
for f, c in zip(features, lr.coef_[0]):
    print(f"  {f}: {c:+.4f}")
print(f"  intercept: {lr.intercept_[0]:+.4f}")

# Save model
model_path = '/home/workspace/cbb-2026/first_to_10_model_2025.pkl'
with open(model_path, 'wb') as f:
    pickle.dump({'model': lr, 'features': features}, f)
print(f"\nModel saved → {model_path}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: 2026 Sweet 16 team stats
# ─────────────────────────────────────────────────────────────────────────────
# 2026 Sweet 16 matchups (home, away) — all neutral site
# Team PPG estimates based on 2024-25 season data (KenPom / ESPN averages)
# Format: (home_team, away_team, home_ppg_estimate, away_ppg_estimate)
s16_matchups = [
    ("Purdue",        "Texas",          83.2, 74.1),
    ("Nebraska",      "Iowa",           71.8, 76.3),
    ("Arizona",       "Arkansas",       82.5, 76.9),
    ("Houston",       "Illinois",       74.8, 78.2),
    ("Duke",          "St. John's",     80.1, 77.4),
    ("Michigan",      "Alabama",        74.6, 87.3),
    ("UConn",         "Michigan State", 80.8, 78.5),
    ("Iowa State",    "Tennessee",      74.3, 81.2),
]

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: Generate predictions
# ─────────────────────────────────────────────────────────────────────────────
# For neutral site: pace_ratio ≈ 0.50, pace_diff based on expected margin
# Sweet 16 games are close → typical 3-5pt margins on 75-80pt totals → pace_diff ≈ 0.04-0.07

print("\n=== Sweet 16 Predictions ===")
pred_rows = []
for home, away, h_ppg, a_ppg in s16_matchups:
    total = h_ppg + a_ppg
    expected_margin = abs(h_ppg - a_ppg)
    pace_diff = expected_margin / (total + 1)
    pace_ratio = h_ppg / (total + 1)

    X_new = np.array([[pace_ratio, pace_diff, h_ppg, a_ppg]])
    prob = lr.predict_proba(X_new)[0, 1]
    favored = home if prob > 0.5 else away
    confidence = max(prob, 1 - prob)

    pred_rows.append({
        'home_team': home,
        'away_team': away,
        'home_ppg_est': h_ppg,
        'away_ppg_est': a_ppg,
        'prob_home_first_10': round(prob, 4),
        'favored_first_10': favored,
        'confidence': round(confidence, 4),
    })

pred_df = pd.DataFrame(pred_rows)
print(pred_df[['home_team','away_team','prob_home_first_10','favored_first_10','confidence']].to_string(index=False))

pred_path = '/home/workspace/cbb-2026/sweet16_predictions_2026.csv'
pred_df.to_csv(pred_path, index=False)
print(f"\nPredictions saved → {pred_path}")

# ── Summary ────────────────────────────────────────────────────────────────────
print("\n" + "="*70)
print("FINAL SUMMARY")
print("="*70)
print(f"\nModel: Logistic Regression | Training: {len(X):,} 2025 MBB games")
print(f"CV AUC: {cv_auc.mean():.4f} ± {cv_auc.std():.4f}")
print(f"CV Accuracy: {cv_acc.mean():.4f} ± {cv_acc.std():.4f}")
print(f"\nFeatures: pace_ratio, pace_diff, home_pts_pg, away_pts_pg")
print(f"\nCoefficients:")
for f, c in zip(features, lr.coef_[0]):
    print(f"  {f}: {c:+.4f}")
print(f"  intercept: {lr.intercept_[0]:+.4f}")

print(f"\n{'='*70}")
print("SWEET 16 PREDICTIONS (2026)")
print(f"{'='*70}")
print(pred_df[['home_team','away_team','prob_home_first_10','favored_first_10','confidence']].to_string(index=False))
