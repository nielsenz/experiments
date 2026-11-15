"""Visiting-fan share in Las Vegas: what the measured data supports for the A's.

Inputs:  data/events.csv           96 Allegiant Stadium events with a surveyed out-of-town share,
                                   transcribed from Stadium Authority quarterly activity reports
         data/benchmarks.csv       estimates, plans and other-market figures
         data/mlb_markets_2025.csv 13 one-team MLB metros, 2025 attendance
Outputs: results/*.csv, results/summary.json
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
AS_SELLOUT = 29_400           # traffic study: 98% of 30,000 fixed seats
AS_LEG_AVG = 26_476           # legislative basis: 2.6M over 95 events, per-game figure derived in a 2024 public comment
AS_VISITOR_SHARE = 0.30
AS_INCREMENTAL_OF_VISITORS = 0.53
AS_INCREMENTAL_PER_YEAR = 405_000   # all 95 planned events
AS_INCREMENTAL_BASEBALL = AS_VISITOR_SHARE * AS_INCREMENTAL_OF_VISITORS * AS_LEG_AVG * AS_DATES   # 81 games
VGK_DATES = 41
VGK_AVG = 17_929              # 2025-26 announced, from ../vegas-nba-demand
BREWERS_OUT_OF_STATE = 0.14   # team ticket data, cited in 2020 CSL study and 2023 legislative testimony
BREWERS_OVERNIGHT_OF_OOS = 0.41
BREWERS_2025 = 2_650_089

ev = pd.read_csv(ROOT / "data" / "events.csv", parse_dates=["date"])
ev["share"] = ev.out_of_town_pct / 100
ev["visitors"] = ev.attendance * ev.share
ev["locals"] = ev.attendance - ev.visitors
ev["came_for_event"] = ev.visitors * ev.main_reason_pct / 100
ev["weekday"] = ev.date.dt.day_name()
ev["midweek"] = ev.weekday.isin(["Monday", "Tuesday", "Wednesday", "Thursday"]).astype(int)
ev["summer"] = ev.date.dt.month.isin([6, 7, 8]).astype(int)
ev["nfl"] = ev.kind.str.startswith("nfl")
ev["season"] = np.where(ev.date.dt.month <= 2, ev.date.dt.year - 1, ev.date.dt.year)

# Transcription check: NFL attendance by report quarter against the reports' own summary table.
SUMMARY_NFL = {"Q4 2022": 284_386, "Q3 2023": 113_333, "Q4 2023": 399_586, "Q3 2024": 216_436, "Q4 2024": 277_159}
got = ev[ev.nfl].groupby("report").attendance.sum()
for q, want in SUMMARY_NFL.items():
    assert int(got[q]) == want, (q, int(got[q]), want)


def logit(p):
    return np.log(p / (1 - p))


def expit(x):
    return 1 / (1 + np.exp(-x))


def ols(d, y, cols):
    X = np.column_stack([np.ones(len(d))] + [d[c].to_numpy(float) for c in cols])
    yv = d[y].to_numpy(float)
    b, *_ = np.linalg.lstsq(X, yv, rcond=None)
    resid = yv - X @ b
    dof = len(d) - X.shape[1]
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * (resid @ resid) / dof)
    r2 = 1 - (resid @ resid) / ((yv - yv.mean()) ** 2).sum()
    out = pd.DataFrame({"target": y, "term": ["intercept"] + cols, "coef": b, "se": se, "t": b / se})
    out["n"] = len(d)
    out["r2"] = r2
    return out


# ---------------------------------------------------------------- 1. by kind
by_kind = (ev.groupby("kind").agg(
    events=("share", "size"), mean_pct=("out_of_town_pct", "mean"), min_pct=("out_of_town_pct", "min"),
    max_pct=("out_of_town_pct", "max"), mean_main_reason_pct=("main_reason_pct", "mean"),
    mean_attendance=("attendance", "mean"), mean_visitors=("visitors", "mean"), mean_locals=("locals", "mean"))
    .round(1).sort_values("mean_pct", ascending=False).reset_index())
by_kind.to_csv(RES / "share_by_kind.csv", index=False)

# ------------------------------------------- 2. share against dates per year
# Raiders games count as 10 dates a year; everything else by nights in the run (1, 2 or 4).
ev["dates_per_year"] = np.where(ev.nfl, 10, ev.run_nights)
ev["cluster"] = np.where(ev.nfl, "Raiders " + ev.season.astype(str),
                         ev.event.str.replace(r" (night|day) \d", "", regex=True) + " " + ev.date.dt.year.astype(str))


def fit_curve(d):
    X = np.column_stack([np.ones(len(d)), np.log(d.dates_per_year)])
    b, *_ = np.linalg.lstsq(X, logit(d.share.to_numpy()), rcond=None)
    return b


specs = {"all 96 events": ev, "excluding preseason": ev[ev.kind != "nfl_preseason"],
         "concerts only (1, 2 or 4 nights)": ev[ev.kind == "concert"],
         "non-NFL events only": ev[~ev.nfl]}
curve_rows, fit_out = [], {}
for name, d in specs.items():
    b = fit_curve(d)
    groups = [g for _, g in d.groupby("cluster")]
    boots = []
    for _ in range(3000):
        pick = RNG.integers(0, len(groups), len(groups))
        s = pd.concat([groups[i] for i in pick])
        if s.dates_per_year.nunique() > 1:
            boots.append(fit_curve(s))
    boots = np.array(boots)
    fit_out[name] = {"n_events": int(len(d)), "n_clusters": len(groups),
                     "slope_per_log_date": round(float(b[1]), 3),
                     "slope_80pct_interval": [round(float(q), 3) for q in np.quantile(boots[:, 1], [0.1, 0.9])]}
    for dates in (1, 2, 4, 10, 41, 81):
        p = expit(boots[:, 0] + boots[:, 1] * np.log(dates))
        curve_rows.append({"spec": name, "dates_per_year": dates,
                           "predicted_pct": round(100 * float(expit(b[0] + b[1] * np.log(dates))), 1),
                           "low80_pct": round(100 * float(np.quantile(p, 0.1)), 1),
                           "high80_pct": round(100 * float(np.quantile(p, 0.9)), 1)})
pd.DataFrame(curve_rows).to_csv(RES / "curve_predictions.csv", index=False)
(RES / "curve_fit.json").write_text(json.dumps(fit_out, indent=2))
by_run = (ev[ev.kind == "concert"].groupby("run_nights")
          .agg(events=("share", "size"), mean_pct=("out_of_town_pct", "mean")).round(1).reset_index())
by_run.to_csv(RES / "concert_share_by_run_length.csv", index=False)

# -------------------------------------------------------- 3. Raiders by game
rg = ev[ev.nfl].copy()
rg["preseason"] = (rg.kind == "nfl_preseason").astype(int)
rg["weeknight"] = rg.midweek
rg["late"] = rg.date.dt.month.isin([12, 1]).astype(int)
rg["division"] = rg.event.str.contains("Broncos|Chiefs|Chargers").astype(int)
for s in (2023, 2024, 2025):
    rg[f"s{s}"] = (rg.season == s).astype(int)
rg_out = rg[["event", "weekday", "season", "preseason", "attendance", "out_of_town_pct", "main_reason_pct",
             "visitors", "locals", "came_for_event"]].round(0)
rg_out.insert(0, "date", rg.date.dt.date)
rg_out.to_csv(RES / "raiders_games.csv", index=False)
terms = ["preseason", "weeknight", "late", "division", "s2023", "s2024", "s2025"]
gm = pd.concat([ols(rg, t, terms) for t in ("out_of_town_pct", "visitors", "locals")]).round(2)
gm.to_csv(RES / "raiders_game_model.csv", index=False)
reg = rg[rg.preseason == 0]
by_season = (reg.groupby("season").agg(
    games=("share", "size"), attendance=("attendance", "mean"), visitors=("visitors", "mean"),
    locals=("locals", "mean"), main_reason_pct=("main_reason_pct", "mean")).round(0))
by_season["out_of_town_pct"] = (100 * reg.groupby("season").visitors.sum() / reg.groupby("season").attendance.sum()).round(1)
by_season.to_csv(RES / "raiders_by_season.csv")
by_opp = (reg.assign(opp=reg.event.str.replace("Raiders vs ", ""))
          .groupby("opp").agg(games=("share", "size"), mean_pct=("out_of_town_pct", "mean"),
                              mean_visitors=("visitors", "mean")).round(0).sort_values("mean_pct", ascending=False))
by_opp.to_csv(RES / "raiders_by_opponent.csv")

# ------------------------------------------ 4. non-NFL: weekday and summer
nn = ev[~ev.nfl].copy()
for k in ("concert", "soccer", "college_football"):
    nn[k] = (nn.kind == k).astype(int)
nn["y2025"] = (nn.date.dt.year == 2025).astype(int)
nn["y2026"] = (nn.date.dt.year == 2026).astype(int)
nm = pd.concat([ols(nn, t, ["midweek", "summer", "concert", "soccer", "college_football", "y2025", "y2026"])
                for t in ("out_of_town_pct", "visitors")]).round(2)
nm.to_csv(RES / "non_nfl_model.csv", index=False)
midweek_tbl = (nn.groupby(["kind", "midweek"]).agg(events=("share", "size"), mean_pct=("out_of_town_pct", "mean"),
                                                   mean_visitors=("visitors", "mean")).round(0).reset_index())
midweek_tbl.to_csv(RES / "non_nfl_midweek.csv", index=False)

# ------------------------------------------------ 5. annual ticket volumes
r25 = rg[rg.season == 2025]            # 8 regular-season games and 1 preseason; the January 2026 game is missing
r_dates = 10
r_vis = r25.visitors.mean() * r_dates
r_loc = r25.locals.mean() * r_dates
r_inc = r25.came_for_event.mean() * r_dates
vgk_total = VGK_AVG * VGK_DATES
plans = {"A's plan, traffic study (30% of 29,400)": AS_SELLOUT, "A's plan, legislative (30% of 26,476)": AS_LEG_AVG}
vol = [
    {"property": "Raiders 2025 (measured, scaled to 10 dates)", "dates": r_dates,
     "visitor_tickets_low": r_vis, "visitor_tickets_high": r_vis, "local_tickets_low": r_loc, "local_tickets_high": r_loc},
    {"property": "Golden Knights 2025-26 (15 to 25% visitors, estimated)", "dates": VGK_DATES,
     "visitor_tickets_low": 0.15 * vgk_total, "visitor_tickets_high": 0.25 * vgk_total,
     "local_tickets_low": 0.75 * vgk_total, "local_tickets_high": 0.85 * vgk_total},
    {"property": "Brewers 2025 (14% out of state, ticket data)", "dates": 81,
     "visitor_tickets_low": BREWERS_OUT_OF_STATE * BREWERS_2025, "visitor_tickets_high": BREWERS_OUT_OF_STATE * BREWERS_2025,
     "local_tickets_low": (1 - BREWERS_OUT_OF_STATE) * BREWERS_2025, "local_tickets_high": (1 - BREWERS_OUT_OF_STATE) * BREWERS_2025},
]
for name, avg in plans.items():
    vol.append({"property": name, "dates": AS_DATES,
                "visitor_tickets_low": AS_VISITOR_SHARE * avg * AS_DATES, "visitor_tickets_high": AS_VISITOR_SHARE * avg * AS_DATES,
                "local_tickets_low": (1 - AS_VISITOR_SHARE) * avg * AS_DATES, "local_tickets_high": (1 - AS_VISITOR_SHARE) * avg * AS_DATES})
vol = pd.DataFrame(vol)
for side in ("visitor", "local"):
    for b in ("low", "high"):
        vol[f"{side}s_per_date_{b}"] = vol[f"{side}_tickets_{b}"] / vol.dates
vol.round(0).to_csv(RES / "annual_ticket_volumes.csv", index=False)
as_vis = (vol.visitor_tickets_low[4], vol.visitor_tickets_low[3])    # legislative, traffic study
as_loc = (vol.local_tickets_low[4], vol.local_tickets_low[3])
lv_vis = (r_vis + 0.15 * vgk_total, r_vis + 0.25 * vgk_total)
lv_loc = (r_loc + 0.75 * vgk_total, r_loc + 0.85 * vgk_total)

# ------------------------------------------ 6. MLB tickets per resident
mlb = pd.read_csv(ROOT / "data" / "mlb_markets_2025.csv")
mlb["tickets_per_resident"] = mlb.attendance_2025 / mlb.metro_pop_2025
peer = mlb[mlb.metro_pop_2025.between(1.3e6, 3.1e6)]
mlb.sort_values("tickets_per_resident").round(3).to_csv(RES / "mlb_tickets_per_resident.csv", index=False)

# ------------------------------------------------------- 7. A's scenarios
local_cases = {"plan, traffic study": 0.70 * AS_SELLOUT, "plan, legislative": 0.70 * AS_LEG_AVG,
               "Raiders regular-season local count": float(reg.locals.mean())}
visitor_cases = {"Golden Knights count, low (15%)": 0.15 * VGK_AVG, "Golden Knights count, high (25%)": 0.25 * VGK_AVG,
                 "Brewers out-of-state count (14% of 32,717)": BREWERS_OUT_OF_STATE * BREWERS_2025 / 81,
                 "plan, legislative (30% of 26,476)": 0.30 * AS_LEG_AVG, "plan, traffic study (30% of 29,400)": 0.30 * AS_SELLOUT}
sc = []
for ln, L in local_cases.items():
    for vn, V in visitor_cases.items():
        sc.append({"locals_case": ln, "visitors_case": vn, "locals_per_game": round(L), "visitors_per_game": round(V),
                   "attendance_per_game": round(min(L + V, 33_000)), "visitor_share_pct": round(100 * V / (L + V), 1),
                   "visitor_tickets_per_year": round(V * AS_DATES),
                   "incremental_at_53pct": round(V * AS_DATES * AS_INCREMENTAL_OF_VISITORS),
                   "incremental_vs_baseball_plan_pct": round(100 * V * AS_DATES * AS_INCREMENTAL_OF_VISITORS / AS_INCREMENTAL_BASEBALL)})
pd.DataFrame(sc).to_csv(RES / "as_scenarios.csv", index=False)

summary = {
    "events": int(len(ev)), "raiders_games": int(len(rg)), "raiders_regular_games": int(len(reg)),
    "raiders_regular_share_weighted_pct": round(100 * float(reg.visitors.sum() / reg.attendance.sum()), 1),
    "raiders_regular_locals_mean_sd_min_max": [round(float(x)) for x in (reg.locals.mean(), reg.locals.std(), reg.locals.min(), reg.locals.max())],
    "raiders_regular_visitors_mean_sd_min_max": [round(float(x)) for x in (reg.visitors.mean(), reg.visitors.std(), reg.visitors.min(), reg.visitors.max())],
    "raiders_corr_attendance_share": round(float(np.corrcoef(reg.attendance, reg.out_of_town_pct)[0, 1]), 2),
    "raiders_corr_attendance_locals": round(float(np.corrcoef(reg.attendance, reg.locals)[0, 1]), 2),
    "raiders_main_reason_mean_pct": round(float(reg.main_reason_pct.mean()), 1),
    "raiders_2025_visitor_tickets": round(float(r_vis)), "raiders_2025_local_tickets": round(float(r_loc)),
    "raiders_2025_came_for_game": round(float(r_inc)),
    "all_events_main_reason_mean_pct": round(float(ev.main_reason_pct.mean()), 1),
    "all_events_main_reason_min_pct": float(ev.main_reason_pct.min()),
    "non_nfl_midweek_events": int(nn.midweek.sum()),
    "as_plan_visitor_tickets_low_high": [round(float(x)) for x in as_vis],
    "as_plan_local_tickets_low_high": [round(float(x)) for x in as_loc],
    "as_plan_visitors_per_game_low_high": [round(0.30 * AS_LEG_AVG), round(0.30 * AS_SELLOUT)],
    "as_plan_incremental_per_year": AS_INCREMENTAL_PER_YEAR,
    "as_plan_incremental_baseball_only": round(AS_INCREMENTAL_BASEBALL),
    "as_plan_incremental_per_game": round(AS_INCREMENTAL_BASEBALL / AS_DATES),
    "as_incremental_baseball_vs_raiders_came_for_game": round(float(AS_INCREMENTAL_BASEBALL / r_inc), 2),
    "as_incremental_all_events_vs_raiders_came_for_game": round(float(AS_INCREMENTAL_PER_YEAR / r_inc), 2),
    "as_visitor_tickets_vs_raiders": [round(float(x / r_vis), 2) for x in as_vis],
    "as_visitor_tickets_vs_raiders_plus_vgk": [round(float(as_vis[0] / lv_vis[1]), 2), round(float(as_vis[1] / lv_vis[0]), 2)],
    "as_local_tickets_vs_raiders_plus_vgk": [round(float(as_loc[0] / lv_loc[1]), 2), round(float(as_loc[1] / lv_loc[0]), 2)],
    "as_visitor_tickets_vs_brewers_out_of_state": [round(float(x / (BREWERS_OUT_OF_STATE * BREWERS_2025)), 2) for x in as_vis],
    "brewers_out_of_state_tickets": round(BREWERS_OUT_OF_STATE * BREWERS_2025),
    "brewers_out_of_state_per_game": round(BREWERS_OUT_OF_STATE * BREWERS_2025 / 81),
    "brewers_overnight_out_of_state_tickets": round(BREWERS_OUT_OF_STATE * BREWERS_OVERNIGHT_OF_OOS * BREWERS_2025),
    "as_local_tickets_per_resident_low_high": [round(float(x / LV_POP), 3) for x in as_loc],
    "as_total_tickets_per_resident_low_high": [round(AS_LEG_AVG * 81 / LV_POP, 3), round(AS_SELLOUT * 81 / LV_POP, 3)],
    "mlb_peer_tickets_per_resident_min_median_max": [round(float(x), 3) for x in (
        peer.tickets_per_resident.min(), peer.tickets_per_resident.median(), peer.tickets_per_resident.max())],
}
(RES / "summary.json").write_text(json.dumps(summary, indent=2))

pd.set_option("display.width", 220)
print(by_kind.to_string(index=False)); print(by_run.to_string(index=False))
print(json.dumps(fit_out, indent=1)); print(pd.DataFrame(curve_rows).to_string(index=False))
print(gm.to_string(index=False)); print(by_season.to_string()); print(by_opp.to_string())
print(nm.to_string(index=False)); print(midweek_tbl.to_string(index=False))
print(vol.round(0).T.to_string()); print(pd.DataFrame(sc).to_string(index=False)); print(json.dumps(summary, indent=1))
