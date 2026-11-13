"""Golden Knights game-level attendance: how much does demand show up in the gate?

Two eras:
  - 2023-24 to 2025-26: every game announced above fixed seats (broker-held
    tickets counted), so attendance is a compressed signal.
  - 2026-27: the team cut broker sales and announced attendance can fall below
    capacity, so the gate starts to show real variation.

Inputs:  data/vgk_home_games.csv (regular-season home games, announced attendance)
Outputs: results/vgk_season_summary.csv, results/vgk_model_coefficients.csv,
         results/vgk_model_fit.json, results/vgk_by_weekday.csv,
         results/vgk_2026_27_vs_model.csv, results/vgk_era_comparison.json,
         results/vgk_attendance_by_game.png
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
RES.mkdir(exist_ok=True)
FIXED_SEATS = 17_367
NEW_ERA = "2026-27"

ORIGINAL_SIX = {"Boston Bruins", "Chicago Blackhawks", "Detroit Red Wings",
                "Montreal Canadiens", "New York Rangers", "Toronto Maple Leafs"}
CANADIAN = {"Calgary Flames", "Edmonton Oilers", "Montreal Canadiens", "Ottawa Senators",
            "Toronto Maple Leafs", "Vancouver Canucks", "Winnipeg Jets"}
PACIFIC = {"Anaheim Ducks", "Calgary Flames", "Edmonton Oilers", "Los Angeles Kings",
           "San Jose Sharks", "Seattle Kraken", "Vancouver Canucks"}

g = pd.read_csv(ROOT / "data" / "vgk_home_games.csv", parse_dates=["date"]).sort_values("date")
g = g.reset_index(drop=True)
g["weekday"] = g.date.dt.day_name()
g["fri_sat"] = g.weekday.isin(["Friday", "Saturday"]).astype(int)
g["sunday"] = (g.weekday == "Sunday").astype(int)
md = g.date.dt.month * 100 + g.date.dt.day
g["holiday_week"] = ((md >= 1223) | (md <= 102)).astype(int)
g["late_season"] = g.date.dt.month.isin([2, 3, 4]).astype(int)
g["home_opener"] = (g.groupby("season").cumcount() == 0).astype(int)
g["original_six"] = g.opponent.isin(ORIGINAL_SIX).astype(int)
g["canadian"] = g.opponent.isin(CANADIAN).astype(int)
g["pacific"] = g.opponent.isin(PACIFIC).astype(int)
g["season_2024_25"] = (g.season == "2024-25").astype(int)
g["season_2025_26"] = (g.season == "2025-26").astype(int)

season = g.groupby("season").attendance.agg(["count", "mean", "std", "min", "max"]).round(1)
season["mean_pct_of_fixed_seats"] = (season["mean"] / FIXED_SEATS * 100).round(1)
season["games_below_fixed_seats"] = g.groupby("season").apply(
    lambda d: int((d.attendance < FIXED_SEATS).sum()), include_groups=False)
season.to_csv(RES / "vgk_season_summary.csv")

old = g[g.season != NEW_ERA].reset_index(drop=True)
new = g[g.season == NEW_ERA].reset_index(drop=True)

old.groupby("weekday").attendance.agg(["count", "mean"]).round(0).reindex(
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
).to_csv(RES / "vgk_by_weekday.csv")

# --- Model on the capped era (2023-24 to 2025-26) ---
FEATURES = ["fri_sat", "sunday", "holiday_week", "late_season", "home_opener",
            "original_six", "canadian", "pacific", "season_2024_25", "season_2025_26"]


def design(d):
    return np.column_stack([np.ones(len(d))] + [d[f].to_numpy(float) for f in FEATURES])


X = design(old)
y = old.attendance.to_numpy(float)
XtX_inv = np.linalg.inv(X.T @ X)
beta = XtX_inv @ X.T @ y
resid = y - X @ beta
dof = len(y) - X.shape[1]
sigma2 = (resid ** 2).sum() / dof
se = np.sqrt(np.diag(XtX_inv) * sigma2)
r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum()
adj_r2 = 1 - (1 - r2) * (len(y) - 1) / dof

H = X @ XtX_inv @ X.T
loo_rmse = float(np.sqrt(((resid / (1 - np.diag(H))) ** 2).mean()))
base_err = []
for i in range(len(old)):
    same = (old.season == old.season.iloc[i]).to_numpy().copy()
    same[i] = False
    base_err.append(y[i] - y[same].mean())
base_rmse = float(np.sqrt(np.mean(np.square(base_err))))

coef = pd.DataFrame({"term": ["intercept"] + FEATURES, "coef": beta.round(1),
                     "std_err": se.round(1), "t": (beta / se).round(2)})
coef.to_csv(RES / "vgk_model_coefficients.csv", index=False)
fit = {
    "seasons": sorted(old.season.unique().tolist()),
    "n_games": int(len(old)), "r2": round(float(r2), 3), "adj_r2": round(float(adj_r2), 3),
    "resid_sd": round(float(np.sqrt(sigma2))),
    "loo_rmse_model": round(loo_rmse), "loo_rmse_season_mean_baseline": round(base_rmse),
    "attendance_sd_all_games": round(float(y.std(ddof=1))),
    "attendance_sd_pct_of_fixed_seats": round(float(y.std(ddof=1)) / FIXED_SEATS * 100, 2),
    "attendance_range": [int(y.min()), int(y.max())],
    "games_below_fixed_seats": int((y < FIXED_SEATS).sum()),
}
(RES / "vgk_model_fit.json").write_text(json.dumps(fit, indent=2))

# --- 2026-27: what the old model would have announced vs what was announced ---
# Predict at the 2025-26 season level (the most recent capped season).
Xn = design(new.assign(season_2025_26=1))
new["model_expected"] = (Xn @ beta).round().astype(int)
new["gap"] = new.attendance - new.model_expected
new["pct_of_fixed_seats"] = (new.attendance / FIXED_SEATS * 100).round(1)
new[["date", "weekday", "opponent", "attendance", "model_expected", "gap",
     "pct_of_fixed_seats"]].to_csv(RES / "vgk_2026_27_vs_model.csv", index=False)


def weekend_gap(d):
    d = d[d.home_opener == 0]
    wk = d[d.fri_sat == 1].attendance
    mid = d[(d.fri_sat == 0) & (d.sunday == 0)].attendance
    return {"fri_sat_games": int(len(wk)), "fri_sat_mean": round(float(wk.mean())),
            "mon_thu_games": int(len(mid)), "mon_thu_mean": round(float(mid.mean())),
            "gap": round(float(wk.mean() - mid.mean()))}


era = {
    "capped_era_2023_24_to_2025_26": {
        "games": int(len(old)), "mean": round(float(old.attendance.mean())),
        "sd": round(float(old.attendance.std(ddof=1))),
        "games_below_fixed_seats": int((old.attendance < FIXED_SEATS).sum()),
        "weekend_vs_midweek_excl_openers": weekend_gap(old),
    },
    "season_2026_27_to_date": {
        "games": int(len(new)), "mean": round(float(new.attendance.mean())),
        "sd": round(float(new.attendance.std(ddof=1))),
        "games_below_fixed_seats": int((new.attendance < FIXED_SEATS).sum()),
        "mean_gap_vs_model": round(float(new.gap.mean())),
        "mean_pct_change_vs_2025_26": round(float(
            new.attendance.mean() / g[g.season == "2025-26"].attendance.mean() - 1) * 100, 1),
        "weekend_vs_midweek_excl_openers": weekend_gap(new),
    },
}
(RES / "vgk_era_comparison.json").write_text(json.dumps(era, indent=2))

fig, ax = plt.subplots(figsize=(9, 4.4))
shades = {"2023-24": "#d9d9d0", "2024-25": "#b9b9ad", "2025-26": "#8a8a7e", "2026-27": "#2a78d6"}
for s, c in shades.items():
    d = g[g.season == s]
    ax.plot(range(1, len(d) + 1), d.attendance, marker="o", ms=3.5,
            lw=2 if s == NEW_ERA else 1, color=c, label=s)
ax.axhline(FIXED_SEATS, color="#666", lw=1, ls="--")
ax.text(41, FIXED_SEATS + 20, "17,367 fixed seats", ha="right", va="bottom", fontsize=8, color="#666")
ax.set_ylim(15_500, 18_900)
ax.set_xlabel("Home game number")
ax.set_ylabel("Announced attendance")
ax.set_title("Golden Knights attendance dropped below capacity in 2026-27", loc="left")
ax.legend(frameon=False, ncol=4, loc="lower right")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(RES / "vgk_attendance_by_game.png", dpi=150)

print(season.to_string(), "\n")
print(coef.to_string(index=False), "\n")
print(json.dumps(fit, indent=2))
print(new[["date", "weekday", "opponent", "attendance", "model_expected", "gap"]].to_string(index=False))
print(json.dumps(era, indent=2))
