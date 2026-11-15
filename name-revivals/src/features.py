"""Feature panel: one row per (name, sex, origin year), using only data up to the origin year.

Target: g10 = log change in the name's share of births over the following 10 years
(3-year trailing means at both ends, EPS added so names under the SSA floor stay finite).
"""
import numpy as np
import pandas as pd
import cmudict
from panel import build, smooth, YEARS, Y0, Y1, ROOT
from bearers import bearer_stock

EPS = 3e-6      # about 5 babies in a year of ~1.7M births of one sex
H = 10
VOWELS = set("AA AE AH AO AW AY EH ER EY IH IY OW OY UH UW".split())


def rhyme(name, d):
    """Final rhyme (last vowel + following consonants, stress stripped) from CMUdict, else None."""
    p = d.get(name.lower())
    if not p:
        return None
    ph = [x.rstrip("012") for x in p[0]]
    for i in range(len(ph) - 1, -1, -1):
        if ph[i] in VOWELS:
            return "-".join(ph[i:])
    return None


def group_loo_momentum(share_s, labels, lag):
    """Leave-one-out log growth over `lag` years of the combined share of the other names in a group."""
    N, T = share_s.shape
    codes, _ = pd.factorize(labels)
    G = np.zeros((codes.max() + 2, T))
    np.add.at(G, codes, share_s)          # code -1 (missing) lands in the last row
    loo = G[codes] - share_s
    out = np.full((N, T), np.nan, dtype=np.float32)
    out[:, lag:] = np.log((loo[:, lag:] + EPS) / (loo[:, :-lag] + EPS))
    lvl = np.log(loo + EPS).astype(np.float32)
    out[codes < 0] = np.nan; lvl[codes < 0] = np.nan
    return out, lvl


def build_panel(min_peak_count=25, origins=None, verbose=True):
    keys, counts, share = build()
    keep = counts.max(axis=1) >= min_peak_count
    keys = keys[keep].reset_index(drop=True); counts = counts[keep]; share = share[keep]
    N, T = share.shape
    sm3, sm5 = smooth(share, 3), smooth(share, 5)
    ls = np.log(sm3 + EPS)
    runmax = np.maximum.accumulate(sm5, axis=1)
    peakyr = np.zeros((N, T), dtype=np.int16); cur = np.zeros(N, dtype=np.int16)
    for t in range(T):
        cur = np.where(sm5[:, t] >= runmax[:, t], t, cur); peakyr[:, t] = cur
    # trailing 30-year minimum and when it happened
    trough = np.empty((N, T)); trough_age = np.zeros((N, T), dtype=np.int16)
    for t in range(T):
        w = sm5[:, max(0, t - 29): t + 1]
        trough[:, t] = w.min(axis=1); trough_age[:, t] = w.shape[1] - 1 - w.argmin(axis=1)
    st = bearer_stock(keys, counts)
    live_tot = {s: st["alive"][(keys.sex == s).to_numpy()].sum(axis=0) for s in "FM"}
    band_tot = {(s, k): st[k][(keys.sex == s).to_numpy()].sum(axis=0) for s in "FM" for k in ("a20_44", "a45_69", "a70p")}

    d = cmudict.dict()
    keys["rhyme"] = [rhyme(n, d) for n in keys.name]
    keys["end2"] = keys.name.str.lower().str[-2:]
    keys["first"] = keys.name.str.lower().str[0]
    snd = {}
    for s in "FM":
        m = (keys.sex == s).to_numpy()
        for col in ("rhyme", "end2", "first"):
            for lag in (5, 10):
                mo, lvl = group_loo_momentum(sm3[m], keys.loc[m, col].to_numpy(), lag)
                snd.setdefault(f"{col}_mom{lag}", np.full((N, T), np.nan, dtype=np.float32))[m] = mo
            snd.setdefault(f"{col}_lvl", np.full((N, T), np.nan, dtype=np.float32))[m] = lvl

    if origins is None:
        origins = range(1920, Y1 + 1)
    sexF = (keys.sex == "F").to_numpy()
    rows = []
    for y in origins:
        t = y - Y0
        el = (counts[:, t] >= 25) | (runmax[:, t] >= 2e-4)
        i = np.where(el)[0]
        g = np.log((sm3[i, t + H] + EPS) / (sm3[i, t] + EPS)) if t + H < T else np.full(len(i), np.nan)
        lag = lambda k: ls[i, t] - ls[i, t - k]
        alive = st["alive"][i, t].astype(float)
        tot = np.where(sexF[i], live_tot["F"][t], live_tot["M"][t])
        f = dict(
            id=i, year=y, g10=g, count=counts[i, t],
            is_f=sexF[i].astype(int),
            logshare=ls[i, t], mom3=lag(3), mom5=lag(5), mom10=lag(10), mom20=lag(20),
            accel=lag(5) - (ls[i, t - 5] - ls[i, t - 10]),
            log_peak=np.log(runmax[i, t] + EPS), rel_peak=ls[i, t] - np.log(runmax[i, t] + EPS),
            peak_age=t - peakyr[i, t], peak_year=peakyr[i, t] + Y0,
            off_trough=np.log((sm5[i, t] + EPS) / (trough[i, t] + EPS)), trough_age=trough_age[i, t],
            frac_alive=alive / np.maximum(st["ever"][i, t], 1),
            mean_age=st["age_sum"][i, t] / np.maximum(alive, 1e-9),
            stock_flow=np.log((alive / tot + EPS) / (sm3[i, t] + EPS)),
            frac_70p=st["a70p"][i, t] / np.maximum(alive, 1e-9),
            # old stock = bearers named 20+ years ago, so a revival's own babies do not move these
            old_surv=st["a20p"][i, t] / np.maximum(st["ever20"][i, t], 1),
            old_mean_age=st["age_sum20p"][i, t] / np.maximum(st["a20p"][i, t], 1e-9),
            centroid_age=t - st["centroid20"][i, t],
        )
        for k in ("a20_44", "a45_69", "a70p"):
            bt = np.where(sexF[i], band_tot[("F", k)][t], band_tot[("M", k)][t])
            f[f"exp_{k}"] = np.log(st[k][i, t] / bt + EPS)
        for k, v in snd.items():
            f[k] = v[i, t]
        rows.append(pd.DataFrame(f))
        if verbose and y % 20 == 0:
            print(y, len(i), flush=True)
    panel = pd.concat(rows, ignore_index=True)
    panel.loc[panel.frac_alive.eq(0) & panel.mean_age.eq(0), ["mean_age", "frac_70p"]] = np.nan
    noold = panel.old_surv.eq(0) & panel.old_mean_age.eq(0)
    panel.loc[noold, ["old_surv", "old_mean_age", "centroid_age"]] = np.nan
    return keys, panel


if __name__ == "__main__":
    keys, panel = build_panel()
    out = ROOT / "data" / "processed"
    keys.to_csv(out / "names.csv", index=False)
    panel.to_pickle(out / "panel.pkl")
    print(panel.shape, keys.shape, keys.rhyme.notna().mean())
