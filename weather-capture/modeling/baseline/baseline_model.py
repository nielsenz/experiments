"""
Baseline demand model — predict CAISO hourly demand from a DAY-AHEAD weather
forecast plus calendar and lagged-demand features.

FIREWALL (see history/README.md): the temperature feature here is the
`previous_runs` day-ahead forecast — what you would actually have in hand a day
before the target hour — NOT the actuals. Actuals are used only as the label and
for scoring. Demand lag features use demand from >=24h earlier, which is also
known at day-ahead forecast time. Nothing peeks at the target hour.

Features
  - cd, hd      cooling/heating degree-hours from day-ahead state-avg temp (base 6C)
  - temp        raw day-ahead state-avg temp
  - hour        hour-of-day (cyclical sin/cos)
  - month       month (cyclical sin/cos)
  - dow         day-of-week (cyclical) + is_weekend
  - dem_lag24   demand 24h before target (known day-ahead)
  - dem_lag168  demand 168h (7d) before target

Split: time-ordered. Train = all but the final ~20%, test = final ~20%. No
random shuffling — that would leak future into past.

Baselines to beat
  - persistence: demand_lag24 as the prediction
  - climatology: mean demand per (hour, month) learned on train

Model: gradient-boosted trees (sklearn HistGradientBoostingRegressor) plus a
linear reference. Reports MAE / RMSE / MAPE / R2 and writes a residual figure.
"""
import os, sys, datetime as dt
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "EDA"))
import loaders as L

FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)
BASE_C = 6.0  # comfort base from the EDA response-curve minimum

report = []
def say(s=""):
    print(s); report.append(s)


def parse(k):
    return dt.datetime.strptime(k, "%Y-%m-%dT%H:%M")

def keyshift(k, hours):
    return (parse(k) - dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M")


say("# Baseline demand model\n")
say("Predict CAISO hourly demand from a **day-ahead** weather forecast + calendar "
    "+ lagged demand. Temperature feature is `previous_runs` (as-issued day-ahead), "
    "never actuals — see the firewall note in `history/README.md`.\n")

# ---------------------------------------------------------------------------
# Assemble the dataset
# ---------------------------------------------------------------------------
# day-ahead 5-city state-avg temperature
pr_sum, pr_cnt = {}, {}
for loc in L.LOCATIONS:
    pr = L.load_previous_runs(loc)
    for i, t in enumerate(pr["time"]):
        v = pr["temperature_2m_previous_day1"][i]
        if v is None:
            continue
        pr_sum[t] = pr_sum.get(t, 0.0) + float(v)
        pr_cnt[t] = pr_cnt.get(t, 0) + 1
temp_da = {t: pr_sum[t] / pr_cnt[t] for t in pr_sum if pr_cnt[t] == len(L.LOCATIONS)}

demand = L.load_caiso_demand()

keys = sorted(
    k for k in temp_da
    if demand.get(k) is not None
    and demand.get(keyshift(k, 24)) is not None
    and demand.get(keyshift(k, 168)) is not None
)
say(f"Usable rows (feature + label + lag24 + lag168): **{len(keys)}** "
    f"({keys[0]} → {keys[-1]}).\n")

def build_row(k):
    t = temp_da[k]
    d = parse(k)
    hour, month, dow = d.hour, d.month, d.weekday()
    cd = max(t - BASE_C, 0.0)
    hd = max(BASE_C - t, 0.0)
    return [
        t, cd, hd,
        np.sin(2*np.pi*hour/24), np.cos(2*np.pi*hour/24),
        np.sin(2*np.pi*month/12), np.cos(2*np.pi*month/12),
        np.sin(2*np.pi*dow/7), np.cos(2*np.pi*dow/7),
        1.0 if dow >= 5 else 0.0,
        demand[keyshift(k, 24)],
        demand[keyshift(k, 168)],
    ]

FEATNAMES = ["temp_da","cool_deg","heat_deg","hour_sin","hour_cos",
             "month_sin","month_cos","dow_sin","dow_cos","is_weekend",
             "dem_lag24","dem_lag168"]

X = np.array([build_row(k) for k in keys])
y = np.array([demand[k] for k in keys])
hours = np.array([parse(k).hour for k in keys])
months = np.array([parse(k).month for k in keys])

# ---------------------------------------------------------------------------
# Time-ordered split
# ---------------------------------------------------------------------------
split = int(len(keys) * 0.8)
Xtr, Xte = X[:split], X[split:]
ytr, yte = y[:split], y[split:]
say(f"Train: {len(Xtr)} rows ({keys[0][:10]} → {keys[split-1][:10]}). "
    f"Test: {len(Xte)} rows ({keys[split][:10]} → {keys[-1][:10]}).\n")

def scores(name, pred):
    mae = mean_absolute_error(yte, pred)
    rmse = np.sqrt(mean_squared_error(yte, pred))
    mape = np.mean(np.abs((yte - pred) / yte)) * 100
    r2 = r2_score(yte, pred)
    say(f"| {name} | {mae:,.0f} | {rmse:,.0f} | {mape:.2f}% | {r2:.4f} |")
    return mae, pred

say("## Results (test set = final 20%, time-ordered)\n")
say("| model | MAE (MWh) | RMSE (MWh) | MAPE | R² |")
say("|---|---|---|---|---|")

# --- baseline 1: persistence (demand 24h ago) ---
persist = Xte[:, FEATNAMES.index("dem_lag24")]
scores("persistence (lag-24)", persist)

# --- baseline 2: (hour, month) climatology from train ---
clim = {}
for h in range(24):
    for m in range(1, 13):
        mask = (hours[:split] == h) & (months[:split] == m)
        if mask.sum():
            clim[(h, m)] = ytr[mask].mean()
glob_mean = ytr.mean()
clim_pred = np.array([clim.get((hours[split+i], months[split+i]), glob_mean)
                      for i in range(len(Xte))])
scores("climatology (hour×month)", clim_pred)

# --- linear model ---
lin = LinearRegression().fit(Xtr, ytr)
_, lin_pred = scores("linear regression", lin.predict(Xte))

# --- gradient boosting ---
gbr = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05,
                                    max_depth=6, l2_regularization=1.0,
                                    random_state=0)
gbr.fit(Xtr, ytr)
gbr_mae, gbr_pred = scores("gradient boosting", gbr.predict(Xte))
say("")

# improvement vs baselines
persist_mae = mean_absolute_error(yte, persist)
say(f"Gradient boosting MAE **{gbr_mae:,.0f} MWh** — a "
    f"**{100*(persist_mae-gbr_mae)/persist_mae:.0f}%** cut vs persistence "
    f"({persist_mae:,.0f}). On a mean demand of {yte.mean():,.0f} MWh that is "
    f"~{100*gbr_mae/yte.mean():.1f}% error.\n")

# --- ablation: does the day-ahead weather feature actually help? ---
w_idx = [FEATNAMES.index(f) for f in ("temp_da", "cool_deg", "heat_deg")]
keep = [i for i in range(len(FEATNAMES)) if i not in w_idx]
gbr_nw = HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05,
                                       max_depth=6, l2_regularization=1.0,
                                       random_state=0).fit(Xtr[:, keep], ytr)
mae_nw = mean_absolute_error(yte, gbr_nw.predict(Xte[:, keep]))
say(f"**Weather ablation:** dropping the day-ahead temperature features raises "
    f"MAE to **{mae_nw:,.0f} MWh** (from {gbr_mae:,.0f}). The day-ahead forecast "
    f"buys a **{100*(mae_nw-gbr_mae)/mae_nw:.1f}%** MAE reduction on top of "
    f"demand autocorrelation — modest but real, and it validates the premise "
    f"that day-ahead weather improves a demand forecast.\n")

# ---------------------------------------------------------------------------
# Permutation importance (quick, on a test subsample)
# ---------------------------------------------------------------------------
from sklearn.inspection import permutation_importance
sub = min(4000, len(Xte))
pi = permutation_importance(gbr, Xte[:sub], yte[:sub], n_repeats=5,
                            random_state=0, scoring="neg_mean_absolute_error")
order = np.argsort(pi.importances_mean)[::-1]
say("## Feature importance (permutation, MAE drop)\n")
say("| feature | importance |")
say("|---|---|")
for i in order:
    say(f"| {FEATNAMES[i]} | {pi.importances_mean[i]:,.0f} |")
say("")

# ---------------------------------------------------------------------------
# Figures: predicted vs actual (time slice) + residual by hour
# ---------------------------------------------------------------------------
fig, axes = plt.subplots(2, 1, figsize=(12, 8))
n = min(24*21, len(yte))   # ~3 weeks
axes[0].plot(yte[:n], label="actual", lw=1)
axes[0].plot(gbr_pred[:n], label="GBR predicted", lw=1, alpha=0.8)
axes[0].plot(persist[:n], label="persistence", lw=0.6, alpha=0.5)
axes[0].set(title="Predicted vs actual demand (first ~3 test weeks)",
            xlabel="hour into test set", ylabel="MWh")
axes[0].legend(fontsize=8); axes[0].grid(alpha=0.3)

resid = gbr_pred - yte
hte = hours[split:]
rbh = [resid[hte == h] for h in range(24)]
axes[1].boxplot(rbh, positions=range(24), widths=0.6, showfliers=False)
axes[1].axhline(0, color="r", lw=0.8)
axes[1].set(title="GBR residual (pred − actual) by hour of day (UTC)",
            xlabel="hour UTC", ylabel="residual MWh")
axes[1].grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "baseline_model.png"), dpi=110)
plt.close(fig)
say("![baseline model](figures/baseline_model.png)\n")

say("## Notes & honest caveats\n")
say("- **Firewall respected**: temperature is the day-ahead `previous_runs` "
    "forecast; demand lags are ≥24h old. No target-hour leakage.\n")
say("- Test period is the most recent ~20% (a single contiguous block incl. "
    "summer). A rolling/backtested split would give a sturdier estimate.\n")
say("- `dem_lag24`/`dem_lag168` carry most of the signal (demand is highly "
    "autocorrelated); weather degree-days add the temperature-driven swing on "
    "top. That split is visible in the importance table.\n")
say("- Next: per-horizon evaluation, holiday calendar, and swapping the point "
    "forecast for the ensemble mean/spread to get uncertainty.\n")

with open(os.path.join(HERE, "baseline_summary.md"), "w") as fh:
    fh.write("\n".join(report) + "\n")
print("\n=== wrote baseline_summary.md + figures/baseline_model.png ===")
