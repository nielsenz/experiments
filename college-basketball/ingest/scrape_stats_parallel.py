"""
Scrape 2025-2026 CBB PBP for team stats - fast parallel approach.
"""
import sportsdataverse as sdv
import json, os, time, pickle
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import numpy as np
import requests

SEASON = 2026
OUT_DIR = '/home/workspace/cbb-2026/source'
os.makedirs(OUT_DIR, exist_ok=True)

def scrape_game(gid):
    """Fetch PBP for one game. Returns (gid, data) or (gid, None) on failure."""
    try:
        raw = sdv.mbb.espn_mbb_pbp(int(gid), raw=True)
        if raw and raw.get('plays'):
            return (str(gid), raw)
    except Exception:
        pass
    return (str(gid), None)

# Step 1: Get all regular season game IDs
print("Fetching full season schedule...")
schedule = sdv.mbb.espn_mbb_schedule(SEASON, return_as_pandas=True)
reg = schedule[schedule['season_type'] == 2].copy()
print(f"Total regular season games: {len(reg)}")
print(f"Date range: {reg['date'].min()} → {reg['date'].max()}")

# Step 2: Batch scrape PBP with high concurrency
game_ids = reg['id'].astype(str).tolist()
print(f"Scraping {len(game_ids)} games...")

done_file = f'{OUT_DIR}/season_pbp_2026_raw.json'
existing = set()
if os.path.exists(done_file):
    with open(done_file) as f:
        existing = set(json.load(f).keys())
    print(f"Already have {len(existing)} games, need {len(game_ids)-len(existing)} more")

to_fetch = [g for g in game_ids if g not in existing]
print(f"Fetching {len(to_fetch)} new games with concurrency=30...")

start = time.time()
results = {}
batch_size = 200

for i in range(0, len(to_fetch), batch_size):
    batch = to_fetch[i:i+batch_size]
    with ThreadPoolExecutor(max_workers=30) as ex:
        futures = {ex.submit(scrape_game, gid): gid for gid in batch}
        done = 0
        for fut in as_completed(futures):
            gid, data = fut.result()
            if data:
                results[gid] = data
            done += 1
    elapsed = time.time() - start
    rate = (i + len(batch)) / elapsed if elapsed > 0 else 0
    remaining = len(to_fetch) - i - len(batch)
    eta = remaining / rate if rate > 0 else 0
    print(f"  Batch {i//batch_size+1}: {done}/{len(batch)} done, {len(results)} total, {elapsed:.0f}s elapsed, ETA {eta:.0f}s")

# Merge with existing
all_data = {}
if existing:
    with open(done_file) as f:
        all_data = json.load(f)
all_data.update(results)

with open(done_file, 'w') as f:
    json.dump(all_data, f)

print(f"\nTotal games scraped: {len(all_data)} in {time.time()-start:.0f}s")

# Step 3: Compute team stats from PBP
print("\nComputing team stats from PBP...")
from collections import defaultdict

team_scores = defaultdict(list)
team_ opponents = defaultdict(list)

for gid, game in all_data.items():
    plays = game.get('plays', [])
    if not plays: continue

    # Get team IDs from boxscore
    teams = {}
    box = game.get('boxscore', {})
    for t in box.get('teams', []):
        tid = t.get('team', {}).get('id')
        if tid:
            teams[tid] = t.get('homeAway')

    # Collect scoring plays
    for play in plays:
        if not play.get('scoringPlay'): continue
        away = play.get('awayScore', 0) or 0
        home = play.get('homeScore', 0) or 0
        if away == 0 and home == 0: continue  # Skip game-start state

        for t in play.get('participants', []):
            tid = t.get('athlete', {}).get('id') or ''
            if tid in teams:
                # This team scored - use cumulative score at this play
                pts = play.get('scoreValue', 0) or 0
                if pts > 0:
                    # Final score for this team in this game
                    pass

    # Actually just use boxscore final scores
    for t in box.get('teams', []):
        tid = t.get('team', {}).get('id')
        stats = t.get('statistics', [])
        pts = 0
        for s in stats:
            if s.get('name') == 'points':
                try: pts = int(s.get('displayValue', 0))
                except: pass
        if pts > 0:
            team_scores[tid].append(pts)

print("Top scorers (avg PPG):")
team_avg = [(tid, np.mean(sc), len(sc)) for tid, sc in team_scores.items() if len(sc) >= 5]
for tid, avg, n in sorted(team_avg, key=lambda x: -x[1])[:10]:
    print(f"  {tid}: {avg:.1f} PPG ({n} games)")

print(f"\nTeams with 5+ games: {len(team_avg)}")
