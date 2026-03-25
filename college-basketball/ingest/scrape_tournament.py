"""
Scrape 2025-2026 CBB tournament PBP - focused fast scraper.
"""
import sportsdataverse as sdv
import pandas as pd
import json
import time
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

OUT_DIR = "/home/workspace/cbb-2026/source"
os.makedirs(OUT_DIR, exist_ok=True)

# NCAA tournament dates 2026
TOURNAMENT_DATES = [
    "20260319", "20260320", "20260321",  # First Four + Round 1
    "20260322", "20260323", "20260324",  # Round 2
    "20260326", "20260327", "20260328",  # Sweet 16
    "20260329", "20260330", "20260331",  # Elite 8
]

LOCK = threading.Lock()

def scrape_date(date_str):
    """Scrape all games for a given date."""
    print(f"  Fetching schedule for {date_str}...")
    try:
        sched = sdv.mbb.espn_mbb_schedule(dates=date_str, return_as_pandas=True)
        if sched is None or sched.empty:
            return date_str, []
        
        # Filter to tournament games
        sched = sched[sched['type_abbreviation'] == 'TRNMNT']
        game_ids = sched['id'].tolist()
        print(f"  {date_str}: {len(game_ids)} tournament games")
        return date_str, game_ids
    except Exception as e:
        print(f"  Error fetching {date_str}: {e}")
        return date_str, []

def scrape_game_pbp(game_id):
    """Scrape PBP for a single game."""
    try:
        result = sdv.mbb.espn_mbb_pbp(game_id=game_id, raw=True)
        return game_id, result
    except Exception as e:
        return game_id, None

def main():
    print("=" * 60)
    print("CBB 2026 TOURNAMENT SCRAPER")
    print("=" * 60)
    
    # Step 1: Get all tournament game IDs
    print("\n[1] Finding tournament games...")
    all_game_ids = []
    
    for date_str in TOURNAMENT_DATES:
        _, gids = scrape_date(date_str)
        all_game_ids.extend(gids)
    
    all_game_ids = list(set(all_game_ids))
    print(f"\nTotal tournament games found: {len(all_game_ids)}")
    
    if not all_game_ids:
        print("No games found!")
        return
    
    # Step 2: Scrape PBP in parallel
    print(f"\n[2] Scraping PBP for {len(all_game_ids)} games...")
    games_data = {}
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(scrape_game_pbp, gid): gid for gid in all_game_ids}
        done = 0
        for future in as_completed(futures):
            gid, data = future.result()
            if data:
                games_data[gid] = data
                with LOCK:
                    done += 1
                    if done % 10 == 0:
                        print(f"  Progress: {done}/{len(all_game_ids)} games")
    
    print(f"\nSuccessfully scraped: {len(games_data)}/{len(all_game_ids)} games")
    
    # Step 3: Save raw JSON
    out_file = f"{OUT_DIR}/tournament_pbp_2026_raw.json"
    with open(out_file, 'w') as f:
        json.dump(games_data, f)
    print(f"\nSaved raw PBP to {out_file}")
    
    # Step 4: Save game metadata (schedule)
    print("\n[3] Saving schedule metadata...")
    sched_rows = []
    for date_str in TOURNAMENT_DATES:
        try:
            sched = sdv.mbb.espn_mbb_schedule(dates=date_str, return_as_pandas=True)
            if sched is not None and not sched.empty:
                sched = sched[sched['type_abbreviation'] == 'TRNMNT']
                sched_rows.append(sched)
        except:
            pass
    
    if sched_rows:
        sched_df = pd.concat(sched_rows, ignore_index=True)
        sched_df.to_csv(f"{OUT_DIR}/tournament_schedule_2026.csv", index=False)
        print(f"Saved {len(sched_df)} schedule rows")
    
    print("\n[DONE] Tournament scrape complete!")
    return games_data

if __name__ == "__main__":
    main()
