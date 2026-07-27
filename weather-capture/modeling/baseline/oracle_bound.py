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

# THE decisive check: even with PERFECT ex-ante knowledge of the net-load surprise,
# how much money is on the table in the ramp? A signal can only be worth trading if
# the BEST POSSIBLE version clears costs. Compute the oracle: trade the sign of the
# surprise every ramp hour, collect the spread in that direction.
ramp=[k for k in keys if 17<=lh(k)<=21]
sur=np.array([(demA[k]-sum(renA[k]))-(demD[k]-sum(renD[k])) for k in ramp])
spr=np.array([rt[k]-da[k] for k in ramp])

# oracle P&L: position = sign(surprise), payoff = position * spread
oracle = np.sign(sur)*spr
print(f"ramp hours: {len(ramp)}")
print(f"ORACLE (perfect surprise sign known ex-ante) mean P&L/hr: ${oracle.mean():+.2f}")
print(f"  win rate: {np.mean(oracle>0):.1%}, std ${oracle.std():.1f}")
print(f"  -> this is the CEILING. Real edge is far below (can't forecast surprise).")

# a plausible bid-ask / DEC-INC cost for DA-vs-RT convergence trading at a hub
for cost in [1,2,5]:
    net=oracle-cost
    print(f"  after ${cost}/MWh round-trip cost: mean ${net.mean():+.2f}/hr, "
          f"annualized/MW over 5 ramp hrs x 365 = ${net.mean()*5*365:+.0f}")
