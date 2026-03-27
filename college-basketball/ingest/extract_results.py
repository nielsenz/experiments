"""
Extract first-to-10 results from completed 2026 tournament PBP.
Also try to get recent team stats from scoreboard API.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TOURNAMENT_PBP, MODEL_2026, PROCESSED_DIR

import requests
import json
import pandas as pd
import numpy as np
import pickle
from datetime import datetime

# Load tournament PBP data
with open(TOURNAMENT_PBP) as f:
    all_games = json.load(f)

# Load model for fallback stats
with open(MODEL_2026, 'rb') as f:
    ma = pickle.load(f)
team_pts_2024 = ma['team_pts']

def extract_first_to_10_with_lag(plays):
    """Find which team reached 10 first using LAG logic."""
    if not plays:
        return None, None, None, None
    rows = []
    for p in plays:
        away = p.get('awayScore', 0) or 0
        home = p.get('homeScore', 0) or 0
        pts = p.get('scoreValue', 0) or 0
        text = p.get('text', '') or ''
        rows.append({'away': away, 'home': home, 'pts': pts, 'text': text})
    df = pd.DataFrame(rows)
    if df.empty:
        return None, None, None, None
    df['prev_away'] = df['away'].shift(1, fill_value=0)
    df['prev_home'] = df['home'].shift(1, fill_value=0)
    df['first_reach_10'] = ((df['prev_away'] < 10) & (df['away'] >= 10)) | \
                           ((df['prev_home'] < 10) & (df['home'] >= 10))
    first_idx = df[df['first_reach_10']].index
    if first_idx.empty:
        return None, None, None, None
    idx = first_idx[0]
    row = df.loc[idx]
    team = 'home' if row['prev_home'] < 10 and row['home'] >= 10 else 'away'
    time_min = idx * 0.25  # rough estimate
    return team, int(row['away']), int(row['home']), row['text']

results = []
scoreboard_url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard'

for gid, game in all_games.items():
    header = game.get('header', {})
    comps_list = header.get('competitions', [])
    if not comps_list:
        continue
    comp = comps_list[0]
    status = header.get('status', {}).get('type', {}).get('name', '')
    is_completed = status == 'STATUS_FINAL'
    is_scheduled = status == 'STATUS_SCHEDULED'

    competitors = comp.get('competitors', [])
    if len(competitors) != 2:
        continue

    home_c = competitors[0] if competitors[0].get('homeAway') == 'home' else competitors[1]
    away_c = competitors[0] if competitors[0].get('homeAway') == 'away' else competitors[1]

    home_name = home_c.get('team', {}).get('shortDisplayName', 'UNK')
    away_name = away_c.get('team', {}).get('shortDisplayName', 'UNK')
    home_id = home_c.get('team', {}).get('id', '')
    away_id = away_c.get('team', {}).get('id', '')

    # Get final scores
    home_score = int(home_c.get('score', {}).get('value') or 0)
    away_score = int(away_c.get('score', {}).get('value') or 0)

    # Get date
    date_str = header.get('date', '')[:10]

    # Extract PBP if completed
    first_to_10_team = None
    first_to_10_text = None
    if is_completed:
        plays = game.get('plays', [])
        if plays:
            first_to_10_team, f10_away, f10_home, first_to_10_text = extract_first_to_10_with_lag(plays)

    results.append({
        'game_id': gid,
        'date': date_str,
        'home_team': home_name,
        'away_team': away_name,
        'home_id': home_id,
        'away_id': away_id,
        'home_score': home_score,
        'away_score': away_score,
        'status': status,
        'is_completed': is_completed,
        'first_to_10_team': first_to_10_team,
        'first_to_10_text': first_to_10_text,
    })

df = pd.DataFrame(results)

# Now get recent team stats from scoreboard (last 3 weeks of regular season)
# Check scoreboard for March 1, 8, 15 dates
recent_stats = {}  # team_id -> list of (pts_for, pts_against)

for date in ['20260301', '20260308', '20260315']:
    resp = requests.get(scoreboard_url, params={'dates': date, 'limit': 300}, timeout=10)
    if resp.status_code != 200:
        continue
    data = resp.json()
    for event in data.get('events', []):
        event_status = event.get('status', {}).get('type', {}).get('name', '')
        if event_status != 'STATUS_FINAL':
            continue
        comp = event.get('competitions', [{}])[0]
        for c in comp.get('competitors', []):
            tid = c.get('team', {}).get('id')
            score_val = int(c.get('score', {}).get('value') or 0)
            if tid and score_val > 0:
                if tid not in recent_stats:
                    recent_stats[tid] = []
                recent_stats[tid].append(score_val)

# Aggregate recent stats per team
def get_recent_ppg(team_id):
    scores = recent_stats.get(team_id, [])
    if len(scores) >= 2:
        return np.mean(scores), len(scores)
    return None, 0

# Match 2026 teams to 2024 stats and get predictions
def match_team(name, teams_2024):
    n = name.lower()
    for t in teams_2024:
        if n in t.lower() or t.lower() in n:
            return t
    return None

teams_2024 = team_pts_2024['team_name'].tolist()
teams_2026 = set(df['home_team'].tolist() + df['away_team'].tolist())

print(f"Total games: {len(df)}")
print(f"Completed: {df['is_completed'].sum()}")
print(f"With F10 result: {df['first_to_10_team'].notna().sum()}")
print(f"\nRecent stats collected for {len(recent_stats)} teams")

# Build predictions using available data
predictions = []
for _, row in df.iterrows():
    pred = {'game_id': row['game_id'], 'date': row['date'],
            'home_team': row['home_team'], 'away_team': row['away_team'],
            'home_score': row['home_score'], 'away_score': row['away_score'],
            'status': row['status'], 'actual_f10': row['first_to_10_team']}

    # Try to get stats from recent games
    h_ppg, h_games = get_recent_ppg(row['home_id'])
    a_ppg, a_games = get_recent_ppg(row['away_id'])

    if h_ppg and a_ppg and h_games >= 2 and a_games >= 2:
        # Use recent stats
        pred['home_pts_pg'] = h_ppg
        pred['away_pts_pg'] = a_ppg
        pred['pace_ratio'] = (h_ppg + a_ppg) / 147.4
        pred['pace_diff'] = h_ppg - a_ppg
        pred['stats_source'] = f'recent({h_games}g/{a_games}g)'
    else:
        # Fall back to 2024 model stats
        h_match = match_team(row['home_team'], teams_2024)
        a_match = match_team(row['away_team'], teams_2024)
        if h_match and a_match:
            h_row = team_pts_2024[team_pts_2024['team_name'] == h_match].iloc[0]
            a_row = team_pts_2024[team_pts_2024['team_name'] == a_match].iloc[0]
            pred['home_pts_pg'] = h_row['pts_pg']
            pred['away_pts_pg'] = a_row['pts_pg']
            pred['pace_ratio'] = (h_row['pts_pg'] + a_row['pts_pg']) / 147.4
            pred['pace_diff'] = h_row['pts_pg'] - a_row['pts_pg']
            pred['stats_source'] = '2024'
        else:
            pred['home_pts_pg'] = 74.4
            pred['away_pts_pg'] = 74.4
            pred['pace_ratio'] = 1.0
            pred['pace_diff'] = 0.0
            pred['stats_source'] = 'avg'

    # Simple log5-style prediction
    home_win_prob = 0.5 + (pred['pace_diff'] / 147.4) * 0.15 + 0.059  # home advantage
    home_win_prob = max(0.3, min(0.75, home_win_prob))
    pred['home_f10_prob'] = round(home_win_prob * 100, 1)

    predictions.append(pred)

pred_df = pd.DataFrame(predictions)

# Save
pred_df.to_csv(PROCESSED_DIR / 'first_to_10_2026.csv', index=False)

# Print summary
completed = pred_df[pred_df['status'] == 'STATUS_FINAL']
pending = pred_df[pred_df['status'] == 'STATUS_SCHEDULED']
in_progress = pred_df[~pred_df['status'].isin(['STATUS_FINAL', 'STATUS_SCHEDULED'])]

print(f"\n=== RESULTS ===")
print(f"Completed games: {len(completed)}")
if len(completed) > 0:
    home_f10 = completed[completed['actual_f10'] == 'home']
    print(f"Home won F10: {len(home_f10)}/{len(completed)} = {len(home_f10)/len(completed)*100:.1f}%")

print(f"\n=== PENDING GAMES ({len(pending)}) ===")
for _, r in pending.sort_values('date').iterrows():
    print(f"  {r['date']} | {r['home_team']} vs {r['away_team']} | P(home)={r['home_f10_prob']}% [{r['stats_source']}]")

print(f"\n=== IN PROGRESS ({len(in_progress)}) ===")
for _, r in in_progress.iterrows():
    actual = f" | ACTUAL: {r['actual_f10'].upper()}" if r['actual_f10'] else ""
    print(f"  {r['date']} | {r['home_team']} {r['home_score']}-{r['away_score']} {r['away_team']} [{r['status']}]{actual}")

print(f"\nSaved to {str(PROCESSED_DIR / 'first_to_10_2026.csv')}")
