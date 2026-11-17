# Las Vegas / Henderson outlook: housing and water scenarios

Two small models behind a 5/10/15-year outlook for living in the Las Vegas Valley (written November 16, 2026).
Both are scenario models with stated assumptions, not fitted forecasts.

```bash
python3 src/housing_scenarios.py   # price history, scenario bands, affordability
python3 src/water_budget.py        # Colorado River demand vs. possible caps to 2041
```

Requires `pandas` and `numpy`.

## Housing (`src/housing_scenarios.py`)

**History.** Las Vegas Realtors' median single-family resale price at 14 dated points (`data/lvr_median_anchors.csv`):

- $124,800 in 1997 to $475,000 in October 2026 is 4.7% a year. From the June 2006 peak it is 2.0% a year; from the May 2022 peak, -0.3%.
- The 2006 peak ($315,000) fell 62.5% to $118,000 in January 2012 and was not regained until February 2020, 13.7 years later.

**Scenarios.** Annual log price change follows an AR(1) process: persistence 0.6, standard deviation 10%, starting from
this year's +0.1%. Drift is 1.0% (downside), 3.0% (base) or 4.5% (upside). 200,000 paths each, nominal dollars, metro median.

| Scenario | 5 years: P10 / P50 / P90 | 10 years | 15 years | P(below today's $475k at 10 years) |
|---|---|---|---|---|
| Downside (1.0%) | $322k / $492k / $758k | $256k / $517k / $1.05M | $219k / $544k / $1.36M | 44% |
| Base (3.0%) | $346k / $529k / $815k | $303k / $613k / $1.25M | $287k / $713k / $1.78M | 32% |
| Upside (4.5%) | $366k / $559k / $860k | $344k / $697k / $1.42M | $352k / $873k / $2.18M | 24% |

- The bands are wide because the volatility is set to look like Las Vegas' own past. With a calmer 7% standard deviation the
  base case at 10 years is $375k / $614k / $1.00M and the chance of sitting below today's price is 25% (`results/base_sensitivity.csv`).
- In the base case there is a 21% chance of a 20% drop from a running peak within 5 years and 40% within 10.
- The drift does most of the work on the median and is an assumption. 3% is roughly inflation; it is below the 4.7% of
  1997-2026 because UNLV CBER now expects population growth to slow from 1.6% to about 0.6% a year by 2029.

**Affordability.** Principal and interest on the $475,000 median with 20% down is $2,574 a month at 7.18% (Freddie Mac, Nov. 5,
2026), against $2,332 at the 6.22% of a year earlier. The same payment would carry a $537,000 home at 6.0% and $599,000 at 5.0%.

## Water (`src/water_budget.py`)

Demand = Clark County population (UNLV CBER 2026 forecast) x Colorado River consumptive use per resident, on three paths,
from two starting points (2025's 198,000 AF or 2024's 212,000 AF). Inputs: `data/water_inputs.csv`.

| Start | Per-resident path | 2031 | 2036 | 2041 | First year over 250k AF | First year over 210k AF |
|---|---|---|---|---|---|---|
| 2025 use | Conservation goal met (95 to 86 GPCD by 2035) | 198k | 197k | 203k | never by 2041 | never by 2041 |
| 2025 use | Flat | 209k | 218k | 224k | never by 2041 | 2032 |
| 2025 use | Rises 10 GPCD | 223k | 241k | 247k | never by 2041 | 2028 |
| 2024 use | Conservation goal met | 215k | 214k | 220k | never by 2041 | already over |
| 2024 use | Flat | 228k | 237k | 244k | never by 2041 | already over |
| 2024 use | Rises 10 GPCD | 242k | 262k | 269k | 2033 | already over |

- No path reaches the full 300,000 AF apportionment by 2041.
- The 250,000 AF allocation set for 2027-2028 holds through 2041 on five of six paths.
- A deeper cut to 210,000 AF (a hypothetical 30%) would bind within a few years unless per-resident use keeps falling.

## Limits

- Price anchors are medians reported in news coverage of Las Vegas Realtors data, not a repeat-sales index; the FHFA index
  could not be downloaded from this environment.
- The price process has no explicit link to mortgage rates, jobs or water; those enter only through the choice of drift.
- The water model covers Colorado River consumptive use only: no groundwater, banked water, or temporary supplies, and the
  2024-2025 population figures are back-cast from CBER's 2026 estimate.
