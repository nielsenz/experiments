"""Chart: out-of-town share by kind of event, measured against estimated or planned.

Inputs:  data/events.csv (benchmark rows are entered below from data/benchmarks.csv)
Output:  results/out_of_town_share.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ev = pd.read_csv(ROOT / "data" / "events.csv")

SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
MEASURED, ESTIMATE = "#2a78d6", "#eb6834"

rows = [
    ("Wrestling, boxing, rugby\n1 or 2 dates", ev[ev.kind == "other_sport"], None),
    ("College football one-offs", ev[ev.kind == "college_football"], None),
    ("Stadium concerts\n1 to 4 nights", ev[ev.kind == "concert"], None),
    ("Raiders, regular season\n8 or 9 dates a year", ev[ev.kind == "nfl_regular"], None),
    ("Soccer matches", ev[ev.kind == "soccer"], None),
    ("Raiders, preseason", ev[ev.kind == "nfl_preseason"], None),
    ("A's ballpark plan\n81 dates a year", None, (27, 30, "plan")),
    ("A's top club buyers\nabout 300 seats", None, (24, 24, "buyers, not attendees")),
    ("Golden Knights\n41 dates a year", None, (15, 25, "estimates")),
    ("Brewers in Milwaukee\n81 dates, out of state", None, (14, 14, "ticket data")),
]

fig, ax = plt.subplots(figsize=(7.2, 7.0), dpi=200)
fig.patch.set_facecolor(SURFACE)
ax.set_facecolor(SURFACE)
rng = np.random.default_rng(7)
n = len(rows)
for i, (label, d, est) in enumerate(rows):
    y = n - 1 - i
    if d is not None:
        jit = rng.uniform(-0.16, 0.16, len(d)) if len(d) > 1 else [0]
        ax.scatter(d.out_of_town_pct, y + np.array(jit), s=46, color=MEASURED,
                   edgecolor=SURFACE, linewidth=1.2, zorder=3)
        m = d.out_of_town_pct.mean()
        ax.plot([m, m], [y - 0.3, y + 0.3], color=INK, lw=1.6, zorder=4)
        ax.text(101, y, f"{m:.0f}%   n={len(d)}", va="center", ha="left", fontsize=9, color=INK)
    else:
        lo, hi, note = est
        ax.plot([lo, hi], [y, y], color=ESTIMATE, lw=2, zorder=3)
        ax.scatter([lo, hi], [y, y], s=52, facecolor=SURFACE, edgecolor=ESTIMATE,
                   linewidth=2, marker="D", zorder=4)
        rng_txt = f"{lo}%" if lo == hi else f"{lo}-{hi}%"
        ax.text(101, y, f"{rng_txt}   {note}", va="center", ha="left", fontsize=9, color=INK)

ax.set_yticks(range(n))
ax.set_yticklabels([r[0] for r in rows][::-1], fontsize=9, color=INK)
ax.set_xlim(0, 100)
ax.set_ylim(-0.6, n - 0.4)
ax.set_xticks(range(0, 101, 20))
ax.set_xticklabels([f"{v}%" for v in range(0, 101, 20)], fontsize=9, color=MUTED)
ax.set_xlabel("Share of attendees from out of town", fontsize=9, color=MUTED)
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.axhline(3.5, color=GRID, lw=1)
for s in ax.spines.values():
    s.set_visible(False)
ax.tick_params(length=0)

h1 = plt.Line2D([], [], marker="o", ls="", color=MEASURED, markersize=7, label="Allegiant Stadium event, surveyed (Stadium Authority reports)")
h2 = plt.Line2D([], [], marker="|", ls="", color=INK, markersize=12, markeredgewidth=1.6, label="Mean of measured events")
h3 = plt.Line2D([], [], marker="D", ls="-", color=ESTIMATE, markerfacecolor=SURFACE, markeredgewidth=2, markersize=6, label="Not an attendee survey in Las Vegas: plan, estimate or other market")
ax.legend(handles=[h1, h2, h3], loc="upper center", bbox_to_anchor=(0.42, -0.09), ncol=1,
          frameon=False, fontsize=8.5, labelcolor=INK)
fig.suptitle("Out-of-town share of Las Vegas crowds", x=0.02, y=0.985, ha="left", fontsize=13, color=INK, fontweight="bold")
fig.text(0.02, 0.938, "96 Allegiant Stadium events, Oct. 2022 to May 2026. No Las Vegas team above 10 dates a year has been surveyed.",
         fontsize=9, color=MUTED, ha="left")
fig.subplots_adjust(left=0.27, right=0.70, top=0.90, bottom=0.20)
fig.savefig(ROOT / "results" / "out_of_town_share.png", facecolor=SURFACE)
