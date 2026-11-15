# Vegas visiting fans

Does the share of out-of-town fans in a Las Vegas crowd fall as a team plays more dates, and what does that mean for the A's
plan of 30% visitors across 81 home games?

Third version. Built from the Las Vegas Stadium Authority's own quarterly activity reports: 96 Allegiant Stadium events from
October 2022 to May 2026, each with scanned attendance, the surveyed out-of-town share and the share of those visitors who said
the event was their main reason for the trip. The first version used 39 events picked up from press coverage.

## Answer

**1. There is no date-count curve in Las Vegas data, and inside concerts it runs the other way.** Acts that play more nights
draw a higher visitor share: 66% for one-night concerts (18), 75% for two-night runs (14), 83% for the one four-night run.
Longer runs are booked for acts people travel to see. What sets the share is the kind of event, not how often it happens.

**2. The Raiders' local crowd is close to a constant.** Across 30 regular-season games in four seasons, locals in the building
average 19,720 with a standard deviation of 2,361. Opponent, weeknight, December and season do not move it. Visitors do all the
moving (27,500 to 45,100), and attendance tracks the visitor share (+0.64) and not the local count (-0.26).

**3. The best-supported visitor count for an A's game is about 5,200, with a plausible range of 2,500 to 10,500. The plan
needs 7,900 to 8,800.** An earlier version of this page called the plan "about twice any measured benchmark", resting on two
numbers near 4,500 (a Golden Knights estimate and the Brewers' out-of-state share). That was too strong: the Cubs report 37%
of fans from outside Illinois, about 13,800 a game. The count is rebuilt below from two channels, each with its own data.

| Channel | Low | Central | High | Plan |
|---|---|---|---|---|
| Came to Las Vegas because of the game | 1,400 | 2,300 | 4,800 | 4,200 to 4,700 |
| Already in town, added a game | 1,000 | 2,900 | 5,700 | 3,700 to 4,100 |
| **Visitors per game** | **2,500** | **5,200** | **10,500** | **7,900 to 8,800** |

- *Came because of the game* is bounded with nine seasons of MLB game logs (21,546 games): the attendance that depends on who
  the visiting team is. Low is league-average sensitivity on an A's schedule, central is the most opponent-sensitive quarter of
  parks, high is the most opponent-dependent park in the majors, which was the A's own in Oakland.
- *Already in town* uses the Allegiant surveys: out-of-town attendees who said the event was not their main reason for the trip.
  Low is a lower-quartile concert, central the median of all 96 events, high an upper-quartile Raiders game.
- The plan is reachable only if both channels run near the top of what has been observed: opponent dependence as high as
  Oakland's, and a walk-up tourist crowd on every one of 81 dates as large as a Raiders game gets on ten.
- Against the tourist pool the ask is small: about 338,000 visitors are in town on an average night, so the plan is 2.4 to
  2.6% of them. That is the real argument for it, and nothing measured elsewhere tests it, because no other MLB city has a
  visitor pool that size relative to its own population.

**4. The plan's incremental-visitor assumption is cautious; its visitor count is the stretch.** The plan counts 53% of
visitors as people who came to Las Vegas for the game. At Raiders games 86.5% say the game was their main reason, and across
all 96 events the figure is 90% and never below 72%. In the build-up above, the came-for-the-game channel yields 116,000 to
387,000 visitors a year, centred on 189,000, against the 341,000 the plan implies for its 81 games (405,000 across all 95
planned events).

**5. In favor of the plan:** the first real sales data. The A's sold out their top club (about 300 seats) with 76% of buyers
from Southern Nevada, so 24% from elsewhere. Those are buyers of the most expensive seats, not attendees, but it is the only
number so far that is not a forecast, and it is near 30%. Baseball series also let one trip use two or three tickets: 643,000
to 714,000 visitor tickets is 214,000 to 357,000 trips, against the Raiders' 344,000. And the last forecast of this kind ran
low: 27% expected at Allegiant, 40 to 49% delivered in 2022.

![Out-of-town share by kind of event](results/out_of_town_share.png)

## What was checked

**Share by kind of event** (`results/share_by_kind.csv`)

| Kind | Events | Out of town | Range | Came mainly for the event | Visitors per event | Locals per event |
|---|---|---|---|---|---|---|
| Wrestling, boxing, rugby | 7 | 80.6% | 74 to 85% | 96% | 40,800 | 9,400 |
| College football one-offs | 9 | 74.9% | 64 to 87% | 86% | 30,500 | 8,600 |
| Concerts | 36 | 71.5% | 42 to 89% | 94% | 34,800 | 13,500 |
| Raiders, regular season | 30 | 64.6% | 54 to 76% | 87% | 36,300 | 19,700 |
| Soccer | 10 | 55.5% | 42 to 68% | 83% | 20,500 | 15,500 |
| Raiders, preseason | 4 | 52.8% | 45 to 58% | 87% | 28,400 | 25,500 |

**Share against dates per year** (`results/curve_fit.json`, `results/curve_predictions.csv`,
`results/concert_share_by_run_length.csv`). Logit fit on log(dates), bootstrapped by run, annual event or Raiders season (54
clusters).

- All 96 events: slope -0.10, 80% interval -0.16 to 0.00. Stretched to 81 dates it gives 61%. That slope is the Raiders against
  everything else, nothing more.
- Concerts alone: slope +0.60, 80% interval +0.36 to +0.81.
- The four-night figure is one run (BTS, 2026), and every 2026 event in the data is a multi-night run in a strong quarter, so
  run length and year cannot be separated. One-night against two-night (18 and 14 events) is the solid part.

**Raiders game model** (`results/raiders_game_model.csv`, `raiders_by_season.csv`, `raiders_by_opponent.csv`). 34 games.

| Effect | Out-of-town share | Visitors | Locals |
|---|---|---|---|
| Preseason | -12.8 pts (t = -4.0) | -8,200 | +6,500 |
| Monday or Thursday night (5 games) | 0.0 pts | +1,300 | +900 |
| December or January | -2.2 pts (t = -0.9) | -2,800 | +100 |
| Division opponent | -0.2 pts | +700 | +600 |
| 2025 season against 2022 | -2.1 pts (t = -0.6) | -2,400 | +300 |

- Opponent is what matters: Vikings, Chiefs and Steelers games ran 70 to 74%, Giants, Chargers and Texans games 58 to 60%.
- 2025 had the lowest season share (62.8% against 65 to 66%) and the fewest visitors per game (34,800 against 36,200 to
  37,100), in the year Las Vegas visitation fell 7.5%. The difference is within noise for eight games.
- The share of visitors naming the game as their main reason slid each season: 89, 88, 86, 84%.

**Non-NFL events** (`results/non_nfl_model.csv`, `non_nfl_midweek.csv`). 62 events.

- Monday-to-Thursday events run 5.7 points lower (t = -1.6, 10 events), but midweek concerts draw the same visitor count as
  weekend ones (35,000 against 34,800). Two BTS nights on a Wednesday and Thursday drew 84% and 78%.
- June to August shows no difference.
- Soccer is the most local product in the building: 19 points below the baseline (t = -3.3).

**Other markets and the A's own numbers** (`data/benchmarks.csv`)

- Brewers: 14% of attendees from out of state, from team ticket data, and 41% of those stayed overnight. On 2025 attendance
  that is 371,000 out-of-state tickets and about 152,000 overnight. Milwaukee is 90 minutes from Chicago. Las Vegas has no
  comparable drive-in market closer than Southern California.
- A's legislative case: 2.6 million a year over 95 events, 30% from out of town, 53% of those incremental, 405,000 incremental
  visitors a year. A public comment in the Stadium Authority's August 2024 agenda book derives 26,476 a game and 4,210
  incremental visitors a game from that; the same arithmetic reproduces here.

## The visitor benchmark, tested four ways

`src/03_opponent_effects.py`, `src/04_benchmark.py`, `results/visitor_benchmark_*.csv`

**1. Other MLB markets** (out-of-state attendees per game, on 2025 attendance)

| Team | Share | Per game | Basis |
|---|---|---|---|
| Brewers, out of state | 14% | 4,600 | team ticket data |
| Brewers, out of state and overnight | 5.7% | 1,900 | 41% of the above, survey |
| Pirates, out of state | about 30% | 5,600 | impact study, seen only second-hand |
| Cubs, outside Illinois | 37% | 13,800 | team marketing figure, 2011 |

Out-of-state counts in MLB run from 4,600 to 13,800. The plan sits inside that range, above Pittsburgh and below Wrigley
Field. Most of the Milwaukee and Pittsburgh figure is drive-in fans from Chicago, Ohio and West Virginia. Las Vegas has four
opponents within 350 miles (Dodgers, Angels, Padres, Diamondbacks), who account for 11 of 81 home games on a balanced schedule.

**2. Opponent-attributable attendance, 30 parks** (`results/opponent_attributable_by_park.csv`)

A game-level model of log attendance on home-team season, each home team's own weekday pattern, month, home opener and
distance, 2015 to 2019 and 2022 to 2025. For each park, opponent effects are shrunk toward zero by sample size, and the
attendance above what the park draws against its 10th-percentile opponent is counted as opponent-attributable.

- League-wide, the visiting team moves attendance from -6% (Marlins) to +21% (Yankees). The top five draws are the Yankees,
  Dodgers, Cubs, Red Sox and Mets.
- An opponent within 150 miles adds 8.8% (t = 12.4); one 150 to 350 miles away adds 2.5% (t = 5.9).
- Opponent-attributable attendance: median park 1,800 a game (7.1% of the gate), highest count 3,400 (Seattle), highest share
  18.7% (Oakland, 3,000 a game). Miami is next at 14.4%. Fenway, Wrigley and Dodger Stadium are at 1 to 2% because they sell
  out regardless.
- On a Las Vegas schedule: 1,400 to 1,600 a game at league-average sensitivity, 2,300 to 2,600 for the top quarter of parks,
  4,300 to 4,800 at Oakland's level.

What this number is: tickets sold against a strong-drawing opponent that are not sold against a weak one. It includes residents
who follow the visitor, which in a city of transplants is a large group and counts as local in the 70/30 split. It excludes
any visiting fans who would come whoever the opponent is. So it is neither a clean ceiling nor a floor; it is the size of the
part of a baseball crowd that responds to the opponent, and the plan's came-for-the-game figure (4,200 to 4,700) equals the
largest value in the majors.

**3. Tourists already in town** (Allegiant surveys)

Out-of-town attendees who did not name the event as their main reason for the trip:

| | Lower quartile | Median | Upper quartile | Maximum |
|---|---|---|---|---|
| Raiders regular season (30) | 3,900 | 4,700 | 5,700 | 7,900 |
| Concerts (36) | 1,000 | 2,000 | 2,800 | 3,900 |
| All 96 events | 1,600 | 2,900 | 4,300 | 10,900 |

A median Raiders game picks up 4,700 such visitors, 1.4% of everyone in town that night. The plan needs 3,700 to 4,100 at every
game, 1.1 to 1.2%.

**4. Top-down from the LVCVA visitor survey** (2025: 38.5 million visitors, 3.2 nights, n = 5,409)

- 5% of visitors attended a sporting event (1.93 million people) and 3% came mainly for one (1.16 million). Surveyed Allegiant
  sports events alone account for 608,000 of the 1.93 million.
- If each A's visitor attends one game, the plan adds 33 to 37% to all visitor sports attendance in Las Vegas. At two games
  each, 17 to 19%.
- Its came-for-the-game visitors equal 29 to 33% of everyone who now comes to Las Vegas mainly for sport (15 to 16% at two
  games each). Its already-in-town visitors equal 39 to 44% of everyone who now attends a sporting event without having come
  for it.
- The survey cannot referee this. Its sampling margin on the 5% is 0.6 points, or 224,000 people, it is reported in whole
  percents (one point is 385,000 people), and it has read 6, 6, 4 and 5% over the last four years with no change in the sports
  calendar large enough to explain the swings. The A's entire visitor target is under two points.

## What is weak

- **Still no surveyed share for any Las Vegas team above 10 dates.** The Golden Knights range is three statements (25% in 2018,
  15 to 20% in 2021, a 10 to 15% target in 2017), none of them survey or ZIP data. T-Mobile Arena is privately owned and files no
  such report.
- **The channel build-up mixes sports and sources.** Its low, central and high values are picked from observed distributions,
  not fitted, and the two channels are added as if independent. Treat 5,200 as the middle of a wide range, not a forecast.
- **Sellout parks hide opponent effects,** so league-wide sensitivity is understated for strong home markets. Las Vegas would
  not be one of those in its early years.
- **The Cubs figure is a 2011 team marketing number** reported in the press, and the Pirates figure reached this page second-hand.
- **The Brewers figure is out of state, not out of metro,** and comes through a consultant study and legislative testimony, not
  a published table. In Milwaukee the gap between the two definitions is large (about half of fans are Wisconsinites from
  outside Milwaukee County). In Las Vegas it is small, which is why out of state is the nearer match to a Las Vegas visitor.
- **Peer tickets per resident flatter the peers** for the same reason: their totals include that drive-in hinterland.
- **"Main reason for travel" is asked of people who already said they were from out of town,** by the stadium operator. It is
  not the same thing as the plan's incremental visitor, though it is the closest measured quantity.
- **Out of town is residence, not rooting interest.** Applied Analysis describes Raiders crowds as about a third locals, a third
  Raiders fans from elsewhere and a third visiting-team fans.
- **Gaps in the reports.** Q1 2023 was not found on the authority's site and the Q1 2026 PDF did not extract as text, so the
  January 2023 and January 2026 Raiders games are missing. Reports before Q4 2022 carry no out-of-town column. UNLV games, high
  school events and open practices have no survey and are left out, as is the Super Bowl.
- **Raiders 2025 annual figures** scale nine surveyed games to ten dates.
- **Golden Knights attendance is announced,** and the team says earlier seasons' figures included broker-held tickets.
- The data was read from the PDFs through a text extraction step. NFL attendance by quarter was checked against the reports'
  own summary table for five quarters and matched exactly; the script asserts this on every run.

## Corrections

- **First idea (a four-row table read as a curve):** the Golden Knights estimate was carrying the conclusion.
- **First version of this folder (39 press-sourced events):** reported a December-and-January drop of 7.7 points (t = -2.0) in
  Raiders games. With all 34 games it is -2.2 points and not distinguishable from zero. Press coverage named the best-attended
  games, which made late-season games look worse than they are. That version also had two Coldplay nights swapped and the 2025
  Las Vegas Bowl attendance off by 100; both are fixed from the source.
- **Second version ("about twice any measured benchmark"):** rested on the Brewers and a Golden Knights estimate. The Cubs
  exceed the plan's count, so the claim is withdrawn and replaced by the channel build-up.
- **Incremental visitors:** the first version used 16% of attendance (381,000 a year). The plan's own figures are 53% of
  visitors and 405,000 a year over 95 events.

## Data

| File | Contents | Source |
|---|---|---|
| `data/events.csv` | 96 events: date, kind, nights in the run, attendance, out-of-town share, main-reason share, report quarter | Las Vegas Stadium Authority, Stadium Activity Reporting (Section 7.4), Q4 2022 to Q2 2026, at lvstadiumauthority.com/meetings |
| `data/benchmarks.csv` | Golden Knights estimates, A's plan and club sales, Brewers, UFC, rodeo, the Allegiant forecast against 2022 | Press and public documents, cited per row |
| `data/mlb_markets_2025.csv` | 13 one-team MLB metros: 2025 attendance, July 2025 metro population | Baseball-Reference; Census |
| `data/mlb_games_attendance.csv.gz` | 24,295 MLB games, 2015 to 2025 without 2020: date, teams, park, attendance | Retrosheet game logs (GitHub mirror, chadwickbureau/retrosheet) |

The information used here was obtained free of charge from and is copyrighted by Retrosheet. Interested parties may contact
Retrosheet at www.retrosheet.org.

## Reproduce

```bash
python3 src/01_visiting_fans.py
python3 src/02_chart.py
python3 src/03_opponent_effects.py
python3 src/04_benchmark.py
```

Requires `pandas`, `numpy`, `matplotlib`.

## What would make this better

- A Golden Knights, Aces or Aviators out-of-town share from ticketing ZIP codes. T-Mobile Arena has reported using purchase ZIP
  codes since 2018.
- The A's general season-ticket and deposit list by residence. The team says the list is over 20,000.
- Q1 2023, Q1 2026 and Q3 2026 activity reports, which add the two missing January games and the start of the 2026 season.
- The same Section 7.4 reporting for the ballpark from 2028. The authority's October 2024 minutes suggest matching reporting
  requirements for the ballpark, in which case the A's share would be measured from the first homestand.
