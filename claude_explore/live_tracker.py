"""
Live F10 Race Tracker — 2026 NCAA Tournament

Polls ESPN API every 15 seconds and displays a live scoreboard showing:
  - Current score + game clock for all active games
  - Race-to-10 progress (who's closer to 10 first)
  - F10 result as soon as it's hit, with bet outcome highlighted
  - Final results when games end

Usage:
  uv run python live_tracker.py

Press Ctrl+C to exit.
"""
import time, requests
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box

console = Console()

POLL_INTERVAL = 15  # seconds
DATES = ['20260326', '20260327', '20260328']

# Our active bets — shown with outcome once F10 is decided
BETS = {
    # home_team_fragment → (bet_team, book_odds)
    "Iowa":        ("Iowa",      -110),
    "Illinois":    ("Illinois",  -105),
    "Purdue":      ("Purdue",    -165),
    "Arizona":     ("Arizona",   -160),
    "Michigan":    ("Michigan",  -175),
    "UConn":       ("UConn",     -125),
}

def american_to_decimal(odds):
    if odds > 0:
        return 1 + odds / 100
    return 1 + 100 / abs(odds)

def fetch_games(date):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates={date}&groups=100"
    try:
        r = requests.get(url, timeout=8)
        return r.json().get('events', [])
    except Exception:
        return []

def fetch_plays(game_id):
    url = f"https://site.web.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={game_id}"
    try:
        r = requests.get(url, timeout=8)
        data = r.json()
        return data.get('plays', data.get('playByPlay', {}).get('plays', []))
    except Exception:
        return []

def extract_f10(plays):
    """Return ('home'|'away', score_when_hit) or None if not reached yet."""
    scored = [p for p in plays if p.get('scoringPlay')]
    for p in scored:
        away = p.get('awayScore', 0)
        home = p.get('homeScore', 0)
        pts  = p.get('scoreValue', 0)
        if away >= 10 and (away - pts) < 10:
            return 'away', away, home
        if home >= 10 and (home - pts) < 10:
            return 'home', home, away
    return None

def progress_bar(score, target=10, width=10):
    filled = min(int(score / target * width), width)
    return "█" * filled + "░" * (width - filled)

def bet_for_game(home_name, away_name):
    """Return (bet_team, book_odds) if we have a bet on this game."""
    for fragment, (team, odds) in BETS.items():
        if fragment.lower() in home_name.lower() or fragment.lower() in away_name.lower():
            return team, odds
    return None, None

def build_table(all_events):
    now = datetime.now().strftime("%H:%M:%S")

    table = Table(
        title=f"[bold cyan]2026 NCAA TOURNAMENT — LIVE F10 TRACKER[/bold cyan]  [dim]{now}[/dim]",
        box=box.ROUNDED, border_style="cyan", header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Game",        width=32)
    table.add_column("Score",       justify="center", width=10)
    table.add_column("Clock",       justify="center", width=9)
    table.add_column("Race to 10",  width=36)
    table.add_column("Bet",         width=28)

    for event in all_events:
        comp   = event['competitions'][0]
        status = event['status']['type']['name']
        desc   = event['status']['type']['description']
        clock  = event['status'].get('displayClock', '')
        period = event['status'].get('period', 0)

        teams  = comp['competitors']
        sides  = {t['homeAway']: t for t in teams}
        home   = sides.get('home', {})
        away   = sides.get('away', {})

        home_name  = home.get('team', {}).get('shortDisplayName', '?')
        away_name  = away.get('team', {}).get('shortDisplayName', '?')
        home_score = int(home.get('score', 0))
        away_score = int(away.get('score', 0))

        game_label = f"[bold]{home_name}[/bold] vs {away_name}"
        score_str  = f"[bold]{home_score}[/bold] – [bold]{away_score}[/bold]"

        # Clock display
        if status == 'STATUS_SCHEDULED':
            clock_str = f"[dim]{event['status'].get('type', {}).get('shortDetail', 'Sched')}[/dim]"
        elif status == 'STATUS_FINAL':
            clock_str = "[green]Final[/green]"
        else:
            clock_str = f"[yellow]P{period} {clock}[/yellow]"

        # F10 race
        gid = event['id']
        f10_result = None
        race_str   = ""

        if status in ('STATUS_IN_PROGRESS', 'STATUS_FINAL'):
            plays = fetch_plays(gid)
            f10_result = extract_f10(plays)

            if f10_result:
                winner, winner_score, loser_score = f10_result
                winner_name = home_name if winner == 'home' else away_name
                race_str = f"[bold green]✓ {winner_name} wins F10![/bold green] ({winner_score}–{loser_score})"
            else:
                h = min(home_score, 9)
                a = min(away_score, 9)
                h_bar = progress_bar(h)
                a_bar = progress_bar(a)
                race_str = (
                    f"{home_name[:8]:<8} [{('green' if h >= a else 'dim')}]{h_bar}[/] {h}\n"
                    f"{away_name[:8]:<8} [{('green' if a > h else 'dim')}]{a_bar}[/] {a}"
                )
        elif status == 'STATUS_SCHEDULED':
            race_str = "[dim]Not started[/dim]"

        # Bet column
        bet_team, book_odds = bet_for_game(home_name, away_name)
        bet_str = ""
        if bet_team:
            if f10_result:
                winner, _, _ = f10_result
                winner_name = home_name if winner == 'home' else away_name
                won = winner_name.lower() in bet_team.lower() or bet_team.lower() in winner_name.lower()
                payout = (american_to_decimal(book_odds) - 1) * 6 if status == 'STATUS_FINAL' else 0
                if won:
                    bet_str = f"[bold green]✓ WON![/bold green]\n[green]+${payout:.2f}[/green] on {bet_team} F10"
                else:
                    bet_str = f"[bold red]✗ Lost[/bold red]\n[red]-$6[/red] on {bet_team} F10"
            elif status == 'STATUS_IN_PROGRESS':
                bet_str = f"[yellow]⚡ Active bet[/yellow]\n{bet_team} F10 ({book_odds})"
            else:
                bet_str = f"[dim]Bet: {bet_team} F10[/dim]\n[dim]{book_odds}[/dim]"

        table.add_row(game_label, score_str, clock_str, race_str, bet_str)

    return table

def main():
    console.print(Panel.fit(
        "[bold white]Live F10 Tracker — 2026 NCAA Tournament[/bold white]\n"
        "[dim]Polling ESPN every 15s | Ctrl+C to exit[/dim]\n"
        "[dim]Active bets: Iowa, Illinois, Purdue, Arizona, Michigan, UConn F10[/dim]",
        border_style="cyan"
    ))

    with Live(console=console, refresh_per_second=1, screen=False) as live:
        while True:
            try:
                all_events = []
                for date in DATES:
                    all_events.extend(fetch_games(date))

                # Filter to tournament games only (has plays or is scheduled)
                tourney = [e for e in all_events if e.get('competitions')]
                tourney.sort(key=lambda e: (
                    0 if e['status']['type']['name'] == 'STATUS_IN_PROGRESS' else
                    1 if e['status']['type']['name'] == 'STATUS_SCHEDULED' else 2
                ))

                if tourney:
                    live.update(build_table(tourney))
                else:
                    live.update("[dim]No tournament games found. Waiting...[/dim]")

            except Exception as ex:
                live.update(f"[red]Fetch error: {ex}[/red] — retrying in {POLL_INTERVAL}s")

            time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[dim]Tracker stopped.[/dim]")
