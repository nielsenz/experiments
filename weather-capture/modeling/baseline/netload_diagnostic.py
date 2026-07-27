#!/usr/bin/env python3
"""
Net-load diagnostic: does CAISO's renewable-forecast error COMPOUND onto its
demand-forecast error in the evening ramp?

net_DAM = SYS_FCST_DA_MW  - (Solar_DAM  + Wind_DAM)      [day-ahead net-load forecast]
net_ACT = SYS_FCST_ACT_MW - (Solar_ACT  + Wind_ACT)      [actual net load]

We compare, BY LOCAL HOUR, three forecast-error series (all CAISO's own,
DAM-vs-ACTUAL, so no model of ours is involved — this is about CAISO/market):
  1. gross-load error : |SYS_FCST_DA_MW - SYS_FCST_ACT_MW|
  2. renewable error  : |(Sol+Wind)_DAM - (Sol+Wind)_ACT|
  3. net-load error   : |net_DAM - net_ACT|

The diagnostic (per the thesis):
  - If in the evening ramp NET error > GROSS error, solar/wind forecast error is
    COMPOUNDING — the ramp hides surprise the gross forecast doesn't show. That is
    where a price signal could live.
  - If NET error <= GROSS error in the ramp (errors partially cancel), the ramp is
    already well-forecast on a net basis and the thesis weakens.

MAPE for net load uses net_ACT as denominator (can be small at solar peak -> we
also report MAE MWh, which is the honest scale-free-of-denominator view).
"""
import sys, glob, gzip, json, datetime as dt
import numpy as np

E = "/var/minis/workspace/experiments/weather-capture/energy/data"
PT = -8  # PST; structure robust to -7 (checked elsewhere)

def load_dem(mk):
    out={}
    for f in sorted(glob.glob(f"{E}/caiso_iso_forecast/{mk}_*.json.gz")):
        for r in json.load(gzip.open(f))["rows"]:
            out[r["start_gmt"][:13]]=float(r["mw"])
    return out

def load_ren(mk):
    out={}
    for f in sorted(glob.glob(f"{E}/caiso_renewables/{mk}_*.json.gz")):
        for r in json.load(gzip.open(f))["rows"]:
            out[r["start_gmt"][:13]]=(float(r["solar_mw"]), float(r["wind_mw"]))
    return out

demD=load_dem("DAM"); demA=load_dem("ACTUAL")
renD=load_ren("DAM"); renA=load_ren("ACTUAL")
keys=sorted(set(demD)&set(demA)&set(renD)&set(renA))
print(f"aligned hours (all 4 series): {len(keys)}")
if len(keys) < 500:
    sys.exit("renewables fetch incomplete — wait for it, then re-run.")

def lh(k): return (int(k[11:13])+PT)%24

# per local hour: mean |error| for gross, renewable, net
buckets={h:{"gross":[], "ren":[], "net":[], "netact":[]} for h in range(24)}
for k in keys:
    g_err = abs(demD[k]-demA[k])
    sD,wD=renD[k]; sA,wA=renA[k]
    r_err = abs((sD+wD)-(sA+wA))
    netD = demD[k]-(sD+wD); netA = demA[k]-(sA+wA)
    n_err = abs(netD-netA)
    b=buckets[lh(k)]
    b["gross"].append(g_err); b["ren"].append(r_err); b["net"].append(n_err); b["netact"].append(netA)

print("\nCAISO forecast error by LOCAL hour (MAE MWh, DAM vs ACTUAL) — its own errors")
print("lh   n    gross    renew     net    net_MAPE  compound?(net>gross)")
for h in range(24):
    b=buckets[h]
    if not b["gross"]: continue
    g=np.mean(b["gross"]); r=np.mean(b["ren"]); n=np.mean(b["net"])
    na=np.mean([abs(x) for x in b["netact"]])
    nmape = n/na*100 if na>0 else float('nan')
    mark = "  <== COMPOUND" if n>g else ""
    ev = " EVENING" if 17<=h<=21 else (" solar" if 10<=h<=15 else "")
    print(f"{h:02d}  {len(b['gross']):4d}  {g:6.0f}  {r:6.0f}  {n:6.0f}  {nmape:6.1f}%{mark}{ev}")
