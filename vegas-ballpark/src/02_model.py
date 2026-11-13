"""Park-factor model: how elevation/temperature (air density), fence distance and wall height drive
home runs and run scoring, then a projection for the A's Las Vegas ballpark.
Run after 01_park_factors.py.  Writes results/*.csv and results/*.png
"""
import os, numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
B = os.path.join(os.path.dirname(__file__), '..'); D = f'{B}/data'; R = f'{B}/results'; os.makedirs(R, exist_ok=True)
rng = np.random.default_rng(7)

def rho_rel(elev_ft, temp_f):
    """Dry-air density relative to sea level at 70F (standard-atmosphere pressure, ideal gas)."""
    p = (1 - 2.25577e-5 * elev_ft * 0.3048) ** 5.25588
    return p * (459.67 + 70) / (459.67 + temp_f)

# ---------- assemble park-configuration table ----------
T = pd.read_csv(f'{D}/park_traits.csv'); ps = pd.read_csv(f'{D}/park_season.csv'); w = pd.read_csv(f'{D}/park_weather.csv')
rows = []
for _, t in T.iterrows():
    s = ps[(ps.park == t.park) & ps.season.between(t.y0, t.y1)]
    ww = w[(w.site == t.park) & w.season.between(t.y0, t.y1)]
    if s.empty: continue
    a = s.sum(numeric_only=True); d = t.to_dict(); d['games'] = a.home_g
    rate = lambda n, den: (a['home_' + n] / a['home_' + den]) / (a['road_' + n] / a['road_' + den])
    d.update(R=rate('r', 'g'), HR=rate('hr', 'ab'), BABIP=rate('hip', 'bip'), K=rate('k', 'pa'), BB=rate('bb', 'pa'),
             XBH=((a['home_2b'] + a['home_3b']) / a.home_ab) / ((a['road_2b'] + a['road_3b']) / a.road_ab))
    d['temp'] = np.average(ww.temp, weights=ww.games); d['wind'] = np.average(ww.wind.fillna(0), weights=ww.games)
    d['dome'] = np.average(ww.dome, weights=ww.games)
    for k in ('hr', 'ab', 'r', 'g'): d['h_' + k] = a['home_' + k]; d['r_' + k] = a['road_' + k]
    rows.append(d)
P = pd.DataFrame(rows)
P['dist'] = (P.lf + 2 * P.lcf + 2 * P.cf + 2 * P.rcf + P.rf) / 8          # mean fence distance, ft
P['wall'] = (P.wall_lf * 3 + P.wall_cf * 2 + P.wall_rf * 3) / 8           # mean wall height, ft
P['rho'] = rho_rel(P.elev_ft, P.temp); P['lrho'] = np.log(P.rho)
P['d_dist'] = P.dist - np.average(P.dist, weights=P.games); P['d_wall'] = P.wall - np.average(P.wall, weights=P.games)
P['w'] = P.games / P.games.mean()
P.to_csv(f'{R}/park_table.csv', index=False)

def wls(X, y, w):
    Xw = X * np.sqrt(w)[:, None]; return np.linalg.lstsq(Xw, y * np.sqrt(w), rcond=None)[0]
def design(df, feats): return np.column_stack([np.ones(len(df))] + [df[f].values for f in feats])
FE = {'HR': ['lrho', 'd_dist', 'd_wall'], 'R': ['lrho', 'd_dist', 'd_wall'], 'BABIP': ['lrho', 'd_dist'],
      'XBH': ['lrho', 'd_dist', 'd_wall'], 'K': ['lrho'], 'BB': ['lrho']}
coef, cv = {}, []
for tgt, feats in FE.items():
    y = np.log(P[tgt].values); X = design(P, feats); b = wls(X, y, P.w.values); coef[tgt] = dict(zip(['const'] + feats, b))
    # leave-one-PARK-out (drop every configuration of that physical park)
    pred = np.zeros(len(P))
    for pk in P.park.unique():
        m = (P.park != pk).values; pred[~m] = X[~m] @ wls(X[m], y[m], P.w.values[m])
    res = y - X @ b; r2 = 1 - np.average(res**2, weights=P.w) / np.average((y - np.average(y, weights=P.w))**2, weights=P.w)
    r2cv = 1 - np.average((y - pred)**2, weights=P.w) / np.average((y - np.average(y, weights=P.w))**2, weights=P.w)
    P[f'{tgt}_fit'] = np.exp(X @ b); P[f'{tgt}_lopo'] = np.exp(pred)
    cv.append(dict(target=tgt, r2_insample=r2, r2_leave_one_park_out=r2cv, rmse_lopo_pct=100 * np.sqrt(np.average((y - pred)**2, weights=P.w)),
                   resid_sd=np.sqrt(np.average(res**2, weights=P.w)), **coef[tgt]))
CV = pd.DataFrame(cv); CV.to_csv(f'{R}/model_coefficients.csv', index=False)
print(CV.round(3).to_string())
# the hard test: fit with NO Coors, predict Coors (an extrapolation 4x beyond the next-highest park)
for tgt in ('HR', 'R'):
    m = (P.park != 'DEN02').values; X = design(P, FE[tgt]); b = wls(X[m], np.log(P[tgt].values[m]), P.w.values[m])
    print(f'{tgt}: coors actual {P[tgt][~m].values[0]:.3f}  predicted without Coors {np.exp(X[~m] @ b)[0]:.3f}  density coef w/o Coors {b[1]:.2f} vs with {coef[tgt]["lrho"]:.2f}')
print(P[['key', 'games', 'elev_ft', 'temp', 'rho', 'dist', 'wall', 'HR', 'HR_lopo', 'R', 'R_lopo']].round(3).sort_values('R').to_string())

# ---------- physics cross-check: carry distance vs air density ----------
def carry(v_mph, la_deg, rho, cd=0.35, cl=0.22, dt=0.005):
    k = 0.5 * 1.2 * 0.00426 / 0.145 * rho; v = v_mph * 0.44704; a = np.radians(la_deg)
    x, y, vx, vy = 0., 1., v * np.cos(a), v * np.sin(a)
    while y > 0:
        s = np.hypot(vx, vy); ax = -k * cd * s * vx - k * cl * s * vy; ay = -9.81 - k * cd * s * vy + k * cl * s * vx
        vx += ax * dt; vy += ay * dt; x += vx * dt; y += vy * dt
    return x / 0.3048
base = carry(103, 28, 1.0)
phys = pd.DataFrame([dict(rho=r, carry_ft=carry(103, 28, r)) for r in np.arange(0.80, 1.021, 0.02)]); phys['gain_ft'] = phys.carry_ft - base
phys.to_csv(f'{R}/physics_carry.csv', index=False)
ft_per_logrho = (carry(103, 28, 0.95) - carry(103, 28, 1.0)) / np.log(0.95)   # ft of carry per unit log-density (negative)
hr_per_ft_fence = coef['HR']['d_dist']                                           # log-HR per ft of average fence distance
implied = -hr_per_ft_fence * ft_per_logrho                                       # physics-implied density coefficient
print(f'\nphysics: 103mph/28deg carries {base:.0f} ft at sea level; {ft_per_logrho:.0f} ft per unit log-density')
print(f'fence coef {hr_per_ft_fence:.4f} log-HR/ft -> physics-implied density coef {implied:.2f} vs fitted {coef["HR"]["lrho"]:.2f}')

# ---------- Las Vegas scenarios ----------
mD, mW = np.average(P.dist, weights=P.games), np.average(P.wall, weights=P.games)
def scen(name, elev, temp, lf, lcf, cf, rcf, rf, wall):
    return dict(scenario=name, elev_ft=elev, temp=temp, rho=rho_rel(elev, temp), lrho=np.log(rho_rel(elev, temp)),
                dist=(lf + 2*lcf + 2*cf + 2*rcf + rf) / 8, wall=wall, d_dist=(lf + 2*lcf + 2*cf + 2*rcf + rf) / 8 - mD, d_wall=wall - mW)
S = pd.DataFrame([
    scen("A's Strip dome, rumored dims 340/380/415, 10ft walls", 2133, 72, 340, 380, 415, 380, 340, 10),
    scen("A's Strip dome, MLB-average dims & walls", 2133, 72, 332, 377, 402, 376, 328, mW),
    scen("A's Strip dome, cozy 325/365/400, 8ft walls", 2133, 72, 325, 365, 400, 365, 325, 8),
    scen("Same site if it were open-air (95F), rumored dims", 2133, 95, 340, 380, 415, 380, 340, 10),
    scen("Las Vegas Ballpark (Aviators, 3,012 ft, open-air 95F)", 3012, 95, 340, 380, 415, 380, 340, 11.5),
    scen("Reference: sea-level 70F park with MLB-average dims", 0, 70, 332, 377, 402, 376, 328, mW),
])
# bootstrap over physical parks for parameter uncertainty + residual noise for 'true park effect' spread
parks = P.park.unique(); NB = 4000; draws = {t: np.zeros((NB, len(S))) for t in FE}
for i in range(NB):
    pick = rng.choice(parks, len(parks)); Pb = pd.concat([P[P.park == p] for p in pick])
    for tgt, feats in FE.items():
        b = wls(design(Pb, feats), np.log(Pb[tgt].values), Pb.w.values)
        sd = CV.set_index('target').loc[tgt, 'resid_sd']
        draws[tgt][i] = design(S, feats) @ b + rng.normal(0, sd, len(S))
out = S[['scenario', 'elev_ft', 'temp', 'rho', 'dist', 'wall']].copy()
for tgt, feats in FE.items():
    out[tgt] = np.exp(design(S, feats) @ np.array(list(coef[tgt].values())))
    out[tgt + '_lo'] = np.exp(np.percentile(draws[tgt], 10, axis=0)); out[tgt + '_hi'] = np.exp(np.percentile(draws[tgt], 90, axis=0))
out.to_csv(f'{R}/vegas_scenarios.csv', index=False)
pd.set_option('display.width', 250)
print(out[['scenario', 'rho', 'dist', 'HR', 'HR_lo', 'HR_hi', 'R', 'R_lo', 'R_hi', 'BABIP', 'XBH', 'K', 'BB']].round(3).to_string())
# rank of the headline scenario among current parks
cur = P[P.y1 == 2025].copy(); v = out.iloc[0]
print('\nheadline scenario rank among 2025 parks: runs #%d of %d, HR #%d' % ((cur.R_fit > v.R).sum() + 1, len(cur) + 1, (cur.HR_fit > v.HR).sum() + 1))
print('runs per game implied (both teams) at 8.9 R/G league baseline: %.2f; half-season team HR at 190 baseline: %.0f' % (8.9 * v.R, 95 * v.HR + 95))

# ---------- charts ----------
ink, mut, acc, acc2 = '#1f2933', '#7b8794', '#c2410c', '#0f766e'
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': mut, 'text.color': ink, 'axes.labelcolor': ink, 'xtick.color': mut, 'ytick.color': mut})
fig, ax = plt.subplots(1, 2, figsize=(12, 5))
for a_, tgt, ttl in ((ax[0], 'HR', 'Home runs'), (ax[1], 'R', 'Runs')):
    a_.scatter(P.rho, P[tgt], s=P.games / 12, c=mut, alpha=.55, lw=0)
    for _, r in P[P.key.isin(['COL', 'ARI', 'SF_b', 'BOS', 'CIN', 'SAC', 'TEX_a', 'ATL', 'SEA', 'KC'])].iterrows(): a_.annotate(r.key.split('_')[0], (r.rho, r[tgt]), xytext=(4, 4), textcoords='offset points', fontsize=8, color=mut)
    a_.errorbar([v.rho], [v[tgt]], yerr=[[v[tgt] - v[tgt + '_lo']], [v[tgt + '_hi'] - v[tgt]]], fmt='o', c=acc, ms=9, capsize=4)
    a_.annotate("A's Vegas dome\n(projected)", (v.rho, v[tgt]), xytext=(8, -4), textcoords='offset points', color=acc, fontsize=9, fontweight='bold')
    lv = out.iloc[4]; a_.scatter([lv.rho], [lv[tgt]], marker='D', c=acc2, s=60); a_.annotate('LV Ballpark (AAA)\nmodel, open-air', (lv.rho, lv[tgt]), xytext=(8, 0), textcoords='offset points', color=acc2, fontsize=8)
    a_.axhline(1, c=mut, lw=.6, ls=':'); a_.invert_xaxis(); a_.set_xlabel('Air density at game time (1.00 = sea level, 70°F)   thinner air →'); a_.set_ylabel(f'{ttl} park factor (home ÷ road)'); a_.set_title(f'{ttl}: thinner air, more offense', loc='left', fontweight='bold')
fig.tight_layout(); fig.savefig(f'{R}/density_vs_offense.png', dpi=150)
fig, ax = plt.subplots(figsize=(8, 9)); c2 = pd.concat([cur[['name', 'R_fit', 'R']].rename(columns={'R_fit': 'val'}), pd.DataFrame([dict(name="A's Las Vegas dome (projected)", val=v.R, R=np.nan)])]).sort_values('val')
col = [acc if 'Las Vegas' in n else mut for n in c2.name]; ax.barh(c2.name, c2.val - 1, left=1, color=col, alpha=.85); ax.scatter(c2.R, c2.name, c=ink, s=14, zorder=3, label='actual 2015–25')
ax.axvline(1, c=ink, lw=.8); ax.set_xlabel('Run park factor (bars = model, dots = actual)'); ax.set_title("Where the A's Vegas park would rank for run scoring", loc='left', fontweight='bold'); ax.legend(frameon=False, loc='lower right')
fig.tight_layout(); fig.savefig(f'{R}/run_factor_ranking.png', dpi=150)
