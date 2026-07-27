import glob, gzip, json
import numpy as np
E="/var/minis/workspace/experiments/weather-capture/energy/data"
PT=-8
def ld(sub,mk,f):
    o={}
    for p in sorted(glob.glob(f"{E}/{sub}/{mk}_*.json.gz")):
        for r in json.load(gzip.open(p))["rows"]: o[r["start_gmt"][:13]]=f(r)
    return o
def ldp(sub,which):
    o={}
    for p in sorted(glob.glob(f"{E}/{sub}/{which}_*.json.gz")):
        for r in json.load(gzip.open(p))["rows"]: o[r["start_gmt"][:13]]=r["lmp"]
    return o
demD=ld("caiso_iso_forecast","DAM",lambda r:float(r["mw"]))
demA=ld("caiso_iso_forecast","ACTUAL",lambda r:float(r["mw"]))
renD=ld("caiso_renewables","DAM",lambda r:(float(r["solar_mw"]),float(r["wind_mw"])))
renA=ld("caiso_renewables","ACTUAL",lambda r:(float(r["solar_mw"]),float(r["wind_mw"])))
def lh(k): return (int(k[11:13])+PT)%24

def oracle_report(tag, da, rt):
    keys=sorted(set(demD)&set(demA)&set(renD)&set(renA)&set(da)&set(rt))
    ramp=[k for k in keys if 17<=lh(k)<=21]
    if not ramp: print(f"{tag}: no overlap"); return
    sur=np.array([(demA[k]-sum(renA[k]))-(demD[k]-sum(renD[k])) for k in ramp])
    spr=np.array([rt[k]-da[k] for k in ramp])
    r=np.corrcoef(sur,spr)[0,1]
    oracle=np.sign(sur)*spr
    # quintile
    o=np.argsort(sur); q=np.array_split(o,5)
    q5q1=spr[q[4]].mean()-spr[q[0]].mean()
    print(f"\n=== {tag} === (ramp hrs {len(ramp)}, 2026-01..06)")
    print(f"  spread mean ${spr.mean():+.2f}  std ${spr.std():.1f}  (nodal congestion widens this?)")
    print(f"  surprise->spread corr r={r:+.3f}   quintile Q5-Q1 ${q5q1:+.2f}")
    print(f"  ORACLE (perfect surprise sign) mean P&L ${oracle.mean():+.2f}/hr, win {np.mean(oracle>0):.1%}")
    for c in [1,2,5]:
        print(f"    after ${c} cost: ${oracle.mean()-c:+.2f}/hr")

# hub (restrict hub prices to same 2026-01..06 window for apples-to-apples)
hubDA=ldp("caiso_prices","DA"); hubRT=ldp("caiso_prices","RT")
hubDA={k:v for k,v in hubDA.items() if "2026-0" in k[:7] and int(k[5:7])<=6}
hubRT={k:v for k,v in hubRT.items() if "2026-0" in k[:7] and int(k[5:7])<=6}
oracle_report("HUB SP15 (2026 H1)", hubDA, hubRT)

nodDA=ldp("caiso_prices_nodal","DA"); nodRT=ldp("caiso_prices_nodal","RT")
oracle_report("NODE MIRALOMA (2026 H1)", nodDA, nodRT)

print("\nREAD: if nodal oracle (even before real forecasting) stays sub-$2 cost,")
print("the nodal escape hatch is closed at this node too.")
