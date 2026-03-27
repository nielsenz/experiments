"""
NCAA Tournament Monte Carlo Bracket Simulator
Fetches the current bracket from ESPN, derives win probabilities from team
efficiency ratings, and simulates the remaining rounds 100,000 times.

Outputs:
  - Championship / Final Four / Elite Eight odds for every remaining team
  - Most likely Final Four combinations
  - "Value picks" — teams whose chalk odds understate their simulated probability
"""
import sys
from pathlib import Path
import numpy as np
from scipy.special import expit          # sigmoid, used for spread → win prob
from collections import defaultdict, Counter
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
from rich import box

console = Console()

# ── Constants ─────────────────────────────────────────────────────────────────
N_SIMS = 100_000
# Spread uncertainty: derived from our spread model CV MAE (~11.6 pts).
# MAE → sigma via sigma ≈ MAE * sqrt(pi/2) ≈ 14.5 pts
SPREAD_SIGMA = 14.5

# Path to our real team stats (relative: run from college-basketball/ or set below)
TEAM_STATS_PATH = Path(__file__).parent.parent / "college-basketball/data/processed/team_stats_2026.csv"

# ── Sweet 16 bracket structure ─────────────────────────────────────────────────
# Team tuples: (name, seed, espn_team_id)
# ID matches team_id in team_stats_2026.csv

SWEET_16 = {
    "South": [
        ("Arizona",  1, 12),
        ("Arkansas", 4, 8),
        ("Houston",  2, 248),
        ("Illinois", 3, 356),
    ],
    "West": [
        ("Purdue",   2, 2509),
        ("Texas",    11, 251),
        ("Nebraska", 4, 158),
        ("Iowa",     9, 2294),
    ],
    "East": [
        ("Duke",       1, 150),
        ("St. John's", 5, 2599),
        ("Michigan",   1, 130),
        ("Alabama",    4, 333),
    ],
    "Midwest": [
        ("Iowa State", 2, 66),
        ("Tennessee",  4, 2633),
        ("UConn",      2, 41),
        ("Michigan St",3, 127),
    ],
}

# Bracket pairs within each region: games[0] winner faces games[1] winner in Elite 8
# games[0] = top half, games[1] = bottom half
REGION_PAIRS = {
    "South":   (("Arizona", "Arkansas"), ("Houston", "Illinois")),
    "West":    (("Purdue", "Texas"),     ("Nebraska", "Iowa")),
    "East":    (("Duke", "St. John's"),  ("Michigan", "Alabama")),
    "Midwest": (("Iowa State", "Tennessee"), ("UConn", "Michigan St")),
}

# National semifinal matchups (Final Four): South vs West, East vs Midwest
SEMIFINAL_MATCHUPS = [("South", "West"), ("East", "Midwest")]

# ── Load ratings from team_stats_2026.csv ─────────────────────────────────────
def get_ratings() -> dict[str, float]:
    """
    Load net ratings (avg_pts - avg_opp_pts) from team_stats_2026.csv.
    Falls back to seed-based estimate only if team_id is missing from the file.
    """
    import csv

    SEED_NET = {1: 22, 2: 17, 3: 13, 4: 9, 5: 6, 6: 4, 7: 2, 8: 0, 9: -1,
                10: -2, 11: -3, 12: -4, 13: -6, 14: -9, 15: -13, 16: -18}

    # Load CSV into id → (avg_pts, avg_opp_pts)
    stats = {}
    if TEAM_STATS_PATH.exists():
        with open(TEAM_STATS_PATH) as f:
            for row in csv.DictReader(f):
                stats[int(row['team_id'])] = (float(row['avg_pts']), float(row['avg_opp_pts']))
    else:
        console.print(f"[red]⚠ team_stats not found at {TEAM_STATS_PATH} — using seed fallbacks[/red]")

    ratings = {}
    all_teams = [(name, seed, tid) for teams in SWEET_16.values() for name, seed, tid in teams]
    for name, seed, tid in all_teams:
        if tid in stats:
            ppg, opp_ppg = stats[tid]
            ratings[name] = ppg - opp_ppg
        else:
            ratings[name] = float(SEED_NET.get(seed, 0))
            console.print(f"  [yellow]⚠ {name} (id={tid}): no stats found, seed-{seed} fallback[/yellow]")

    return ratings

# ── Win probability ────────────────────────────────────────────────────────────
def win_prob(rating_a: float, rating_b: float, sigma: float = SPREAD_SIGMA) -> float:
    """P(team_a beats team_b) from their net ratings and spread uncertainty."""
    spread = rating_a - rating_b   # predicted margin for A
    return float(expit(spread / sigma * 1.7))  # 1.7 ≈ pi/sqrt(3), logistic scale factor

# ── Simulate one bracket path from Sweet 16 onward ────────────────────────────
def simulate_bracket(ratings: dict[str, float], rng: np.random.Generator) -> dict[str, list[str]]:
    """
    Simulate from Sweet 16 → champion.
    Returns dict mapping each team to the rounds they reached:
      'sweet16', 'elite8', 'final4', 'championship', 'champion'
    """
    reached = defaultdict(list)

    # All teams start at Sweet 16
    for teams in SWEET_16.values():
        for name, _, _ in teams:
            reached[name].append('sweet16')

    region_winners = {}

    for region, ((a1, a2), (b1, b2)) in REGION_PAIRS.items():
        # Elite 8 game 1: a1 vs a2
        pa = win_prob(ratings[a1], ratings[a2])
        w_top = a1 if rng.random() < pa else a2

        # Elite 8 game 2: b1 vs b2
        pb = win_prob(ratings[b1], ratings[b2])
        w_bot = b1 if rng.random() < pb else b2

        for t in [w_top, w_bot]:
            reached[t].append('elite8')

        # Regional final (Final Four entry)
        pf = win_prob(ratings[w_top], ratings[w_bot])
        region_winner = w_top if rng.random() < pf else w_bot
        reached[region_winner].append('final4')
        region_winners[region] = region_winner

    # Final Four
    finalists = []
    for r1, r2 in SEMIFINAL_MATCHUPS:
        t1, t2 = region_winners[r1], region_winners[r2]
        p = win_prob(ratings[t1], ratings[t2])
        finalist = t1 if rng.random() < p else t2
        reached[finalist].append('championship')
        finalists.append(finalist)

    # Championship
    p = win_prob(ratings[finalists[0]], ratings[finalists[1]])
    champion = finalists[0] if rng.random() < p else finalists[1]
    reached[champion].append('champion')

    return reached

# ── Run simulation ─────────────────────────────────────────────────────────────
def run_simulation(ratings: dict[str, float]) -> dict:
    rng = np.random.default_rng(42)
    all_teams = [name for teams in SWEET_16.values() for name, _, _ in teams]
    round_counts = {t: defaultdict(int) for t in all_teams}
    final_four_combos = Counter()

    console.print(f"\n[bold cyan]Running {N_SIMS:,} simulations...[/bold cyan]")
    for _ in track(range(N_SIMS), description="Simulating...", console=console):
        result = simulate_bracket(ratings, rng)
        for team, rounds in result.items():
            for r in rounds:
                round_counts[team][r] += 1
        # Track Final Four combos
        f4 = tuple(sorted(t for t, rs in result.items() if 'final4' in rs))
        final_four_combos[f4] += 1

    # Convert to probabilities
    probs = {}
    for team in all_teams:
        probs[team] = {r: round_counts[team][r] / N_SIMS for r in
                       ['sweet16', 'elite8', 'final4', 'championship', 'champion']}

    return probs, final_four_combos

# ── Seed → implied championship probability (Vegas-style baseline) ─────────────
SEED_CHAMP_ODDS = {1: 0.30, 2: 0.14, 3: 0.07, 4: 0.04, 5: 0.02, 6: 0.015,
                   7: 0.01, 8: 0.008, 9: 0.007, 10: 0.006, 11: 0.005, 12: 0.004}

def seed_for(name: str) -> int:
    for teams in SWEET_16.values():
        for n, seed, _ in teams:
            if n == name:
                return seed
    return 8

# ── Display ────────────────────────────────────────────────────────────────────
def bar(p: float, width: int = 20) -> str:
    filled = int(p * width)
    return "█" * filled + "░" * (width - filled)

def pct(p: float) -> str:
    return f"{p*100:5.1f}%"

def american_odds(p: float) -> str:
    if p <= 0 or p >= 1:
        return "N/A"
    if p >= 0.5:
        return f"-{int(p/(1-p)*100)}"
    return f"+{int((1-p)/p*100)}"

def display_results(probs: dict, final_four_combos: Counter, ratings: dict):
    # Sort teams by championship probability
    teams_sorted = sorted(probs.keys(), key=lambda t: probs[t]['champion'], reverse=True)

    console.print()
    console.print(Panel.fit(
        "[bold white]2026 NCAA TOURNAMENT — MONTE CARLO BRACKET SIMULATOR[/bold white]\n"
        f"[dim]{N_SIMS:,} simulations from Sweet 16 onward[/dim]",
        border_style="cyan"
    ))

    # ── Main odds table ────────────────────────────────────────────────────────
    t = Table(title="Championship & Round Odds", box=box.ROUNDED, border_style="cyan",
              header_style="bold cyan")
    t.add_column("Team",        style="bold white", width=16)
    t.add_column("Seed",        justify="center", width=5)
    t.add_column("Net Rtg",     justify="right", width=8)
    t.add_column("Elite 8",     justify="right", width=9)
    t.add_column("Final 4",     justify="right", width=9)
    t.add_column("Final",       justify="right", width=8)
    t.add_column("Champion",    justify="right", width=10)
    t.add_column("Odds",        justify="right", width=8)
    t.add_column("",            width=22)

    for team in teams_sorted:
        p = probs[team]
        seed = seed_for(team)
        net = ratings.get(team, 0)
        champ_p = p['champion']
        style = "green" if champ_p >= 0.10 else ("yellow" if champ_p >= 0.04 else "")
        t.add_row(
            team,
            str(seed),
            f"{net:+.1f}",
            pct(p['elite8']),
            pct(p['final4']),
            pct(p['championship']),
            f"[{style}]{pct(champ_p)}[/{style}]" if style else pct(champ_p),
            american_odds(champ_p),
            f"[dim]{bar(champ_p, 20)}[/dim]",
        )

    console.print(t)

    # ── Value picks ────────────────────────────────────────────────────────────
    console.print()
    vt = Table(title="Value Picks (sim prob vs seed baseline)", box=box.SIMPLE,
               border_style="yellow", header_style="bold yellow")
    vt.add_column("Team",       style="bold", width=16)
    vt.add_column("Seed",       justify="center", width=5)
    vt.add_column("Sim Champ",  justify="right", width=10)
    vt.add_column("Seed Base",  justify="right", width=10)
    vt.add_column("Edge",       justify="right", width=8)
    vt.add_column("Verdict",    width=24)

    value_teams = []
    for team in teams_sorted:
        seed = seed_for(team)
        sim_p = probs[team]['champion']
        base_p = SEED_CHAMP_ODDS.get(seed, 0.003)
        edge = sim_p - base_p
        value_teams.append((team, seed, sim_p, base_p, edge))

    value_teams.sort(key=lambda x: -x[4])
    for team, seed, sim_p, base_p, edge in value_teams:
        if edge > 0.01:
            verdict = "[green]✓ Model likes them[/green]"
        elif edge < -0.02:
            verdict = "[red]✗ Model fades them[/red]"
        else:
            verdict = "[dim]≈ Fair value[/dim]"
        vt.add_row(team, str(seed), pct(sim_p), pct(base_p),
                   f"[green]+{edge*100:.1f}%[/green]" if edge > 0 else f"[red]{edge*100:.1f}%[/red]",
                   verdict)

    console.print(vt)

    # ── Most likely Final Fours ────────────────────────────────────────────────
    console.print()
    ft = Table(title="10 Most Likely Final Fours", box=box.SIMPLE,
               border_style="magenta", header_style="bold magenta")
    ft.add_column("Final Four",  width=60)
    ft.add_column("Prob",        justify="right", width=8)
    ft.add_column("",            width=16)

    for combo, count in final_four_combos.most_common(10):
        p = count / N_SIMS
        ft.add_row(
            "  ·  ".join(combo),
            pct(p),
            f"[dim]{bar(p * 10, 16)}[/dim]",
        )
    console.print(ft)

    # ── Regional breakdown ────────────────────────────────────────────────────
    console.print()
    rt = Table(title="Regional Winner Probabilities", box=box.SIMPLE, border_style="blue")
    for region in SWEET_16:
        region_teams = sorted(
            [name for name, _, _ in SWEET_16[region]],
            key=lambda t: probs[t]['final4'],
            reverse=True,
        )
        rt.add_column(region, width=20, header_style="bold blue")

    rows = []
    max_teams = max(len(SWEET_16[r]) for r in SWEET_16)
    for i in range(max_teams):
        row = []
        for region in SWEET_16:
            region_teams = sorted(
                [name for name, _, _ in SWEET_16[region]],
                key=lambda t: probs[t]['final4'],
                reverse=True,
            )
            if i < len(region_teams):
                t = region_teams[i]
                row.append(f"{t} {pct(probs[t]['final4'])}")
            else:
                row.append("")
        rows.append(row)

    for row in rows:
        rt.add_row(*row)
    console.print(rt)

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    ratings = get_ratings()

    console.print("\n[bold]Team Net Ratings (PPG − Opp PPG):[/bold]")
    for name, net in sorted(ratings.items(), key=lambda x: -x[1]):
        console.print(f"  {name:<20} {net:+6.1f}  {bar(max(0, net+10)/35, 25)}")

    probs, ff_combos = run_simulation(ratings)
    display_results(probs, ff_combos, ratings)
