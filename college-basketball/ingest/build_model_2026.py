"""
Build 2025-2026 team stats from scraped PBP, apply to first-to-10 model.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SEASON_PBP, PROCESSED_DIR, TOURNAMENT_PBP, MODEL_2026

import json, pickle, pandas as pd, numpy as np
from collections import defaultdict

PBP_FILE = SEASON_PBP
OUT_DIR = PROCESSED_DIR

print("Loading PBP data...")
with open(PBP_FILE) as f:
    all_games = json.load(f)
print(f"Loaded {len(all_games)} games")

# ---- Build 2025-2026 team stats ----
team_scores = defaultdict(list)  # team_id -> list of pts scored
team_opp_scores = defaultdict(list)  # team_id -> list of pts allowed
team_game_pace = defaultdict(list)  # team_id -> pace (total pts in game)

for gid, game in all_games.items():
    plays = game.get('plays', [])
    if not plays:
        continue

    # Get team IDs and names from boxscore
    box = game.get('boxscore', {})
    teams = box.get('teams', [])
    if len(teams) != 2:
        continue

    team_info = {}
    for t in teams:
        team_info[t['team']['homeAway']] = {
            'id': t['team']['id'],
            'name': t['team'].get('shortDisplayName', t['team'].get('displayName', 'UNK')),
            'score': int(t.get('score', {}).get('value', 0))
        }

    # Get final score from scoring plays
    scored_plays = [p for p in plays if p.get('scoringPlay')]
    if not scored_plays:
        continue

    final_play = scored_plays[-1]
    away_final = final_play.get('awayScore', 0)
    home_final = final_play.get('homeScore', 0)

    if away_final == 0 and home_final == 0:
        continue

    # Home team
    if 'home' in team_info:
        tid = team_info['home']['id']
        team_scores[tid].append(home_final)
        team_opp_scores[tid].append(away_final)
        team_game_pace[tid].append(home_final + away_final)

    # Away team
    if 'away' in team_info:
        tid = team_info['away']['id']
        team_scores[tid].append(away_final)
        team_opp_scores[tid].append(home_final)
        team_game_pace[tid].append(away_final + home_final)

# Build team stats DataFrame
rows = []
for tid, scores in team_scores.items():
    if len(scores) < 5:  # Min 5 games
        continue
    opp = team_opp_scores[tid]
    pace = team_game_pace[tid]
    rows.append({
        'team_id': tid,
        'team_name': team_info.get('home', {}).get('name', 'UNK'),  # We'll fix names below
        'avg_pts': np.mean(scores),
        'avg_opp_pts': np.mean(opp),
        'avg_pace': np.mean(pace),
        'games': len(scores),
    })

# Fix team names from boxscore
name_map = {}
for gid, game in all_games.items():
    box = game.get('boxscore', {})
    for t in box.get('teams', []):
        tid = t['team']['id']
        name = t['team'].get('shortDisplayName', t['team'].get('displayName', 'UNK'))
        if tid not in name_map:
            name_map[tid] = name

team_pts_2026 = pd.DataFrame(rows)
team_pts_2026['team_name'] = team_pts_2026['team_id'].map(name_map)

# Create pace_ratio: team_pace / league_avg_pace
league_avg_pace = team_pts_2026['avg_pace'].mean()
team_pts_2026['pace_ratio'] = team_pts_2026['avg_pace'] / league_avg_pace

print(f"\n2025-2026 team stats: {len(team_pts_2026)} teams")
print(f"League avg pace: {league_avg_pace:.1f}")
print(f"\nTop scoring teams:")
print(team_pts_2026.nlargest(10, 'avg_pts')[['team_name', 'avg_pts', 'avg_opp_pts', 'avg_pace', 'games']])

# ---- Save team stats ----
team_pts_2026.to_csv(f'{OUT_DIR}/team_stats_2026.csv', index=False)
print(f"\nSaved team stats to {OUT_DIR}/team_stats_2026.csv")

# ---- Apply to tournament ----
print("\n" + "="*60)
print("APPLYING TO 2026 TOURNAMENT")
print("="*60)

with open(MODEL_2026, 'rb') as f:
    ma = pickle.load(f)
model = ma['model']
team_pts_2024 = ma['team_pts']
team_pts_2024['team_name_lower'] = team_pts_2024['team_name'].str.lower().str.strip()

# Tournament PBP
with open(TOURNAMENT_PBP) as f:
    tourn_games = json.load(f)

# Build winner set from completed games
winners = {}
for gid, game in tourn_games.items():
    comps = game.get('competitions', [{}])[0].get('competitors', [])
    status = game.get('status', {})
    if status.get('type', {}).get('name') == 'STATUS_FINAL':
        for c in comps:
            if c.get('winner'):
                winners[c['team']['id']] = c['team'].get('shortDisplayName', c['team'].get('displayName', '?'))

def name_to_pts(name, team_pts_df, fallback_df):
    """Get (pts_pg, pace_ratio) for a team name."""
    if pd.isna(name) or name in ('TBD', 'TBD Seed', ''):
        return None, None
    # Try 2026 stats first
    match = team_pts_df[team_pts_df['team_name'].str.lower().str.strip() == name.lower().strip()]
    if len(match) == 0:
        # Try partial match
        match = team_pts_df[team_pts_df['team_name'].str.lower().str.contains(name.lower().strip(), na=False)]
    if len(match) > 0:
        row = match.iloc[0]
        return row['avg_pts'], row['pace_ratio']
    # Fallback to 2024
    fb_match = fallback_df[fallback_df['team_name_lower'].str.contains(name.lower().strip(), na=False)]
    if len(fb_match) > 0:
        row = fb_match.iloc[0]
        return row['avg_pts'], None  # No pace_ratio for fallback
    return None, None

def extract_first_to_10(plays):
    """Extract first-to-10 result from PBP plays."""
    scored = [p for p in plays if p.get('scoringPlay')]
    for i, p in enumerate(scored):
        away = p.get('awayScore', 0)
        home = p.get('homeScore', 0)
        pts = p.get('scoreValue', 0)
        if away >= 10 and (away - pts) < 10:
            return 'away', away, home
        if home >= 10 and (home - pts) < 10:
            return 'home', away, home
    return None, 0, 0

results = []
for gid, game in tourn_games.items():
    comps = game.get('competitions', [{}])[0].get('competitors', [])
    status = game.get('status', {})
    plays = game.get('plays', [])

    home_comp = next((c for c in comps if c.get('homeAway') == 'home'), None)
    away_comp = next((c for c in comps if c.get('homeAway') == 'away'), None)
    if not home_comp or not away_comp:
        continue

    home_id = home_comp['team']['id']
    away_id = away_comp['team']['id']
    home_name = home_comp['team'].get('shortDisplayName', home_comp['team'].get('displayName', 'UNK'))
    away_name = away_comp['team'].get('shortDisplayName', away_comp['team'].get('displayName', 'UNK'))
    game_status = status.get('type', {}).get('name', 'UNKNOWN')

    # Try to get date
    date = game.get('date', '')[:10] if game.get('date') else '2026-03-01'

    row = {
        'game_id': gid,
        'date': date,
        'home_team': home_name,
        'away_team': away_name,
        'status': game_status,
    }

    # Check if completed with PBP
    if plays and game_status == 'STATUS_FINAL':
        winner_team, away_f, home_f = extract_first_to_10(plays)
        row['home_score'] = home_f
        row['away_score'] = away_f
        row['f10_winner'] = winner_team
        row['f10_home_win'] = 1 if winner_team == 'home' else 0
        row['result_note'] = 'COMPLETED'
    else:
        # Get scores from competitors if available
        try:
            home_score = int(home_comp.get('score', {}).get('value', 0) or 0)
            away_score = int(away_comp.get('score', {}).get('value', 0) or 0)
            row['home_score'] = home_score
            row['away_score'] = away_score
        except:
            row['home_score'] = 0
            row['away_score'] = 0
        row['f10_winner'] = None
        row['f10_home_win'] = None
        row['result_note'] = 'SCHEDULED'

    # Get 2026 stats
    hp, hr = name_to_pts(home_name, team_pts_2026, team_pts_2024)
    ap, ar = name_to_pts(away_name, team_pts_2026, team_pts_2024)

    row['home_pts_pg_26'] = hp
    row['away_pts_pg_26'] = ap
    row['home_pace_r26'] = hr
    row['away_pace_r26'] = ar
    row['has_2026_stats'] = hp is not None and ap is not None

    # Predict
    if hp and ap:
        pace_ratio = (hr + ar) / 2 if (hr and ar) else 1.0
        pace_diff = (hr - ar) if (hr and ar) else 0.0
        X = np.array([[pace_ratio, pace_diff, hp, ap]])
        row['prob_home_win'] = model.predict_proba(X)[0][1]
        # Adjust for neutral site (tournament)
        row['prob_home_win_adj'] = row['prob_home_win'] * 0.95  # Slight home dampening for tournament
    else:
        row['prob_home_win'] = None
        row['prob_home_win_adj'] = None

    results.append(row)

df = pd.DataFrame(results).sort_values('date')

# Print results
print("\n=== COMPLETED GAMES ===")
comp = df[df['result_note'] == 'COMPLETED'].copy()
comp['correct'] = ((comp['f10_home_win'] == 1) & (comp['home_score'] > comp['away_score'])) | \
                  ((comp['f10_home_win'] == 0) & (comp['away_score'] > comp['home_score']))
home_f10_rate = comp['f10_home_win'].mean() if len(comp) > 0 else 0
print(f"Completed: {len(comp)} games | Home F10 rate: {home_f10_rate:.1%}")

print("\n=== PENDING / LIVE GAMES ===")
pending = df[df['result_note'] == 'SCHEDULED'].copy()
pending = pending.sort_values('date')
print(f"{'Date':<12} {'Home':<22} {'Away':<22} {'Score':>10}  {'P(Home)':>8}")
print("-" * 80)
for _, r in pending.iterrows():
    score = f"{r['home_score']}-{r['away_score']}" if (r['home_score'] > 0 or r['away_score'] > 0) else "—"
    prob = f"{r['prob_home_win_adj']:.1%}" if r['prob_home_win_adj'] else "N/A"
    print(f"{r['date']:<12} {r['home_team']:<22} {r['away_team']:<22} {score:>10}  {prob:>8}")

print("\n=== PREDICTIONS FOR TBD MATCHUPS ===")
tdb = df[df['home_team'] == 'TBD'].copy()
print(f"{len(tdb)} TBD games excluded")

df.to_csv(f'{OUT_DIR}/first_to_10_2026_v2.csv', index=False)
print(f"\nSaved to {OUT_DIR}/first_to_10_2026_v2.csv")
