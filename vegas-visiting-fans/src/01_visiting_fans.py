"""Visiting-fan share in Las Vegas: what the measured data supports for the A's.

Inputs:  data/events.csv           39 events with a reported out-of-town share
         data/benchmarks.csv       estimates and plans (Golden Knights, A's, UFC)
         data/raiders_seasons.csv  Raiders season totals
         data/mlb_markets_2025.csv 13 one-team MLB metros, 2025 attendance
Outputs: results/share_by_kind.csv, results/curve_fit.json,
         results/curve_predictions.csv, results/raiders_games.csv,
         results/raiders_game_model.csv, results/annual_ticket_volumes.csv,
         results/mlb_tickets_per_resident.csv, results/as_scenarios.csv,
         results/summary.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
RES.mkdir(exist_ok=True)
RNG = np.random.default_rng(20261115)

LV_POP = 2_407_226            # Las Vegas MSA, Census July 2025
AS_DATES = 81
AS_SELLOUT = 29_400           # 98% of 30,000 fixed seats (traffic study basis)
AS_CAPACITY = 33_000
AS_VISITOR_SHARE = 0.30       # plan
AS_INCREMENTAL_SHARE = 0.16   # plan: fans who would not otherwise be in town
VGK_DATES = 41
VGK_AVG = 17_929              # 2025-26, from ../vegas-nba-demand

ev = pd.read_csv(ROOT / "data" / "events.csv")
ev["share"] = ev.out_of_town_pct / 100
ev["visitors"] = ev.attendance * ev.share
ev["locals"] = ev.attendance * (1 - ev.share)


def logit(p):
    return np.log(p / (1 - p))


def expit(x):
    return 1 / (1 + np.exp(-x))


# ---------------------------------------------------------------- 1. by kind
by_kind = (ev.groupby("kind")
           .agg(events=("share", "size"), mean_pct=("out_of_town_pct", "mean"),
                min_pct=("out_of_town_pct", "min"), max_pct=("out_of_town_pct", "max"),
                dates_per_year=("dates_per_year", "median"))
           .round(1).sort_values("mean_pct", ascending=False).reset_index())
by_kind.to_csv(RES / "share_by_kind.csv", index=False)

# ------------------------------------------- 2. share against dates per year
# Measured events only cover 1 to 10 dates a year. The fit is extrapolated to
# 41 and 81 dates and then compared with the Golden Knights estimates, which
# were held out.


def fit_curve(d):
    X = np.column_stack([np.ones(len(d)), np.log(d.dates_per_year)])
    b, *_ = np.linalg.lstsq(X, logit(d.share.to_numpy()), rcond=None)
    return b


def predict(b, dates):
    return float(expit(b[0] + b[1] * np.log(dates)))


specs = {
    "all measured events": ev,
    "excluding preseason": ev[ev.kind != "raiders_preseason"],
    "excluding rodeo": ev[ev.kind != "rodeo"],
    "excluding preseason and rodeo": ev[~ev.kind.isin(["raiders_preseason", "rodeo"])],
}
rows, fit_out = [], {}
for name, d in specs.items():
    b = fit_curve(d)
    # Bootstrap by property so 16 Raiders games do not count as 16 independent points.
    props = d.property.unique()
    boots = []
    for _ in range(4000):
        pick = RNG.choice(props, size=len(props), replace=True)
        s = pd.concat([d[d.property == p] for p in pick])
        if s.dates_per_year.nunique() < 2:
            continue
        boots.append(fit_curve(s))
    boots = np.array(boots)
    fit_out[name] = {
        "n_events": int(len(d)), "n_properties": int(len(props)),
        "intercept": round(float(b[0]), 3), "slope_per_log_date": round(float(b[1]), 3),
        "slope_80pct_interval": [round(float(q), 3) for q in np.quantile(boots[:, 1], [0.1, 0.9])],
    }
    for dates in (1, 2, 10, 41, 81):
        p = [expit(bb[0] + bb[1] * np.log(dates)) for bb in boots]
        rows.append({"spec": name, "dates_per_year": dates,
                     "predicted_pct": round(100 * predict(b, dates), 1),
                     "low80_pct": round(100 * float(np.quantile(p, 0.1)), 1),
                     "high80_pct": round(100 * float(np.quantile(p, 0.9)), 1)})
pd.DataFrame(rows).to_csv(RES / "curve_predictions.csv", index=False)
(RES / "curve_fit.json").write_text(json.dumps(fit_out, indent=2))

# -------------------------------------------------------- 3. Raiders by game
rg = ev[ev.property == "Raiders"].copy()
rg["date"] = pd.to_datetime(rg.date)
rg["weekday"] = rg.date.dt.day_name()
rg["preseason"] = (rg.kind == "raiders_preseason").astype(int)
rg["monday"] = (rg.weekday == "Monday").astype(int)
rg["late"] = rg.date.dt.month.isin([12, 1]).astype(int)   # December and January
rg_out = rg[["date", "event", "weekday", "preseason", "attendance", "out_of_town_pct",
             "visitors", "locals"]].copy()
rg_out[["visitors", "locals"]] = rg_out[["visitors", "locals"]].round(0)
rg_out.to_csv(RES / "raiders_games.csv", index=False)

full = rg.dropna(subset=["attendance", "date"])
reg = full[full.preseason == 0]


def ols(y, cols, d):
    X = np.column_stack([np.ones(len(d))] + [d[c].to_numpy(float) for c in cols])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ b
    dof = len(d) - X.shape[1]
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * (resid @ resid) / dof)
    return pd.DataFrame({"term": ["intercept"] + cols, "coef": b, "se": se, "t": b / se})


gm = []
for target in ("out_of_town_pct", "visitors", "locals"):
    t = ols(full[target].to_numpy(float), ["preseason", "monday", "late"], full)
    t.insert(0, "target", target)
    gm.append(t)
gm = pd.concat(gm).round(2)
gm.to_csv(RES / "raiders_game_model.csv", index=False)

corr_att_share = float(np.corrcoef(reg.attendance, reg.out_of_town_pct)[0, 1])
corr_att_locals = float(np.corrcoef(reg.attendance, reg.locals)[0, 1])

# ------------------------------------------------ 4. annual ticket volumes
seasons = pd.read_csv(ROOT / "data" / "raiders_seasons.csv")
r25 = seasons[seasons.season == 2025].iloc[0]
raiders_vis = r25.total_attendance * r25.out_of_town_pct / 100
raiders_loc = r25.total_attendance - raiders_vis
vgk_total = VGK_AVG * VGK_DATES
as_total = AS_SELLOUT * AS_DATES
vol = pd.DataFrame([
    {"property": "Raiders 2025 (measured)", "dates": int(r25.home_dates),
     "visitor_tickets_low": raiders_vis, "visitor_tickets_high": raiders_vis,
     "local_tickets_low": raiders_loc, "local_tickets_high": raiders_loc},
    {"property": "Golden Knights 2025-26 (15 to 25% visitors, estimated)", "dates": VGK_DATES,
     "visitor_tickets_low": 0.15 * vgk_total, "visitor_tickets_high": 0.25 * vgk_total,
     "local_tickets_low": 0.75 * vgk_total, "local_tickets_high": 0.85 * vgk_total},
    {"property": "A's plan (30% of a 29,400 sellout)", "dates": AS_DATES,
     "visitor_tickets_low": AS_VISITOR_SHARE * as_total, "visitor_tickets_high": AS_VISITOR_SHARE * as_total,
     "local_tickets_low": (1 - AS_VISITOR_SHARE) * as_total, "local_tickets_high": (1 - AS_VISITOR_SHARE) * as_total},
])
vol["visitors_per_date_low"] = vol.visitor_tickets_low / vol.dates
vol["visitors_per_date_high"] = vol.visitor_tickets_high / vol.dates
vol["locals_per_date_low"] = vol.local_tickets_low / vol.dates
vol["locals_per_date_high"] = vol.local_tickets_high / vol.dates
vol.round(0).to_csv(RES / "annual_ticket_volumes.csv", index=False)

existing_vis = (vol.visitor_tickets_low[:2].sum(), vol.visitor_tickets_high[:2].sum())
existing_loc = (vol.local_tickets_low[:2].sum(), vol.local_tickets_high[:2].sum())
as_vis, as_loc = vol.visitor_tickets_low[2], vol.local_tickets_low[2]

# ------------------------------------------ 5. MLB tickets per resident
mlb = pd.read_csv(ROOT / "data" / "mlb_markets_2025.csv")
mlb["tickets_per_resident"] = mlb.attendance_2025 / mlb.metro_pop_2025
mlb["avg_attendance"] = mlb.attendance_2025 / mlb.home_dates
peer = mlb[mlb.metro_pop_2025.between(1.3e6, 3.1e6)]
mlb.sort_values("tickets_per_resident").round(3).to_csv(RES / "mlb_tickets_per_resident.csv", index=False)
as_local_tpr = as_loc / LV_POP
as_total_tpr = as_total / LV_POP

# ------------------------------------------------------- 6. A's scenarios
local_cases = {
    "plan (20,580)": (1 - AS_VISITOR_SHARE) * AS_SELLOUT,
    "peer low (Pirates/Orioles rate)": peer.tickets_per_resident.min() * LV_POP / AS_DATES,
    "peer median rate": peer.tickets_per_resident.median() * LV_POP / AS_DATES,
}
visitor_cases = {
    "Knights count, low (15%)": 0.15 * VGK_AVG,
    "Knights count, high (25%)": 0.25 * VGK_AVG,
    "plan, incremental only (16%)": AS_INCREMENTAL_SHARE * AS_SELLOUT,
    "plan (30%)": AS_VISITOR_SHARE * AS_SELLOUT,
}
sc = []
for ln, L in local_cases.items():
    for vn, V in visitor_cases.items():
        att = min(L + V, AS_CAPACITY)
        sc.append({"locals_case": ln, "visitors_case": vn, "locals_per_game": round(L),
                   "visitors_per_game": round(V), "attendance_per_game": round(att),
                   "visitor_share_pct": round(100 * V / (L + V), 1),
                   "visitor_tickets_per_year": round(V * AS_DATES),
                   "shortfall_vs_plan_visitor_tickets": round(as_vis - V * AS_DATES)})
sc = pd.DataFrame(sc)
sc.to_csv(RES / "as_scenarios.csv", index=False)

summary = {
    "events_with_measured_share": int(len(ev)),
    "raiders_games_with_share": int(len(rg)),
    "raiders_regular_games_with_attendance": int(len(reg)),
    "raiders_regular_mean_share_pct": round(float(reg.out_of_town_pct.mean()), 1),
    "raiders_regular_mean_locals_per_game": round(float(reg.locals.mean())),
    "raiders_regular_locals_range": [round(float(reg.locals.min())), round(float(reg.locals.max()))],
    "raiders_regular_mean_visitors_per_game": round(float(reg.visitors.mean())),
    "raiders_regular_visitors_range": [round(float(reg.visitors.min())), round(float(reg.visitors.max()))],
    "raiders_corr_attendance_vs_share": round(corr_att_share, 2),
    "raiders_corr_attendance_vs_locals": round(corr_att_locals, 2),
    "raiders_2025_visitor_tickets": round(float(raiders_vis)),
    "raiders_2025_local_tickets": round(float(raiders_loc)),
    "vgk_visitor_tickets_range": [round(0.15 * vgk_total), round(0.25 * vgk_total)],
    "vgk_local_tickets_range": [round(0.75 * vgk_total), round(0.85 * vgk_total)],
    "as_plan_visitor_tickets": round(float(as_vis)),
    "as_plan_local_tickets": round(float(as_loc)),
    "as_plan_incremental_visitor_tickets": round(AS_INCREMENTAL_SHARE * as_total),
    "as_visitor_tickets_vs_raiders": round(float(as_vis / raiders_vis), 2),
    "as_visitor_tickets_vs_raiders_plus_vgk": [round(float(as_vis / existing_vis[1]), 2),
                                               round(float(as_vis / existing_vis[0]), 2)],
    "as_local_tickets_vs_raiders_plus_vgk": [round(float(as_loc / existing_loc[1]), 2),
                                             round(float(as_loc / existing_loc[0]), 2)],
    "as_visitors_per_game_vs_vgk": [round(float(0.30 * AS_SELLOUT / (0.25 * VGK_AVG)), 2),
                                    round(float(0.30 * AS_SELLOUT / (0.15 * VGK_AVG)), 2)],
    "as_local_tickets_per_resident": round(float(as_local_tpr), 3),
    "as_total_tickets_per_resident": round(float(as_total_tpr), 3),
    "mlb_peer_metros": peer.metro.tolist(),
    "mlb_peer_tickets_per_resident_min_median_max": [
        round(float(peer.tickets_per_resident.min()), 3),
        round(float(peer.tickets_per_resident.median()), 3),
        round(float(peer.tickets_per_resident.max()), 3)],
    "visitor_trips_if_2_or_3_games_per_trip": [round(float(as_vis / 3)), round(float(as_vis / 2))],
}
(RES / "summary.json").write_text(json.dumps(summary, indent=2))

print(by_kind.to_string(index=False))
print(json.dumps(fit_out, indent=2))
print(pd.DataFrame(rows).to_string(index=False))
print(rg_out.to_string(index=False))
print(gm.to_string(index=False))
print(vol.round(0).T.to_string())
print(mlb.sort_values("tickets_per_resident")[["team", "metro_pop_2025", "avg_attendance", "tickets_per_resident"]].round(3).to_string(index=False))
print(sc.to_string(index=False))
print(json.dumps(summary, indent=2))
