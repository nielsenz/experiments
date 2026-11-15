"""Living-bearer stock: how many people with each name are still alive in each year.

Uses the SSA cohort life tables (Actuarial Study 120, Table 7; decade cohorts 1900-2010)
as redistributed in the hadley/babynames R package.  Approximations, all documented in the README:
  * cohorts before 1900 use the 1900 table, cohorts after 2010 use the 2010 table;
  * tables are linearly interpolated between decades;
  * SSA name counts for people born before 1937 only include people who lived to apply for a
    Social Security number, so their survival is taken conditional on reaching 1937;
  * migration is ignored.
"""
import numpy as np
import pandas as pd
from panel import ROOT, YEARS, Y0


def survival_matrix(sex):
    """S[b, t] = P(person of this sex born in year index b is alive in year index t)."""
    lt = pd.read_csv(ROOT / "data" / "processed" / "ssa_cohort_lifetables.csv")
    lt = lt[lt.sex == sex]
    dec = np.sort(lt.year.unique())
    lx = np.stack([lt[lt.year == d].sort_values("x").lx.to_numpy() / 1e5 for d in dec])  # [decade, age 0..119]
    T = len(YEARS)
    S = np.zeros((T, T))
    for bi, b in enumerate(YEARS):
        pos = np.clip((b - dec[0]) / 10.0, 0, len(dec) - 1)
        lo = int(np.floor(pos)); hi = min(lo + 1, len(dec) - 1); w = pos - lo
        l = (1 - w) * lx[lo] + w * lx[hi]
        base = l[max(0, 1937 - b)] if b < 1937 else 1.0
        for ti in range(bi, T):
            a = ti - bi
            S[bi, ti] = min(1.0, l[a] / base) if a < len(l) else 0.0
    return S


def bearer_stock(keys, counts):
    """Per name-year: living bearers, their mean age, and living bearers in age bands."""
    N, T = counts.shape
    age = np.subtract.outer(-np.arange(T), -np.arange(T)).astype(float)  # age[b, t] = t - b
    out = {k: np.zeros((N, T), dtype=np.float32) for k in
           ("alive", "age_sum", "a0_19", "a20_44", "a45_69", "a70p", "a20p", "age_sum20p")}
    for s in ("F", "M"):
        m = (keys.sex == s).to_numpy()
        S = survival_matrix(s)
        C = counts[m]
        out["alive"][m] = C @ S
        out["age_sum"][m] = C @ (S * age)
        out["a20p"][m] = C @ (S * (age >= 20))
        out["age_sum20p"][m] = C @ (S * age * (age >= 20))
        for k, (lo, hi) in {"a0_19": (0, 19), "a20_44": (20, 44), "a45_69": (45, 69), "a70p": (70, 200)}.items():
            out[k][m] = C @ (S * ((age >= lo) & (age <= hi)))
    ever = np.cumsum(counts, axis=1)
    out["ever"] = ever.astype(np.float32)
    # the "old stock": everyone given the name at least 20 years before the year in question
    ever20 = np.zeros_like(ever); ever20[:, 20:] = ever[:, :-20]
    by = np.cumsum(counts * np.arange(T)[None, :], axis=1)
    by20 = np.zeros_like(by); by20[:, 20:] = by[:, :-20]
    out["ever20"] = ever20.astype(np.float32)
    out["centroid20"] = (by20 / np.maximum(ever20, 1)).astype(np.float32)   # mean birth-year index of the old stock
    return out
