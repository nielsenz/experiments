"""Disneyland Park crowd forecaster.
Data: queue-times.com daily crowd-level % for Disneyland Park (data/disneyland_daily_crowd.csv, 2023-01 -> 2026-11).
Target: each day's percentile rank within its own calendar year (the raw % drifts a lot year to year).
Validation: forward-chaining (train on earlier years, test on the next). Output: 2026-27 day-level forecast + best windows.
"""
import os, numpy as np, pandas as pd, datetime as dt
from dateutil.easter import easter
from sklearn.linear_model import RidgeCV
from sklearn.ensemble import HistGradientBoostingRegressor
from scipy.stats import spearmanr
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
B = os.path.join(os.path.dirname(__file__), '..'); R = f'{B}/results'

def nth_weekday(y, m, wd, n):  # n-th weekday (Mon=0) of month; n=-1 -> last
    if n > 0:
        d = dt.date(y, m, 1); d += dt.timedelta((wd - d.weekday()) % 7 + 7 * (n - 1)); return d
    d = dt.date(y, m + 1, 1) - dt.timedelta(1) if m < 12 else dt.date(y, 12, 31)
    return d - dt.timedelta((d.weekday() - wd) % 7)
def holidays(y):
    return {'newyear': dt.date(y, 1, 1), 'mlk': nth_weekday(y, 1, 0, 3), 'presidents': nth_weekday(y, 2, 0, 3), 'memorial': nth_weekday(y, 5, 0, -1),
            'july4': dt.date(y, 7, 4), 'labor': nth_weekday(y, 9, 0, 1), 'columbus': nth_weekday(y, 10, 0, 2), 'veterans': dt.date(y, 11, 11),
            'thanksgiving': nth_weekday(y, 11, 3, 4), 'christmas': dt.date(y, 12, 25)}

def features(dates, event=None):
    f = pd.DataFrame({'date': pd.to_datetime(dates)}); d = f.date.dt
    f['dow'] = d.dayofweek; doy = d.dayofyear
    for k in (1, 2, 3, 4):
        f[f's{k}'] = np.sin(2 * np.pi * k * doy / 365.25); f[f'c{k}'] = np.cos(2 * np.pi * k * doy / 365.25)
    for i in range(7): f[f'dow{i}'] = (f.dow == i).astype(int)
    H = {y: holidays(y) for y in range(f.date.dt.year.min() - 1, f.date.dt.year.max() + 2)}
    def rel(day, name, yrs=(0,)):
        return min(((day - H[day.year + o][name]).days for o in yrs), key=abs)
    dd = [x.date() for x in f.date]
    f['fed_holiday'] = [int(any(x == v for v in H[x.year].values())) for x in dd]
    for name in ('mlk', 'presidents', 'memorial', 'labor', 'columbus'):   # Monday holidays: Sat-Mon weekend and the days after
        f[f'{name}_wknd'] = [int(-2 <= rel(x, name) <= 0) for x in dd]
    f['presidents_week'] = [int(1 <= rel(x, 'presidents') <= 4) for x in dd]          # 'ski week' in parts of CA
    f['veterans_week'] = [int(-2 <= rel(x, 'veterans') <= 3) for x in dd]
    f['thanksgiving_week'] = [int(-4 <= rel(x, 'thanksgiving') <= 3) for x in dd]
    f['xmas_ny'] = [int((x.month == 12 and x.day >= 20) or (x.month == 1 and x.day <= 5)) for x in dd]
    f['pre_xmas_lull'] = [int(x.month == 12 and 8 <= x.day <= 19) for x in dd]
    f['after_ny_week'] = [int(x.month == 1 and 6 <= x.day <= 12) for x in dd]
    e = [(x - easter(x.year)).days for x in dd]
    f['easter_wk_before'] = [int(-9 <= v <= -1) for v in e]; f['easter_wk_after'] = [int(0 <= v <= 6) for v in e]; f['easter_2wk_before'] = [int(-16 <= v <= -10) for v in e]
    f['fall_break'] = [int(x.month == 10 and 4 <= x.day <= 19) for x in dd]              # Arizona / Utah school fall breaks
    f['summer'] = [int((x.month == 6 and x.day >= 10) or x.month == 7 or (x.month == 8 and x.day <= 15)) for x in dd]
    f['late_aug_sep'] = [int((x.month == 8 and x.day > 15) or (x.month == 9 and x.day <= 15)) for x in dd]
    f['event_night'] = 0 if event is None else np.asarray(event, int)                    # separately-ticketed after-hours party
    return f
FE = None
def XY(df):
    global FE
    f = features(df.date, df.event if 'event' in df else None); FE = [c for c in f.columns if c not in ('date', 'dow')]
    return f[FE].values

d = pd.read_csv(f'{B}/data/disneyland_daily_crowd.csv', parse_dates=['date'])
d['year'] = d.date.dt.year; d['event'] = d.close_hour.isin([19, 20, 21, 1]).astype(int)
d['rank'] = d.groupby('year').crowd_pct.rank(pct=True) * 100
d['wk'] = d.date.dt.to_period('W-SUN')

def evaluate(pred, test, label):
    rs = spearmanr(pred, test['rank']).statistic
    w = pd.DataFrame({'p': pred, 'a': test['rank'].values, 'wk': test.wk.values}).groupby('wk').mean(); rw = spearmanr(w.p, w.a).statistic
    q = pd.qcut(pred, 5, labels=False); a = test.crowd_pct.values
    return dict(model=label, test_year=int(test.year.iloc[0]), spearman_daily=rs, spearman_weekly=rw, actual_pct_quietest_fifth=a[q == 0].mean(),
                actual_pct_all=a.mean(), actual_pct_busiest_fifth=a[q == 4].mean())
rows = []
for ty in (2025, 2026):
    tr, te = d[d.year < ty], d[d.year == ty]
    base = tr.assign(m=tr.date.dt.month, w=tr.date.dt.dayofweek).groupby(['m', 'w'])['rank'].mean()
    pb = np.array([base.get((m, w), 50) for m, w in zip(te.date.dt.month, te.date.dt.dayofweek)]); rows.append(evaluate(pb, te, 'baseline: month x weekday mean'))
    rg = RidgeCV(alphas=np.logspace(-1, 3, 20)).fit(XY(tr), tr['rank']); pr = rg.predict(XY(te)); rows.append(evaluate(pr, te, 'ridge on calendar features'))
    gb = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.04, max_iter=250, l2_regularization=5, min_samples_leaf=25, random_state=0).fit(XY(tr), tr['rank'])
    pg = gb.predict(XY(te)); rows.append(evaluate(pg, te, 'gradient boosting')); rows.append(evaluate((pr + pg) / 2, te, 'ridge + boosting blend'))
    rows.append(evaluate(XY(te.assign(event=0)) @ rg.coef_ + rg.intercept_, te, 'ridge, event nights unknown'))
bt = pd.DataFrame(rows); bt.to_csv(f'{R}/backtest.csv', index=False); pd.set_option('display.width', 220); print(bt.round(2).to_string())

# ---------- final fit on everything, effect sizes ----------
rg = RidgeCV(alphas=np.logspace(-1, 3, 20)).fit(XY(d), d['rank']); gb = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.04, max_iter=250, l2_regularization=5, min_samples_leaf=25, random_state=0).fit(XY(d), d['rank'])
co = pd.Series(rg.coef_, FE); eff = co[[c for c in FE if not c[0] in 'sc' or c in ('summer',)]].sort_values()
eff.rename('ridge_effect_percentile_points').to_csv(f'{R}/calendar_effects.csv'); print(eff.round(1).to_string())
dow = d.groupby(d.date.dt.day_name())['rank'].mean().reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']); print(dow.round(1).to_string())
ev = d.groupby('event').agg(rank=('rank', 'mean'), pct=('crowd_pct', 'mean'), n=('rank', 'size')); print(ev.round(1))

# ---------- forecast ----------
fd = pd.DataFrame({'date': pd.date_range('2026-11-11', '2027-12-31')})
fd['score'] = (rg.predict(XY(fd)) + gb.predict(XY(fd))) / 2
fd['score'] = fd.score.clip(0, 100).round(1); fd['weekday'] = fd.date.dt.day_name()
hi = {1: 70, 2: 70, 3: 72, 4: 74, 5: 76, 6: 80, 7: 85, 8: 87, 9: 86, 10: 81, 11: 75, 12: 69}   # Anaheim avg daily high, F (climate normals, approx)
fd['avg_high_f'] = fd.date.dt.month.map(hi)
fx = features(fd.date); flags = ['fed_holiday', 'thanksgiving_week', 'xmas_ny', 'veterans_week', 'fall_break', 'easter_wk_before', 'easter_wk_after', 'presidents_week', 'summer']
fd['notes'] = [', '.join(c for c in flags if fx[c].iloc[i]) for i in range(len(fd))]
fd['tier'] = pd.cut(fd.score, [-1, 35, 45, 55, 65, 101], labels=['quietest', 'quiet', 'average', 'busy', 'busiest'])
fd.to_csv(f'{R}/forecast_2026-11_to_2027-12.csv', index=False)
# best 3-day mid-week windows (Tue-Thu), cool weather, no holiday flags
fd['wk'] = fd.date.dt.to_period('W-SUN'); mid = fd[fd.date.dt.dayofweek.isin([1, 2, 3])]
win = mid.groupby('wk').agg(start=('date', 'min'), end=('date', 'max'), score=('score', 'mean'), high=('avg_high_f', 'mean'), notes=('notes', lambda s: ', '.join(sorted(set(', '.join(s).split(', ')) - {''}))), n=('date', 'size'))
win = win[win.n == 3].drop(columns='n'); win['cool'] = win.high <= 76
win.sort_values('score').to_csv(f'{R}/best_midweek_windows.csv', index=False)
print(win[win.cool & (win.start >= '2027-01-01')].sort_values('score').head(12).round(1).to_string())
print(win[(win.start >= '2027-09-01')].sort_values('score').head(8).round(1).to_string())
print(win[win.start < '2027-01-01'].sort_values('score').round(1).to_string())

# ---------- charts ----------
ink, mut = '#1f2933', '#7b8794'
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'text.color': ink, 'axes.labelcolor': ink, 'xtick.color': mut, 'ytick.color': mut})
y27 = fd[fd.date.dt.year == 2027].copy(); grid = np.full((7, 54), np.nan); off = y27.date.iloc[0].dayofweek
for i, s in enumerate(y27.score): grid[(i + off) % 7, (i + off) // 7] = s
fig, ax = plt.subplots(figsize=(13, 3.2)); im = ax.imshow(grid, cmap='YlOrRd', vmin=25, vmax=75, aspect='auto')
ax.set_yticks(range(7)); ax.set_yticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']); ms = [((pd.Timestamp(2027, m, 1).dayofyear - 1 + off) // 7) for m in range(1, 13)]
ax.set_xticks(ms); ax.set_xticklabels(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']); ax.set_title('Disneyland Park 2027: forecast crowd score (percentile within year; lighter = quieter)', loc='left', fontweight='bold')
fig.colorbar(im, ax=ax, fraction=.015, pad=.01); fig.tight_layout(); fig.savefig(f'{R}/forecast_2027_calendar.png', dpi=150)
fig, ax = plt.subplots(figsize=(7, 3.6)); piv = d.pivot_table(index='year', columns=d.date.dt.dayofweek, values='crowd_pct')
for y, r in piv.iterrows(): ax.plot(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], r.values, marker='o', label=str(y))
ax.set_ylabel('Mean crowd level, %'); ax.set_title('Sunday is the quietest day, every year', loc='left', fontweight='bold'); ax.legend(frameon=False, ncol=4); fig.tight_layout(); fig.savefig(f'{R}/weekday_pattern.png', dpi=150)

# ---------- best 3-day windows on ANY consecutive days (the weekday pattern says weekends are not the enemy) ----------
fd = fd.reset_index(drop=True); fd['w3'] = fd.score.rolling(3).mean().shift(-2); fd['high3'] = fd.avg_high_f.rolling(3).mean().shift(-2)
cand = fd.dropna(subset=['w3']).sort_values('w3'); picks = []
for _, r in cand.iterrows():
    if all(abs((r.date - p.date).days) >= 7 for p in picks): picks.append(r)
anyw = pd.DataFrame([dict(start=p.date.date(), days=f"{p.weekday[:3]}-{(p.date + pd.Timedelta(days=2)).day_name()[:3]}", score=round(p.w3, 1), avg_high_f=round(p.high3), cool=p.high3 <= 76) for p in picks])
anyw.to_csv(f'{R}/best_3day_windows_any_days.csv', index=False)
print(anyw[anyw.cool & (pd.to_datetime(anyw.start) >= '2027-01-01')].head(12).to_string()); print(anyw[pd.to_datetime(anyw.start) < '2027-01-01'].head(5).to_string())
print(fd.groupby(fd.date.dt.month).score.mean().round(1).to_string())
