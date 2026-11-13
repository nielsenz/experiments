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

133 regular-season home games: 2023-24 to 2025-26 (123 games) and 2026-27 through Nov. 11 (10 games).

**Capped era, 2023-24 to 2025-26.** Every game was announced above the 17,367 fixed seats, so the gate barely moves.

- Season averages slid each year: 18,139, then 17,975, then 17,929.
- The range across 123 games was 17,564 to 18,724, with a standard deviation of 240 (1.4% of fixed seats).
- OLS on opponent and calendar flags plus season levels explains 55% of the variance (adjusted 51%). Leave-one-out error is 175 seats, against 227 for a season-mean baseline.

| Effect | Seats | t |
| --- | --- | --- |
| Home opener | +626 | 6.1 |
| Holiday week (Dec. 23 to Jan. 2) | +276 | 4.5 |
| Friday or Saturday | +188 | 5.3 |
| February to April | +176 | 5.2 |
| Original Six opponent | +146 | 3.3 |
| Canadian opponent | -93 | -2.4 |
| Pacific Division opponent | +73 | 2.0 |
| Sunday | +47 | 0.9 |
| 2024-25 vs 2023-24 | -167 | -4.4 |
| 2025-26 vs 2023-24 | -207 | -5.5 |

**2026-27, after the team cut sales to ticket brokers.** The gate now shows real variation.

- Average attendance is 17,055 through 10 games, down 4.9% from 2025-26. Six of the 10 were below fixed seats.
- Games ran an average of 851 seats below what the capped-era model expected, and as much as 1,821 below (Oct. 8 against Toronto, 15,977).
- The weekend premium is far larger than the capped era showed: Friday and Saturday games averaged 17,360 against 16,655 for Monday to Thursday, a gap of 705 seats. The same gap was 154 seats in 2023-24 to 2025-26. This rests on 4 weekend and 5 midweek games, so it is an early signal.
- Reading: the old announced numbers hid a soft midweek. Weak dates were being absorbed by brokers and by price, not by the gate. `results/vgk_2026_27_vs_model.csv` has the game-by-game gaps.

## What is missing

- **Prices.** This is not yet a price model. No free historical source of Golden Knights resale or face prices was reachable from the build environment. The useful next data is a per-game get-in price and median listing price, captured on a schedule before each home game.
- **Earlier seasons.** 2017-18 to 2022-23 game logs are not in the data yet. They would show whether the opponent and calendar effects were stable before 2023-24. (2019-20 was cut short and 2020-21 ran under capacity limits, so those two need separate handling.)
- **The rest of 2026-27.** Ten games is a small sample. Refresh `data/vgk_home_games.csv` as the season goes on; this is the first season where attendance itself can be modeled.
- **Full-season NBA attendance.** The market model uses 2026-27 through Nov. 11, 2026 (4 to 7 home games a team). Rerun with a full season.

## Data

| File | Contents | Source |
| --- | --- | --- |
| `data/nba_market_attendance.csv` | 29 U.S. NBA teams: metro population, average home attendance, count of MLB/NFL/NBA/NHL teams in the metro | NBA attendance file through Nov. 11, 2026; Census July 2025 metro estimates; team counts tallied by hand |
| `data/vgk_home_games.csv` | 133 Golden Knights regular-season home games with announced attendance | Hockey-Reference team game logs, 2023-24 to 2026-27 (through Nov. 11, 2026) |

Checks: the 2024-25 game log averages 17,975, matching the figure LVSportsBiz reported for that season, and its 29 home wins match the team's 29-9-3 home record.

## Caveats

- Announced attendance is tickets distributed, not people in the building.
- The opponent groups are hand-assigned and overlap (Toronto and Montreal are both Original Six and Canadian).
- Ten terms on 123 games is a small sample. Treat effects under about 100 seats as noise.
- Toronto is excluded from the NBA market model. Sacramento is counted as a one-team market although the A's play there through 2027.
