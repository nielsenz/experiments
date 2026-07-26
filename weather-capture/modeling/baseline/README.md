# modeling/baseline — first demand model

A baseline model that predicts CAISO hourly demand from a **day-ahead** weather
forecast plus calendar and lagged-demand features. This is the first model in the
project; it exists to set an honest bar, not to be state of the art.

## Run

```bash
# deps: py3-numpy py3-scikit-learn py3-matplotlib (apk)
cd weather-capture/modeling/baseline
python3 baseline_model.py
```

Outputs `baseline_summary.md` and `figures/baseline_model.png`.

## What it does

- **Label:** CAISO hourly demand (`energy/`).
- **Weather feature:** the `previous_runs` day-ahead temperature (5-city
  state average) → raw temp + cooling/heating degree-hours (base 6 °C, the EDA
  response-curve minimum). This is the as-issued forecast you'd actually hold a
  day ahead — **not** actuals.
- **Calendar:** hour, month, day-of-week (cyclical) + weekend flag.
- **Demand lags:** demand 24 h and 168 h before the target hour — both known at
  day-ahead time.
- **Split:** time-ordered, train = first 80 %, test = final 20 % (a contiguous
  block through summer 2026). No shuffling.
- **Models:** persistence and hour×month climatology baselines, plus linear
  regression and `HistGradientBoostingRegressor`.

## Firewall

Respected throughout (see `../../history/README.md`). The temperature feature is
the day-ahead forecast; demand lags are ≥ 24 h old; nothing reads the target
hour. Actuals appear only as the label and for scoring.

## Headline results (test set)

| model | MAE (MWh) | MAPE | R² |
|---|---|---|---|
| persistence (lag-24) | 1,347 | 5.16 % | 0.79 |
| climatology (hour×month) | 2,256 | 8.27 % | 0.46 |
| linear regression | 1,074 | 4.12 % | 0.88 |
| **gradient boosting** | **890** | **3.32 %** | **0.91** |

- GBR cuts MAE **34 %** vs persistence; ~**3.4 %** error on ~25.8 GW mean demand.
- **Weather ablation:** dropping day-ahead temperature raises MAE 890 → 927 MWh,
  a **~4 %** reduction attributable to the weather forecast — modest but real,
  and it validates the project's premise.
- **Importance:** `dem_lag24` dominates (demand is highly autocorrelated),
  `temp_da` is second. The trees read the temperature response straight from raw
  temp, so the hand-built degree-days come out near-zero importance here — a
  finding, not a bug (they'd matter more for the linear model).
- **Residuals** are widest and slightly low-biased in the evening/overnight peak
  hours — the classic "the peak is the hard part" pattern.

## Honest caveats / next steps

- Single contiguous test block; a rolling/backtested split would be sturdier.
- No holiday calendar yet — holidays look like anomalous weekdays.
- Point forecast only. Swapping in the ensemble mean/spread (`history/features/
  ensemble_mean/`) would add calibrated uncertainty.
- Per-forecast-horizon evaluation (the `previous_day1` feature is a specific
  lead time) would sharpen the operational story.
