"""Stress tests for the Las Vegas projection.
A. Park effects from a game-level Poisson model with batting-team-season and pitching-team-season effects
   (removes team quality and unbalanced schedules from the park factors).
B. Second stage on those park effects under many specifications.
C. An independent estimate of the air-density effect from day-to-day temperature swings inside each open-air park.
D. Vegas projections under each estimate; out-of-sample check against Las Vegas Ballpark (Aviators).
Writes results/robustness_*.csv.  Run after 03_game_table.py."""
import os, numpy as np, pandas as pd, scipy.sparse as sp, warnings
from sklearn.linear_model import PoissonRegressor
import statsmodels.api as sm
warnings.filterwarnings('ignore')
B = os.path.join(os.path.dirname(__file__), '..'); D = f'{B}/data'; R = f'{B}/results'; rng = np.random.default_rng(11)
def rho_rel(elev_ft, temp_f, rh=0.0):
    p = (1 - 2.25577e-5 * elev_ft * 0.3048) ** 5.25588
    tc = (np.asarray(temp_f, float) - 32) / 1.8; e = rh * 0.61094 * np.exp(17.625 * tc / (tc + 243.04)) / 101.325   # vapour pressure / sea-level pressure
    return p * (459.67 + 70) / (459.67 + temp_f) * (1 - 0.378 * e / p)
T = pd.read_csv(f'{D}/park_traits.csv'); g = pd.read_csv(f'{D}/games.csv.gz')
def config(park, season):
    m = T[(T.park == park) & (T.y0 <= season) & (T.y1 >= season)]
    return m.key.iloc[0] if len(m) else f'{park}_other'
ck = {(p, s): config(p, s) for p, s in g[['park', 'season']].drop_duplicates().itertuples(index=False)}
g['cfg'] = [ck[(p, s)] for p, s in zip(g.park, g.season)]
# two rows per game: one for each batting side
def long(g):
    a = g.rename(columns=lambda c: c[2:] if c.startswith('v_') else c)[['season', 'cfg', 'vis', 'home', 'r', 'hr', 'ab', 'k', 'bb', 'pa', 'xbh', 'hip', 'bip']].assign(bat=g.vis + g.season.astype(str), pit=g.home + g.season.astype(str), homebat=0)
    b = g.rename(columns=lambda c: c[2:] if c.startswith('h_') else c)[['season', 'cfg', 'vis', 'home', 'r', 'hr', 'ab', 'k', 'bb', 'pa', 'xbh', 'hip', 'bip']].assign(bat=g.home + g.season.astype(str), pit=g.vis + g.season.astype(str), homebat=1)
    return pd.concat([a, b], ignore_index=True)
OUTC = {'R': ('r', None), 'HR': ('hr', 'ab'), 'K': ('k', 'pa'), 'BB': ('bb', 'pa'), 'BABIP': ('hip', 'bip'), 'XBH': ('xbh', 'ab')}
def park_effects(gs):
    L = long(gs); cats = [pd.Categorical(L[c]) for c in ('cfg', 'bat', 'pit')]
    X = sp.hstack([sp.csr_matrix((np.ones(len(L)), (np.arange(len(L)), c.codes)), shape=(len(L), len(c.categories))) for c in cats] + [sp.csr_matrix(L.homebat.values[:, None])]).tocsr()
    n = gs.groupby('cfg').size(); out = pd.DataFrame({'games': n})
    for name, (y, ex) in OUTC.items():
        e = L[ex].values.astype(float) if ex else np.ones(len(L)); ok = e > 0
        m = PoissonRegressor(alpha=1e-7, max_iter=3000, tol=1e-9).fit(X[ok], L[y].values[ok] / e[ok], sample_weight=e[ok])
        b = pd.Series(m.coef_[:len(cats[0].categories)], cats[0].categories); out[name] = b - np.average(b.reindex(n.index), weights=n)
    return out
def stage2_table(pe):
    P = T.merge(pe, left_on='key', right_index=True); W = pd.read_csv(f'{D}/park_weather.csv')
    P['temp'] = [np.average(W[(W.site == r.park) & W.season.between(r.y0, r.y1)].temp, weights=W[(W.site == r.park) & W.season.between(r.y0, r.y1)].games) for r in P.itertuples()]
    P['dome'] = [np.average(W[(W.site == r.park) & W.season.between(r.y0, r.y1)].dome, weights=W[(W.site == r.park) & W.season.between(r.y0, r.y1)].games) for r in P.itertuples()]
    P['dist'] = (P.lf + 2 * P.lcf + 2 * P.cf + 2 * P.rcf + P.rf) / 8; P['wall'] = (3 * P.wall_lf + 2 * P.wall_cf + 3 * P.wall_rf) / 8
    P['lrho'] = np.log(rho_rel(P.elev_ft, P.temp)); P['w'] = P.games / P.games.mean(); return P.reset_index(drop=True)
def wls(X, y, w): return np.linalg.lstsq(X * np.sqrt(w)[:, None], y * np.sqrt(w), rcond=None)[0]
MD = MW = None
def X2(P, feats): 
    cols = {'lrho': P.lrho, 'd_dist': P.dist - MD, 'd_wall': P.wall - MW, 'dome': P.get('dome', 0)}
    return np.column_stack([np.ones(len(P))] + [np.asarray(cols[f], float) for f in feats])
def vegas(temp=72, elev=2133, dims=(340, 380, 415, 380, 340), wall=10, dome=1):
    return pd.DataFrame([dict(lrho=np.log(rho_rel(elev, temp)), dist=(dims[0] + 2 * dims[1] + 2 * dims[2] + 2 * dims[3] + dims[4]) / 8, wall=wall, dome=dome)])
pe_all = park_effects(g); P = stage2_table(pe_all); MD, MW = np.average(P.dist, weights=P.games), np.average(P.wall, weights=P.games)
P.to_csv(f'{R}/robustness_park_effects.csv', index=False)
raw = pd.read_csv(f'{R}/park_table.csv').set_index('key')
print('team-adjusted vs raw run factors, corr of logs: %.3f' % np.corrcoef(P.R, np.log(raw.R.reindex(P.key)))[0, 1])
print(P.assign(Rf=np.exp(P.R), HRf=np.exp(P.HR), raw_R=raw.R.reindex(P.key).values)[['key', 'games', 'Rf', 'raw_R', 'HRf']].round(3).sort_values('Rf').tail(8).to_string())

# ---------- B. specification grid ----------
V = vegas(); F3 = ['lrho', 'd_dist', 'd_wall']; rowsB = []
def run(label, P_, feats, tgt, w=None, Vx=V):
    w = P_.w.values if w is None else w; b = wls(X2(P_, feats), P_[tgt].values, w)
    rowsB.append(dict(spec=label, target=tgt, n_parks=len(P_), density_coef=b[1], vegas=float(np.exp(X2(Vx, feats) @ b)[0])))
for tgt in ('R', 'HR'):
    run('baseline: team-adjusted effects, 2015-25', P, F3, tgt)
    run('drop Coors', P[P.park != 'DEN02'], F3, tgt)
    run('drop Coors and Chase', P[~P.park.isin(['DEN02', 'PHO01'])], F3, tgt)
    run('density only (no fence terms)', P, ['lrho'], tgt)
    run('add roof term', P, F3 + ['dome'], tgt)
    run('unweighted', P, F3, tgt, w=np.ones(len(P)))
    run('drop one-season samples (<150 games)', P[P.games >= 150], F3, tgt)
    Praw = P.assign(R=np.log(raw.R.reindex(P.key).values), HR=np.log(raw.HR.reindex(P.key).values)); run('raw home/road ratios (first version)', Praw, F3, tgt)
    for lab, yrs in (('2018-25 only', (2018, 2025)), ('2021-25 only', (2021, 2025)), ('exclude 2020', None)):
        gs = g[g.season.between(*yrs)] if yrs else g[g.season != 2020]; Pw = stage2_table(park_effects(gs)); run(lab, Pw, F3, tgt)
    # fence-measurement noise: jitter distances by 4 ft and walls by 2 ft
    sims = []
    for _ in range(400):
        Pj = P.assign(dist=P.dist + rng.normal(0, 4, len(P)), wall=P.wall + rng.normal(0, 2, len(P))); b = wls(X2(Pj, F3), Pj[tgt].values, Pj.w.values); sims.append(float(np.exp(X2(V, F3) @ b)[0]))
    rowsB.append(dict(spec='fence data jittered (median of 400)', target=tgt, n_parks=len(P), density_coef=np.nan, vegas=float(np.median(sims)), vegas_p5=float(np.percentile(sims, 5)), vegas_p95=float(np.percentile(sims, 95))))
SB = pd.DataFrame(rowsB); SB.to_csv(f'{R}/robustness_specifications.csv', index=False); pd.set_option('display.width', 200); print(SB.round(3).to_string())

# ---------- C. within-park temperature elasticity (open-air games only) ----------
o = g[(g.dome == 0) & g.temp.notna() & ~g.cfg.str.endswith('_other')].copy(); o['ps'] = o.park + o.season.astype(str)
o['lrt'] = np.log((459.67 + 70) / (459.67 + o.temp)); o['r'] = o.v_r + o.h_r; o['hr'] = o.v_hr + o.h_hr; o['ab'] = o.v_ab + o.h_ab; o['k'] = o.v_k + o.h_k; o['pa'] = o.v_pa + o.h_pa
o['hip'] = o.v_hip + o.h_hip; o['bip'] = o.v_bip + o.h_bip; o['xbh'] = o.v_xbh + o.h_xbh
rowsC = []
def within(y, ex, label, extra):
    Xd = pd.get_dummies(o.ps, drop_first=False, dtype=float); Xd['lrt'] = o.lrt.values
    if 'wind' in extra: Xd['wind_out'] = o.wind_out.values
    if 'month' in extra: Xd = pd.concat([Xd, pd.get_dummies(o.month.clip(4, 9), prefix='m', drop_first=True, dtype=float).set_index(Xd.index)], axis=1)
    if 'night' in extra: Xd['night'] = (o.daynight == 'night').astype(float).values
    off = np.log(o[ex].values) if ex else np.log(o.outs.values / 54)
    m = sm.GLM(o[y].values, Xd.values, family=sm.families.Poisson(), offset=off).fit(cov_type='cluster', cov_kwds={'groups': pd.factorize(o.park)[0]})
    i = list(Xd.columns).index('lrt'); rowsC.append(dict(outcome=label, controls='+'.join(extra) or 'park-season only', games=len(o), density_coef=m.params[i], se=m.bse[i]))
for y, ex, lab in (('r', None, 'R'), ('hr', 'ab', 'HR'), ('k', 'pa', 'K'), ('hip', 'bip', 'BABIP'), ('xbh', 'ab', 'XBH')):
    for extra in ([], ['wind', 'night'], ['wind', 'night', 'month']): within(y, ex, lab, extra)
SC = pd.DataFrame(rowsC); SC.to_csv(f'{R}/robustness_within_park_temperature.csv', index=False); print(SC.round(3).to_string())
print('temp sd within park-season: %.1f F' % o.groupby('ps').temp.std().mean())

# ---------- D. projections under each density estimate ----------
mean_lrho = np.average(P.lrho, weights=P.games); cR = SC[(SC.outcome == 'R') & (SC.controls == 'wind+night+month')].density_coef.iloc[0]; cH = SC[(SC.outcome == 'HR') & (SC.controls == 'wind+night+month')].density_coef.iloc[0]
# HR: hold the density coefficient at the within-park value and re-estimate fence terms from the cross-section
yH = P.HR.values - cH * (P.lrho.values - mean_lrho); bH = wls(X2(P, ['d_dist', 'd_wall']), yH, P.w.values)
bR = wls(X2(P, F3), P.R.values, P.w.values); bHx = wls(X2(P, F3), P.HR.values, P.w.values)
print('HR fence terms with density fixed at within-park value: %.4f per ft distance, %.4f per ft wall  (free fit: %.4f, %.4f)' % (bH[1], bH[2], bHx[2], bHx[3]))
SCN = {"A's dome 72F, rumored 340/380/415, 10 ft": vegas(), "A's dome 72F, MLB-average fences": vegas(dims=(332, 377, 402, 376, 328), wall=MW),
       "A's dome 72F, cozy 325/365/400, 8 ft": vegas(dims=(325, 365, 400, 365, 325), wall=8), "A's dome 70F, rumored": vegas(temp=70), "A's dome 75F, rumored": vegas(temp=75),
       "Open-air on the Strip 95F, rumored": vegas(temp=95, dome=0), "Las Vegas Ballpark 3,012 ft, 95F, 340/380/415, 11 ft": vegas(temp=95, elev=3012, wall=11, dome=0),
       "Las Vegas Ballpark at 102F (2026 series)": vegas(temp=102, elev=3012, wall=11, dome=0)}
rowsD = []
for name, v in SCN.items():
    dl = v.lrho.iloc[0] - mean_lrho
    rowsD.append(dict(scenario=name, density=float(np.exp(v.lrho.iloc[0])), R_cross_park=float(np.exp(X2(v, F3) @ bR)[0]), R_within_park_temp=float(np.exp(cR * dl)),
                      HR_cross_park=float(np.exp(X2(v, F3) @ bHx)[0]), HR_within_park_temp=float(np.exp(cH * dl + X2(v, ['d_dist', 'd_wall']) @ bH)[0])))
SD = pd.DataFrame(rowsD); SD.to_csv(f'{R}/robustness_scenarios.csv', index=False); print(SD.round(3).to_string())
# interval for the headline: bootstrap parks (stage 2) + residual park-to-park spread
res = P.R.values - X2(P, F3) @ bR; sd = np.sqrt(np.average(res ** 2, weights=P.w)); parks = P.park.unique(); dr = []
for _ in range(4000):
    Pb = pd.concat([P[P.park == p] for p in rng.choice(parks, len(parks))]); dr.append(float((X2(V, F3) @ wls(X2(Pb, F3), Pb.R.values, Pb.w.values))[0] + rng.normal(0, sd)))
print('headline runs: %.3f  80%% interval %.3f-%.3f  (parameter-only 80%%: %.3f-%.3f); residual sd %.3f' % (np.exp(X2(V, F3) @ bR)[0], *np.exp(np.percentile(dr, [10, 90])), *np.exp(np.percentile(np.array(dr), [10, 90])), sd))
cur = P[P.y1 == 2025].assign(Rf=np.exp(P.R)); print('2025-era parks above the Vegas projection (actual team-adjusted):', cur[cur.Rf > np.exp(X2(V, F3) @ bR)[0]][['key', 'Rf']].round(3).values.tolist())
print('humidity: dry dome air (20%% RH) vs typical 55%% RH at same temp changes density by %+.2f%%' % (100 * (rho_rel(2133, 72, .20) / rho_rel(2133, 72, .55) - 1)))
print('field sunk 45 ft changes density by %+.2f%%' % (100 * (rho_rel(2133 - 45, 72) / rho_rel(2133, 72) - 1)))

# ---------- E. altitude and temperature as separate terms; roof coefficient; analog anchors ----------
P['lp'] = np.log((1 - 2.25577e-5 * P.elev_ft * 0.3048) ** 5.25588); P['lt'] = np.log((459.67 + 70) / (459.67 + P.temp))
def fit_se(cols, tgt, mask=None):
    Q = P if mask is None else P[mask]; X = np.column_stack([np.ones(len(Q))] + [Q[c].values for c in cols]); m = sm.WLS(Q[tgt].values, X, weights=Q.w.values).fit(); return m.params, m.bse
Q = P.assign(d_dist=P.dist - MD, d_wall=P.wall - MW); P['d_dist'], P['d_wall'] = Q.d_dist, Q.d_wall
for tgt in ('R', 'HR'):
    b, se = fit_se(['lp', 'lt', 'd_dist', 'd_wall'], tgt); print(f'{tgt}: altitude coef {b[1]:.2f} (se {se[1]:.2f}), temperature coef {b[2]:.2f} (se {se[2]:.2f})')
    v = vegas(); lpv = np.log((1 - 2.25577e-5 * 2133 * 0.3048) ** 5.25588); ltv = np.log((459.67 + 70) / (459.67 + 72))
    print(f'   Vegas dome with separate terms: {np.exp(b[0] + b[1] * lpv + b[2] * ltv + b[3] * (v.dist.iloc[0] - MD) + b[4] * (v.wall.iloc[0] - MW)):.3f}')
    b, se = fit_se(['lrho', 'd_dist', 'd_wall', 'dome'], tgt); print(f'   roof coef {b[4]:.3f} (se {se[4]:.3f})')
ch = P[P.key == 'ARI'].iloc[0]; co = P[P.key == 'COL'].iloc[0]; vl = vegas().lrho.iloc[0]
print('Chase (humidor era) team-adjusted R %.3f HR %.3f density %.3f' % (np.exp(ch.R), np.exp(ch.HR), np.exp(ch.lrho)))
print('Chase-anchored Vegas runs (move from Chase density to Vegas density at slope -1.63): %.3f' % (np.exp(ch.R) * np.exp(-1.633 * (vl - ch.lrho))))
print('Coors-anchored: interpolate log runs on density between the MLB average park and Coors: %.3f' % np.exp(co.R * (vl - mean_lrho) / (co.lrho - mean_lrho)))
print('mean MLB density %.3f; Coors %.3f; Vegas dome %.3f; share of the way to Coors %.0f%%' % (np.exp(mean_lrho), np.exp(co.lrho), np.exp(vl), 100 * (vl - mean_lrho) / (co.lrho - mean_lrho)))
