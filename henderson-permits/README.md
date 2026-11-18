# Henderson permits

Who pulls building permits in Henderson, NV, how long they take to issue, and how many expire. Built to test a
product idea: a tool that helps small residential contractors get permits faster.

Results live in [`results/SUMMARY.md`](results/SUMMARY.md), regenerated on every run.

## Data

- **Source:** the City of Henderson's `DSC_Permits` table on its ArcGIS open data hub
  (https://gis-hendersonnv.opendata.arcgis.com/), refreshed daily by the city. About 277,000 permits since 2017.
- **`data/dsc_permits.csv.gz`** is a slim copy: permit type, work class, status, dates, working days from application to
  issuance, valuation, ZIP, and the contractor's name, state license number and phone.
- **Left out on purpose:** property-owner names and addresses, the permit's street address and parcel number, and
  free-text descriptions. This repo is public and the analysis does not need them. `fetch_permits.py --full` keeps
  everything; write that somewhere private.
- `data/manifest.json` records when the copy was taken and how many rows it has.

## What the numbers mean

- **Days** is the city's field: working days between application and issuance. It includes the applicant's own time
  (resubmitting corrections, paying fees), so it is not pure review time, and it cannot separate a bounced
  submittal from a slow payer. Correction cycles are not in this table.
- **Trades** are defined from the city's own `PermitType` / `WorkClass` values; see `TRADES` in `src/analyze.py`.
- **Contractors** are grouped by state license number where one is recorded, otherwise by cleaned-up name. Permits with
  no professional listed (mostly owner-builders) are lumped together and kept out of the rankings.
- **Expiry** only counts permits issued at least a year before the data date, so each has had time to close.
  "Expired" is the city's status; the working assumption is that it means the permit lapsed without a final inspection.

## Run

```
pip install -r henderson-permits/requirements.txt
python henderson-permits/src/fetch_permits.py     # about 5 minutes, ~280 requests
python henderson-permits/src/analyze.py
```

The `henderson-permits` workflow does the same on GitHub and commits the data and results. Run it from the Actions tab
to refresh.
