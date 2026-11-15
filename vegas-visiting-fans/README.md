# Vegas visiting fans

Does the share of out-of-town fans in a Las Vegas crowd fall as a team plays more dates, and what does that mean for the A's
plan of 30% visitors across 81 home games?

Built from 39 events with a reported out-of-town share (Las Vegas Stadium Authority quarterly reports, as published by the
Review-Journal, LVSportsBiz, KSNV and others), plus estimates and plans for the Golden Knights and the A's.

## Answer

**The measured data does not show a date-count curve.** Every measured event sits between 1 and 10 dates a year, and across
that range the share barely moves. The only evidence that a 41-date team draws far fewer visitors is the Golden Knights
figure, which is an estimate (15 to 25%), not a measurement.

**What the data does support is a statement about counts:**

| | Dates | Visitor tickets a year | Local tickets a year | Visitors per date | Locals per date |
|---|---|---|---|---|---|
| Raiders 2025 (measured) | 10 | 339,000 | 208,000 | 33,900 | 20,800 |
| Golden Knights 2025-26 (estimated 15 to 25% visitors) | 41 | 110,000 to 184,000 | 551,000 to 625,000 | 2,700 to 4,500 | 13,400 to 15,200 |
| A's plan (30% of a 29,400 sellout) | 81 | 714,000 | 1,667,000 | 8,820 | 20,580 |

- The A's plan needs **2.1 times the Raiders' visitor tickets**, and 1.4 to 1.6 times the Raiders and Golden Knights combined.
- It needs **2.0 to 2.2 times the local tickets** the Raiders and Golden Knights sell between them.
- Per game, it needs 2.0 to 3.3 times the visitors a Golden Knights game is estimated to draw.
- The Raiders average 20,072 locals at a regular-season game (range 14,235 to 24,645, 13 games). The A's plan needs 20,580
  locals, 81 times a year.

**The local ask is ordinary by MLB standards; the visitor ask is the part without a precedent.** The plan's local tickets come
to 0.69 per resident. Eight one-team MLB metros of 1.3 to 3.1 million people sold 0.63 to 1.68 total tickets per resident in
2025 (median 0.79). With visitors included the plan is 0.99 per resident, which would rank third of 13 one-team metros, behind
Milwaukee and San Diego.

**If locals show up as planned and visitors arrive at the Golden Knights' estimated count**, the A's draw 23,300 to 25,100 a
game, not 29,400, and sell 218,000 to 363,000 visitor tickets a year: 351,000 to 497,000 short of plan. The park is not empty
in that case. What is missing is the tourism the public money was justified by.

**The best case for the plan:** baseball is played in series. If a visiting fan attends two or three games per trip, 714,000
visitor tickets is 238,000 to 357,000 trips, about what the Raiders already generate (339,000 visitor tickets, one game per
trip). And the last forecast of this kind was too low: the stadium authority expected 27% visitors at Allegiant Stadium events
and got 40 to 49% in 2022.

![Out-of-town share by kind of event](results/out_of_town_share.png)

## What was checked

**1. Share by kind of event** (`results/share_by_kind.csv`)

| Kind | Events | Mean | Range |
|---|---|---|---|
| National Finals Rodeo | 1 | 88.5% | reported as 87 to 90% |
| One-off sports events | 7 | 73.6% | 58 to 87% |
| Stadium concerts | 14 | 69.1% | 54 to 83% |
| Raiders, regular season | 14 | 64.3% | 54 to 76% |
| Raiders, preseason | 3 | 51.0% | 45 to 58% |

**2. Share against dates per year** (`results/curve_fit.json`, `results/curve_predictions.csv`)

A logit fit of share on log(dates per year), with a bootstrap that resamples whole properties so that 17 Raiders games do not
count as 17 independent points.

- Slope: -0.14 per log date. The 80% interval is -0.28 to +0.56, so the sign is not established.
- Extrapolated far outside the data, the fit gives 61% at 41 dates and 58% at 81 dates (80% intervals 54 to 94% and 50 to 96%).
- Dropping preseason games, the rodeo, or both moves the 81-date figure between 54% and 64%.
- The Golden Knights estimates (15 to 25%) were held out. The fit misses them by about 40 points. Date count is not what
  separates the Golden Knights from the Raiders. A resident team built on about 14,000 season tickets is a different kind
  of property from a destination event, and no destination-style property in the data plays more than 10 dates.

**3. Raiders game by game** (`results/raiders_games.csv`, `results/raiders_game_model.csv`)

- Visitors drive the gate. Across 13 regular-season games, attendance correlates +0.63 with the out-of-town share and -0.21
  with the local count. Locals are steady near 20,000; visitors swing from 27,500 to 45,100.
- Preseason games run 22 points lower (t = -3.4, 3 games): 14,000 fewer visitors and 11,300 more locals.
- December and January games run 7.7 points lower (t = -2.0, 4 games), about 7,500 fewer visitors.
- Monday night games show no difference (3 games). An NFL Monday night game is a national event, so this says nothing about a
  Tuesday in May.

**4. Tickets per resident, MLB** (`results/mlb_tickets_per_resident.csv`)

13 one-team MLB metros, 2025 attendance over July 2025 metro population. The peer band of 1.3 to 3.1 million matches the one
used in `../vegas-nba-demand`.

**5. A's scenarios** (`results/as_scenarios.csv`)

Three local cases (plan, peer low, peer median) crossed with four visitor cases (Golden Knights count at 15% and 25%, the
plan's 16% incremental-only visitors, the full plan), capped at 33,000.

## What is weak

- **No measured share exists above 10 dates a year.** The Golden Knights number is the whole case for a low share at high
  frequency, and it comes from three statements: 25% (former LVCVA chief, 2018), 15 to 20% (Applied Analysis, 2021), and a
  team target of 10 to 15% (2017). None is survey or ZIP-code data. One measured Golden Knights season would settle more than
  everything in this folder.
- **Reporting is selective.** Press coverage of each quarterly report names the best-attended events, so high-draw games are
  over-represented. The season averages (63%, 68%, 62% for 2023 to 2025) are the unbiased Raiders figures; the game-level mean
  of 64% agrees with them.
- **The A's 30% is a planning assumption** from a traffic study and legislative testimony, on a 98% sellout basis. A second
  version of the plan says 27%.
- **"Out of town" is self-reported or ZIP-based residence**, not rooting interest. Aguero describes Raiders crowds as roughly a
  third locals, a third Raiders fans from elsewhere and a third visiting-team fans.
- **Peer tickets per resident include visitors** in those markets, so the comparison slightly flatters the peers.
- **Some dates are not from the attendance sources.** The Sept. 15 and Sept. 28, 2025 dates come from the NFL schedule, and 15
  events are known only by quarter. The 2025 game against the 49ers is treated as preseason because the quarter held one
  preseason game and the 49ers were not a regular-season home opponent. See the `date_basis` column.
- **WrestleMania** is entered once at half its two-night attendance with the two-night average share.
- **Two Beyonce 2025 attendance figures** were reported without saying which night each belonged to, so they are left blank.
- UFC (88%) is shown in `data/benchmarks.csv` but not fitted, because no count of dates per year was sourced.

## Correction to the first pass

The first version of this idea was a four-row table (UFC, Raiders, Golden Knights, A's) read as a curve: more dates, lower
share. Three of those rows were measured or planned; the Golden Knights row was an estimate, and it was carrying the
conclusion. With 39 measured events the curve does not appear. The claim that survives is about ticket counts, above.

## Data

| File | Contents | Source |
|---|---|---|
| `data/events.csv` | 39 events: date, venue, kind, dates per year, attendance, out-of-town share | Stadium Authority quarterly reports via the Review-Journal, LVSportsBiz, KSNV, casino.org and casinos.com; `source` column per row |
| `data/benchmarks.csv` | Golden Knights estimates, A's plan, UFC, the Allegiant forecast against its 2022 result | Press, cited per row |
| `data/raiders_seasons.csv` | Raiders season totals and out-of-town share, 2023 to 2025 | Review-Journal |
| `data/mlb_markets_2025.csv` | 13 one-team MLB metros: 2025 attendance and July 2025 metro population | Baseball-Reference 2025 league page; Census estimates |

Stadium Authority attendance is scanned tickets, not announced attendance. Golden Knights attendance (17,929) is announced,
from `../vegas-nba-demand`.

Checks: Baseball-Reference and ESPN team totals agree to within 0.1% for all 13 metros except Cincinnati (0.6%). Metro
populations match the figures already used in `../vegas-nba-demand`. Weekdays are computed from the dates, and the three
Monday games match the Monday Night Football schedule.

## Reproduce

```bash
python3 src/01_visiting_fans.py
python3 src/02_chart.py
```

Requires `pandas`, `numpy`, `matplotlib`.

## What would make this better

- The Stadium Authority's quarterly activity reports themselves (PDFs in board meeting packets). They list every ticketed
  event, which removes the selection problem and roughly doubles the Raiders sample.
- Any measured out-of-town share for the Golden Knights, Aces or Aviators.
- The 2026 Raiders season, when the fourth-quarter report is out in early 2027.
- The A's first season of deposits by ZIP code, if the team or the authority publishes it.
