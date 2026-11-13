"""NBA market-size model: what would a Las Vegas team draw?

Inputs:  data/nba_market_attendance.csv (29 U.S. NBA teams)
Outputs: results/market_summary.json, results/peer_group.csv,
         results/residents_per_team.csv, results/vegas_ticket_scenarios.csv,
         results/peer_attendance.png
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

LV_POP = 2_407_226          # Clark County / Las Vegas MSA, Census July 2025
LV_VISITORS_2025 = 38_545_700
HOME_GAMES = 41
PEER_LO, PEER_HI = 1.3e6, 3.1e6

df = pd.read_csv(ROOT / "data" / "nba_market_attendance.csv")
df["pop_per_team"] = df.metro_pop_2025 / df.big4_teams
df["tickets_per_resident"] = HOME_GAMES * df.avg_home_att / df.metro_pop_2025

# League-wide fit: attendance ~ log(metro population)
X = np.column_stack([np.ones(len(df)), np.log(df.metro_pop_2025 / 1e6)])
y = df.avg_home_att.to_numpy(float)
beta, *_ = np.linalg.lstsq(X, y, rcond=None)
resid = y - X @ beta
sd = np.sqrt((resid ** 2).sum() / (len(df) - 2))
r2 = 1 - (resid ** 2).sum() / ((y - y.mean()) ** 2).sum()
x0 = np.array([1.0, np.log(LV_POP / 1e6)])
pred = float(x0 @ beta)
se = float(sd * np.sqrt(1 + x0 @ np.linalg.inv(X.T @ X) @ x0))
T80 = 1.314  # t quantile, 27 df, two-sided 80%

peers = df[(df.metro_pop_2025 >= PEER_LO) & (df.metro_pop_2025 <= PEER_HI)].sort_values(
    "avg_home_att", ascending=False)
peers.to_csv(RES / "peer_group.csv", index=False)

summary = {
    "n_teams": int(len(df)),
    "league_mean": round(float(y.mean())),
    "ols_intercept": round(float(beta[0]), 1),
    "ols_slope_log_pop_m": round(float(beta[1]), 1),
    "ols_r2": round(float(r2), 3),
    "ols_resid_sd": round(float(sd)),
    "vegas_ols_prediction": round(pred),
    "vegas_ols_80pct_interval": [round(pred - T80 * se), round(pred + T80 * se)],
    "peer_n": int(len(peers)),
    "peer_median": round(float(peers.avg_home_att.median())),
    "peer_mean": round(float(peers.avg_home_att.mean())),
    "peer_iqr": [round(float(q)) for q in np.percentile(peers.avg_home_att, [25, 75])],
    "teams_averaging_20000_plus": df[df.avg_home_att >= 20000].team.tolist(),
}
(RES / "market_summary.json").write_text(json.dumps(summary, indent=2))

# Residents per big-four team, by metro, plus Las Vegas today and in 2028
metros = df.drop_duplicates("metro")[["metro", "metro_pop_2025", "big4_teams"]].copy()
lv = pd.DataFrame({"metro": ["Las Vegas (today)", "Las Vegas (2028, with A's and NBA)"],
                   "metro_pop_2025": [LV_POP, LV_POP], "big4_teams": [2, 4]})
metros = pd.concat([metros, lv], ignore_index=True)
metros["residents_per_team"] = (metros.metro_pop_2025 / metros.big4_teams).round().astype(int)
metros.sort_values("residents_per_team").to_csv(RES / "residents_per_team.csv", index=False)

# Ticket scenarios for Las Vegas
rows = []
for seats in (17_500, 18_000, 18_500):
    for visitor_share in (0.0, 0.15, 0.25, 0.35):
        total = HOME_GAMES * seats
        local = total * (1 - visitor_share)
        rows.append({
            "seats": seats, "visitor_share": visitor_share, "season_tickets": total,
            "local_tickets": round(local),
            "local_tickets_per_resident": round(local / LV_POP, 3),
            "visitor_tickets": round(total * visitor_share),
            "visitor_tickets_pct_of_2025_visitors": round(100 * total * visitor_share / LV_VISITORS_2025, 2),
        })
pd.DataFrame(rows).to_csv(RES / "vegas_ticket_scenarios.csv", index=False)

fig, ax = plt.subplots(figsize=(8, 4.8))
p = peers.iloc[::-1]
ax.barh(p.team + " (" + p.metro + ")", p.avg_home_att, color="#b9b9ad")
ax.axvline(summary["peer_median"], color="#2a78d6", lw=2)
ax.text(summary["peer_median"], len(p) - 0.3, f"Peer median {summary['peer_median']:,}",
        color="#2a78d6", ha="center", va="bottom", fontsize=9)
ax.set_xlabel("Average home attendance, 2026-27 through Nov. 11")
ax.set_title("NBA teams in metros of 1.3 to 3.1 million people", loc="left")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(RES / "peer_attendance.png", dpi=150)
print(json.dumps(summary, indent=2))
