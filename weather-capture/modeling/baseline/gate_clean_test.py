#!/usr/bin/env python3
"""
Gate-closure clean test, cheapest form: split our model's error and CAISO's error
by whether the target hour's weather feature is GATE-CLEAN or LEAKING.

Leak rule (see /tmp/gate_latency.py): our previous_day1 feature is issued ~24h
before the valid time. CAISO's DAM gate closes ~10:00 PT on D-1. So for a target
at local hour h, our feature is issued (h - 24h) local = h o'clock on D-1. That is
BEFORE the 10:00 gate iff h <= 10 (local). Thus:
   - CLEAN hours   : local hour  0..10   (feature issued at/before gate)
   - LEAKING hours : local hour 11..23   (feature issued AFTER gate; up to +13h)

If our edge over CAISO is REAL, it should be present (or at least not vanish) in
the CLEAN hours. If the edge is an artifact of latency, it will be concentrated
in the LEAKING hours and absent in the CLEAN ones.

This uses ONLY existing data. It does not fix the leak (that needs older weather
vintages); it localizes it, which is enough to answer 'is the edge real?'.

Truth = OASIS ACTUAL. We compare, hour-bucketed:
  - CAISO DAM forecast error
  - our day-ahead-honest model error (trained once, evaluated per bucket)
"""
import sys, glob, gzip, json, datetime as dt
import numpy as np
sys.path.insert(0,"/var/minis/workspace/experiments/weather-capture/modeling/EDA")
import loaders as L
from sklearn.ensemble import HistGradientBoostingRegressor

ISO="/var/minis/workspace/experiments/weather-capture/energy/data/caiso_iso_forecast"
BASE_C=6.0
PT_OFFSET=-7  # representative; leak structure identical for -8

def load_oasis(m):
    out={}
    for f in sorted(glob.glob(f"{ISO}/{m}_*.json.gz")):
        for r in json.load(gzip.open(f))["rows"]:
            out[r["start_gmt"][:13]]=float(r["mw"])
    return out
def hk(k,h): return (dt.datetime.strptime(k,"%Y-%m-%dT%H")-dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H")
def local_hour(k): return (int(k[11:13]) + PT_OFFSET) % 24

truth=load_oasis("ACTUAL"); iso=load_oasis("DAM")
# day-ahead temp feature
s,c={},{}
for loc in L.LOCATIONS:
    pr=L.load_previous_runs(loc)
    for i,t in enumerate(pr["time"]):
        v=pr["temperature_2m_previous_day1"][i]
        if v is None: continue
        kk=t[:13]; s[kk]=s.get(kk,0.)+float(v); c[kk]=c.get(kk,0)+1
temp={kk:s[kk]/c[kk] for kk in s if c[kk]==5}
dem=L.load_caiso_demand()

keys=[k for k in sorted(truth) if k in temp and hk(k,168)+":00" in dem]
print(f"rows: {len(keys)}")

def feat(k):
    d=dt.datetime.strptime(k,"%Y-%m-%dT%H"); t=temp[k]
    return [t,max(t-BASE_C,0),max(BASE_C-t,0),
            np.sin(2*np.pi*d.hour/24),np.cos(2*np.pi*d.hour/24),
            np.sin(2*np.pi*d.month/12),np.cos(2*np.pi*d.month/12),
            np.sin(2*np.pi*d.weekday()/7),np.cos(2*np.pi*d.weekday()/7),
            1. if d.weekday()>=5 else 0., dem[hk(k,168)+":00"]]
X=np.array([feat(k) for k in keys]); y=np.array([truth[k] for k in keys])

# single expanding split: train first 70%, test last 30% (fast; this is a
# diagnostic, not the headline number)
split=int(len(keys)*0.7)
m=HistGradientBoostingRegressor(max_iter=180,learning_rate=0.07,max_depth=6,
    l2_regularization=1.0,random_state=0).fit(X[:split],y[:split])
pred=m.predict(X[split:])
te_keys=keys[split:]; te_truth=y[split:]

rows=[]
for i,k in enumerate(te_keys):
    if k in iso:
        rows.append((local_hour(k), abs(pred[i]-te_truth[i])/te_truth[i]*100,
                     abs(iso[k]-te_truth[i])/te_truth[i]*100))
lh=np.array([r[0] for r in rows]); om=np.array([r[1] for r in rows]); im=np.array([r[2] for r in rows])

def bucket(name, mask):
    if mask.sum()==0: print(f"{name}: no hours"); return
    o=om[mask].mean(); ii=im[mask].mean()
    print(f"{name:28} n={mask.sum():5d}  ours {o:5.2f}%   CAISO {ii:5.2f}%   edge {ii-o:+5.2f}pts")

print("\n=== MAPE by gate-cleanliness (test set, vs OASIS ACTUAL) ===")
bucket("CLEAN (local 0-10)",  lh<=10)
bucket("LEAKING (local 11-23)", lh>=11)
print()
bucket("  clean: overnight 0-5", lh<=5)
bucket("  clean: morning 6-10", (lh>=6)&(lh<=10))
bucket("  leak: midday 11-16", (lh>=11)&(lh<=16))
bucket("  leak: evening 17-22", (lh>=17)&(lh<=22))
print("\nREAD: if 'edge' is real it persists in CLEAN hours. If it's latency,")
print("edge is large in LEAKING hours and ~0 (or negative) in CLEAN hours.")
