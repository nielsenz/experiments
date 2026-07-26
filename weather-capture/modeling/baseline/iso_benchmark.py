#!/usr/bin/env python3
"""
The honest scorecard: our demand model vs CAISO's OWN day-ahead forecast, judged
against the SAME truth, over ROLLING-ORIGIN folds.

Three things this fixes relative to modeling/baseline/baseline_model.py:

1. FAIR TRUTH. Our baseline scored against EIA gross demand; the ISO forecast is
   an OASIS quantity. Here BOTH forecasts are scored against OASIS 'CA ISO-TAC'
   ACTUAL (SYS_FCST_ACT_MW), so the ruler is identical.

2. FAIR INFORMATION SET. Our baseline leaned on dem_lag24 (demand 24h before the
   target). A genuine day-ahead forecast, issued the morning before the operating
   day, does NOT have same-relative-position recent load for the early operating
   hours. We therefore evaluate two variants:
     - "ours_lag24"      : keeps 24h/168h lags (the easier game; upper bound)
     - "ours_dayahead"   : drops the 24h lag, keeps only 168h (week-ago) + weather
                           + calendar -> closer to a real day-ahead information set
   The gap between them tells us how much of our 3.3% was autocorrelation.

3. ROLLING-ORIGIN BACKTEST. Instead of one 80/20 split (whose test set is a single
   Jan-Jul 2026 weather regime), we walk forward: train on everything up to fold
   start, test the next block, advance. Report mean +/- spread across folds. A
   number seen across folds is worth ten from one lucky split.

Truth = OASIS ACTUAL. ISO forecast = OASIS DAM. Our features respect the firewall
(day-ahead previous_runs temperature; demand lags are >=168h or, in the lag24
variant, >=24h; never the target hour).
"""
import os, sys, glob, gzip, json, datetime as dt
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "EDA"))
import loaders as L
from sklearn.ensemble import HistGradientBoostingRegressor

HERE = os.path.dirname(os.path.abspath(__file__))
ISO_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "energy", "data", "caiso_iso_forecast"))
BASE_C = 6.0


def load_oasis(market):
    """Return {'YYYY-MM-DDTHH' (UTC) -> MW} for a market across all monthly files."""
    out = {}
    for f in sorted(glob.glob(os.path.join(ISO_DIR, f"{market}_*.json.gz"))):
        d = json.load(gzip.open(f))
        for r in d["rows"]:
            out[r["start_gmt"][:13]] = float(r["mw"])
    return out


def state_avg_dayahead_temp():
    """5-city state-average previous_runs day-ahead temperature, keyed 'YYYY-MM-DDTHH'."""
    s, c = {}, {}
    for loc in L.LOCATIONS:
        pr = L.load_previous_runs(loc)
        for i, t in enumerate(pr["time"]):
            v = pr["temperature_2m_previous_day1"][i]
            if v is None:
                continue
            k = t[:13]
            s[k] = s.get(k, 0.0) + float(v)
            c[k] = c.get(k, 0) + 1
    return {k: s[k] / c[k] for k in s if c[k] == len(L.LOCATIONS)}


def hkey(k, hours_back):
    d = dt.datetime.strptime(k, "%Y-%m-%dT%H") - dt.timedelta(hours=hours_back)
    return d.strftime("%Y-%m-%dT%H")


def build_matrix(variant, temp, demand_eia, y_truth):
    """Rows over hours present in BOTH truth and features. Label = OASIS ACTUAL.
    demand_eia supplies the lag features (recent load history)."""
    keys = []
    for k in sorted(y_truth):
        if k not in temp:
            continue
        if hkey(k, 168) + ":00" not in demand_eia:
            continue
        if variant == "lag24" and hkey(k, 24) + ":00" not in demand_eia:
            continue
        keys.append(k)

    X, y = [], []
    for k in keys:
        d = dt.datetime.strptime(k, "%Y-%m-%dT%H")
        t = temp[k]
        feat = [
            t, max(t - BASE_C, 0.0), max(BASE_C - t, 0.0),
            np.sin(2*np.pi*d.hour/24), np.cos(2*np.pi*d.hour/24),
            np.sin(2*np.pi*d.month/12), np.cos(2*np.pi*d.month/12),
            np.sin(2*np.pi*d.weekday()/7), np.cos(2*np.pi*d.weekday()/7),
            1.0 if d.weekday() >= 5 else 0.0,
            demand_eia[hkey(k, 168) + ":00"],           # week-ago load
        ]
        if variant == "lag24":
            feat.append(demand_eia[hkey(k, 24) + ":00"])  # day-ago load (easier game)
        X.append(feat)
        y.append(y_truth[k])
    return keys, np.array(X), np.array(y)


def metrics(pred, truth):
    err = pred - truth
    mae = float(np.mean(np.abs(err)))
    mape = float(np.mean(np.abs(err) / truth) * 100)
    rmse = float(np.sqrt(np.mean(err**2)))
    return mae, mape, rmse


def rolling_eval(keys, X, y, n_folds=4, min_train=8000):
    """Walk-forward. Trains a fresh GBM per fold on an expanding window.

    NOTE: models are kept deliberately light (max_iter=180) so each fit finishes
    quickly — in the iSH/mobile sandbox a heavy multi-fold loop can be OS-killed
    mid-run. If you have headroom, raise max_iter/n_folds for a tighter estimate.
    """
    n = len(keys)
    fold_size = (n - min_train) // n_folds
    out = []
    for i in range(n_folds):
        tr_end = min_train + i * fold_size
        te_end = tr_end + fold_size if i < n_folds - 1 else n
        Xtr, ytr = X[:tr_end], y[:tr_end]
        Xte, yte = X[tr_end:te_end], y[tr_end:te_end]
        te_keys = keys[tr_end:te_end]
        if len(Xte) == 0:
            continue
        m = HistGradientBoostingRegressor(max_iter=180, learning_rate=0.07,
                                          max_depth=6, l2_regularization=1.0,
                                          random_state=0).fit(Xtr, ytr)
        mae, mape, rmse = metrics(m.predict(Xte), yte)
        out.append({"fold": i, "test_from": te_keys[0], "test_to": te_keys[-1],
                    "n": len(te_keys), "mae": mae, "mape": mape, "rmse": rmse,
                    "keys": te_keys})
        print(f"    fold {i}: MAPE {mape:.2f}%  MAE {mae:,.0f}", flush=True)
    return out


def main():
    print("Loading OASIS truth + forecast ...")
    truth = load_oasis("ACTUAL")
    iso = load_oasis("DAM")
    print(f"  OASIS ACTUAL hours: {len(truth)}   OASIS DAM hours: {len(iso)}")
    if len(truth) < 2000:
        sys.exit("Not enough OASIS data yet — let the fetch finish, then re-run.")

    temp = state_avg_dayahead_temp()
    dem = L.load_caiso_demand()

    lines = []
    def say(s=""):
        print(s); lines.append(s)

    say("# ISO benchmark — the honest scorecard\n")
    say("Truth for every metric below = OASIS `CA ISO-TAC` ACTUAL (SYS_FCST_ACT_MW).\n")

    # ---- ISO forecast skill on the hours where we have its forecast+truth ----
    iso_keys = sorted(set(iso) & set(truth))
    ip = np.array([iso[k] for k in iso_keys]); it = np.array([truth[k] for k in iso_keys])
    imae, imape, irmse = metrics(ip, it)
    say(f"**CAISO day-ahead forecast (DAM) vs OASIS ACTUAL** — {len(iso_keys)} hours")
    say(f"MAE {imae:,.0f} MWh | MAPE {imape:.2f}% | RMSE {irmse:,.0f}\n")

    # ---- our two model variants, rolling-origin ----
    results = {}
    for variant in ("lag24", "dayahead"):
        keys, X, y = build_matrix(variant, temp, dem, truth)
        folds = rolling_eval(keys, X, y, n_folds=4)
        maes = [f["mae"] for f in folds]; mapes = [f["mape"] for f in folds]
        results[variant] = folds
        say(f"**Our model ({variant}) vs OASIS ACTUAL — rolling-origin, {len(folds)} folds** "
            f"({len(keys)} rows)")
        say(f"MAPE per fold: " + ", ".join(f"{m:.2f}%" for m in mapes))
        say(f"MAE  {np.mean(maes):,.0f} ± {np.std(maes):,.0f} MWh   "
            f"MAPE {np.mean(mapes):.2f}% ± {np.std(mapes):.2f}%\n")

    # ---- head-to-head on the SAME final-fold hours where ISO forecast exists ----
    da = results["dayahead"]
    if da:
        last = da[-1]
        hrs = [k+":00" if False else k for k in last["keys"] if k in iso and k in truth]
        if hrs:
            ip2 = np.array([iso[k] for k in hrs]); tt = np.array([truth[k] for k in hrs])
            _, iso_mape2, _ = metrics(ip2, tt)
            say("## Head-to-head on the most-recent fold (hours where ISO forecast exists)")
            say(f"ISO day-ahead MAPE here: {iso_mape2:.2f}% over {len(hrs)} hours.")
            say("(Our day-ahead-variant fold MAPE above is the comparable model number.)\n")

    say("## Reading it")
    say("- If `dayahead` model MAPE >> `lag24`, most of the baseline's 3.3% was "
        "demand autocorrelation, not weather-driven skill.")
    say("- Compare `dayahead` model vs ISO DAM: that is the real 'do we have edge?' number.")
    say("- Rolling spread (±) shows whether any edge survives across weather regimes.")

    with open(os.path.join(HERE, "iso_benchmark_summary.md.tmp"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(os.path.join(HERE, "iso_benchmark_summary.md.tmp"),
               os.path.join(HERE, "iso_benchmark_summary.md"))
    print("\n=== wrote iso_benchmark_summary.md ===")


if __name__ == "__main__":
    main()
