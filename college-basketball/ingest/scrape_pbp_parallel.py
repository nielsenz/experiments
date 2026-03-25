"""
Step 2: Parallel PBP fetch for collected game IDs.
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json, os, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

OUT_DIR = '/home/workspace/cbb-2026/source'
PBP_FILE = f'{OUT_DIR}/season_pbp_2026.json'

# Load game IDs
with open(f'{OUT_DIR}/game_ids_2026.txt') as f:
    game_ids = [l.strip() for l in f if l.strip()]
print(f"Loaded {len(game_ids)} game IDs")

# Thread-safe session
session_lock = threading.Lock()
_sessions = []
def get_session():
    with session_lock:
        if len(_sessions) < 30:
            s = requests.Session()
            adapter = HTTPAdapter(pool_connections=30, pool_maxsize=30,
                                  max_retries=Retry(total=2, backoff_factor=0.1))
            s.mount('https://', adapter)
            _sessions.append(s)
        return _sessions[0]

def fetch_pbp(gid):
    try:
        s = get_session()
        url = 'https://site.web.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary'
        r = s.get(url, params={'event': gid}, timeout=8)
        if r.status_code == 200:
            data = r.json()
            if data.get('plays'):
                return (gid, data)
    except Exception:
        pass
    return (gid, None)

# Parallel fetch
print(f"Fetching PBP for {len(game_ids)} games...")
start = time.time()
results = {}
done = 0
errors = 0

with ThreadPoolExecutor(max_workers=30) as executor:
    futures = {executor.submit(fetch_pbp, gid): gid for gid in game_ids}
    for fut in as_completed(futures):
        gid, data = fut.result()
        if data:
            results[gid] = data
            done += 1
        else:
            errors += 1
        if (done + errors) % 50 == 0:
            elapsed = time.time() - start
            rate = (done + errors) / elapsed
            print(f"  {done+errors}/{len(game_ids)} | {done} OK | {errors} err | {rate:.1f}/s")

elapsed = time.time() - start
print(f"\nDone: {done} games with PBP in {elapsed:.1f}s ({done/elapsed:.1f}/sec)")
print(f"Saving to {PBP_FILE}")
with open(PBP_FILE, 'w') as f:
    json.dump(results, f)
print(f"Saved {len(results)} games.")
