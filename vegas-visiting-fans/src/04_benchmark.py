"""Test the "about 4,500 visitors a game" benchmark from four independent directions.

Inputs:  data/events.csv, results/summary.json, results/opponent_summary.json,
         results/vegas_opponent_projection.csv (run 01 and 03 first)
Outputs: results/visitor_benchmark_legs.csv, results/visitor_benchmark_channels.csv,
         results/visitor_benchmark.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
S = json.loads((RES / "summary.json").read_text())
proj = pd.read_csv(RES / "vegas_opponent_projection.csv")
ev = pd.read_csv(ROOT / "data" / "events.csv", parse_dates=["date"])

# Plan (legislative and traffic-study versions)
PLAN_V = np.array(S["as_plan_visitors_per_game_low_high"], float)      # visitors per game
PLAN_TRIP = 0.53 * PLAN_V                                              # came because of the game
PLAN_INCID = 0.47 * PLAN_V                                             # already in town
DATES = 81

# LVCVA Visitor Profile 2025
VISITORS = 38_545_700
NIGHTS = 3.2
SAMPLE = 5_409
ATTENDED, PRIMARY = 0.05, 0.03
in_town = VISITORS * NIGHTS / 365
att_n, prim_n = ATTENDED * VISITORS, PRIMARY * VISITORS
incid_n = att_n - prim_n
moe = 1.96 * np.sqrt(ATTENDED * (1 - ATTENDED) / SAMPLE)               # sampling only; the survey also rounds to whole percents

# Leg A: Allegiant events, visitors who did not come mainly for the event
ev["visitors"] = ev.attendance * ev.out_of_town_pct / 100
ev["incidental"] = ev.visitors * (1 - ev.main_reason_pct / 100)
ev["trip"] = ev.visitors - ev.incidental
nfl = ev.kind == "nfl_regular"
incid = {"Raiders regular season": ev[nfl].incidental, "Concerts": ev[ev.kind == "concert"].incidental,
         "All 96 events": ev.incidental}
legA = {k: [round(float(x)) for x in (s.quantile(.25), s.median(), s.quantile(.75), s.max())] for k, s in incid.items()}

# Leg B: other MLB markets, out-of-state attendees per game on 2025 attendance
mlb = [("Brewers, out of state (ticket data)", 0.14, 32_717), ("Brewers, out of state and overnight", 0.14 * 0.41, 32_717),
       ("Pirates, out of state (secondary source)", 0.30, 18_827), ("Cubs, outside Illinois (team figure, 2011)", 0.37, 37_259)]
legB = [{"benchmark": n, "share_pct": round(100 * s, 1), "per_game": round(s * a)} for n, s, a in mlb]

# Leg C: opponent-attributable attendance projected on a Las Vegas schedule (script 03)
legC = proj[proj.base_attendance == 26_476].set_index("case").opponent_attributable_per_game.to_dict()
legC_hi = proj[proj.base_attendance == 29_400].set_index("case").opponent_attributable_per_game.to_dict()

legs = pd.DataFrame(
    [{"leg": "Plan", "benchmark": "A's plan, all visitors", "per_game_low": PLAN_V[0], "per_game_high": PLAN_V[1]},
     {"leg": "Plan", "benchmark": "A's plan, came for the game (53%)", "per_game_low": PLAN_TRIP[0], "per_game_high": PLAN_TRIP[1]},
     {"leg": "Plan", "benchmark": "A's plan, already in town (47%)", "per_game_low": PLAN_INCID[0], "per_game_high": PLAN_INCID[1]},
     {"leg": "Estimate", "benchmark": "Golden Knights, 15 to 25% of 17,929", "per_game_low": 0.15 * 17_929, "per_game_high": 0.25 * 17_929}]
    + [{"leg": "Other MLB markets", "benchmark": r["benchmark"], "per_game_low": r["per_game"], "per_game_high": r["per_game"]} for r in legB]
    + [{"leg": "Opponent-attributable (game logs)", "benchmark": k, "per_game_low": legC[k], "per_game_high": legC_hi[k]} for k in legC]
    + [{"leg": "Already in town (Allegiant survey)", "benchmark": f"{k}: middle half of events", "per_game_low": v[0], "per_game_high": v[2]}
       for k, v in legA.items()])
legs.round(0).to_csv(RES / "visitor_benchmark_legs.csv", index=False)

# Channel build-up for one A's game
c_keys = list(legC)
channels = pd.DataFrame([
    {"channel": "Came because of the game", "low": legC[c_keys[0]], "central": legC[c_keys[1]], "high": legC_hi[c_keys[2]],
     "low_basis": "league-average opponent sensitivity", "central_basis": "top quarter of parks",
     "high_basis": "most opponent-dependent park (the A's in Oakland)", "plan_low": PLAN_TRIP[0], "plan_high": PLAN_TRIP[1]},
    {"channel": "Already in town", "low": legA["Concerts"][0], "central": legA["All 96 events"][1], "high": legA["Raiders regular season"][2],
     "low_basis": "lower-quartile concert", "central_basis": "median Allegiant event", "high_basis": "upper-quartile Raiders game",
     "plan_low": PLAN_INCID[0], "plan_high": PLAN_INCID[1]}])
tot = {"channel": "Total visitors per game", "low": channels.low.sum(), "central": channels.central.sum(), "high": channels.high.sum(),
       "low_basis": "", "central_basis": "", "high_basis": "", "plan_low": PLAN_V[0], "plan_high": PLAN_V[1]}
channels = pd.concat([channels, pd.DataFrame([tot])], ignore_index=True)
channels.round(0).to_csv(RES / "visitor_benchmark_channels.csv", index=False)

out = {
    "visitors_in_town_per_night": round(in_town),
    "plan_visitors_share_of_in_town_pct": [round(100 * x / in_town, 2) for x in PLAN_V],
    "plan_incidental_share_of_in_town_pct": [round(100 * x / in_town, 2) for x in PLAN_INCID],
    "raiders_incidental_per_game_median": legA["Raiders regular season"][1],
    "raiders_incidental_share_of_in_town_pct": round(100 * legA["Raiders regular season"][1] / in_town, 2),
    "allegiant_incidental_quartiles_max": legA,
    "lvcva_attended_sport": round(att_n), "lvcva_primary_sport": round(prim_n), "lvcva_incidental_sport": round(incid_n),
    "lvcva_attended_moe_people": round(moe * VISITORS), "lvcva_attended_moe_pts": round(100 * moe, 2),
    "lvcva_one_point_in_people": round(0.01 * VISITORS),
    "plan_visitor_tickets": [round(x * DATES) for x in PLAN_V],
    "plan_vs_attended_one_game_each_pct": [round(100 * x * DATES / att_n) for x in PLAN_V],
    "plan_vs_attended_two_games_each_pct": [round(100 * x * DATES / 2 / att_n) for x in PLAN_V],
    "plan_trip_vs_primary_one_game_each_pct": [round(100 * x * DATES / prim_n) for x in PLAN_TRIP],
    "plan_trip_vs_primary_two_games_each_pct": [round(100 * x * DATES / 2 / prim_n) for x in PLAN_TRIP],
    "plan_incidental_vs_incidental_pct": [round(100 * x * DATES / incid_n) for x in PLAN_INCID],
    "allegiant_2025_sports_visitors": round(float(ev[(ev.date.dt.year == 2025) & (ev.kind != "concert")].visitors.sum())),
    "other_mlb_per_game": legB,
    "opponent_projection_per_game": {k: [legC[k], legC_hi[k]] for k in legC},
    "channel_totals_low_central_high": [round(float(tot[k])) for k in ("low", "central", "high")],
}
(RES / "visitor_benchmark.json").write_text(json.dumps(out, indent=2))
pd.set_option("display.width", 220)
print(legs.round(0).to_string(index=False)); print(channels.round(0).to_string(index=False)); print(json.dumps(out, indent=1))
