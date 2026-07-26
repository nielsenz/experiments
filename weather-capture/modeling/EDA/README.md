# modeling/EDA — initial exploration

First-pass exploratory analysis of the `weather-capture/history/` tree, ahead of
any modeling. Nothing here trains a model; it characterizes the data so the
modeling choices later are grounded.

## Contents

```
modeling/EDA/
├── loaders.py        reusable readers for the 4 history/energy sources (no pandas; numpy + stdlib)
├── eda.py            weather-only analysis: stats, profiles, forecast skill, spread, CSV export
├── join_demand_weather.py   CAISO demand × weather join: response curve, demand profiles, degree-days
├── eda_summary.md    generated weather EDA summary
├── join_summary.md   generated demand-vs-weather summary
├── figures/          generated plots
│   ├── profiles.png                  diurnal & seasonal temp/solar, all locations
│   ├── forecast_vs_actual_temp.png   day-ahead temp forecast vs actual scatter
│   ├── demand_vs_temp.png            CAISO demand-temperature response curve
│   └── demand_profiles.png           diurnal (local) & seasonal demand
└── csv/              analysis-ready exports
    ├── actuals_hourly.csv            time, location, 4 actual variables (~142k rows)
    └── temp_forecast_vs_actual.csv   aligned forecast/actual/error (~108k rows)
```

## Reproduce

```bash
# from repo root; deps: py3-numpy py3-matplotlib (apk)
cd weather-capture/modeling/EDA
python3 eda.py                    # weather-only EDA
python3 join_demand_weather.py    # demand × weather (needs energy/ data present)
```

`loaders.py` can be imported by future modeling code — it flattens the gzipped
monthly archives into plain `{var: [values]}` time series and handles the
`_previous_day1` suffix and `None` gaps.

## Key findings

1. **Usable modeling window is 2024-02-04 → today.** The `previous_runs` day-ahead
   feature is 100% null before that (Jan 2024 empty, early Feb ramps in) even
   though the API accepted the request. Actuals go back to 2023-05-01, but that
   earlier stretch has labels with no day-ahead feature — descriptive use only.

2. **The day-ahead temperature feature is high-skill.** ECMWF IFS HRES day-ahead
   temperature tracks actuals at MAE ≈ 1.2–1.5 °C, RMSE ≈ 1.5–1.9 °C, corr ≈ 0.98
   across all five sites. Bias is small (< 0.5 °C). Solar radiation correlates
   just as tightly (~0.99) but with large absolute RMSE because of its range.
   **Cloud cover is the weak feature** — corr 0.43 (LA) to 0.70 (Sacramento);
   the coastal marine layer is the hardest to forecast.

3. **`wind_speed_100m` is missing from the ensemble_mean archive for DWD ICON and
   GFS** — only ECMWF IFS provides it. The other three variables are present for
   all three models. Any ensemble 100 m wind feature must come from ECMWF.

4. **Physically sane structure.** Diurnal and seasonal profiles look correct once
   you account for UTC (local = UTC−7/−8): pre-dawn temp trough, solar-noon peak,
   summer maxima. Desert sites (Las Vegas, Henderson, Fresno) run hotter and more
   variable than coastal LA.

## Demand × weather findings (`join_demand_weather.py`)

Joins CAISO system demand (EIA) to a 5-city state-average of the actuals weather
on UTC hours — **28,384 aligned hours**, 2023-05 → today.

5. **Textbook demand–temperature response curve.** Flat "comfort" demand
   (~22.5 GW) from roughly 2–18 °C, then a sharp cooling-driven ramp above ~20 °C
   as AC load engages — reaching ~35 GW near 40 °C. Cooling-side sensitivity is
   **~400 MWh per °C**. Variance fans out in the hot regime, which is exactly why
   summer demand (and summer forecast error) is the hard, high-stakes part.

6. **Cooling dominates this footprint.** With base ≈ 6 °C (the response minimum),
   cooling-degree-hours correlate with demand at **+0.63**, heating-degrees at
   only −0.09. Degree-day transforms are the natural first features; a plain
   linear temp correlation (+0.62) understates the U-shaped signal.

7. **Demand profiles are classic CAISO.** Evening peak ~20:00 local (~29 GW),
   pre-dawn trough ~05:00 (~22 GW); seasonal peak in August (~30.7 GW) with a
   small winter heating uptick. Solar radiation and cloud cover correlate weakly
   with demand on their own — temperature is the dominant weather driver.

## Caveats carried from the data

- **Times are UTC** throughout. CAISO / energy work will want local time —
  convert at join time.
- **The firewall still applies.** `actuals` here are verification labels, never
  a feature. See `../../history/README.md`.
- **Do not join archive ensemble mean with captured members** into one series —
  different statistics. See the seam note in the history README.
- The ensemble_mean archive is a rolling ~93-day window, so its span here is
  short (≈ Apr 25 → today) relative to the 2+ years of actuals/previous_runs.
