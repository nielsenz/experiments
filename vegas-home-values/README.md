# Las Vegas / Henderson home-price model

A hedonic model of 350 recently sold homes (closings roughly June–September 2026) across ten Las Vegas Valley areas, built from
public listing-site sold pages. It prices a home from area, size, beds, baths and attached/detached, and reports how wrong it is.

## Results

| Area | Sales | Median price | Median $/sqft | Premium vs Henderson citywide* | 2,000 sqft 3bd/2.5ba |
|---|---|---|---|---|---|
| Summerlin | 40 | $611,500 | $301 | +12.8% | $599k |
| Sun City Summerlin (55+) | 41 | $462,500 | $297 | +10.6% | $587k |
| Seven Hills | 25 | $695,000 | $281 | +8.8% | $578k |
| Anthem | 6 | $472,500 | $267 | +0.8% | $535k |
| Sun City Anthem (55+) | 41 | $470,000 | $274 | +0.6% | $534k |
| Henderson (citywide) | 35 | $422,000 | $267 | 0 | $531k |
| Silverado Ranch | 41 | $418,000 | $259 | −2.5% | $518k |
| Centennial Hills | 41 | $435,000 | $251 | −6.4% | $497k |
| Southern Highlands | 39 | $539,999 | $238 | −6.4% | $497k |
| Mountains Edge | 41 | $455,000 | $240 | −9.7% | $479k |

\*For the same size, beds, baths and type.

- **Size:** 10% more square footage adds 8.3% to price, so $/sqft falls as homes get bigger. Comparing a 1,600 sqft home with a
  3,000 sqft one on $/sqft overstates the big one by about 10%.
- **An extra bath adds ~5%; an extra bedroom at the same square footage subtracts ~2%; attached units sell ~15% lower.**
- **Accuracy (5-fold cross-validation):** median error 10.2%, 80% of sales within 20%. An 80% range around any estimate runs from
  −16% to +27%. A plain area-median $/sqft rule scores 11.7%, so the model is a modest improvement, not a breakthrough.
- **Seven Hills is the hardest area to price (15% median error).** Two homes on the same street with the same 2,123 sqft floor plan
  sold for $538,900 and $743,000. Lot, view, pool, gate and remodel status drive that spread and none of them are in listing-card data.

## Limits

- Listing cards only: no lot size, year built, pool, view, or condition; sale dates for only some rows, so no time trend.
- One page (about 40 sales) per area; the areas are the ones whose pages could be read, not a designed sample. Estates over $2.5M
  or 6,000 sqft are excluded.
- Clark County's bulk assessor file, which has the missing fields, is a paid subscription. Adding it is the single biggest upgrade.

## Use

```
python src/hedonic_model.py                              # fit, validate, write results/
python src/hedonic_model.py "Seven Hills" 2400 4 3       # estimate + 80% range
```

Outputs: `results/area_table.csv`, `results/model.json` (coefficients and error bands), `results/sales_with_cv_predictions.csv`.
