# Vegas NBA demand

Two questions about an NBA expansion team in Las Vegas:

1. How many fans would it draw, judged against NBA markets of similar size?
2. How does Las Vegas demand respond to opponent, day and calendar, judged from Golden Knights game-level attendance?

Run from this folder:

```bash
python3 src/01_market_model.py
python3 src/02_vgk_game_model.py
```

Requires `pandas`, `numpy`, `matplotlib`.

## Findings

### 1. Market model (`src/01_market_model.py`)

- The 12 NBA teams in metros of 1.3 to 3.1 million people have a median average attendance of 18,219 (middle half: 16,402 to 19,088).
- A league-wide fit of attendance on log metro population puts Las Vegas (2.41 million) at 17,590, with an 80% prediction interval of 15,307 to 19,872. The fit is weak: R² is 0.16.
- Only two teams average 20,000 or more (76ers, Bulls). An 18,000-seat arena matches projected demand; 20,000 to 25,000 seats does not.
- Filling 18,000 seats for 41 games takes 738,000 tickets. With a 25% visitor share, residents buy 0.23 tickets each per season, against 0.49 in Oklahoma City and 0.56 in Salt Lake City.
- With the A's and an NBA team in 2028, Las Vegas would have about 602,000 residents per MLB/NFL/NBA/NHL team. Only New Orleans is lower among NBA markets.

### 2. Golden Knights game model (`src/02_vgk_game_model.py`)

82 regular-season home games, 2024-25 and 2025-26.

- Announced attendance barely moves. Every game was above the 17,367 fixed seats, the range was 17,564 to 18,393, and the standard deviation was 193 (1.1% of fixed seats).
- Within that narrow band the pattern is clear. OLS on nine flags explains 52% of the variance (adjusted 46%). Leave-one-out error is 152 seats, against 195 for a season-mean baseline.

| Effect | Seats | t |
| --- | --- | --- |
| Home opener | +570 | 5.4 |
| Holiday week (Dec. 23 to Jan. 2) | +225 | 4.1 |
| February to April | +182 | 5.1 |
| Original Six opponent | +140 | 3.0 |
| Friday or Saturday | +131 | 3.6 |
| Canadian opponent | -91 | -2.3 |
| Pacific Division opponent | +48 | 1.3 |
| Sunday | +40 | 0.7 |
| 2025-26 season | -43 | -1.3 |

- The gate count shows the direction of demand, not its size. In a building that reports itself full every night, the difference between a strong and weak date shows up in price, not attendance.
- The announced numbers also overstated demand. In October 2026, after the team cut sales to ticket brokers, a home game drew 15,977 and the sellout streak ended at 377 games. Broker-held tickets had been counted as attendance.

## What is missing

- **Prices.** This is not yet a price model. No free historical source of Golden Knights resale or face prices was reachable from the build environment. The useful next data is a per-game get-in price and median listing price, captured on a schedule before each home game.
- **More seasons.** Only 2024-25 and 2025-26 game logs were collected. 2017-18 to 2023-24 and the current season would show whether the opponent and calendar effects are stable, and 2026-27 is the first season where announced attendance can fall below capacity.
- **Full-season NBA attendance.** The market model uses 2026-27 through Nov. 11, 2026 (4 to 7 home games a team). Rerun with a full season.

## Data

| File | Contents | Source |
| --- | --- | --- |
| `data/nba_market_attendance.csv` | 29 U.S. NBA teams: metro population, average home attendance, count of MLB/NFL/NBA/NHL teams in the metro | NBA attendance file through Nov. 11, 2026; Census July 2025 metro estimates; team counts tallied by hand |
| `data/vgk_home_games.csv` | 82 Golden Knights regular-season home games with announced attendance | Hockey-Reference team game logs, 2024-25 and 2025-26 |

Checks: the 2024-25 game log averages 17,975, matching the figure LVSportsBiz reported for that season, and its 29 home wins match the team's 29-9-3 home record.

## Caveats

- Announced attendance is tickets distributed, not people in the building.
- The opponent groups are hand-assigned and overlap (Toronto and Montreal are both Original Six and Canadian).
- Nine flags on 82 games is a small sample. Treat effects under about 100 seats as noise.
- Toronto is excluded from the NBA market model. Sacramento is counted as a one-team market although the A's play there through 2027.
