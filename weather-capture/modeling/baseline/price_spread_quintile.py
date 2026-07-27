import glob, gzip, json
import numpy as np
E="/var/minis/workspace/experiments/weather-capture/energy/data"
PT=-8
def ld(sub,mk,f):
    o={}
    for p in sorted(glob.glob(f"{E}/{sub}/{mk}_*.json.gz")):
        for r in json.load(gzip.open(p))["rows"]: o[r["start_gmt"][:13]]=f(r)
    return o
demD=ld("caiso_iso_forecast","DAM",lambda r:float(r["mw"]))
demA=ld("caiso_iso_forecast","ACTUAL",lambda r:float(r["mw"]))
renD=ld("caiso_renewables","DAM",lambda r:(float(r["solar_mw"]),float(r["wind_mw"])))
renA=ld("caiso_renewables","ACTUAL",lambda r:(float(r["solar_mw"]),float(r["wind_mw"])))
da=ld("caiso_prices","DA",lambda r:float(r["lmp"]))
rt=ld("caiso_prices","RT",lambda r:float(r["lmp"]))
keys=sorted(set(demD)&set(demA)&set(renD)&set(renA)&set(da)&set(rt))
def lh(k): return (int(k[11:13])+PT)%24

# ramp hours 17-21: bucket net_surprise into quintiles, look at mean spread per quintile
ramp=[k for k in keys if 17<=lh(k)<=21]
sur=np.array([ (demA[k]-sum(renA[k])) - (demD[k]-sum(renD[k])) for k in ramp])
spr=np.array([ rt[k]-da[k] for k in ramp])
order=np.argsort(sur)
q=np.array_split(order,5)
print("EVENING RAMP (17-21): net-load surprise quintile -> mean DA->RT spread")
print("quintile   mean_surprise_MWh   mean_spread$   median_spread$   n")
for i,idx in enumerate(q):
    print(f"  Q{i+1}      {sur[idx].mean():+8.0f}        {spr[idx].mean():+7.2f}       {np.median(spr[idx]):+7.2f}    {len(idx)}")
print(f"\nSpread when surprise HIGH (Q5) minus LOW (Q1): {spr[q[4]].mean()-spr[q[0]].mean():+.2f} $/MWh")

# placebo: same for overnight 0-5 where thesis predicts NO mechanism
print("\nPLACEBO overnight (0-5): same quintile analysis")
night=[k for k in keys if lh(k)<=5]
sn=np.array([ (demA[k]-sum(renA[k])) - (demD[k]-sum(renD[k])) for k in night])
pn=np.array([ rt[k]-da[k] for k in night])
o2=np.argsort(sn); q2=np.array_split(o2,5)
print(f"Spread Q5-Q1 overnight: {pn[q2[4]].mean()-pn[q2[0]].mean():+.2f} $/MWh (should be ~0 if ramp signal is real mechanism)")

# how big is ramp spread variance? context for whether a few $ matters
print(f"\nramp spread: mean {spr.mean():+.2f}, std {spr.std():.2f}, "
      f"P90 {np.percentile(spr,90):.1f}, P10 {np.percentile(spr,10):.1f} $/MWh")
