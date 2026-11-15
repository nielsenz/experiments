"""Studies 1 and 2: when do fallen names start rising again, and what sets the clock?

Sample: once-common names (peak share >= 0.05% of that sex's births, peak in 1885 or later) that have
fallen to <= 20% of their peak, observed each year 1960-2014.  Outcome: is the name's share of births
higher 10 years later ("rising")?  Three candidate clocks:
  peak_age      years since the name's peak
  centroid_age  years since the average birth year of its bearers
  old_mean_age  average age of its living bearers aged 20+ (from SSA cohort life tables)
"""
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from panel import ROOT

warnings.filterwarnings("ignore")
P = ROOT / "data" / "processed"; RES = ROOT / "results"
CLOCKS = {"peak_age": ("Years since the name's peak", np.arange(40, 131, 10)),
          "centroid_age": ("Years since bearers' average birth year", np.arange(40, 101, 10)),
          "old_mean_age": ("Average age of living adult bearers", np.arange(40, 81, 5))}


def sample():
    p = pd.read_pickle(P / "panel.pkl")
    f = p[(p.log_peak >= np.log(5e-4)) & (p.rel_peak <= np.log(0.2)) & (p.peak_year >= 1885)
          & p.g10.notna() & (p.year >= 1960)].dropna(subset=list(CLOCKS)).copy()
    f["up"] = (f.g10 > 0).astype(int)
    f["double"] = (f.g10 >= np.log(2)).astype(int)
    return f


def binned(f, col, edges, extra=()):
    f = f.copy()
    f["bin_lo"] = pd.cut(f[col], edges, right=False, labels=edges[:-1]).astype(float)
    g = f.dropna(subset=["bin_lo"]).groupby(["bin_lo", "is_f", *extra])
    t = g.agg(share_rising=("up", "mean"), share_doubling=("double", "mean"), name_years=("up", "size"),
              names=("id", "nunique")).reset_index()
    t.insert(0, "clock", col)
    return t


def logit_fit(d, col):
    """up ~ clock + clock^2 + girl; returns (girl coefficient, girls' 50% crossing, boys' 50% crossing)."""
    x = (d[col] - d[col].mean()) / d[col].std()
    X = np.column_stack([x, x ** 2, d.is_f])
    m = LogisticRegression(C=1e6, max_iter=500).fit(X, d.up)
    grid = np.linspace(d[col].quantile(0.01), d[col].quantile(0.99), 400)
    gx = (grid - d[col].mean()) / d[col].std()
    cross = []
    for s in (1, 0):
        pr = m.predict_proba(np.column_stack([gx, gx ** 2, np.full(len(gx), s)]))[:, 1]
        cross.append(grid[np.argmax(pr >= 0.5)] if (pr >= 0.5).any() else np.nan)
    return m.coef_[0][2], cross[0], cross[1]


def sex_gap(f, n_boot=400, seed=0):
    rng = np.random.default_rng(seed)
    ids = f.id.unique(); grp = {i: g for i, g in f.groupby("id")}
    rows = []
    for label, d in {"1960-2014": f, "1960-1989": f[f.year <= 1989], "1990-2014": f[f.year >= 1990]}.items():
        boots = None
        if label == "1960-2014":
            boots = {c: [] for c in CLOCKS}
            for _ in range(n_boot):
                b = pd.concat([grp[i] for i in rng.choice(ids, len(ids))])
                for c in CLOCKS:
                    boots[c].append(logit_fit(b, c))
        for c in CLOCKS:
            coef, xf, xm = logit_fit(d, c)
            r = {"years": label, "clock": c, "girl_log_odds": coef, "girl_odds_ratio": np.exp(coef),
                 "girls_cross_50pct": xf, "boys_cross_50pct": xm}
            if boots:
                a = np.array(boots[c], dtype=float)
                r["or_ci_lo"], r["or_ci_hi"] = np.exp(np.nanpercentile(a[:, 0], [2.5, 97.5]))
                r["girls_cross_lo"], r["girls_cross_hi"] = np.nanpercentile(a[:, 1], [2.5, 97.5])
                r["boys_cross_lo"], r["boys_cross_hi"] = np.nanpercentile(a[:, 2], [2.5, 97.5])
                r["boys_cross_defined_share"] = np.mean(~np.isnan(a[:, 2]))
            rows.append(r)
    return pd.DataFrame(rows)


def figure(tab):
    ink, sub, grid, surf = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    col = {1: "#2a78d6", 0: "#eb6834"}; lab = {1: "Girls' names", 0: "Boys' names"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True, facecolor=surf)
    for ax, c in zip(axes, ("peak_age", "old_mean_age")):
        t = tab[(tab.clock == c) & (tab.names >= 25)]
        width = np.diff(CLOCKS[c][1])[0]
        for s in (1, 0):
            d = t[t.is_f == s]
            x = d.bin_lo + width / 2
            ax.plot(x, d.share_rising * 100, color=col[s], lw=2, marker="o", ms=6, mec=surf, mew=1.5, label=lab[s])
            ax.annotate(lab[s], (x.iloc[-1], d.share_rising.iloc[-1] * 100), xytext=(7, 0),
                        textcoords="offset points", va="center", fontsize=9.5, color=ink)
        ax.axhline(50, color=sub, lw=0.8, ls=(0, (2, 3)))
        ax.set_xlabel(CLOCKS[c][0], color=sub, fontsize=10)
        ax.set_facecolor(surf); ax.grid(axis="y", color=grid, lw=0.8); ax.set_axisbelow(True)
        for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
        ax.spines["bottom"].set_color(grid); ax.tick_params(colors=sub, length=0, labelsize=9)
        ax.set_ylim(0, 85); ax.margins(x=0.02)
        ax.set_xlim(ax.get_xlim()[0], ax.get_xlim()[1] + (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.2)
    axes[0].set_ylabel("Fallen names rising over the next 10 years (%)", color=sub, fontsize=10)
    axes[0].set_title("Clock 1: years since the name peaked", loc="left", fontsize=11, color=ink, pad=8)
    axes[1].set_title("Clock 2: how old its living bearers are", loc="left", fontsize=11, color=ink, pad=8)
    axes[0].legend(frameon=False, fontsize=9.5, loc="upper left", labelcolor=ink)
    fig.suptitle("Share of fallen US baby names that are rising again, by two clocks", x=0.01, ha="left",
                 fontsize=13, color=ink, fontweight="bold")
    fig.text(0.01, 0.01, "Once-common names at 20% or less of their peak, each year 1960-2014; bins with fewer than 25 names dropped. "
             "Source: SSA national name files 1880-2024, SSA cohort life tables.", fontsize=8, color=sub)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(RES / "two_clocks.png", dpi=170, facecolor=surf)


def main():
    f = sample()
    print("name-years", len(f), "names", f.id.nunique(), "girls", f[f.is_f == 1].id.nunique(), "boys", f[f.is_f == 0].id.nunique())
    tab = pd.concat([binned(f, c, e) for c, (_, e) in CLOCKS.items()])
    tab.round(4).to_csv(RES / "clock_bins.csv", index=False)
    f["period"] = pd.cut(f.year, [1959, 1979, 1994, 2004, 2014], labels=["1960-79", "1980-94", "1995-2004", "2005-14"])
    per = pd.concat([binned(f, c, e, extra=("period",)) for c, (_, e) in CLOCKS.items() if c != "centroid_age"])
    per[per.names >= 15].round(4).to_csv(RES / "clock_bins_by_period.csv", index=False)
    gap = sex_gap(f)
    gap.round(3).to_csv(RES / "sex_gap_by_clock.csv", index=False)
    pd.set_option("display.width", 250)
    for c in CLOCKS:
        print(tab[tab.clock == c].pivot(index="bin_lo", columns="is_f", values=["share_rising", "names"]).round(2).to_string())
    print(gap.round(2).to_string())
    figure(tab)
    robustness()



def robustness():
    """Does the sex gap vanish on the bearer-age clock under other sample definitions?"""
    p = pd.read_pickle(P / "panel.pkl")
    rows = []
    for peak_min in (2.5e-4, 5e-4, 1e-3):
        for fallen in (0.1, 0.2, 0.33):
            for outcome in ("up", "double"):
                f = p[(p.log_peak >= np.log(peak_min)) & (p.rel_peak <= np.log(fallen)) & (p.peak_year >= 1885)
                      & p.g10.notna() & (p.year >= 1960)].dropna(subset=list(CLOCKS)).copy()
                f["up"] = (f.g10 > (0 if outcome == "up" else np.log(2))).astype(int)
                r = {"peak_share_min": peak_min, "fallen_to": fallen, "outcome": "rising" if outcome == "up" else "doubling",
                     "names": f.id.nunique()}
                for c in ("peak_age", "old_mean_age"):
                    r[f"girl_odds_ratio_{c}"] = np.exp(logit_fit(f, c)[0])
                rows.append(r)
    t = pd.DataFrame(rows).round(5)
    t.to_csv(RES / "sex_gap_robustness.csv", index=False)
    print(t.to_string())


if __name__ == "__main__":
    main()
