"""
Scrape ESPN CBB 2025-2026 season PBP data using sportsdataverse.
Usage: python scrape_pbp.py [season_year] [--max-date YYYYMMDD]
"""
import sportsdataverse as sdv
import pandas as pd
import json
import time
import os
import sys
from datetime import datetime

SEASON = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
MAX_DATE = sys.argv[2] if len(sys.argv) > 2 else None

OUT_DIR = f"/home/workspace/cbb-2026/source/pbp_raw_{SEASON}"
os.makedirs(OUT_DIR, exist_ok=True)

print(f"[1] Fetching calendar for {SEASON}...")
cal = sdv.mbb.espn_mbb_calendar(SEASON, ondays=True, return_as_pandas=True)
cal['date_only'] = pd.to_datetime(cal['dates']).dt.strftime('%Y%m%d')
if MAX_DATE:
    cal = cal[cal['date_only'] <= MAX_DATE]
print(f"    Dates to scrape: {len(cal)}")

print(f"[2] Scraping schedules per date...")
all_games = []
for i, row in cal.iterrows():
    date_str = row['dateURL'].replace('-', '')
    try:
        sched = sdv.mbb.espn_mbb_schedule(dates=date_str, return_as_pandas=True)
        if sched is not None and len(sched) > 0:
            sched['query_date'] = date_str
            all_games.append(sched)
    except Exception as e:
        print(f"    ERROR on {date_str}: {e}")
    if (i + 1) % 30 == 0:
        print(f"    Progress: {i+1}/{len(cal)} dates")
        time.sleep(0.5)

if all_games:
    sched_df = pd.concat(all_games, ignore_index=True)
    sched_df = sched_df[sched_df['season_type'].isin([2, 3])]  # regular + tournament
    sched_df = sched_df.drop_duplicates(subset=['game_id'])
    sched_df.to_csv(f"{OUT_DIR}/schedule.csv", index=False)
    print(f"    Total games found: {len(sched_df)}")
    print(f"    By type: {sched_df['season_type'].value_counts().to_dict()}")
else:
    print("No games found!")
    sys.exit(1)

# Get game IDs to scrape (prefer completed games, those with PBP available)
game_ids = sched_df[sched_df['play_by_play_available'] == True]['game_id'].tolist()
completed = sched_df[sched_df['status_type_completed'] == True]['game_id'].tolist()
pending = sched_df[sched_df['status_type_completed'] == False]['game_id'].tolist()
print(f"[3] Games with PBP available: {len(game_ids)}")
print(f"    Completed: {len(completed)}, In-progress/Scheduled: {len(pending)}")

# Scrape PBP for each game
print(f"[4] Scraping PBP for {len(game_ids)} games...")
plays_list = []
errors = []
for i, gid in enumerate(game_ids):
    out_file = f"{OUT_DIR}/pbp_{gid}.json"
    if os.path.exists(out_file):
        # Load cached
        with open(out_file) as f:
            plays = json.load(f)
    else:
        try:
            result = sdv.mbb.espn_mbb_pbp(game_id=int(gid), raw=True)
            plays = result.get('plays', [])
            # Cache
            with open(out_file, 'w') as f:
                json.dump(plays, f)
        except Exception as e:
            errors.append((gid, str(e)))
            plays = []
        time.sleep(0.1)  # be nice to ESPN

    for p in plays:
        p['game_id'] = gid
        plays_list.append(p)

    if (i + 1) % 200 == 0:
        print(f"    Scraped {i+1}/{len(game_ids)} games...")

print(f"    Done! Total plays: {len(plays_list)}, Errors: {len(errors)}")
if errors:
    print(f"    First 5 errors: {errors[:5]}")

# Save raw plays
plays_df = pd.DataFrame(plays_list)
plays_df.to_csv(f"{OUT_DIR}/pbp_raw.csv", index=False)
print(f"    Saved to {OUT_DIR}/pbp_raw.csv")

# Save schedule
sched_df.to_csv(f"{OUT_DIR}/schedule.csv", index=False)
print(f"[5] Schedule saved: {len(sched_df)} games")
print(f"Done! Season {SEASON} scrape complete.")
