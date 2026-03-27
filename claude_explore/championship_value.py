"""
Championship futures value finder.
Compares our bracket Monte Carlo odds vs current book odds to find mispriced teams.
"""
import sys
from pathlib import Path
import numpy as np
from scipy.special import expit
from collections import defaultdict, Counter
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

sys.path.insert(0, str(Path(__file__).parent))
from bracket_simulator import SWEET_16, REGION_PAIRS, SEMIFINAL_MATCHUPS, SPREAD_SIGMA, N_SIMS, get_ratings, simulate_bracket

console = Console()

# ── Current book championship odds (American) as of March 26, 2026 ─────────────
# Source: ESPN, VegasInsider, BetMGM
BOOK_ODDS = {
    "Michigan":    330,
    "Arizona":     350,
    "Duke":        380,
    "Houston":     700,
    "Purdue":     1200,
    "Illinois":   1400,
    "Iowa State": 1700,
    "UConn":      2500,
    "Michigan St":3000,
    "Nebraska":   3900,
    "Tennessee":  5000,
    "Arkansas":   6000,
    "Alabama":    8000,
    "St. John's": 8000,
    "Texas":     15000,
    "Iowa":      20000,
}

def american_to_implied(odds: int) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)

def american_to_decimal(odds: int) -> float:
    if odds > 0:
        return 1 + odds / 100
    return 1 + 100 / abs(odds)

def ev_per_100(model_p: float, book_odds: int) -> float:
    payout = american_to_decimal(book_odds) - 1
    return model_p * payout * 100 - (1 - model_p) * 100

def run_sim(ratings):
    rng = np.random.default_rng(42)
    all_teams = [name for teams in SWEET_16.values() for name, _, _ in teams]
    counts = defaultdict(int)
    for _ in range(N_SIMS):
        result = simulate_bracket(ratings, rng)
        for team, rounds in result.items():
            if 'champion' in rounds:
                counts[team] += 1
    return {t: counts[t] / N_SIMS for t in all_teams}

def bar(v, lo, hi, width=20):
    if hi == lo:
        return "─" * width
    p = (v - lo) / (hi - lo)
    filled = int(p * width)
    return "█" * filled + "░" * (width - filled)

if __name__ == '__main__':
    console.print("[dim]Loading team ratings...[/dim]")
    ratings = get_ratings()

    console.print(f"[dim]Running {N_SIMS:,} simulations...[/dim]")
    sim_probs = run_sim(ratings)

    # Build comparison rows
    rows = []
    for team, sim_p in sim_probs.items():
        book_american = BOOK_ODDS.get(team)
        if book_american is None:
            continue
        book_p = american_to_implied(book_american)
        edge = sim_p - book_p
        ev = ev_per_100(sim_p, book_american)
        rows.append((team, sim_p, book_p, book_american, edge, ev))

    rows.sort(key=lambda x: -x[4])  # sort by edge descending

    console.print()
    console.print(Panel.fit(
        "[bold white]CHAMPIONSHIP FUTURES — MODEL vs BOOK[/bold white]\n"
        "[dim]Model: Monte Carlo sim using real season net ratings (PPG − Opp PPG)\n"
        f"Spread sigma: {SPREAD_SIGMA} pts | {N_SIMS:,} simulations | Odds as of March 26, 2026[/dim]",
        border_style="cyan"
    ))

    t = Table(box=box.ROUNDED, border_style="cyan", header_style="bold cyan")
    t.add_column("Team",         width=14)
    t.add_column("Net Rtg",      justify="right", width=8)
    t.add_column("Sim %",        justify="right", width=8)
    t.add_column("Book %",       justify="right", width=8)
    t.add_column("Book Odds",    justify="right", width=10)
    t.add_column("Edge",         justify="right", width=9)
    t.add_column("EV/$100",      justify="right", width=9)
    t.add_column("Verdict",      width=22)

    edges = [r[4] for r in rows]
    lo, hi = min(edges), max(edges)

    for team, sim_p, book_p, book_amer, edge, ev in rows:
        net = ratings.get(team, 0)
        odds_str = f"+{book_amer}" if book_amer > 0 else str(book_amer)

        if edge > 0.04:
            verdict = "[bold green]✓ Strong value[/bold green]"
            edge_str = f"[bold green]+{edge*100:.1f}%[/bold green]"
            ev_str   = f"[bold green]+${ev:.0f}[/bold green]"
        elif edge > 0.01:
            verdict = "[green]✓ Slight value[/green]"
            edge_str = f"[green]+{edge*100:.1f}%[/green]"
            ev_str   = f"[green]+${ev:.0f}[/green]"
        elif edge > -0.01:
            verdict = "[dim]≈ Fair[/dim]"
            edge_str = f"{edge*100:+.1f}%"
            ev_str   = f"${ev:+.0f}"
        elif edge > -0.04:
            verdict = "[yellow]Slight fade[/yellow]"
            edge_str = f"[yellow]{edge*100:+.1f}%[/yellow]"
            ev_str   = f"[yellow]${ev:+.0f}[/yellow]"
        else:
            verdict = "[red]✗ Overpriced[/red]"
            edge_str = f"[red]{edge*100:+.1f}%[/red]"
            ev_str   = f"[red]${ev:+.0f}[/red]"

        t.add_row(team, f"{net:+.1f}", f"{sim_p*100:.1f}%", f"{book_p*100:.1f}%",
                  odds_str, edge_str, ev_str, verdict)

    console.print(t)
    console.print()
    console.print("[bold]Top value bets:[/bold]")
    for team, sim_p, book_p, book_amer, edge, ev in rows:
        if edge > 0.02:
            console.print(f"  [green]►[/green] [bold]{team}[/bold] +{book_amer}: "
                          f"model {sim_p*100:.1f}% vs book {book_p*100:.1f}% "
                          f"→ [green]+${ev:.0f} EV per $100[/green]")

    console.print()
    console.print("[dim]Note: EV assumes model probabilities are correct. "
                  "Our spread model has ±11.6 pt MAE — treat as directional signal only. "
                  "Futures bets carry vig; shop lines across books.[/dim]")
