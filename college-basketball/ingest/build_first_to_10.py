"""
Build first-to-10 model for 2026 CBB tournament.
1. Extract actual first-to-10 outcomes from completed games
2. Predict for scheduled round 1 games using regular season stats
"""
import json
import pandas as pd
import numpy as np
import pickle
from concurrent.futures import ThreadPoolExecutor
import sportsdataverse as sdv
import time

# ─── Load 2024 model for team stats ───────────────────────────────────────────
with open('/home/workspace/cbb-pbp/first_to_10_model.pkl', 'rb') as f:
    model_artifacts = pickle.load(f)

team_pts_2024 = model_artifacts['team_pts']  # team_name -> avg pts

# ─── Load 2026 tournament data ────────────────────────────────────────────────
with open('/home/workspace/cbb-2026/source/tournament_pbp_2026_raw.json') as f:
    all_games = json.load(f)

sched_df = pd.read_csv('/home/workspace/cbb-2026/source/tournament_schedule_2026.csv')
sched_df['game_date'] = pd.to_datetime(sched_df['date']).dt.strftime('%Y-%m-%d')

# ─── Extract first-to-10 from completed games ───────────────────────────────────
def first_to_10_from_plays(plays):
    if not plays:
        return None
    prev_away = prev_home = 0
    for p in plays:
        away = p.get('awayScore', 0)
        home = p.get('homeScore', 0)
        if away >= 10 and prev_away < 10:
            return 'away'
        if home >= 10 and prev_home < 10:
            return 'home'
        prev_away, prev_home = away, home
    return None

def get_game_info(header):
    comps = header.get('competitions', [{}])[0] if header.get('competitions') else {}
    teams = comps.get('competitors', [])
    date = comps.get('date', '')[:10]
    status = comps.get('status', {}).get('type', {}).get('name', 'unknown')
    home_team = away_team = None
    home_score = away_score = 0
    for t in teams:
        name = t['team'].get('nickname', t['team'].get('abbreviation', '?'))
        if t.get('homeAway') == 'home':
            home_team = name
            home_score = t.get('score', {}).get('value', 0)
        else:
            away_team = name
            away_score = t.get('score', {}).get('value', 0)
    return date, status, home_team, away_team, home_score, away_score

# ─── Extract from PBP ───────────────────────────────────────────────────────────
f10_results = []
for gid, game in all_games.items():
    plays = game.get('plays', [])
    header = game.get('header', {})
    date, status, home, away, home_score, away_score = get_game_info(header)
    winner = first_to_10_from_plays(plays)
    f10_results.append({
        'game_id': gid,
        'date': date,
        'status': status,
        'home_team': home,
        'away_team': away,
        'home_score': home_score,
        'away_score': away_score,
        'first_to_10': winner,
        'n_plays': len(plays)
    })

rdf = pd.DataFrame(f10_results)
rdf['date'] = pd.to_datetime(rdf['date'], errors='coerce')
rdf = rdb.sort_values('date').reset_index(drop=True)

# ─── Completed games first-to-10 ──────────────────────────────────────────────
completed = rdb[rdb['status'].isin(['STATUS_FINAL', 'STATUS_IN_PROGRESS']) & rdb['first_to_10'].notna()]
scheduled = rdb[rdb['status'] == 'STATUS_SCHEDULED']

print("=" * 65)
print("2026 NCAA TOURNAMENT — FIRST TO 10 RESULTS")
print("=" * 65)
print(f"\nCompleted games: {len(completed)}")
print(rdb[~rdb['first_to_10'].isna()][['date', 'home_team', 'away_team', 'first_to_10', 'home_score', 'away_score']].to_string(index=False))

home_f10 = (completed['first_to_10'] == 'home').sum()
print(f"\nHome first-to-10 rate: {home_f10}/{len(completed)} = {home_f10/len(completed)*100:.1f}%")
print(f"Baseline (2024 model): 59.1%")

# ─── Build features for scheduled games ───────────────────────────────────────
print(f"\nScheduled round 1 games to predict: {len(scheduled)}")

# Map 2026 team names to 2024 model names
# The 2026 schedule uses nicknames like "Blue Devils" for Duke
# The 2024 model uses "Duke" as team_name

# Manual name mapping
name_map = {
    'Blue Devils': 'Duke',
    'Huskies': 'UConn',
    'Wolverines': 'Michigan',
    'Spartans': 'Michigan State',
    'Buckeyes': 'Ohio State',
    'Wildcats': 'Kentucky',
    'Bulldogs': 'Gonzaga',
    'Cougars': 'Houston',
    'Tar Heels': 'North Carolina',
    'Jayhawks': 'Kansas',
    'Boilermakers': 'Purdue',
    'Volunteers': 'Tennessee',
    'Gators': 'Florida',
    'Razorbacks': 'Arkansas',
    'Longhorns': 'Texas',
    'Badgers': 'Wisconsin',
    'Red Raiders': 'Texas Tech',
    'Bruins': 'UCLA',
    'Aggies': 'Texas A&M',
    'Cyclones': 'Iowa State',
    'Tigers': 'Auburn',
    'Cavaliers': 'Virginia',
    'Cardinals': 'Louisville',
    'Warriors': 'Maine',
    'Paladins': 'Furman',
    'Bison': 'North Dakota State',
    'Panthers': 'Iowa',
    'Cornhuskers': 'Nebraska',
    'Rainbow Warriors': 'Hawaii',
    'Commodores': 'Vanderbilt',
    ' Rams': 'Colorado State',
    'Owls': 'Temple',
    'Horned Frogs': 'TCU',
    'Billikens': "Saint Louis",
    'Lancers': 'Loyola Chicago',
    'Zips': 'Akron',
    'RedHawks': 'Miami (OH)',
    'Broncos': 'Santa Clara',
    'Red Storm': "St John's",
    'Knights': 'UCF',
    'Hawkeyes': 'Iowa',
    'Hurricanes': 'Miami',
    'Sharks': 'Saint Joseph\'s',
    'Seahawks': 'Wagner',
    'Flyers': 'Dayton',
    'Wolf Pack': 'Nevada',
    'Flames': 'Liberty',
    'Demon Deacons': 'Wake Forest',
    'Redbirds': 'Illinois State',
    'Revolutionaries': 'William & Mary',
    'Lobos': 'New Mexico',
    'Shockers': 'Wichita State',
    'Golden Bears': 'California',
    'Hawks': 'Monmouth',
    'Bears': 'Bryant',
    'Mocs': 'Chattanooga',
    'Jackals': 'McNeese',
    'Gaels': 'Saint Mary\'s',
    'Terriers': 'Boston University',
    'Pirates': 'High Point',
    'Tritons': 'UC San Diego',
    'Vandals': 'Idaho',
    'Fighting Illini': 'Illinois',
    'Crimson Tide': 'Alabama',
    'Pride': 'Northeast',
    'Raiders': 'Colgate',
    'Redbirds': 'Belmont',
    'Golden Hurricane': 'Tulsa',
    'Rebels': 'UNLV',
}

# For teams not in the 2024 data, use league average
league_avg_pts = team_pts_2024['avg_pts'].mean()
print(f"\nLeague avg pts (2024): {league_avg_pts:.1f}")

def get_team_pts_2026(team_name):
    mapped = name_map.get(team_name, team_name)
    if mapped in team_pts_2024['team_name'].values:
        return team_pts_2024[team_pts_2024['team_name'] == mapped]['avg_pts'].values[0]
    return league_avg_pts

# Build prediction features
pred_rows = []
for _, row in scheduled.iterrows():
    home = row['home_team']
    away = row['away_team']
    
    if pd.isna(home) or pd.isna(away) or home == 'TBD' or away == 'TBD':
        continue
    
    home_pts = get_team_pts_2026(home)
    away_pts = get_team_pts_2026(away)
    
    pace_ratio = (home_pts + away_pts) / 2 / 70.0  # 70 is approx league avg pace
    pace_diff = home_pts - away_pts
    
    pred_rows.append({
        'game_id': row['game_id'],
        'date': row['date'],
        'home_team': home,
        'away_team': away,
        'home_pts_pg': home_pts,
        'away_pts_pg': away_pts,
        'pace_ratio': pace_ratio,
        'pace_diff': pace_diff,
    })

pred_df = pd.DataFrame(pred_rows)
print(f"\nScheduled games with predictions: {len(pred_df)}")

if len(pred_df) > 0:
    X_pred = pred_df[['pace_ratio', 'pace_diff', 'home_pts_pg', 'away_pts_pg']]
    probs = model_artifacts['model'].predict_proba(X_pred)[:, 1]
    pred_df['prob_home_first10'] = probs
    pred_df['prob_pct'] = (probs * 100).round(1)
    
    print("\nScheduled games + predictions:")
    print(pred_df[['date', 'home_team', 'away_team', 'home_pts_pg', 'away_pts_pg', 'prob_pct']].to_string(index=False))

# ─── Save results ──────────────────────────────────────────────────────────────
rdf.to_csv('/home/workspace/cbb-2026/first_to_10_results.csv', index=False)
pred_df.to_csv('/home/workspace/cbb-2026/first_to_10_predictions.csv', index=False)
print(f"\nResults saved.")
