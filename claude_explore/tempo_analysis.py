"""
Early-Game Scoring Tempo Analysis

Hypothesis: Some teams score their first 10 points faster than their season PPG
suggests. If true, "fast-start" ratings should improve F10 predictions beyond
what PPG alone captures.

Approach:
  1. Load all 1,138 regular season PBP games
  2. For each game, measure how many plays it takes each team to reach 5 and 10 pts
  3. Build per-team "fast-start" ratings: median plays-to-10, variance, home vs away splits
  4. Check correlation with actual F10 win rate
  5. Compare a "tempo-augmented" model vs the base PPG model

This reveals whether the model is leaving signal on the table.
"""
import json, sys
from pathlib import Path
from collections import defaultdict
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

CBB = Path(__file__).parent.parent / "college-basketball"
PBP_PATH   = CBB / "data/raw/season_pbp_2026.json"
STATS_PATH = CBB / "data/processed/team_stats_2026.csv"

# ── Load data ──────────────────────────────────────────────────────────────────
console.print("[dim]Loading PBP data...[/dim]")
with open(PBP_PATH) as f:
    all_games = json.load(f)
console.print(f"[dim]Loaded {len(all_games):,} games[/dim]")

import csv
team_stats = {}
with open(STATS_PATH) as f:
    for row in csv.DictReader(f):
        team_stats[str(row['team_id'])] = {
            'name': row['team_name'],
            'ppg': float(row['avg_pts']),
            'opp_ppg': float(row['avg_opp_pts']),
        }

# ── Extract tempo metrics per game ────────────────────────────────────────────
console.print("[dim]Extracting early-scoring sequences...[/dim]")

# Per-team storage: list of (plays_to_5, plays_to_10, was_home, won_f10)
team_tempo = defaultdict(list)
f10_labels = defaultdict(list)  # team_id → list of (won_f10: bool)

game_count = 0
skip_count = 0

for gid, game in all_games.items():
    plays = game.get('plays', [])
    if not plays:
        skip_count += 1
        continue

    box_teams = game.get('boxscore', {}).get('teams', [])
    if len(box_teams) != 2:
        skip_count += 1
        continue

    home_id = away_id = None
    for t in box_teams:
        tid = str(t.get('team', {}).get('id', ''))
        if t.get('homeAway') == 'home':
            home_id = tid
        elif t.get('homeAway') == 'away':
            away_id = tid
    if not home_id or not away_id:
        skip_count += 1
        continue

    # Walk through plays, tracking each team's score progression
    home_milestones = {}  # 5 → play_index, 10 → play_index
    away_milestones = {}
    home_score = away_score = 0
    f10_winner = None

    for i, play in enumerate(plays):
        if not play.get('scoringPlay'):
            continue
        prev_h, prev_a = home_score, away_score
        home_score = play.get('homeScore', home_score)
        away_score = play.get('awayScore', away_score)
        play_num = i + 1

        # Check milestones
        for milestone in [5, 10]:
            if prev_h < milestone <= home_score and milestone not in home_milestones:
                home_milestones[milestone] = play_num
            if prev_a < milestone <= away_score and milestone not in away_milestones:
                away_milestones[milestone] = play_num

        # F10
        if f10_winner is None:
            pts = play.get('scoreValue', 0)
            if away_score >= 10 and (away_score - pts) < 10:
                f10_winner = 'away'
            elif home_score >= 10 and (home_score - pts) < 10:
                f10_winner = 'home'

    if f10_winner is None:
        skip_count += 1
        continue

    game_count += 1

    # Record metrics for each team
    # Home team
    if 10 in home_milestones and home_id in team_stats:
        team_tempo[home_id].append({
            'plays_to_5':  home_milestones.get(5, home_milestones[10]),
            'plays_to_10': home_milestones[10],
            'is_home': True,
            'won_f10': f10_winner == 'home',
        })
        f10_labels[home_id].append(f10_winner == 'home')

    # Away team
    if 10 in away_milestones and away_id in team_stats:
        team_tempo[away_id].append({
            'plays_to_5':  away_milestones.get(5, away_milestones[10]),
            'plays_to_10': away_milestones[10],
            'is_home': False,
            'won_f10': f10_winner == 'away',
        })
        f10_labels[away_id].append(f10_winner == 'away')

console.print(f"[dim]{game_count:,} games processed, {skip_count} skipped[/dim]")

# ── Compute per-team tempo ratings ────────────────────────────────────────────
team_ratings = []

for tid, records in team_tempo.items():
    if tid not in team_stats or len(records) < 5:
        continue

    plays_to_10 = [r['plays_to_10'] for r in records]
    plays_to_5  = [r['plays_to_5']  for r in records]
    won_f10     = [r['won_f10']     for r in records]

    # Home vs away split
    home_p10 = [r['plays_to_10'] for r in records if r['is_home']]
    away_p10 = [r['plays_to_10'] for r in records if not r['is_home']]

    stats = team_stats[tid]
    net_rating = stats['ppg'] - stats['opp_ppg']

    team_ratings.append({
        'tid': tid,
        'name': stats['name'],
        'ppg': stats['ppg'],
        'net': net_rating,
        'n_games': len(records),
        'median_plays_to_10': np.median(plays_to_10),
        'median_plays_to_5':  np.median(plays_to_5),
        'std_plays_to_10': np.std(plays_to_10),
        'f10_win_rate': np.mean(won_f10),
        'home_p10': np.median(home_p10) if home_p10 else None,
        'away_p10': np.median(away_p10) if away_p10 else None,
        'home_away_gap': (np.median(home_p10) - np.median(away_p10))
                          if home_p10 and away_p10 else None,
    })

team_ratings.sort(key=lambda x: x['median_plays_to_10'])

# ── Correlation analysis ───────────────────────────────────────────────────────
# Does plays_to_10 predict F10 win rate beyond PPG?
p10_vals  = np.array([t['median_plays_to_10'] for t in team_ratings])
ppg_vals  = np.array([t['ppg'] for t in team_ratings])
net_vals  = np.array([t['net'] for t in team_ratings])
f10_rates = np.array([t['f10_win_rate'] for t in team_ratings])

corr_p10_f10  = np.corrcoef(p10_vals, f10_rates)[0, 1]
corr_ppg_f10  = np.corrcoef(ppg_vals, f10_rates)[0, 1]
corr_net_f10  = np.corrcoef(net_vals, f10_rates)[0, 1]

# Partial correlation: does p10 add signal beyond ppg?
# Residualize p10 on ppg, then correlate residuals with f10_rate
ppg_mean, ppg_std = ppg_vals.mean(), ppg_vals.std()
ppg_norm = (ppg_vals - ppg_mean) / ppg_std
p10_residuals = p10_vals - (np.dot(ppg_norm, p10_vals) / len(ppg_norm)) * ppg_norm
partial_corr = np.corrcoef(p10_residuals, f10_rates)[0, 1]

# ── Sweet 16 teams tempo ───────────────────────────────────────────────────────
SWEET_16_IDS = {
    '12': 'Arizona', '8': 'Arkansas', '248': 'Houston', '356': 'Illinois',
    '2509': 'Purdue', '251': 'Texas', '158': 'Nebraska', '2294': 'Iowa',
    '150': 'Duke', '2599': "St. John's", '130': 'Michigan', '333': 'Alabama',
    '66': 'Iowa State', '2633': 'Tennessee', '41': 'UConn', '127': 'Michigan St',
}

sweet16_tempo = [t for t in team_ratings if t['tid'] in SWEET_16_IDS]
sweet16_tempo.sort(key=lambda x: x['median_plays_to_10'])

# ── Display ───────────────────────────────────────────────────────────────────
console.print()
console.print(Panel.fit(
    "[bold white]EARLY-GAME SCORING TEMPO ANALYSIS[/bold white]\n"
    f"[dim]{game_count:,} regular season games | Measures how quickly teams score their first 10 pts[/dim]",
    border_style="yellow"
))

# Correlation summary
console.print()
console.print("[bold]Correlation with F10 win rate:[/bold]")
console.print(f"  PPG (season avg):          r = [bold]{corr_ppg_f10:+.3f}[/bold]  — higher PPG → wins F10 more often")
console.print(f"  Net rating (PPG−OppPPG):   r = [bold]{corr_net_f10:+.3f}[/bold]  — stronger teams win F10 more")
console.print(f"  Plays-to-10 (raw):         r = [bold]{corr_p10_f10:+.3f}[/bold]  — fewer plays → wins F10 more often")
console.print(f"  Plays-to-10 (partial, after PPG): r = [bold]{partial_corr:+.3f}[/bold]  ← new signal beyond PPG?")
console.print()
if abs(partial_corr) > 0.10:
    console.print(f"  [green]✓ Tempo carries independent signal (|r|={abs(partial_corr):.3f} > 0.10)[/green]")
    console.print(f"  [green]  Adding plays-to-10 to the F10 model could improve predictions.[/green]")
else:
    console.print(f"  [yellow]≈ Tempo adds limited signal beyond PPG (|r|={abs(partial_corr):.3f})[/yellow]")
    console.print(f"  [yellow]  PPG already captures most of the early-scoring tendency.[/yellow]")

# Sweet 16 tempo table
console.print()
st = Table(title="Sweet 16 Teams — Early-Scoring Tempo", box=box.ROUNDED,
           border_style="yellow", header_style="bold yellow")
st.add_column("Team",          width=14)
st.add_column("PPG",           justify="right", width=7)
st.add_column("Net",           justify="right", width=6)
st.add_column("Plays to 10",   justify="right", width=11)
st.add_column("Plays to 5",    justify="right", width=10)
st.add_column("Std Dev",       justify="right", width=8)
st.add_column("F10 Win%",      justify="right", width=10)
st.add_column("Tempo Type",    width=18)

all_p10 = [t['median_plays_to_10'] for t in team_ratings]
p10_p25, p10_p75 = np.percentile(all_p10, 25), np.percentile(all_p10, 75)

for t in sweet16_tempo:
    p10 = t['median_plays_to_10']
    if p10 <= p10_p25:
        tempo_label = "[green]🔥 Explosive starter[/green]"
    elif p10 <= p10_p75:
        tempo_label = "[white]Avg pace[/white]"
    else:
        tempo_label = "[red]🐢 Slow starter[/red]"

    consistency = f"±{t['std_plays_to_10']:.1f}"
    st.add_row(
        t['name'],
        f"{t['ppg']:.1f}",
        f"{t['net']:+.1f}",
        f"{p10:.1f}",
        f"{t['median_plays_to_5']:.1f}",
        consistency,
        f"{t['f10_win_rate']:.1%}",
        tempo_label,
    )

console.print(st)

# Home/away gap — biggest home court tempo advantage
console.print()
ha_teams = [t for t in team_ratings if t['home_away_gap'] is not None and t['n_games'] >= 10]
ha_teams.sort(key=lambda x: x['home_away_gap'])  # most home-favored first (negative = faster at home)

hat = Table(title="Home vs Away Tempo Gap (Sweet 16 only)", box=box.SIMPLE,
            border_style="cyan", header_style="bold cyan")
hat.add_column("Team",      width=14)
hat.add_column("Home P10",  justify="right", width=10)
hat.add_column("Away P10",  justify="right", width=10)
hat.add_column("Gap",       justify="right", width=8)
hat.add_column("Meaning",   width=34)

s16_ha = [t for t in ha_teams if t['tid'] in SWEET_16_IDS]
s16_ha.sort(key=lambda x: x['home_away_gap'])

for t in s16_ha:
    gap = t['home_away_gap']
    if gap < -2:
        meaning = "[green]Faster at home — home advantage is real[/green]"
    elif gap > 2:
        meaning = "[red]Slower at home — performs better away[/red]"
    else:
        meaning = "[dim]Neutral — tempo consistent home/away[/dim]"
    hat.add_row(t['name'], f"{t['home_p10']:.1f}", f"{t['away_p10']:.1f}",
                f"{gap:+.1f}", meaning)

console.print(hat)

console.print()
console.print("[bold]Tournament implication:[/bold]")
console.print("  All Sweet 16 games are at [bold]neutral sites[/bold]. Teams that rely on home-court")
console.print("  tempo advantage (faster at home, slower away) may be overrated by our model,")
console.print("  which was trained on regular season games with real home/away assignments.")
console.print()
console.print("  [bold]Teams to fade in F10 (fast at home, slow away):[/bold]")
fade_teams = [t for t in s16_ha if t.get('home_away_gap', 0) < -2]
if fade_teams:
    for t in fade_teams:
        console.print(f"    [red]►[/red] {t['name']}: {t['home_p10']:.1f} plays at home vs {t['away_p10']:.1f} away (gap {t['home_away_gap']:+.1f})")
else:
    console.print("    [dim]No strong home-dependent starters among Sweet 16 teams[/dim]")
