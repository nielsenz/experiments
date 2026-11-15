"""Chart: out-of-town share by kind of event, measured against estimated or planned.

Inputs:  data/events.csv, data/benchmarks.csv
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
bm = pd.read_csv(ROOT / "data" / "benchmarks.csv")

SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
MEASURED, ESTIMATE = "#2a78d6", "#eb6834"

rows = [
    ("National Finals Rodeo\n10 nights a year", ev[ev.kind == "rodeo"], None),
    ("One-off sports events\n1 or 2 dates", ev[ev.kind == "one_off_sport"], None),
    ("Stadium concerts\n1 or 2 dates", ev[ev.kind == "concert"], None),
    ("Raiders, regular season\n8 or 9 dates a year", ev[ev.kind == "raiders_regular"], None),
    ("Raiders, preseason\n1 or 2 dates a year", ev[ev.kind == "raiders_preseason"], None),
    ("A's ballpark plan\n81 dates a year", None, (27, 30)),
    ("Golden Knights, estimates\n41 dates a year", None, (15, 25)),
]

fig, ax = plt.subplots(figsize=(7.2, 5.6), dpi=200)
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
        lo, hi = est
        ax.plot([lo, hi], [y, y], color=ESTIMATE, lw=2, zorder=3)
        ax.scatter([lo, hi], [y, y], s=52, facecolor=SURFACE, edgecolor=ESTIMATE,
                   linewidth=2, marker="D", zorder=4)
        ax.text(101, y, f"{lo}-{hi}%   not measured", va="center", ha="left", fontsize=9, color=INK)

ax.set_yticks(range(n))
ax.set_yticklabels([r[0] for r in rows][::-1], fontsize=9, color=INK)
ax.set_xlim(0, 100)
ax.set_ylim(-0.6, n - 0.4)
ax.set_xticks(range(0, 101, 20))
ax.set_xticklabels([f"{v}%" for v in range(0, 101, 20)], fontsize=9, color=MUTED)
ax.set_xlabel("Share of attendees from outside Southern Nevada", fontsize=9, color=MUTED)
ax.grid(axis="x", color=GRID, lw=0.8)
ax.set_axisbelow(True)
ax.axhline(1.5, color=GRID, lw=1)
for s in ax.spines.values():
    s.set_visible(False)
ax.tick_params(length=0)

h1 = plt.Line2D([], [], marker="o", ls="", color=MEASURED, markersize=7, label="Measured event (Stadium Authority reports, press)")
h2 = plt.Line2D([], [], marker="|", ls="", color=INK, markersize=12, markeredgewidth=1.6, label="Mean of measured events")
h3 = plt.Line2D([], [], marker="D", ls="-", color=ESTIMATE, markerfacecolor=SURFACE, markeredgewidth=2, markersize=6, label="Estimate or plan, low to high")
ax.legend(handles=[h1, h2, h3], loc="upper center", bbox_to_anchor=(0.42, -0.13), ncol=1,
          frameon=False, fontsize=8.5, labelcolor=INK)
fig.suptitle("Out-of-town share of Las Vegas crowds", x=0.02, ha="left", fontsize=13, color=INK, fontweight="bold")
fig.text(0.02, 0.925, "39 events with a reported share, 2022 to 2025. Nothing above 10 dates a year has been measured.",
         fontsize=9, color=MUTED, ha="left")
fig.subplots_adjust(left=0.26, right=0.74, top=0.89, bottom=0.25)
fig.savefig(ROOT / "results" / "out_of_town_share.png", facecolor=SURFACE)
