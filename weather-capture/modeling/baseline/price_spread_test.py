#!/usr/bin/env python3
"""
STEP 3 — the actual question: does net-load forecast error predict the DA->RT
price spread, by hour?

For each hour:
  net_surprise = net_ACT - net_DAM   (+ = MORE net load than forecast = tighter
                                       supply than the DA market planned for)
  spread       = RT_lmp - DA_lmp     (+ = RT settled above DA)

Economic prior: if actual net load exceeds the day-ahead forecast, real-time is
tighter than planned -> RT should tend to print above DA. So we expect a POSITIVE
correlation between net_surprise and spread, strongest in the ramp hours where
scarcity is priced. If corr ~ 0, the market already prices the net-load
expectation and there's no exploitable surprise -> thesis does not clear.

Reports per-hour Pearson r and a simple sign-agreement rate, plus the ramp bucket.
Truth-side net load uses CAISO's own DAM vs ACTUAL (net_surprise is CAISO's own
forecast miss) — the cleanest first cut. (A later version could substitute OUR
net-load forecast, but the gate-clean test already showed we don't beat CAISO in
the ramp, so CAISO's own miss is the right first probe.)
"""
import sys, glob, gzip, json, datetime as dt
import numpy as np
E="/var/minis/workspace/experiments/weather-capture/energy/data"
PT=-8

def load_dem(mk):
    o={}
    for f in sorted(glob.glob(f"{E}/caiso_iso_forecast/{mk}_*.json.gz")):
        for r in json.load(gzip.open(f))["rows"]: o[r["start_gmt"][:13]]=float(r["mw"])
    return o
def load_ren(mk):
    o={}
    for f in sorted(glob.glob(f"{E}/caiso_renewables/{mk}_*.json.gz")):
        for r in json.load(gzip.open(f))["rows"]: o[r["start_gmt"][:13]]=(float(r["solar_mw"]),float(r["wind_mw"]))
    return o
def load_price(w):
    o={}
    for f in sorted(glob.glob(f"{E}/caiso_prices/{w}_*.json.gz")):
        for r in json.load(gzip.open(f))["rows"]: o[r["start_gmt"][:13]]=float(r["lmp"])
    return o

demD=load_dem("DAM");demA=load_dem("ACTUAL");renD=load_ren("DAM");renA=load_ren("ACTUAL")
da=load_price("DA");rt=load_price("RT")
keys=sorted(set(demD)&set(demA)&set(renD)&set(renA)&set(da)&set(rt))
print(f"aligned hours (load+ren+price): {len(keys)}")
if len(keys)<500: sys.exit("price fetch incomplete — wait, then re-run.")

def lh(k): return (int(k[11:13])+PT)%24
rows=[]
for k in keys:
    sD,wD=renD[k]; sA,wA=renA[k]
    netD=demD[k]-(sD+wD); netA=demA[k]-(sA+wA)
    surprise = netA-netD          # + = more net load than DA forecast
    spread = rt[k]-da[k]          # + = RT above DA
    rows.append((lh(k), surprise, spread))
rows=np.array(rows)

def corr(mask):
    x=rows[mask,1]; y=rows[mask,2]
    if len(x)<30 or np.std(x)==0 or np.std(y)==0: return float('nan'),len(x),float('nan')
    r=np.corrcoef(x,y)[0,1]
    signagree=np.mean(np.sign(x)==np.sign(y))
    return r, len(x), signagree

print("\nnet-load surprise (netACT-netDAM) vs DA->RT spread (RT-DA), by local hour")
print("lh    n     Pearson_r   sign_agree   mean_|spread|$")
for h in range(24):
    m=rows[:,0]==h
    r,n,sa=corr(m)
    msp=np.mean(np.abs(rows[m,2])) if m.sum() else float('nan')
    ev=" EVENING" if 17<=h<=21 else (" solar" if 10<=h<=15 else "")
    print(f"{h:02d}  {n:5d}    {r:+.3f}      {sa:.2f}        {msp:6.1f}{ev}")

print("\n=== bucket correlations ===")
for name,lo,hi in [("overnight 0-5",0,5),("morning 6-10",6,10),("midday solar 11-15",11,15),
                   ("evening ramp 17-21",17,21),("late 22-23",22,23)]:
    m=(rows[:,0]>=lo)&(rows[:,0]<=hi)
    r,n,sa=corr(m)
    print(f"{name:22} r={r:+.3f}  n={n}  sign_agree={sa:.2f}")
print("\nREAD: positive r in the ramp = net-load surprise predicts spread there.")
print("r~0 = market already prices the net-load expectation; no exploitable surprise.")
