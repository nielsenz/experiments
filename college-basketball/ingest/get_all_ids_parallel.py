"""
Get ALL game IDs for 2025-2026 season - parallel date queries.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SOURCE_DIR

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

OUT = SOURCE_DIR / 'full_game_ids.txt'

session = requests.Session()
session.mount('https://', HTTPAdapter(max_retries=2))
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

# All days Nov 2025 - Mar 2026
days = []
for ym, label in [('202511','Nov'),('202512','Dec'),('202601','Jan'),('202602','Feb'),('202603','Mar')]:
    m = int(ym[4:6])
    y = int(ym[:4])
    import calendar
    last = calendar.monthrange(y, m)[1]
    for d in range(1, last+1):
        days.append(f'{ym}{d:02d}')

print(f"Querying {len(days)} days")

def fetch_day(dt):
    url = f'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates={dt}&limit=300'
    try:
        r = session.get(url, headers=UA, timeout=10)
        if r.status_code == 200:
            return [e['id'] for e in r.json().get('events', [])]
    except:
        pass
    return []

all_ids = set()
with ThreadPoolExecutor(max_workers=20) as ex:
    futures = {ex.submit(fetch_day, d): d for d in days}
    done = 0
    for fut in as_completed(futures):
        gids = fut.result()
        all_ids.update(gids)
        done += 1
        if done % 30 == 0:
            print(f"  {done}/{len(days)} days... {len(all_ids)} IDs so far")

valid = sorted([g for g in all_ids if g.isdigit() and len(g)==9 and g.startswith('401')])
with open(OUT,'w') as f:
    for g in valid: f.write(g+'\n')
print(f"\nTotal: {len(valid)} game IDs -> {OUT}")
