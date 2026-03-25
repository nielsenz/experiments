"""
Scrape 2025-2026 CBB regular season PBP for team stats - optimized.
1. Get schedule for all dates (parallel)
2. Filter to past/completed games only
3. Fetch PBP in parallel
4. Compute team PPG from scoring plays
"""
import sportsdataverse as sdv
import json
import pandas as pd
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

SEASON = 2026
OUTPUT_DIR = "/home/workspace/cbb-2026/source"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── Step 1: Get all game IDs (parallel schedule scan) ───────────
print("Getting calendar...")
cal = sdv.mbb.espn_mbb_calendar(SEASON, ondays=True, return_as_pandas=True)
all_dates = []
for d in cal['dates'].tolist():
    date_str = d[:10].replace('-', '')  # '2025-11-10T08:00Z' -> '20251110'
    all_dates.append(date_str)
print(f"Dates: {len(all_dates)}")

def get_ids(d):
    try:
        df = sdv.mbb.espn_mbb_schedule(dates=d, return_as_pandas=True)
        if df is None or df.empty:
            return []
        cols = df.columns.tolist()
        id_col = 'id' if 'id' in cols else None
        if id_col is None:
            return []
        ids = df[id_col].dropna().astype(str).tolist()
        # Only keep regular season games (season_type 2)
        if 'season_type' in cols:
            ids = [str(i) for i, st in zip(df['id'], df['season_type']) if st == 2]
        return ids
    except:
        return []

print("Scanning schedule (parallel, 16 workers)...")
t0 = time.time()
all_ids = set()
with ThreadPoolExecutor(max_workers=16) as ex:
    futures = {ex.submit(get_ids, d): d for d in all_dates}
    for fut in as_completed(futures):
        all_ids.update(fut.result())
        if len(all_ids) % 500 == 0:
            print(f"  {len(all_ids)} game IDs so far...")

game_ids = sorted(all_ids, key=int)
print(f"Total game IDs: {len(game_ids)} ({time.time()-t0:.0f}s)")

# ─── Step 2: Check what's already saved ─────────────────────────
cache_file = f"{OUTPUT_DIR}/season_pbp_2026_raw.json"
existing = {}
if os.path.exists(cache_file):
    try:
        with open(cache_file) as f:
            existing = json.load(f)
        print(f"Already cached: {len(existing)} games")
    except:
        existing = {}

to_scrape = [g for g in game_ids if g not in existing]
print(f"Need to scrape: {len(to_scrape)} games")

# ─── Step 3: Fetch PBP (parallel) ───────────────────────────────
if to_scrape:
    print(f"Fetching PBP ({len(to_scrape)} games, 24 workers)...")
    t1 = time.time()
    done = 0
    errors = 0
    checkpoint_interval = 500

    def fetch(gid):
        try:
            r = sdv.mbb.espn_mbb_pbp(game_id=int(gid), raw=True)
            return gid, r
        except:
            return gid, None

    with ThreadPoolExecutor(max_workers=24) as ex:
        futures = {ex.submit(fetch, g): g for g in to_scrape}
        for fut in as_completed(futures):
            gid, result = fut.result()
            if result and result.get('plays') and len(result['plays']) > 0:
                existing[gid] = result
                done += 1
            else:
                errors += 1
            if (done + errors) % checkpoint_interval == 0:
                elapsed = time.time() - t1
                rate = (done + errors) / elapsed
                eta = (len(to_scrape) - done - errors) / rate if rate > 0 else 0
                print(f"  {done+errors}/{len(to_scrape)} | {rate:.0f}/sec | ETA {eta:.0f}s")
                # Save checkpoint
                with open(cache_file, 'w') as f:
                    json.dump(existing, f)

    print(f"Done: {done} games, {errors} errors ({time.time()-t1:.0f}s)")
    with open(cache_file, 'w') as f:
        json.dump(existing, f)
    print("Saved.")

# ─── Step 4: Compute team stats from scoring plays ───────────────
print("Computing team stats...")

# Build plays index with team names
from collections import defaultdict

team_game = defaultdict(lambda: {'pts': [], 'poss': []})  # team -> {pts:[], poss:[]}

for gid, game in existing.items():
    plays = game.get('plays', [])
    if not plays:
        continue

    header = game.get('header', {})
    comps_list = header.get('competitions') or []
    if not comps_list:
        continue
    comps = comps_list[0]
    teams = comps.get('competitors') or []
    home_t = away_t = None
    for t in teams:
        if not isinstance(t, dict):
            continue
        ht = t.get('team', {})
        if t.get('homeAway') == 'home':
            home_t = ht.get('abbreviation') or ht.get('nickname') or 'HOME'
        elif t.get('homeAway') == 'away':
            away_t = ht.get('abbreviation') or ht.get('nickname') or 'AWAY'

    if not home_t or not away_t:
        continue

    game_home_pts = 0
    game_away_pts = 0
    game_home_poss = 0
    game_away_poss = 0

    for p in plays:
        if not isinstance(p, dict):
            continue
        if not p.get('scoringPlay'):
            continue
        t = p.get('team', {})
        if not isinstance(t, dict):
            continue
        tn = t.get('abbreviation') or t.get('nickname') or t.get('id', '?')
        pts = p.get('scoreValue', 0)

        if tn == home_t:
            game_home_pts += pts
            game_home_poss += 1
        elif tn == away_t:
            game_away_pts += pts
            game_away_poss += 1

    if game_home_pts > 0 or game_away_pts > 0:
        team_game[home_t]['pts'].append(game_home_pts)
        team_game[home_t]['poss'].append(game_home_poss)
        team_game[away_t]['pts'].append(game_away_pts)
        team_game[away_t]['poss'].append(game_away_poss)

rows = []
for team, data in team_game.items():
    if data['pts'] and len(data['pts']) >= 3:
        rows.append({
            'team_name': team,
            'games': len(data['pts']),
            'avg_pts': round(sum(data['pts']) / len(data['pts']), 1),
            'avg_poss': round(sum(data['poss']) / len(data['poss']), 1),
        })

team_stats = pd.DataFrame(rows).sort_values('team_name').reset_index(drop=True)
print(f"\nTeams: {len(team_stats)}")
print(team_stats.to_string(index=False))

team_stats.to_csv(f"{OUTPUT_DIR}/team_stats_2026.csv", index=False)
print(f"\nSaved team_stats_2026.csv")
