"""
Generate totals and spread predictions for 2026 NCAA Tournament Sweet 16.

Compares model predictions vs book lines to find over/under and spread edges.
"""
import pickle, warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

from config import MODELS_DIR, SCHEDULE, TEAM_STATS, PROCESSED_DIR, LEAGUE_AVG_PPG, LEAGUE_AVG_OPP_PPG, LEAGUE_AVG_PACE

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

def compute_features(h_ppg, a_ppg, h_opp, a_opp):
    return {
        'home_ppg': h_ppg, 'away_ppg': a_ppg,
        'home_opp_ppg': h_opp, 'away_opp_ppg': a_opp,
        'total_ppg': h_ppg + a_ppg,
        'home_net': h_ppg - h_opp,
        'away_net': a_ppg - a_opp,
        'avg_net': ((h_ppg - h_opp) + (a_ppg - a_opp)) / 2,
        'def_strength': (h_opp + a_opp) / 2,
    }

# ── Load models ────────────────────────────────────────────────────────────────
with open(MODELS_DIR / 'totals_spread_model.pkl', 'rb') as f:
    artifacts = pickle.load(f)

totals_model = artifacts['totals_model']
spread_model = artifacts['spread_model']
FEATURE_COLS = artifacts['features']
totals_cv_mae = artifacts['totals_cv_mae']
spread_cv_mae = artifacts['spread_cv_mae']
avg_total = artifacts['avg_total']
avg_margin = artifacts['avg_margin']

# ── Load team stats ────────────────────────────────────────────────────────────
team_stats_df = pd.read_csv(TEAM_STATS)
stats_by_id = {}
for _, row in team_stats_df.iterrows():
    stats_by_id[str(row['team_id'])] = {
        'name': row['team_name'],
        'avg_pts': float(row['avg_pts']),
        'avg_opp_pts': float(row['avg_opp_pts']),
        'avg_pace': float(row['avg_pace']),
    }

def get_stats(team_id):
    sid = str(int(float(team_id))) if str(team_id) not in ('', 'nan') else ''
    if sid and sid in stats_by_id:
        s = stats_by_id[sid]
        return s['avg_pts'], s['avg_opp_pts'], s['avg_pace'], s['name'], 'team_stats'
    return LEAGUE_AVG_PPG, LEAGUE_AVG_OPP_PPG, LEAGUE_AVG_PACE, str(team_id), 'league_avg'

# ── Load tournament schedule ───────────────────────────────────────────────────
sched = pd.read_csv(SCHEDULE)
sched['game_date'] = pd.to_datetime(sched['date'], utc=True, errors='coerce').dt.strftime('%Y-%m-%d')
sched['game_date'] = sched['game_date'].fillna(sched['date'].astype(str).str[:10])
sched = sched.drop_duplicates(subset='id')

# ── Generate predictions ───────────────────────────────────────────────────────
rows = []
for _, game in sched.iterrows():
    home_id = game.get('home_id', '')
    away_id = game.get('away_id', '')
    home_name = game.get('home_name', game.get('home_short_display_name', str(home_id)))
    away_name = game.get('away_name', game.get('away_short_display_name', str(away_id)))
    status = game.get('status', game.get('status_type_name', ''))
    game_date = game.get('game_date', '')

    if pd.isna(home_id) or pd.isna(away_id):
        continue
    if str(home_name).upper() in ('TBD', 'NAN', '') or str(away_name).upper() in ('TBD', 'NAN', ''):
        continue

    h_ppg, h_opp, h_pace, h_name, h_src = get_stats(home_id)
    a_ppg, a_opp, a_pace, a_name, a_src = get_stats(away_id)

    feats = compute_features(h_ppg, a_ppg, h_opp, a_opp)
    X = np.array([[feats[c] for c in FEATURE_COLS]])

    pred_total = float(totals_model.predict(X)[0])
    pred_spread = float(spread_model.predict(X)[0])  # positive = home wins by this much

    src = 'team_stats' if h_src == 'team_stats' and a_src == 'team_stats' else 'partial_fallback'

    rows.append({
        'game_date': game_date,
        'status': status,
        'home_team': home_name,
        'away_team': away_name,
        'home_ppg': round(h_ppg, 1),
        'away_ppg': round(a_ppg, 1),
        'home_opp_ppg': round(h_opp, 1),
        'away_opp_ppg': round(a_opp, 1),
        'pred_total': round(pred_total, 1),
        'pred_spread': round(pred_spread, 1),   # home - away; negative means away favored
        'stats_source': src,
    })

df = pd.DataFrame(rows).sort_values(['game_date', 'home_team']).reset_index(drop=True)

# ── Save ───────────────────────────────────────────────────────────────────────
out = PROCESSED_DIR / 'totals_predictions_2026.csv'
df.to_csv(out, index=False)

# ── Print Sweet 16 summary ─────────────────────────────────────────────────────
print("=" * 90)
print("2026 NCAA TOURNAMENT — TOTALS & SPREAD PREDICTIONS")
print("=" * 90)
print(f"Totals model CV MAE: ±{totals_cv_mae:.1f} pts | Spread model CV MAE: ±{spread_cv_mae:.1f} pts")
print(f"Season avg total: {avg_total:.1f} pts | Season avg margin: {avg_margin:+.1f} pts")
print(f"Note: All tournament games are neutral site — treat 'home' as team 1 in schedule")
print()

scheduled = df[df['status'] == 'STATUS_SCHEDULED']
completed = df[df['status'] == 'STATUS_FINAL']

if not scheduled.empty:
    print(f"UPCOMING GAMES ({len(scheduled)})")
    print(f"{'Date':<12} {'Home':<22} {'Away':<22} {'Pred Total':>11} {'Pred Spread':>12}")
    print("-" * 82)
    for _, r in scheduled.iterrows():
        spread_str = f"{r['home_team'].split()[-1]} {r['pred_spread']:+.1f}"
        print(f"{r['game_date']:<12} {r['home_team']:<22} {r['away_team']:<22} "
              f"{r['pred_total']:>10.1f}  {spread_str:>12}")

print()
print("HOW TO USE VS BOOK LINES:")
print("  Totals: if pred_total > book O/U → lean OVER; if pred_total < book → lean UNDER")
print("  Spread: pred_spread is home - away margin. Compare to book's spread.")
print(f"          Model MAE ≈ ±{totals_cv_mae:.0f} pts totals, ±{spread_cv_mae:.0f} pts spread — use for large edges only")
print()
print(f"Full predictions saved → {out}")
print(f"Total games: {len(df)} ({len(scheduled)} upcoming, {len(completed)} completed)")
