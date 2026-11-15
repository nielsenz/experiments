"""Study 3: walk-forward backtest of 10-year name forecasts with feature ablations,
then the live forecast from 2024 to 2034.

For each test origin T the model is trained only on origins <= T-10, i.e. on 10-year outcomes
that were fully observed by year T.
"""
import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import roc_auc_score
from panel import ROOT

P = ROOT / "data" / "processed"
RES = ROOT / "results"

MOM = ["is_f", "logshare", "mom3", "mom5", "mom10", "mom20", "accel"]
HIST = ["log_peak", "rel_peak", "peak_age", "off_trough", "trough_age"]
BEAR = ["old_mean_age", "old_surv", "centroid_age", "frac_alive", "mean_age",
        "stock_flow", "frac_70p", "exp_a20_44", "exp_a45_69", "exp_a70p"]
SOUND = ["rhyme_mom5", "rhyme_mom10", "end2_mom5", "end2_mom10", "first_mom5", "first_mom10"]
# model name -> (features, model it is compared against)
MODELS = {
    "A momentum": (MOM, "linear momentum"),
    "B momentum + own long history": (MOM + HIST, "A momentum"),
    "B + bearer-age clock only": (MOM + HIST + ["old_mean_age"], "B momentum + own long history"),
    "B + all living-bearer features": (MOM + HIST + BEAR, "B momentum + own long history"),
    "B + sound neighbours": (MOM + HIST + SOUND, "B momentum + own long history"),
}
LIVE_MODEL = "B + bearer-age clock only"
TEST_ORIGINS = [1984, 1989, 1994, 1999, 2004, 2009, 2014]
TRAIN_START = 1950


def hgb():
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_depth=6,
                                         min_samples_leaf=50, l2_regularization=1.0, random_state=0)


def vintage(d):
    """Once-common names (peak share >= 0.05% of births) now at <= 20% of that peak, 40+ years on."""
    return (d.log_peak >= np.log(5e-4)) & (d.rel_peak <= np.log(0.2)) & (d.peak_age >= 40)


def dormant(d):
    """Fallen vintage names that have not started moving yet: 10-year momentum still negative."""
    return vintage(d) & (d.mom10 < 0)


UNIVERSES = {"all names with 100+ births": lambda d: d["count"] >= 100,
             "fallen vintage names": vintage,
             "fallen vintage names still falling": dormant}


def score(d, pred):
    pred = np.asarray(pred)
    const = np.std(pred) == 0
    r = {"n": len(d), "spearman": np.nan if const else spearmanr(d.g10, pred)[0],
         "rmse": float(np.sqrt(np.mean((d.g10 - pred) ** 2))),
         "r2_vs_nochange": 1 - np.sum((d.g10 - pred) ** 2) / np.sum(d.g10 ** 2)}
    up = (d.g10 > 0).to_numpy()
    r["base_share_up"] = up.mean()
    if 0 < up.sum() < len(up) and not const:
        r["auc_up"] = roc_auc_score(up, pred)
        k = max(1, len(d) // 10)
        top = np.argsort(-pred)[:k]
        r["top10_share_up"] = up[top].mean()
        r["top10_median_g10"] = float(np.median(d.g10.to_numpy()[top]))
    return r


def main():
    p = pd.read_pickle(P / "panel.pkl")
    keys = pd.read_csv(P / "names.csv")
    rows, preds = [], []
    for T in TEST_ORIGINS:
        tr = p[(p.year >= TRAIN_START) & (p.year <= T - 10)]
        te = p[p.year == T].copy()
        te["pred_nochange"] = 0.0
        te["pred_linear momentum"] = LinearRegression().fit(tr[["mom5", "mom10"]], tr.g10).predict(te[["mom5", "mom10"]])
        for name, (cols, _) in MODELS.items():
            te["pred_" + name] = hgb().fit(tr[cols], tr.g10).predict(te[cols])
        preds.append(te)
        for uni, maskf in UNIVERSES.items():
            d = te[maskf(te)]
            for c in [c for c in te.columns if c.startswith("pred_")]:
                rows.append({"origin": T, "universe": uni, "model": c[5:], **score(d, d[c])})
        print(T, len(tr), len(te), flush=True)
    pd.DataFrame(rows).to_csv(RES / "backtest_by_origin.csv", index=False)
    allp = pd.concat(preds)
    keep = ["name", "sex", "year", "count", "g10", "peak_year", "peak_age", "old_mean_age", "mom10", "log_peak", "rel_peak"]
    allp.merge(keys[["name", "sex"]], left_on="id", right_index=True)[
        keep + [c for c in allp if c.startswith("pred_")]].round(4).to_csv(RES / "backtest_predictions.csv.gz", index=False)

    # pooled scores, with a bootstrap over names for each model's gain over its reference model
    rng = np.random.default_rng(0)
    models = [c[5:] for c in allp if c.startswith("pred_")]
    summ = []
    for uni, maskf in UNIVERSES.items():
        d = allp[maskf(allp)]
        base = {m: score(d, d["pred_" + m]) for m in models}
        ids = d.id.unique(); grp = {i: g for i, g in d.groupby("id")}
        boot = {m: [] for m in models}
        for _ in range(300):
            b = pd.concat([grp[i] for i in rng.choice(ids, len(ids))])
            for m in models:
                if m != "nochange":
                    boot[m].append(spearmanr(b.g10, b["pred_" + m])[0])
        for m in models:
            r = {"universe": uni, "model": m, **base[m]}
            if m in MODELS:
                ref = MODELS[m][1]
                diff = np.array(boot[m]) - np.array(boot[ref])
                r["compared_with"] = ref
                r["spearman_gain"] = base[m]["spearman"] - base[ref]["spearman"]
                r["gain_ci_lo"], r["gain_ci_hi"] = np.percentile(diff, [2.5, 97.5])
            summ.append(r)
    summ = pd.DataFrame(summ)
    summ.to_csv(RES / "backtest_summary.csv", index=False)
    print(summ.round(3).to_string())

    # live forecast: train on every origin whose outcome is known (<= 2014), predict from 2024
    cols = MODELS[LIVE_MODEL][0]
    tr = p[(p.year >= TRAIN_START) & (p.year <= 2014)]
    live = p[p.year == 2024].copy()
    live["pred_g10"] = hgb().fit(tr[cols], tr.g10).predict(live[cols])
    live["pred_multiple"] = np.exp(live.pred_g10)
    live["vintage"] = vintage(live)
    live["still_falling"] = dormant(live)
    live = live.merge(keys[["name", "sex"]], left_on="id", right_index=True)
    live["share_2024_pct"] = (np.exp(live.logshare) - 3e-6) * 100
    out = live[["name", "sex", "count", "share_2024_pct", "peak_year", "peak_age", "old_mean_age", "mom10",
                "vintage", "still_falling", "pred_g10", "pred_multiple"]].rename(columns={"count": "births_2024"})
    out.sort_values("pred_g10", ascending=False).round(5).to_csv(RES / "forecast_2024_to_2034.csv", index=False)
    json.dump({"made": "2026-11-15", "data_through": 2024,
               "target": "log change in share of births, mean of 2022-24 to mean of 2032-34",
               "model": LIVE_MODEL, "train_origins": [TRAIN_START, 2014], "features": cols},
              open(RES / "forecast_meta.json", "w"), indent=1)


if __name__ == "__main__":
    main()
