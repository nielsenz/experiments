"""
Build per-team early-scoring tempo stats from season PBP.

Output: data/processed/team_tempo_2026.csv
Columns:
  team_id, team_name, n_games,
  median_p10,           # overall median plays to reach 10 pts
  median_p5,            # overall median plays to reach 5 pts
  std_p10,              # consistency (lower = more predictable starter)
  home_p10,             # median plays to 10 in home games
  away_p10,             # median plays to 10 in away games
  neutral_p10,          # (home_p10 + away_p10) / 2 — best estimate for neutral site
  f10_win_rate          # fraction of games where this team won F10
"""
import json, csv, sys
from pathlib import Path
from collections import defaultdict
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SEASON_PBP, TEAM_STATS, PROCESSED_DIR

print("Loading PBP data...")
with open(SEASON_PBP) as f:
    all_games = json.load(f)
print(f"Loaded {len(all_games):,} games")

# Load team name lookup
team_names = {}
with open(TEAM_STATS) as f:
    for row in csv.DictReader(f):
        team_names[str(row['team_id'])] = row['team_name']

# Per-team records: list of dicts
team_records = defaultdict(list)  # tid → [{plays_to_5, plays_to_10, is_home, won_f10}]

skip = 0
for gid, game in all_games.items():
    plays = game.get('plays', [])
    if not plays:
        skip += 1
        continue

    box_teams = game.get('boxscore', {}).get('teams', [])
    if len(box_teams) != 2:
        skip += 1
        continue

    home_id = away_id = None
    for t in box_teams:
        tid = str(t.get('team', {}).get('id', ''))
        if t.get('homeAway') == 'home':
            home_id = tid
        elif t.get('homeAway') == 'away':
            away_id = tid
    if not home_id or not away_id:
        skip += 1
        continue

    # Walk scoring plays, track milestones
    home_milestones = {}
    away_milestones = {}
    home_score = away_score = 0
    f10_winner = None

    for i, play in enumerate(plays):
        if not play.get('scoringPlay'):
            continue
        prev_h, prev_a = home_score, away_score
        home_score = play.get('homeScore', home_score)
        away_score = play.get('awayScore', away_score)
        play_num = i + 1

        for milestone in [5, 10]:
            if prev_h < milestone <= home_score and milestone not in home_milestones:
                home_milestones[milestone] = play_num
            if prev_a < milestone <= away_score and milestone not in away_milestones:
                away_milestones[milestone] = play_num

        if f10_winner is None:
            pts = play.get('scoreValue', 0)
            if away_score >= 10 and (away_score - pts) < 10:
                f10_winner = 'away'
            elif home_score >= 10 and (home_score - pts) < 10:
                f10_winner = 'home'

    if f10_winner is None or 10 not in home_milestones or 10 not in away_milestones:
        skip += 1
        continue

    team_records[home_id].append({
        'plays_to_5':  home_milestones.get(5, home_milestones[10]),
        'plays_to_10': home_milestones[10],
        'is_home': True,
        'won_f10': f10_winner == 'home',
    })
    team_records[away_id].append({
        'plays_to_5':  away_milestones.get(5, away_milestones[10]),
        'plays_to_10': away_milestones[10],
        'is_home': False,
        'won_f10': f10_winner == 'away',
    })

print(f"Processed {len(all_games) - skip:,} games, {skip} skipped")

# Compute per-team stats
LEAGUE_P10 = np.median([r['plays_to_10'] for records in team_records.values() for r in records])

rows = []
for tid, records in team_records.items():
    if len(records) < 5:
        continue

    p10_all  = [r['plays_to_10'] for r in records]
    p5_all   = [r['plays_to_5']  for r in records]
    home_p10 = [r['plays_to_10'] for r in records if r['is_home']]
    away_p10 = [r['plays_to_10'] for r in records if not r['is_home']]

    med_home = np.median(home_p10) if home_p10 else None
    med_away = np.median(away_p10) if away_p10 else None

    # Neutral estimate: average of home and away; fall back to overall median
    if med_home is not None and med_away is not None:
        neutral_p10 = (med_home + med_away) / 2
    else:
        neutral_p10 = np.median(p10_all)

    rows.append({
        'team_id':      tid,
        'team_name':    team_names.get(tid, tid),
        'n_games':      len(records),
        'median_p10':   round(np.median(p10_all), 2),
        'median_p5':    round(np.median(p5_all), 2),
        'std_p10':      round(np.std(p10_all), 2),
        'home_p10':     round(med_home, 2) if med_home is not None else '',
        'away_p10':     round(med_away, 2) if med_away is not None else '',
        'neutral_p10':  round(neutral_p10, 2),
        'f10_win_rate': round(np.mean([r['won_f10'] for r in records]), 4),
    })

rows.sort(key=lambda r: float(r['neutral_p10']))

# Write CSV
out = PROCESSED_DIR / 'team_tempo_2026.csv'
with open(out, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {len(rows)} teams → {out}")
print(f"League median plays-to-10: {LEAGUE_P10:.1f}")
print(f"\nFastest 5 starters (neutral_p10):")
for r in rows[:5]:
    print(f"  {r['team_name']:<22} {r['neutral_p10']:5.1f}  (home={r['home_p10']}, away={r['away_p10']})")
print(f"\nSlowest 5 starters:")
for r in rows[-5:]:
    print(f"  {r['team_name']:<22} {r['neutral_p10']:5.1f}  (home={r['home_p10']}, away={r['away_p10']})")
