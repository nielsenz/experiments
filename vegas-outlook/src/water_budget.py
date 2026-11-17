"""Southern Nevada's Colorado River budget to 2041: demand vs. possible caps.

Demand = Clark County population x Colorado River consumptive use per resident.
Population follows UNLV CBER's 2026 forecast (2.505M in 2026, +204k by 2036,
2.77M in 2040, 3.08M in 2060; linear between those points). Per-resident use starts
from either the 2025 figure (198,000 AF) or the 2024 figure (212,000 AF) and then
follows one of three paths. Caps: the full 300,000 AF apportionment, the 250,000 AF
set for 2027-2028, and a hypothetical 210,000 AF (a 30% cut) as a stress case.

This counts Colorado River consumptive use only. It ignores groundwater, banked
water and other temporary supplies, all of which add cushion.

Run: python3 src/water_budget.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
RES.mkdir(exist_ok=True)

POP_POINTS = {2024: 2_425_000, 2025: 2_465_000, 2026: 2_505_000, 2036: 2_709_000, 2040: 2_770_000, 2060: 3_080_000}
# 2024 and 2025 are back-cast at +40,000 a year (CBER's stated 2026 gain); used only to turn
# the 2024/2025 use totals into per-resident figures.
BASELINES = {"2025 use (198k AF)": (198_000, 2025), "2024 use (212k AF)": (212_000, 2024)}
# Per-resident paths, as a multiple of the baseline reached by 2035 and held after.
PATHS = {
    "conservation goal met (95 to 86 GPCD by 2035)": 86 / 95,
    "flat per-resident use": 1.0,
    "use rises 10 GPCD (SNWA's climate/ageing-system caution)": 105 / 95,
}
CAPS = {"full apportionment": 300_000, "2027-28 allocation": 250_000, "stress: 30% cut": 210_000}
YEARS = list(range(2026, 2042))


def pop(year):
    xs, ys = zip(*sorted(POP_POINTS.items()))
    return float(np.interp(year, xs, ys))


def main():
    rows = []
    for bname, (use, byear) in BASELINES.items():
        per_cap = use / pop(byear)
        for pname, mult in PATHS.items():
            for y in YEARS:
                f = min(max((y - 2025) / (2035 - 2025), 0), 1)
                d = pop(y) * per_cap * (1 + (mult - 1) * f)
                rows.append({"baseline": bname, "path": pname, "year": y, "population": round(pop(y)),
                             "demand_af": round(d)})
    df = pd.DataFrame(rows)
    df.to_csv(RES / "water_demand_paths.csv", index=False)

    summ = []
    for (b, p), g in df.groupby(["baseline", "path"], sort=False):
        rec = {"baseline": b, "path": p}
        for y in (2031, 2036, 2041):
            rec[f"demand_{y}"] = int(g.loc[g.year == y, "demand_af"].iloc[0])
        for cname, cap in CAPS.items():
            over = g[g.demand_af > cap]
            rec[f"first_year_over_{cap // 1000}k"] = int(over.year.min()) if len(over) else "never by 2041"
        summ.append(rec)
    summ = pd.DataFrame(summ)
    summ.to_csv(RES / "water_summary.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 60)
    print(summ.to_string(index=False))
    print(f"\nPer-resident Colorado River use: 2025 {198_000 / pop(2025) * 325851 / 365:.1f} gal/day, "
          f"2024 {212_000 / pop(2024) * 325851 / 365:.1f} gal/day")


if __name__ == "__main__":
    main()
