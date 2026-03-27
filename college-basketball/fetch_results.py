"""
Fetch Sweet 16 final scores from ESPN API and update result tracking CSVs.

Run after games complete to fill in:
  - betting_lines_sweet16.csv  (F10 bet results)
  - sweet16_totals_spread_lines.csv  (totals/spread tracking)
"""
import json, requests
import pandas as pd
from pathlib import Path

from config import PROCESSED_DIR, TOURNAMENT_PBP

DATES = ['20260326', '20260327', '20260328']

def fetch_scores(date):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates={date}&groups=100"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    results = {}
    for e in r.json().get('events', []):
        status = e['status']['type']['name']
        if status != 'STATUS_FINAL':
            continue
        comp = e['competitions'][0]
        teams = comp['competitors']
        scores = {t['homeAway']: (t['team']['shortDisplayName'], int(t.get('score', 0))) for t in teams}
        h_name, h_score = scores.get('home', ('?', 0))
        a_name, a_score = scores.get('away', ('?', 0))
        results[e['id']] = {
            'home_team': h_name, 'away_team': a_name,
            'home_score': h_score, 'away_score': a_score,
            'total': h_score + a_score,
            'spread': h_score - a_score,
            'status': status,
        }
    return results

# Fetch all dates
all_results = {}
for d in DATES:
    all_results.update(fetch_scores(d))

if not all_results:
    print("No final games found yet.")
    exit()

print(f"Found {len(all_results)} completed games\n")
for gid, r in all_results.items():
    print(f"  {r['home_team']:20} {r['home_score']:3} - {r['away_score']:<3} {r['away_team']:20}  total={r['total']}  margin={r['spread']:+d}")

# ── Update sweet16_totals_spread_lines.csv ─────────────────────────────────────
totals_path = PROCESSED_DIR / 'sweet16_totals_spread_lines.csv'
if totals_path.exists():
    df = pd.read_csv(totals_path)
    updated = 0
    for gid, r in all_results.items():
        mask = (df['home_team'].str.contains(r['home_team'], case=False, na=False) |
                df['away_team'].str.contains(r['home_team'], case=False, na=False))
        if mask.sum() == 1:
            idx = df[mask].index[0]
            df.at[idx, 'actual_total'] = r['total']
            df.at[idx, 'actual_home_score'] = r['home_score']
            df.at[idx, 'actual_away_score'] = r['away_score']
            df.at[idx, 'actual_spread'] = r['spread']
            updated += 1
    df.to_csv(totals_path, index=False)
    print(f"\nUpdated {updated} rows in {totals_path.name}")

# ── Update betting_lines_sweet16.csv ──────────────────────────────────────────
f10_path = PROCESSED_DIR / 'betting_lines_sweet16.csv'
if f10_path.exists():
    # For F10 we need PBP — fetch game summaries to get first-to-10
    def get_first_to_10(game_id):
        url = f"https://site.web.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={game_id}"
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            plays = data.get('plays', data.get('playByPlay', {}).get('plays', []))
            scored = [p for p in plays if p.get('scoringPlay')]
            for p in scored:
                away = p.get('awayScore', 0)
                home = p.get('homeScore', 0)
                pts = p.get('scoreValue', 0)
                if away >= 10 and (away - pts) < 10:
                    return 'away'
                if home >= 10 and (home - pts) < 10:
                    return 'home'
        except Exception as e:
            print(f"  F10 fetch failed for {game_id}: {e}")
        return None

    df_f10 = pd.read_csv(f10_path)
    print(f"\nF10 bet tracking — {f10_path.name}:")
    print("(Fill in actual_f10_winner manually or run with game IDs once PBP available)")
    print(df_f10[['game_date', 'bet_team', 'opponent', 'stake', 'model_prob', 'edge']].to_string(index=False))
