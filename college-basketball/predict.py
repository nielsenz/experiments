"""
Generate first-to-10 predictions for 2026 NCAA Tournament betting.

Outputs predictions for all scheduled + completed tournament games using the
no-leakage model trained on 1138 regular season games.
"""
import pickle, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

from config import (MODEL_PATH, SCHEDULE, TEAM_STATS, TEAM_TEMPO, PREDICTIONS_OUT, PROCESSED_DIR,
                    LEAGUE_AVG_PPG, LEAGUE_AVG_OPP_PPG, LEAGUE_AVG_PACE)
from features import compute_features, FEATURE_COLS, LEAGUE_NEUTRAL_P10

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ── Load model ─────────────────────────────────────────────────────────────────
with open(MODEL_PATH, 'rb') as f:
    artifacts = pickle.load(f)

model = artifacts['model']
base_rate = artifacts['home_f10_base_rate']
cv_auc = artifacts['cv_auc_mean']
trained_on = artifacts['trained_on']

# ── Load team stats + tempo ────────────────────────────────────────────────────
team_stats_df = pd.read_csv(TEAM_STATS)
stats_by_id = {}
for _, row in team_stats_df.iterrows():
    stats_by_id[str(row['team_id'])] = {
        'name': row['team_name'],
        'avg_pts': float(row['avg_pts']),
        'avg_opp_pts': float(row['avg_opp_pts']),
        'avg_pace': float(row['avg_pace']),
    }

tempo_by_id = {}
if TEAM_TEMPO.exists():
    tempo_df = pd.read_csv(TEAM_TEMPO)
    for _, row in tempo_df.iterrows():
        tempo_by_id[str(row['team_id'])] = float(row['neutral_p10'])

def get_stats(team_id):
    sid = str(int(float(team_id))) if team_id not in ('', 'nan') else ''
    if sid and sid in stats_by_id:
        s = stats_by_id[sid]
        tempo = tempo_by_id.get(sid, LEAGUE_NEUTRAL_P10)
        return s['avg_pts'], s['avg_opp_pts'], s['avg_pace'], tempo, s['name'], 'team_stats_2026'
    return LEAGUE_AVG_PPG, LEAGUE_AVG_OPP_PPG, LEAGUE_AVG_PACE, LEAGUE_NEUTRAL_P10, str(team_id), 'league_avg'

# ── Load tournament schedule ───────────────────────────────────────────────────
sched = pd.read_csv(SCHEDULE)

# Normalize date column (handle both UTC ISO and plain date strings)
sched['game_date'] = pd.to_datetime(sched['date'], utc=True, errors='coerce').dt.strftime('%Y-%m-%d')
sched['game_date'] = sched['game_date'].fillna(sched['date'].astype(str).str[:10])

# De-dup
sched = sched.drop_duplicates(subset='id')

# ── Generate predictions ───────────────────────────────────────────────────────
rows = []
for _, game in sched.iterrows():
    home_id = game.get('home_id', '')
    away_id = game.get('away_id', '')
    # Updated schedule uses home_name/away_name; original uses home_short_display_name
    home_name = game.get('home_name', game.get('home_short_display_name', str(home_id)))
    away_name = game.get('away_name', game.get('away_short_display_name', str(away_id)))
    status = game.get('status', game.get('status_type_name', ''))
    game_date = game.get('game_date', '')

    # Skip TBD matchups
    if pd.isna(home_id) or pd.isna(away_id):
        continue
    if str(home_name).upper() in ('TBD', 'NAN', '') or str(away_name).upper() in ('TBD', 'NAN', ''):
        continue

    h_ppg, h_opp, h_pace, h_tempo, h_resolved, h_src = get_stats(home_id)
    a_ppg, a_opp, a_pace, a_tempo, a_resolved, a_src = get_stats(away_id)

    feats = compute_features(h_ppg, a_ppg, h_opp, a_opp, h_pace, a_pace, h_tempo, a_tempo)
    X = np.array([[feats[c] for c in FEATURE_COLS]])
    prob_home = float(model.predict_proba(X)[0, 1])
    prob_away = 1.0 - prob_home

    edge_team = home_name if prob_home >= 0.5 else away_name
    edge_pct = abs(prob_home - 0.5) * 100

    src = 'team_stats_2026' if h_src == 'team_stats_2026' and a_src == 'team_stats_2026' else 'partial_fallback'

    rows.append({
        'game_date': game_date,
        'status': status,
        'home_team': home_name,
        'away_team': away_name,
        'home_ppg': round(h_ppg, 1),
        'away_ppg': round(a_ppg, 1),
        'home_opp_ppg': round(h_opp, 1),
        'away_opp_ppg': round(a_opp, 1),
        'pace_ratio': round(feats['pace_ratio'], 4),
        'ppg_diff': round(feats['ppg_diff'], 1),
        'total_ppg': round(feats['total_ppg'], 1),
        'prob_home_f10': round(prob_home, 4),
        'prob_away_f10': round(prob_away, 4),
        'edge_team': edge_team,
        'edge_pct': round(edge_pct, 1),
        'stats_source': src,
    })

df = pd.DataFrame(rows).sort_values(['game_date', 'home_team']).reset_index(drop=True)

# ── Save ───────────────────────────────────────────────────────────────────────
df.to_csv(PREDICTIONS_OUT, index=False)

# ── Print betting summary ──────────────────────────────────────────────────────
print("=" * 80)
print("2026 NCAA TOURNAMENT — FIRST-TO-10 PREDICTIONS")
print("=" * 80)
print(f"Model: GBM trained on {trained_on} games | CV AUC: {cv_auc:.4f}")
print(f"Base rate: home team scores first-to-10 in {base_rate:.1%} of games")
print(f"Note: All tournament games are neutral site")
print()

scheduled = df[df['status'] == 'STATUS_SCHEDULED']
completed = df[df['status'] == 'STATUS_FINAL']

if not scheduled.empty:
    print(f"{'UPCOMING GAMES':}")
    print(f"{'Date':<12} {'Home':<24} {'Away':<24} {'P(Home)':>9} {'P(Away)':>9} {'Edge':>10}")
    print("-" * 92)
    for _, r in scheduled.iterrows():
        edge_str = f"+{r['edge_pct']:.1f}% {r['edge_team'].split()[-1]}"
        print(f"{r['game_date']:<12} {r['home_team']:<24} {r['away_team']:<24} "
              f"{r['prob_home_f10']:>8.1%} {r['prob_away_f10']:>9.1%} {edge_str:>12}")

if not completed.empty:
    print(f"\n{'COMPLETED GAMES ({} results)'.format(len(completed))}")
    print(f"{'Date':<12} {'Home':<24} {'Away':<24} {'P(Home)':>9} {'P(Away)':>9}")
    print("-" * 80)
    for _, r in completed.iterrows():
        print(f"{r['game_date']:<12} {r['home_team']:<24} {r['away_team']:<24} "
              f"{r['prob_home_f10']:>8.1%} {r['prob_away_f10']:>9.1%}")

print(f"\nFull predictions saved → {PREDICTIONS_OUT}")
print(f"Total games: {len(df)} ({len(scheduled)} upcoming, {len(completed)} completed)")
