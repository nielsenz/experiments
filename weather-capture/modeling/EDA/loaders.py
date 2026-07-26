"""
Shared loaders for the weather-capture history tree.

Reads the gzipped raw-JSON archives under weather-capture/history/ and returns
plain Python dict-of-lists time series. No pandas dependency (not available in
this env), just stdlib + the raw bytes on disk.

Three sources, matching history_sources.json:

  verification/historical_forecast_actuals/<loc>/<YYYY-MM>.json.gz
      -> actuals. LABELS ONLY. Never a feature (see history/README.md firewall).

  features/previous_runs_ifs_hres/<loc>_ecmwf_ifs025/<YYYY-MM>.json.gz
      -> ECMWF IFS HRES as-issued day-ahead forecast. Variables carry the
         _previous_day1 suffix. Real data begins 2024-02-04; Jan 2024 is null.

  features/ensemble_mean/<loc>_<model>/archive.json.gz
      -> ensemble mean + spread from the archive. Rolling ~93-day window.
         Three models: dwd_icon_eps_ensemble_mean_seamless,
         ncep_gefs025_ensemble_mean, ecmwf_ifs025_ensemble_mean.
"""
import json, gzip, glob, os

# EDA/ lives at weather-capture/modeling/EDA/, history/ at weather-capture/history/
HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY = os.path.normpath(os.path.join(HERE, "..", "..", "history"))

LOCATIONS = ["fresno-ca", "sacramento-ca", "los-angeles-ca", "las-vegas-nv", "henderson-nv"]
VARS = ["temperature_2m", "shortwave_radiation", "cloud_cover", "wind_speed_100m"]
ENSEMBLE_MODELS = [
    "dwd_icon_eps_ensemble_mean_seamless",
    "ncep_gefs025_ensemble_mean",
    "ecmwf_ifs025_ensemble_mean",
]


def _read_gz_json(path):
    with gzip.open(path) as fh:
        return json.load(fh)


def _concat_months(pattern):
    """Read all monthly files matching a glob, concatenate hourly series in time order."""
    files = sorted(glob.glob(pattern))
    if not files:
        return None
    out = None
    for f in files:
        h = _read_gz_json(f)["hourly"]
        if out is None:
            out = {k: list(v) for k, v in h.items()}
        else:
            for k, v in h.items():
                out.setdefault(k, []).extend(v)
    return out


def load_actuals(loc):
    """Verification actuals for a location. Returns hourly dict or None."""
    p = os.path.join(HISTORY, "verification", "historical_forecast_actuals", loc, "20*.json.gz")
    return _concat_months(p)


def load_previous_runs(loc):
    """ECMWF IFS HRES as-issued day-ahead forecast. Returns hourly dict or None.
    Variable names carry the _previous_day1 suffix."""
    p = os.path.join(HISTORY, "features", "previous_runs_ifs_hres",
                     f"{loc}_ecmwf_ifs025", "20*.json.gz")
    return _concat_months(p)


def load_ensemble_mean(loc, model):
    """Ensemble mean/spread archive for one location+model. Returns hourly dict or None."""
    p = os.path.join(HISTORY, "features", "ensemble_mean", f"{loc}_{model}", "archive.json.gz")
    if not os.path.exists(p):
        return None
    return _read_gz_json(p)["hourly"]


# energy/ sits at weather-capture/energy/, alongside history/
ENERGY = os.path.normpath(os.path.join(HERE, "..", "..", "energy"))


def load_caiso_demand():
    """CAISO hourly demand (the prediction label) from energy/data/caiso_demand/.

    Returns a dict {utc_hour_key -> demand_MWh_or_None} where the key is
    normalized to 'YYYY-MM-DDTHH:MM' (":00" minutes) to match the weather
    series' time strings exactly. Values are floats in megawatthours; missing
    EIA hours come through as None. De-duplicates repeated periods (keeps last).
    """
    out = {}
    files = sorted(glob.glob(os.path.join(ENERGY, "data", "caiso_demand", "20*.json.gz")))
    for f in files:
        d = _read_gz_json(f)
        for row in d.get("data", []):
            p = row.get("period")           # 'YYYY-MM-DDTHH'
            if not p:
                continue
            key = p if len(p) > 13 else p + ":00"   # -> 'YYYY-MM-DDTHH:00'
            v = row.get("value")
            out[key] = None if v is None else float(v)
    return out


def local_hour(utc_key, utc_offset_hours=-8):
    """Map a UTC 'YYYY-MM-DDTHH:MM' key to local hour-of-day.

    California/Nevada are UTC-8 (PST) / UTC-7 (PDT). A fixed offset is a
    deliberate simplification for descriptive EDA — good enough to read diurnal
    structure; not for production feature engineering across DST boundaries.
    """
    h = int(utc_key[11:13])
    return (h + utc_offset_hours) % 24


def to_float(series):
    """Coerce a list that may contain None to a list of floats/NaN via numpy."""
    import numpy as np
    return np.array([np.nan if x is None else float(x) for x in series], dtype=float)


if __name__ == "__main__":
    a = load_actuals("fresno-ca")
    print("actuals fresno-ca:", len(a["time"]), "hours,", a["time"][0], "->", a["time"][-1])
    pr = load_previous_runs("fresno-ca")
    print("previous_runs fresno-ca:", len(pr["time"]), "hours")
    em = load_ensemble_mean("fresno-ca", "ncep_gefs025_ensemble_mean")
    print("ensemble_mean fresno-ca gfs:", len(em["time"]), "hours")
    dem = load_caiso_demand()
    keys = sorted(dem)
    nn = sum(1 for k in keys if dem[k] is None)
    print(f"caiso demand: {len(dem)} hours, {nn} null, {keys[0]} -> {keys[-1]}")
