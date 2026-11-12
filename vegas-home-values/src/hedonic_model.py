"""Las Vegas / Henderson hedonic home-price model from recently-sold listing data (data/sold_homes.csv).
log(price) = area effect + size + beds + baths + attached-unit flag.  5-fold CV for honest error. Writes results/.
Usage: python hedonic_model.py            -> fit, validate, write tables
       python hedonic_model.py "Seven Hills" 2128 3 2.5   -> point estimate + 80% range for a home
"""
import os, sys, json, numpy as np, pandas as pd
B = os.path.join(os.path.dirname(__file__), '..'); R = f'{B}/results'; os.makedirs(R, exist_ok=True)
d = pd.read_csv(f'{B}/data/sold_homes.csv')
d['attached'] = d.address.str.contains('#').astype(int)           # condo/townhome units carry a unit number
d['ppsf'] = d.price / d.sqft
d = d[(d.price < 2.5e6) & (d.sqft < 6000)].reset_index(drop=True)  # custom estates are a different market
areas = sorted(d.area.unique()); REF = 'Henderson (citywide)'
def design(df):
    X = pd.DataFrame({'const': 1.0, 'lsqft': np.log(df.sqft / 2000), 'beds': df.beds - 3, 'baths': df.baths - 2.5, 'attached': df.attached})
    for a in areas:
        if a != REF: X['area_' + a] = (df.area == a).astype(float)
    return X
def fit(X, y, lam=1.0):   # ridge on area effects only (partial pooling toward the citywide level)
    P = np.diag([0 if not c.startswith('area_') else lam for c in X.columns]); V = X.values; return np.linalg.solve(V.T @ V + P, V.T @ y)
def huber_fit(X, y, it=8):  # iteratively down-weight big misses (view lots, remodels, distress)
    b = fit(X, y)
    for _ in range(it):
        r = y - X.values @ b; s = 1.4826 * np.median(np.abs(r)); w = np.minimum(1, 1.345 * s / np.maximum(np.abs(r), 1e-9))
        Xw = X.values * np.sqrt(w)[:, None]; P = np.diag([0 if not c.startswith('area_') else 1.0 for c in X.columns]); b = np.linalg.solve(Xw.T @ Xw + P, Xw.T @ (y * np.sqrt(w)))
    return b
X = design(d); y = np.log(d.price.values); b = huber_fit(X, y); coef = pd.Series(b, X.columns)
rng = np.random.default_rng(3); fold = rng.integers(0, 5, len(d)); pred = np.zeros(len(d))
for k in range(5): pred[fold == k] = X.values[fold == k] @ huber_fit(X[fold != k], y[fold != k])
err = np.exp(pred - y) - 1; d['cv_pred'] = np.exp(pred).round(-2); d['cv_err_pct'] = (100 * err).round(1)
q10, q90 = np.percentile(y - pred, [10, 90])
summary = dict(n=len(d), median_abs_pct_error=float(np.median(np.abs(err)) * 100), mean_abs_pct_error=float(np.mean(np.abs(err)) * 100),
               within_10pct=float(np.mean(np.abs(err) < .10) * 100), within_20pct=float(np.mean(np.abs(err) < .20) * 100),
               r2_cv=float(1 - np.sum((y - pred)**2) / np.sum((y - y.mean())**2)), band80_low=float(np.exp(q10)), band80_high=float(np.exp(q90)),
               naive_area_median_ppsf_mape=None)
# naive comparison: area median $/sqft x sqft (also cross-validated)
nv = np.zeros(len(d))
for k in range(5):
    m = d[fold != k].groupby('area').ppsf.median(); nv[fold == k] = d[fold == k].area.map(m).values * d[fold == k].sqft.values
summary['naive_area_median_ppsf_mape'] = float(np.median(np.abs(nv / d.price - 1)) * 100)
json.dump(dict(summary=summary, coef=coef.to_dict(), ref=REF), open(f'{R}/model.json', 'w'), indent=1)
by = d.groupby('area').agg(sales=('price', 'size'), median_price=('price', 'median'), median_sqft=('sqft', 'median'), median_ppsf=('ppsf', 'median'),
                           median_abs_err_pct=('cv_err_pct', lambda s: s.abs().median()))
by['premium_vs_henderson_pct'] = [100 * (np.exp(coef.get('area_' + a, 0)) - 1) for a in by.index]
by['typical_2000sf_3bd_2.5ba'] = [np.exp(coef.const + coef.get('area_' + a, 0)) for a in by.index]
by = by.sort_values('premium_vs_henderson_pct', ascending=False); by.round(1).to_csv(f'{R}/area_table.csv')
d.sort_values(['area', 'address']).to_csv(f'{R}/sales_with_cv_predictions.csv', index=False)
def estimate(area, sqft, beds, baths, attached=0):
    x = pd.DataFrame([dict(area=area, sqft=sqft, beds=beds, baths=baths, attached=attached)]); p = float(np.exp(design(x).values @ b)[0])
    return p, p * np.exp(q10), p * np.exp(q90)
if len(sys.argv) >= 5:
    p, lo, hi = estimate(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])); print(f'{sys.argv[1]}: ${p:,.0f}  (80% range ${lo:,.0f} - ${hi:,.0f})')
else:
    pd.set_option('display.width', 200); print(json.dumps(summary, indent=1)); print(coef.round(3).to_string()); print(by.round(1).to_string())
    print('size elasticity: +10%% sqft -> %+.1f%% price; extra bath %+.1f%%; extra bedroom at same sqft %+.1f%%; attached unit %+.1f%%' % (100 * (1.1**coef.lsqft - 1), 100 * (np.exp(coef.baths) - 1), 100 * (np.exp(coef.beds) - 1), 100 * (np.exp(coef.attached) - 1)))
    sh = d[d.area == 'Seven Hills'].sort_values('cv_err_pct'); print(sh[['address', 'price', 'sqft', 'beds', 'baths', 'ppsf', 'cv_pred', 'cv_err_pct']].round(0).to_string())
    for s in (1600, 2128, 2400, 3000, 3700): print(s, ['%.0f' % v for v in estimate('Seven Hills', s, 3 if s < 2300 else 4, 2.5 if s < 2300 else 3)])
