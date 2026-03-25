"""
Extract first-to-10 outcomes from completed tournament games.
"""
import json
import pandas as pd

with open('/home/workspace/cbb-2026/source/tournament_pbp_2026_raw.json') as f:
    all_data = json.load(f)

def extract_first_to_10(game_data):
    """Find which team reached 10 first."""
    plays = game_data.get('plays', [])
    if not plays:
        return None
    
    for play in plays:
        away = play.get('awayScore', 0)
        home = play.get('homeScore', 0)
        if away >= 10 or home >= 10:
            if away >= 10 and home < 10:
                return 'away'
            elif home >= 10 and away < 10:
                return 'home'
            elif away >= 10 and home >= 10:
                # Both reached at same time - check who crossed 10 first
                prev_away = play.get('awayScore', 0) - play.get('scoreValue', 0) if play.get('scoreValue', 0) > 0 else 0
                prev_home = play.get('homeScore', 0) - play.get('scoreValue', 0) if play.get('scoreValue', 0) > 0 else 0
                # Actually need LAG - check previous play's scores
                return None  # Can't determine without LAG
    return None

# Check one completed game manually
gid = '401856523'
if gid in all_data:
    game = all_data[gid]
    plays = game.get('plays', [])
    print(f"Game {gid} - {len(plays)} plays")
    if plays:
        # Find first 10
        for i, play in enumerate(plays[:50]):
            away = play.get('awayScore', 0)
            home = play.get('homeScore', 0)
            if away >= 10 or home >= 10:
                print(f"First to reach 10: away={away}, home={home} at play {i}")
                print(f"Play text: {play.get('text', '')}")
                print(f"Score value: {play.get('scoreValue', 0)}")
                break
