"""Las Vegas / Henderson home-price scenarios at 5, 10 and 15 years.

This is a scenario model, not a fitted forecast. History (Las Vegas Realtors
median single-family resale price at 14 dated anchors) sets the long-run growth
rate and shows how violent the swings have been. The simulation is an AR(1)
process on annual log price changes whose drift, persistence and volatility are
stated assumptions, each varied in a sensitivity grid.

Run: python3 src/housing_scenarios.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
RES.mkdir(exist_ok=True)

START_PRICE = 475_000        # LVR median single-family resale, Oct 2026
START_YOY = 0.001            # +0.1% year over year, Oct 2026
HORIZONS = [5, 10, 15]
N = 200_000
SEED = 20261116

# Drift = long-run nominal growth in the median, per year (log points).
SCENARIOS = {
    "downside": 0.010,   # prices lag inflation: weak tourism, water/heat discount, high rates
    "base": 0.030,       # roughly inflation plus a little; slower population growth than 1997-2026
    "upside": 0.045,     # repeats the 1997-2026 average: land scarcity, rates fall, in-migration
}
PHI = 0.6                # year-to-year persistence of price changes
SD = 0.10                # unconditional st. dev. of annual log change


def history():
    a = pd.read_csv(ROOT / "data" / "lvr_median_anchors.csv", parse_dates=["date"])
    a["years"] = (a["date"] - a["date"].iloc[0]).dt.days / 365.25
    rows = []
    for i in range(1, len(a)):
        dt = a["years"].iloc[i] - a["years"].iloc[i - 1]
        g = np.log(a["median_sf_price"].iloc[i] / a["median_sf_price"].iloc[i - 1]) / dt
        rows.append({"from": a["date"].iloc[i - 1].date(), "to": a["date"].iloc[i].date(),
                     "years": round(dt, 2), "annualized_change_pct": round((np.exp(g) - 1) * 100, 1)})
    seg = pd.DataFrame(rows)
    seg.to_csv(RES / "history_segments.csv", index=False)

    def cagr(d0, d1):
        r0, r1 = a[a["date"] == d0].iloc[0], a[a["date"] == d1].iloc[0]
        return (r1["median_sf_price"] / r0["median_sf_price"]) ** (1 / (r1["years"] - r0["years"])) - 1

    out = {
        "cagr_1997_2026": cagr("1997-07-01", "2026-10-01"),
        "cagr_2000_2026": cagr("2000-07-01", "2026-10-01"),
        "cagr_2006peak_2026": cagr("2006-06-01", "2026-10-01"),
        "cagr_2012trough_2026": cagr("2012-01-01", "2026-10-01"),
        "cagr_2022peak_2026": cagr("2022-05-01", "2026-10-01"),
        "peak_to_trough_2006_2012": 118000 / 315000 - 1,
        "years_to_regain_2006_peak": 13.7,
    }
    return a, seg, out


def simulate(mu, phi=PHI, sd=SD, n=N, years=15, seed=SEED):
    rng = np.random.default_rng(seed)
    eps_sd = sd * np.sqrt(1 - phi ** 2)
    r = np.full(n, START_YOY)
    logp = np.zeros((n, years + 1))
    for t in range(1, years + 1):
        r = mu + phi * (r - mu) + rng.normal(0, eps_sd, n)
        logp[:, t] = logp[:, t - 1] + r
    return START_PRICE * np.exp(logp)


def summarize(paths):
    rows = []
    for h in HORIZONS:
        p = paths[:, h]
        run_max = np.maximum.accumulate(paths[:, : h + 1], axis=1)
        dd = (paths[:, : h + 1] / run_max - 1).min(axis=1)
        rows.append({
            "year": h,
            "p10": np.percentile(p, 10), "p25": np.percentile(p, 25), "p50": np.percentile(p, 50),
            "p75": np.percentile(p, 75), "p90": np.percentile(p, 90),
            "prob_below_today": (p < START_PRICE).mean(),
            "prob_drawdown_20pct_by_then": (dd <= -0.20).mean(),
        })
    return pd.DataFrame(rows)


def payment(price, rate, down=0.20, years=30):
    loan = price * (1 - down)
    r = rate / 12
    return loan * r / (1 - (1 + r) ** (-years * 12))


def main():
    anchors, seg, hist = history()
    print("History (LVR median single-family):")
    print(seg.to_string(index=False))
    for k, v in hist.items():
        print(f"  {k}: {v:.3f}")

    all_rows, fan_rows = [], []
    for name, mu in SCENARIOS.items():
        paths = simulate(mu)
        s = summarize(paths)
        s.insert(0, "scenario", name)
        s.insert(1, "drift_pct", mu * 100)
        all_rows.append(s)
        for t in range(16):
            q = np.percentile(paths[:, t], [10, 50, 90])
            fan_rows.append({"scenario": name, "year": 2026 + t, "p10": q[0], "p50": q[1], "p90": q[2]})
    out = pd.concat(all_rows)
    out.to_csv(RES / "price_scenarios.csv", index=False)
    pd.DataFrame(fan_rows).round(0).to_csv(RES / "price_fan.csv", index=False)
    pd.set_option("display.width", 200)
    print("\nScenarios (metro median, nominal $):")
    print(out.round({"p10": -3, "p25": -3, "p50": -3, "p75": -3, "p90": -3,
                     "prob_below_today": 3, "prob_drawdown_20pct_by_then": 3}).to_string(index=False))

    # Sensitivity of the base case to persistence and volatility.
    sens = []
    for phi in (0.3, 0.6, 0.8):
        for sd in (0.07, 0.10, 0.13):
            s = summarize(simulate(SCENARIOS["base"], phi=phi, sd=sd, n=100_000))
            for _, r in s.iterrows():
                sens.append({"phi": phi, "sd": sd, "year": int(r["year"]), "p10": round(r["p10"], -3),
                             "p50": round(r["p50"], -3), "p90": round(r["p90"], -3),
                             "prob_below_today": round(r["prob_below_today"], 3),
                             "prob_drawdown_20pct": round(r["prob_drawdown_20pct_by_then"], 3)})
    sens = pd.DataFrame(sens)
    sens.to_csv(RES / "base_sensitivity.csv", index=False)
    print("\nBase-case sensitivity, year 10:")
    print(sens[sens.year == 10].to_string(index=False))

    # Does the assumed process allow a 2006-2012-sized crash? (check on realism of the tails)
    paths = simulate(SCENARIOS["base"], sd=0.13, n=100_000)
    run_max = np.maximum.accumulate(paths, axis=1)
    worst = (paths / run_max - 1).min(axis=1)
    print(f"\nP(drawdown of 40%+ within 15y | base, sd=0.13): {(worst <= -0.40).mean():.3f}")

    # Affordability: payment on the median, and what the same payment buys at other rates.
    aff = []
    base_pay = payment(START_PRICE, 0.0718)
    for rate in (0.0718, 0.0622, 0.060, 0.055, 0.050):
        pay = payment(START_PRICE, rate)
        same_pay_price = START_PRICE * base_pay / pay
        aff.append({"rate_pct": rate * 100, "p_and_i_on_475k_20pct_down": round(pay),
                    "price_same_payment_buys": round(same_pay_price, -3)})
    aff = pd.DataFrame(aff)
    aff.to_csv(RES / "affordability.csv", index=False)
    print("\nAffordability:")
    print(aff.to_string(index=False))


if __name__ == "__main__":
    main()
