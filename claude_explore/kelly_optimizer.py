"""
Kelly Criterion Bankroll Optimizer — 2026 Sweet 16 First-to-10 Bets

The bets here are all **First-to-10 (F10) props**: which team scores 10 points
first in an NCAA tournament game. Our GBM model (CV AUC 0.604) assigns each
team a probability; we compare that to the book's implied probability from the
American odds to measure edge.

Kelly Criterion in plain English:
  "Bet exactly the fraction of your bankroll equal to your edge divided by your
   net payout odds."

  f* = (b*p - q) / b    where b = net decimal odds (e.g. -110 → b = 0.909)
                               p = your model's win probability
                               q = 1 - p (loss probability)

  Edge > 0 → positive Kelly → bet some amount
  Edge ≤ 0 → Kelly = 0     → don't bet

In practice, bet HALF-Kelly (f*/2) to account for model error and variance.
Full Kelly is theoretically optimal but requires a perfectly calibrated model —
half-Kelly is the professional standard.

Computes:
  - Full / Half / Quarter Kelly stake sizes
  - Expected value per bet
  - Simulated bankroll growth over 500 cycles (2,000 Monte Carlo trials)
  - Risk of ruin at each staking level

Usage:
  uv run python kelly_optimizer.py                    # built-in Sweet 16 F10 bets
  uv run python kelly_optimizer.py path/to/bets.csv  # load from CSV
                                                       # cols: bet_team, model_prob,
                                                       #       book_odds (American), stake
"""
import sys
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box
import csv
from pathlib import Path

console = Console()

# ── Sweet 16 F10 bets (from betting_lines_sweet16.csv) ────────────────────────
SWEET_16_BETS = [
    # (label,            model_prob, book_american_odds, stake)
    ("Iowa F10",          0.6098,    -110,  11),
    ("Illinois F10",      0.5603,    -105,  11),
    ("Purdue F10",        0.6545,    -165,   6),
    ("Arizona F10",       0.7107,    -160,   6),
    ("Michigan F10",      0.7291,    -175,   6),
    ("UConn F10",         0.6062,    -125,   6),
]

# ── Conversions ────────────────────────────────────────────────────────────────
def american_to_decimal(odds: int) -> float:
    """Convert American odds to decimal (return on $1 including stake)."""
    if odds > 0:
        return 1 + odds / 100
    return 1 + 100 / abs(odds)

def american_to_implied(odds: int) -> float:
    """Book's implied probability (with vig)."""
    d = american_to_decimal(odds)
    return 1 / d

def kelly_fraction(p: float, b: float) -> float:
    """
    Kelly criterion: f* = (bp - q) / b
    p = model win probability, b = net odds (decimal - 1), q = 1 - p
    Returns fraction of bankroll to bet. Negative = no bet.
    """
    q = 1 - p
    f = (b * p - q) / b
    return max(0.0, f)

def ev_per_100(p: float, american_odds: int) -> float:
    """Expected value of a $100 bet."""
    d = american_to_decimal(american_odds)
    return p * (d - 1) * 100 - (1 - p) * 100

def edge(model_p: float, book_american: int) -> float:
    return model_p - american_to_implied(book_american)

# ── Monte Carlo bankroll simulation ───────────────────────────────────────────
def simulate_bankroll(bets: list[dict], bankroll: float, fraction: float,
                      n_cycles: int = 500, n_sims: int = 2_000,
                      rng: np.random.Generator = None) -> dict:
    """
    Simulate bankroll evolution over n_cycles rounds of the same bet set.
    fraction: multiplier on full Kelly (1.0 = full Kelly, 0.5 = half Kelly, etc.)
    Returns dict with percentile curves and risk_of_ruin.
    """
    if rng is None:
        rng = np.random.default_rng(42)

    ruin_threshold = bankroll * 0.10
    final_rolls = np.ones(n_sims) * bankroll
    ruin_count = 0
    trajectories = np.ones((n_sims, n_cycles + 1)) * bankroll

    for sim in range(n_sims):
        roll = bankroll
        ruined = False
        for cycle in range(n_cycles):
            for bet in bets:
                if roll < 1:
                    ruined = True
                    break
                f = bet['kelly'] * fraction
                stake = roll * f
                decimal = american_to_decimal(bet['book_odds'])
                if rng.random() < bet['model_prob']:
                    roll += stake * (decimal - 1)
                else:
                    roll -= stake
            trajectories[sim, cycle + 1] = roll
            if ruined or roll < ruin_threshold:
                ruined = True
                trajectories[sim, cycle + 1:] = roll
                break
        if ruined or roll < ruin_threshold:
            ruin_count += 1
        final_rolls[sim] = roll

    return {
        'median':       np.median(final_rolls),
        'p25':          np.percentile(final_rolls, 25),
        'p75':          np.percentile(final_rolls, 75),
        'p10':          np.percentile(final_rolls, 10),
        'p90':          np.percentile(final_rolls, 90),
        'risk_of_ruin': ruin_count / n_sims,
        'trajectories': trajectories,
    }

# ── ASCII sparkline ────────────────────────────────────────────────────────────
def sparkline(values: list[float], width: int = 30) -> str:
    blocks = "▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    if hi == lo:
        return blocks[3] * width
    normed = [(v - lo) / (hi - lo) for v in values]
    indices = [min(int(n * len(blocks)), len(blocks) - 1) for n in normed]
    return "".join(blocks[i] for i in indices[-width:])

def bar(p: float, width: int = 20) -> str:
    filled = int(p * width)
    return "█" * filled + "░" * (width - filled)

def pct(p: float) -> str:
    return f"{p*100:.1f}%"

# ── Load bets ─────────────────────────────────────────────────────────────────
def load_bets(path: str = None) -> list[dict]:
    raw = SWEET_16_BETS
    if path:
        raw = []
        with open(path) as f:
            for row in csv.DictReader(f):
                raw.append((
                    row['bet_team'],
                    float(row['model_prob']),
                    int(row['book_odds']),
                    float(row.get('stake', 10)),
                ))

    bets = []
    for label, model_p, book_odds, stake in raw:
        b = american_to_decimal(book_odds) - 1  # net odds
        k = kelly_fraction(model_p, b)
        bets.append({
            'label': label,
            'model_prob': model_p,
            'book_odds': book_odds,
            'stake': stake,
            'implied_prob': american_to_implied(book_odds),
            'edge': edge(model_p, book_odds),
            'ev_per_100': ev_per_100(model_p, book_odds),
            'kelly': k,
            'decimal': american_to_decimal(book_odds),
        })
    return bets

# ── Display ───────────────────────────────────────────────────────────────────
def display(bets: list[dict], bankroll: float = 1000.0):
    console.print()
    console.print(Panel.fit(
        "[bold white]KELLY CRITERION BANKROLL OPTIMIZER[/bold white]\n"
        f"[dim]2026 Sweet 16 — First-to-10 props | Starting bankroll: ${bankroll:,.0f}[/dim]\n\n"
        "[dim]These are race-to-10 bets: which team scores 10 points first in the game.\n"
        "Model: GBM trained on 1,137 regular season games (CV AUC 0.604).\n"
        "Edge = model probability − book implied probability.\n"
        "Kelly fraction = how much of your bankroll the math says to risk.[/dim]",
        border_style="green"
    ))

    # ── Per-bet analysis ──────────────────────────────────────────────────────
    t = Table(title="Bet Analysis", box=box.ROUNDED, border_style="green",
              header_style="bold green")
    t.add_column("Bet",          width=16)
    t.add_column("Model P",      justify="right", width=9)
    t.add_column("Book P",       justify="right", width=8)
    t.add_column("Edge",         justify="right", width=8)
    t.add_column("EV/$100",      justify="right", width=9)
    t.add_column("Full Kelly",   justify="right", width=11)
    t.add_column("½ Kelly $",    justify="right", width=10)
    t.add_column("Placed $",     justify="right", width=9)
    t.add_column("Verdict",      width=20)

    total_placed = sum(b['stake'] for b in bets)
    for b in sorted(bets, key=lambda x: -x['edge']):
        full_k_pct = b['kelly'] * 100
        half_k_dollar = bankroll * b['kelly'] * 0.5

        e = b['edge']
        ev = b['ev_per_100']
        verdict = (
            "[bold green]Strong edge[/bold green]" if e > 0.08 else
            "[green]Good edge[/green]"             if e > 0.04 else
            "[yellow]Marginal[/yellow]"            if e > 0.01 else
            "[red]No edge[/red]"
        )
        t.add_row(
            b['label'],
            pct(b['model_prob']),
            pct(b['implied_prob']),
            f"[green]+{pct(e)}[/green]" if e > 0 else f"[red]{pct(e)}[/red]",
            f"[green]+${ev:.2f}[/green]" if ev > 0 else f"[red]${ev:.2f}[/red]",
            f"{full_k_pct:.1f}%",
            f"${half_k_dollar:.2f}",
            f"${b['stake']:.0f}",
            verdict,
        )

    console.print(t)

    # ── Portfolio summary ─────────────────────────────────────────────────────
    total_ev = sum(b['ev_per_100'] * b['stake'] / 100 for b in bets)
    console.print(f"\n[bold]Total staked:[/bold] ${total_placed}  |  "
                  f"[bold]Expected profit:[/bold] "
                  f"[green]+${total_ev:.2f}[/green]" if total_ev >= 0 else f"[red]${total_ev:.2f}[/red]")

    # ── Staking strategy comparison ───────────────────────────────────────────
    console.print("\n[bold cyan]Simulating bankroll growth (2,000 trials × 500 bet cycles)...[/bold cyan]")
    rng = np.random.default_rng(42)

    strategies = [
        ("Full Kelly",    1.0,  "red"),
        ("Half Kelly",    0.5,  "green"),
        ("Quarter Kelly", 0.25, "yellow"),
        ("Flat 2%",       None, "blue"),    # special: always 2% of starting bankroll
    ]

    results = {}
    for name, frac, color in strategies:
        if frac is None:
            # Flat staking: replace kelly with fixed 2% of starting bankroll
            flat_bets = [{**b, 'kelly': 0.02} for b in bets]
            r = simulate_bankroll(flat_bets, bankroll, 1.0, rng=rng)
        else:
            r = simulate_bankroll(bets, bankroll, frac, rng=rng)
        results[name] = (r, color)

    st = Table(title="Staking Strategy Comparison (500 cycles)", box=box.ROUNDED,
               border_style="cyan", header_style="bold cyan")
    st.add_column("Strategy",     width=16)
    st.add_column("Median",       justify="right", width=10)
    st.add_column("10th %ile",    justify="right", width=10)
    st.add_column("90th %ile",    justify="right", width=10)
    st.add_column("Risk of Ruin", justify="right", width=13)
    st.add_column("Growth",       justify="right", width=10)
    st.add_column("",             width=24)

    for name, (r, color) in results.items():
        growth = (r['median'] / bankroll - 1) * 100
        ror = r['risk_of_ruin']
        ror_style = "red" if ror > 0.20 else ("yellow" if ror > 0.05 else "green")
        st.add_row(
            f"[{color}]{name}[/{color}]",
            f"${r['median']:,.0f}",
            f"${r['p10']:,.0f}",
            f"${r['p90']:,.0f}",
            f"[{ror_style}]{ror:.1%}[/{ror_style}]",
            f"[green]+{growth:.0f}%[/green]" if growth >= 0 else f"[red]{growth:.0f}%[/red]",
            f"[dim]{sparkline(list(np.median(r['trajectories'], axis=0)[::17]), 24)}[/dim]",
        )

    console.print(st)

    console.print()
    console.print(
        "[bold]Key insight:[/bold] Half-Kelly maximizes long-run growth while halving "
        "variance and risk of ruin vs Full Kelly. Quarter-Kelly is safest for "
        "small edges like these (~5-10%)."
    )
    console.print(
        "[dim]Risk of ruin = probability bankroll falls below 10% of starting value "
        "at any point in 500 cycles.[/dim]"
    )

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else None
    bets = load_bets(path)
    display(bets, bankroll=1000.0)
