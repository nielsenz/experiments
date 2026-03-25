"""
Fast CBB 2025-2026 PBP scraper using direct ESPN API.
Uses session pooling for speed.
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

SEASON = 2026
OUT_DIR = '/home/workspace/cbb-2026/source'
os.makedirs(OUT_DIR, exist_ok=True)

# Thread-safe session factory
session_lock = threading.Lock()
_sessions = []

def get_session():
    with session_lock:
        if len(_sessions) < 50:
            s = requests.Session()
            adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20,
                                  max_retries=Retry(total=2, backoff_factor=0.1))
            s.mount('https://', adapter)
            _sessions.append(s)
        return _sessions[0]

def api(url, params=None, max_retries=2):
    for attempt in range(max_retries):
        try:
            s = get_session()
            r = s.get(url, params=params, timeout=10)
            if r.status_code == 200:
                return r.json()
            # 404/403 means no data - return None
            if r.status_code in (404, 403):
                return None
        except Exception:
            if attempt == max_retries - 1:
                return None
            time.sleep(0.5 * (attempt + 1))
    return None

def fetch_pbp(game_id):
    """Fetch PBP for one game."""
    data = api(
        'https://site.web.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary',
        params={'event': game_id}
    )
    return (str(game_id), data)

def fetch_schedule_page(date_str):
    """Fetch all games for a date."""
    data = api(
        'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard',
        params={'dates': date_str, 'limit': 300}
    )
    return data

# ---- Step 1: Build full game ID list via calendar ----
print("Building game ID list...")
all_game_ids = set()

# Get calendar dates
cal_data = api('https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard',
               params={'dates': f'{SEASON}0101-{SEASON}1231', 'limit': 1})
if not cal_data:
    print("Calendar API failed, trying date range...")
    # Try monthly chunks
    for month in ['01','02','03','04','05','06','11','12']:
        for day_start in ['01','08','15','22']:
            date_str = f'{SEASON}{month}{day_start}'
            d = api('https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard',
                   params={'dates': date_str, 'limit': 300})
            if d and 'events' in d:
                for ev in d['events']:
                    all_game_ids.add(ev['id'])
    print(f"Games found so far: {len(all_game_ids)}")
else:
    print(f"Calendar: {cal_data.get('season', {})}")

# Also do Feb-March (peak conference play) more densely
print("Dense scan Feb-March...")
for month in ['02', '03']:
    days_in_month = 31
    for day in range(1, 32):
        date_str = f'{SEASON}{month}{day:02d}'
        d = api('https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard',
               params={'dates': date_str, 'limit': 300})
        if d and 'events' in d:
            for ev in d['events']:
                all_game_ids.add(ev['id'])
    print(f"  {month}/: {len(all_game_ids)} total")

# Deduplicate and save
all_game_ids = sorted(all_game_ids)
print(f"\nTotal unique game IDs: {len(all_game_ids)}")
print(f"Saving to {OUT_DIR}/game_ids_2026.txt")
with open(f'{OUT_DIR}/game_ids_2026.txt', 'w') as f:
    for gid in all_game_ids:
        f.write(f"{gid}\n")
print("Done - game IDs saved.")
