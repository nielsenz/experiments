"""
F10 Model Backtest — 2026 NCAA Tournament

Validates the first-to-10 model against 31 completed tournament games.
Uses game_id bridge: results.csv → schedule → predictions.csv

Shows:
  - Per-game accuracy table (predicted prob vs actual outcome)
  - Calibration: when model says X%, does it win X% of the time?
  - Brier score and log-loss
  - Simulated betting P&L if you'd bet every edge game flat
"""
import sys, csv, math
from pathlib import Path
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()

CBB = Path(__file__).parent.parent / "college-basketball"
RESULTS_PATH  = CBB / "data/processed/first_to_10_results.csv"
SCHEDULE_PATH = CBB / "source/tournament_schedule_2026_updated.csv"
PREDS_PATH    = CBB / "data/processed/predictions_2026.csv"

# ── Load data ──────────────────────────────────────────────────────────────────
def load_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))

results  = load_csv(RESULTS_PATH)
schedule = load_csv(SCHEDULE_PATH)
preds    = load_csv(PREDS_PATH)

# Build lookup: game_id → schedule row
sched_by_id = {row['id']: row for row in schedule}

# Build lookup: (home_name, away_name) → pred row
# Predictions use full names from schedule; join by home_name
pred_by_teams = {}
for p in preds:
    pred_by_teams[(p['home_team'].strip().lower(), p['away_team'].strip().lower())] = p

# ── Join results → schedule → predictions ─────────────────────────────────────
matched = []
unmatched = []

for r in results:
    if r['status'] != 'STATUS_FINAL':
        continue
    gid = r['game_id']
    s = sched_by_id.get(gid)
    if not s:
        unmatched.append((gid, 'no schedule row'))
        continue

    home_full = s['home_name'].strip()
    away_full = s['away_name'].strip()
    key = (home_full.lower(), away_full.lower())

    p = pred_by_teams.get(key)
    if not p:
        unmatched.append((gid, f'{home_full} vs {away_full} not in preds'))
        continue

    actual_home_wins_f10 = (r['first_to_10'] == 'home')
    prob_home = float(p['prob_home_f10'])

    matched.append({
        'gid': gid,
        'date': r['date'][:10],
        'home': home_full,
        'away': away_full,
        'prob_home': prob_home,
        'actual_home': actual_home_wins_f10,
        'correct': (prob_home >= 0.5) == actual_home_wins_f10,
    })

console.print(f"[dim]Matched {len(matched)}/{len([r for r in results if r['status']=='STATUS_FINAL'])} completed games | {len(unmatched)} unmatched[/dim]")
if unmatched:
    for gid, reason in unmatched[:5]:
        console.print(f"  [yellow]⚠ {gid}: {reason}[/yellow]")

if not matched:
    console.print("[red]No matched games — check file paths.[/red]")
    sys.exit(1)

# ── Metrics ───────────────────────────────────────────────────────────────────
n = len(matched)
correct = sum(1 for m in matched if m['correct'])
accuracy = correct / n

# Brier score: mean((prob - actual)^2) — lower is better, coin flip = 0.25
brier = sum((m['prob_home'] - int(m['actual_home']))**2 for m in matched) / n
brier_baseline = 0.25  # random 50/50

# Log-loss
log_loss = -sum(
    math.log(m['prob_home']) if m['actual_home'] else math.log(1 - m['prob_home'])
    for m in matched
) / n
log_loss_baseline = math.log(2)  # 0.693, coin flip

# Calibration buckets
buckets = defaultdict(lambda: {'n': 0, 'hits': 0})
for m in matched:
    bucket = round(m['prob_home'] * 10) / 10  # round to nearest 0.1
    buckets[bucket]['n'] += 1
    buckets[bucket]['hits'] += int(m['actual_home'])

# Flat-bet P&L: bet $10 on predicted winner whenever edge > 5%
pnl = 0
bets_placed = 0
for m in matched:
    edge = abs(m['prob_home'] - 0.5)
    if edge < 0.05:
        continue
    bets_placed += 1
    won = m['correct']
    pnl += 10 if won else -10

# ── Display ───────────────────────────────────────────────────────────────────
console.print()
console.print(Panel.fit(
    "[bold white]FIRST-TO-10 MODEL BACKTEST — 2026 NCAA TOURNAMENT[/bold white]\n"
    f"[dim]{n} completed games | Model: GBM trained on 1,137 regular season games[/dim]",
    border_style="green"
))

# Summary metrics
mt = Table(box=box.SIMPLE, show_header=False)
mt.add_column("Metric", style="bold", width=22)
mt.add_column("Value",  width=12)
mt.add_column("vs Baseline", width=20)

mt.add_row("Games evaluated", str(n), "")
mt.add_row("Accuracy",
    f"[bold green]{accuracy:.1%}[/bold green]" if accuracy > 0.54 else f"{accuracy:.1%}",
    f"baseline 50.0% {'↑' if accuracy > 0.50 else '↓'}")
mt.add_row("Brier score",
    f"[bold green]{brier:.4f}[/bold green]" if brier < brier_baseline else f"{brier:.4f}",
    f"coin flip = {brier_baseline:.4f} {'↑ better' if brier < brier_baseline else '↓ worse'}")
mt.add_row("Log-loss",
    f"[bold green]{log_loss:.4f}[/bold green]" if log_loss < log_loss_baseline else f"{log_loss:.4f}",
    f"coin flip = {log_loss_baseline:.4f} {'↑ better' if log_loss < log_loss_baseline else '↓ worse'}")
mt.add_row("Flat-bet P&L",
    f"[bold green]+${pnl}[/bold green]" if pnl > 0 else f"[red]${pnl}[/red]",
    f"on {bets_placed} bets @ $10 flat, edge>5%")

console.print(mt)

# Per-game table
console.print()
gt = Table(title="Per-Game Results", box=box.ROUNDED, border_style="green", header_style="bold")
gt.add_column("Date",     width=11)
gt.add_column("Home",     width=16)
gt.add_column("Away",     width=16)
gt.add_column("P(Home)",  justify="right", width=9)
gt.add_column("Actual",   justify="center", width=9)
gt.add_column("✓/✗",     justify="center", width=5)
gt.add_column("Edge",     justify="right", width=7)

for m in sorted(matched, key=lambda x: x['date']):
    actual_str = "[green]Home[/green]" if m['actual_home'] else "[red]Away[/red]"
    check = "[green]✓[/green]" if m['correct'] else "[red]✗[/red]"
    edge_pct = abs(m['prob_home'] - 0.5) * 100
    prob_str = f"{m['prob_home']:.1%}"
    gt.add_row(m['date'], m['home'][:15], m['away'][:15],
               prob_str, actual_str, check, f"{edge_pct:.1f}%")

console.print(gt)

# Calibration
console.print()
ct = Table(title="Calibration (when model says X%, how often does home actually win F10?)",
           box=box.SIMPLE, border_style="cyan", header_style="bold cyan")
ct.add_column("Pred range",  width=14)
ct.add_column("N games",     justify="right", width=9)
ct.add_column("Actual %",    justify="right", width=10)
ct.add_column("Expected %",  justify="right", width=11)
ct.add_column("Gap",         justify="right", width=8)
ct.add_column("",            width=20)

for bucket in sorted(buckets.keys()):
    b = buckets[bucket]
    if b['n'] == 0:
        continue
    actual_p = b['hits'] / b['n']
    gap = actual_p - bucket
    gap_str = f"[green]{gap:+.1%}[/green]" if abs(gap) < 0.10 else f"[red]{gap:+.1%}[/red]"
    bar_len = int(actual_p * 20)
    bar_str = "[green]" + "█" * bar_len + "[/green]" + "░" * (20 - bar_len)
    ct.add_row(
        f"{max(0,bucket-0.05):.0%}–{min(1,bucket+0.05):.0%}",
        str(b['n']),
        f"{actual_p:.1%}",
        f"{bucket:.1%}",
        gap_str,
        bar_str,
    )

console.print(ct)
console.print()
console.print(
    "[bold]Calibration interpretation:[/bold] A well-calibrated model has "
    "small gaps in every bucket. Large positive gaps mean the model is [green]underconfident[/green]; "
    "large negative gaps mean it's [red]overconfident[/red]."
)
