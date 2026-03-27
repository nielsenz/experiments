"""
Get full season game IDs - November through March.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SOURCE_DIR

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

OUT = SOURCE_DIR / 'all_game_ids.txt'

session = requests.Session()
session.mount('https://', HTTPAdapter(max_retries=3))
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

MONTHS = [
    ('202511', '2025-11'),
    ('202512', '2025-12'),
    ('202601', '2026-01'),
    ('202602', '2026-02'),
    ('202603', '2026-03'),
]

all_ids = set()
for ym, label in MONTHS:
    url = f'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates={ym}&groups=40&limit=300'
    r = session.get(url, headers=UA, timeout=30)
    if r.status_code == 200:
        data = r.json()
        gids = [e['id'] for e in data.get('events', [])]
        print(f"{label}: {len(gids)} game IDs")
        all_ids.update(gids)
    else:
        print(f"{label}: FAILED {r.status_code}")
    time.sleep(0.3)

# Remove any that are clearly future/in-season only
valid_ids = [gid for gid in all_ids if gid.isdigit() and len(gid) == 9 and gid.startswith('401')]
valid_ids.sort()

with open(OUT, 'w') as f:
    for gid in valid_ids:
        f.write(gid + '\n')

print(f"\nTotal unique game IDs: {len(valid_ids)}")
print(f"Saved to: {OUT}")
