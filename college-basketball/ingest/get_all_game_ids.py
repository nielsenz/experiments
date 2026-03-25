"""
Get full season game IDs - all months.
"""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
import threading

OUT_DIR = '/home/workspace/cbb-2026/source'

session_lock = threading.Lock()
_sessions = []
def get_session():
    with session_lock:
        if len(_sessions) < 10:
            s = requests.Session()
            adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
            s.mount('https://', adapter)
            _sessions.append(s)
        return _sessions[0]

def fetch_games(date_str):
    try:
        s = get_session()
        r = s.get(
            'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard',
            params={'dates': date_str, 'limit': 300},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            if 'events' in data:
                return [ev['id'] for ev in data['events']]
    except:
        pass
    return []

all_ids = set()
# Scan Nov 2025 through March 2026
months = {
    '202511': list(range(1, 31)),
    '202512': list(range(1, 32)),
    '202601': list(range(1, 32)),
    '202602': list(range(1, 29)),
    '202603': list(range(1, 32)),
}

for month, days in months.items():
    for day in days:
        date_str = f'{month}{day:02d}'
        ids = fetch_games(date_str)
        all_ids.update(ids)
    print(f"{month}: {len(all_ids)} total game IDs")

print(f"\nGrand total: {len(all_ids)} unique game IDs")
with open(f'{OUT_DIR}/game_ids_2026.txt', 'w') as f:
    for gid in sorted(all_ids):
        f.write(f"{gid}\n")
