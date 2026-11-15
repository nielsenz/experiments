"""How much of an MLB crowd depends on who the visiting team is?

Retrosheet game logs, 2015-2019 and 2022-2025 (2020 had no fans, 2021 had capacity limits).
The quantity estimated is "opponent-attributable attendance": tickets that are sold against
a strong-drawing opponent and not against a weak-drawing one, holding the home team's season,
its own weekday pattern, the month and the home opener fixed. It is an upper bound on
travelling visiting-team fans, because it also contains residents who follow the visitor and
residents who come to see stars.

Inputs:  data/mlb_games_attendance.csv.gz  (built from Retrosheet GL files by --build PATH)
Outputs: results/opponent_effects_league.csv, results/opponent_attributable_by_park.csv,
         results/opponent_distance_effects.csv, results/vegas_opponent_projection.csv,
         results/opponent_summary.json
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
DATA = ROOT / "data" / "mlb_games_attendance.csv.gz"

if len(sys.argv) == 3 and sys.argv[1] == "--build":
    fr = [pd.read_csv(f, header=None, usecols=[0, 2, 3, 6, 12, 16, 17],
                      names=["date", "dow", "vis", "home", "daynight", "park", "att"], dtype={"date": str})
          for f in sorted(glob.glob(sys.argv[2] + "/*"))]
    pd.concat(fr).to_csv(DATA, index=False)

COORD = {  # city centres, degrees
    "ANA": (33.80, -117.88), "ARI": (33.45, -112.07), "ATL": (33.89, -84.47), "BAL": (39.28, -76.62),
    "BOS": (42.35, -71.10), "CHA": (41.83, -87.63), "CHN": (41.95, -87.66), "CIN": (39.10, -84.51),
    "CLE": (41.50, -81.69), "COL": (39.76, -104.99), "DET": (42.34, -83.05), "HOU": (29.76, -95.36),
    "KCA": (39.05, -94.48), "LAN": (34.07, -118.24), "MIA": (25.78, -80.22), "MIL": (43.03, -87.97),
    "MIN": (44.98, -93.28), "NYA": (40.83, -73.93), "NYN": (40.76, -73.85), "OAK": (37.75, -122.20),
    "PHI": (39.91, -75.17), "PIT": (40.45, -80.01), "SDN": (32.71, -117.16), "SEA": (47.59, -122.33),
    "SFN": (37.78, -122.39), "SLN": (38.62, -90.19), "TBA": (27.77, -82.65), "TEX": (32.75, -97.08),
    "TOR": (43.64, -79.39), "WAS": (38.87, -77.01), "LVG": (36.09, -115.18)}


def miles(a, b):
    la1, lo1, la2, lo2 = map(np.radians, (*COORD[a], *COORD[b]))
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 3958.8 * 2 * np.arcsin(np.sqrt(h))


g = pd.read_csv(DATA, dtype={"date": str})
g["season"] = g.date.str[:4].astype(int)
g = g.replace({"vis": {"ATH": "OAK"}, "home": {"ATH": "OAK"}})
g = g[(g.season != 2021) & (g.att > 0)]
g = g[~((g.season == 2025) & g.home.isin(["OAK", "TBA"]))]          # minor-league parks
primary = g.groupby(["season", "home"]).park.agg(lambda s: s.mode()[0]).rename("ppark").reset_index()
g = g.merge(primary)
g = g[g.park == g.ppark].copy()                                      # drop neutral-site and relocated games
g["month"] = g.date.str[4:6].astype(int).clip(4, 9)
g["hs"] = g.home + g.season.astype(str)
g["opener"] = (g.groupby("hs").date.transform("min") == g.date).astype(int)
g["wk"] = np.select([g.dow.isin(["Fri"]), g.dow.isin(["Sat"]), g.dow.isin(["Sun"])], ["Fri", "Sat", "Sun"], "MonThu")
g["dist"] = [miles(v, h) for v, h in zip(g.vis, g.home)]
g["near"] = (g.dist < 150).astype(int)
g["mid"] = ((g.dist >= 150) & (g.dist < 350)).astype(int)
g["y"] = np.log(g.att)
teams = sorted(g.vis.unique())


def design(d, visitor=True, distance=True):
    cols = [pd.get_dummies(d.hs, dtype=float),
            pd.get_dummies(d.home + "_" + d.wk, dtype=float).drop(columns=[f"{t}_MonThu" for t in d.home.unique()]),
            pd.get_dummies(d.month, prefix="m", dtype=float).iloc[:, 1:], d[["opener"]].astype(float)]
    if distance:
        cols.append(d[["near", "mid"]].astype(float))
    if visitor:
        cols.append(pd.get_dummies(d.vis, prefix="v", dtype=float).drop(columns=["v_" + teams[0]]))
    return pd.concat(cols, axis=1)


def fit(d, **kw):
    X = design(d, **kw)
    b, *_ = np.linalg.lstsq(X.to_numpy(), d.y.to_numpy(), rcond=None)
    return pd.Series(b, index=X.columns), d.y.to_numpy() - X.to_numpy() @ b


# ---- league-wide visitor effects and distance effects
coef, resid = fit(g)
v = coef[[c for c in coef.index if c.startswith("v_")]].rename(lambda s: s[2:])
v[teams[0]] = 0.0
v = v - v.mean()
sigma = resid.std()
n_games = len(g)
league = pd.DataFrame({"visitor": v.index, "effect_log": v.values, "effect_pct": 100 * (np.exp(v.values) - 1),
                       "road_games": g.vis.value_counts().reindex(v.index).values}).sort_values("effect_pct", ascending=False)
league.round(3).to_csv(RES / "opponent_effects_league.csv", index=False)
X = design(g).to_numpy()
cov_diag = np.diag(np.linalg.inv(X.T @ X)) * resid.var() * n_games / (n_games - X.shape[1])
se = pd.Series(np.sqrt(cov_diag), index=design(g).columns)
dist_tbl = pd.DataFrame({"term": ["within 150 miles", "150 to 350 miles"],
                         "effect_pct": [100 * (np.exp(coef[k]) - 1) for k in ("near", "mid")],
                         "t": [coef[k] / se[k] for k in ("near", "mid")],
                         "games": [int(g.near.sum()), int(g.mid.sum())]})
dist_tbl.round(2).to_csv(RES / "opponent_distance_effects.csv", index=False)

# ---- park by park: attendance attributable to the opponent
_, r0 = fit(g, visitor=False, distance=False)       # residual with no opponent information at all
g["r0"] = r0
rows = []
for h, d in g.groupby("home"):
    s2 = d.r0.var()
    m = d.groupby("vis").r0.agg(["mean", "size"])
    tau2 = max(m["mean"].var() - (s2 / m["size"]).mean(), 1e-6)       # between-opponent variance
    shrunk = m["mean"] * tau2 / (tau2 + s2 / m["size"])               # empirical-Bayes opponent effects
    order = shrunk.sort_values()
    w = m["size"].reindex(order.index).cumsum() / m["size"].sum()
    ref = float(order[w >= 0.10].iloc[0])                             # opponent at the 10th percentile of games
    e = d.vis.map(shrunk).to_numpy()
    attributable = d.att.to_numpy() * (1 - np.exp(np.minimum(ref - e, 0)))
    top = shrunk.sort_values(ascending=False).head(3)
    rows.append({"home": h, "games": len(d), "avg_attendance": d.att.mean(),
                 "opponent_sd_pct": 100 * np.sqrt(tau2),
                 "attributable_per_game": attributable.mean(),
                 "attributable_share_pct": 100 * attributable.sum() / d.att.sum(),
                 "best_opponents": ", ".join(f"{k} +{100 * (np.exp(x - ref) - 1):.0f}%" for k, x in top.items())})
park = pd.DataFrame(rows).sort_values("attributable_share_pct", ascending=False)
park.round(1).to_csv(RES / "opponent_attributable_by_park.csv", index=False)

# ---- projection for a Las Vegas schedule
home_games = {t: 81 * 0 for t in teams}
division, natural = ["SEA", "HOU", "TEX", "ANA"], "SFN"
al = ["BAL", "BOS", "CHA", "CLE", "DET", "KCA", "MIN", "NYA", "TBA", "TOR"]
nl = [t for t in teams if t not in division + al + [natural, "OAK"]]
for t in division:
    home_games[t] = 6.5
for t in al:
    home_games[t] = 3.2
home_games[natural] = 2.0
for t in nl:
    home_games[t] = 21.0 / len(nl)
sched = pd.Series(home_games).drop("OAK")
assert abs(sched.sum() - 81) < 0.01
lv_dist = pd.Series({t: miles(t, "LVG") for t in sched.index})
mid_lv = ((lv_dist >= 150) & (lv_dist < 350)).astype(float)
proj = []
for label, scale in (("league-average sensitivity", 1.0),
                     ("most opponent-sensitive quarter of parks", float(park.opponent_sd_pct.quantile(0.875) / park.opponent_sd_pct.median())),
                     ("most opponent-sensitive park", float(park.opponent_sd_pct.max() / park.opponent_sd_pct.median()))):
    e = scale * (v.reindex(sched.index) + coef["mid"] * mid_lv)
    order = e.sort_values()
    w = sched.reindex(order.index).cumsum() / 81
    ref = float(order[w >= 0.10].iloc[0])
    share = float((sched * (1 - np.exp(np.minimum(ref - e, 0)))).sum() / 81)
    for base in (26_476, 29_400):
        proj.append({"case": label, "sensitivity_scale": round(scale, 2), "base_attendance": base,
                     "opponent_attributable_share_pct": round(100 * share, 1),
                     "opponent_attributable_per_game": round(base * share)})
proj = pd.DataFrame(proj)
proj.to_csv(RES / "vegas_opponent_projection.csv", index=False)

summary = {
    "games": int(n_games), "seasons": sorted(int(s) for s in g.season.unique()),
    "residual_sd_pct": round(100 * float(sigma), 1),
    "league_visitor_effect_range_pct": [round(float(league.effect_pct.min()), 1), round(float(league.effect_pct.max()), 1)],
    "top5_visitors": league.head(5).visitor.tolist(),
    "park_attributable_per_game_median": round(float(park.attributable_per_game.median())),
    "park_attributable_per_game_min_max": [round(float(park.attributable_per_game.min())), round(float(park.attributable_per_game.max()))],
    "park_attributable_share_median_pct": round(float(park.attributable_share_pct.median()), 1),
    "park_attributable_share_max_pct": round(float(park.attributable_share_pct.max()), 1),
    "vegas_drivable_opponents": sorted(mid_lv[mid_lv == 1].index.tolist()),
    "vegas_drivable_home_games": round(float((sched * mid_lv).sum()), 1),
}
(RES / "opponent_summary.json").write_text(json.dumps(summary, indent=2))
pd.set_option("display.width", 200)
print(league.round(2).to_string(index=False)); print(dist_tbl.round(2).to_string(index=False))
print(park.round(1).to_string(index=False)); print(proj.to_string(index=False)); print(json.dumps(summary, indent=1))
