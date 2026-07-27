import sys, glob, gzip, json, datetime as dt
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
E="/var/minis/workspace/experiments/weather-capture/energy/data"
PT=-8
def ld_dem(mk):
    o={}
    for f in sorted(glob.glob(f"{E}/caiso_iso_forecast/{mk}_*.json.gz")):
        for r in json.load(gzip.open(f))["rows"]: o[r["start_gmt"][:13]]=float(r["mw"])
    return o
def ld_ren(mk):
    o={}
    for f in sorted(glob.glob(f"{E}/caiso_renewables/{mk}_*.json.gz")):
        for r in json.load(gzip.open(f))["rows"]: o[r["start_gmt"][:13]]=(float(r["solar_mw"]),float(r["wind_mw"]))
    return o
demD=ld_dem("DAM");demA=ld_dem("ACTUAL");renD=ld_ren("DAM");renA=ld_ren("ACTUAL")
keys=sorted(set(demD)&set(demA)&set(renD)&set(renA))
def lh(k): return (int(k[11:13])+PT)%24

# signed net error (netD - netA): + means CAISO OVER-forecast net load (under-forecast renewables/solar)
se={h:[] for h in range(24)}
lvl={h:[] for h in range(24)}
for k in keys:
    sD,wD=renD[k]; sA,wA=renA[k]
    netD=demD[k]-(sD+wD); netA=demA[k]-(sA+wA)
    se[lh(k)].append(netD-netA); lvl[lh(k)].append(netA)

hrs=range(24)
mean_se=[np.mean(se[h]) for h in hrs]
std_se=[np.std(se[h]) for h in hrs]
mean_lvl=[np.mean(lvl[h]) for h in hrs]

fig,ax=plt.subplots(2,1,figsize=(11,8))
ax[0].axhline(0,color='k',lw=.6)
ax[0].plot(hrs,mean_se,'-o',label='mean signed net error (netDAM - netACT)')
ax[0].fill_between(hrs,[m-s for m,s in zip(mean_se,std_se)],[m+s for m,s in zip(mean_se,std_se)],alpha=.2,label='±1 std')
ax[0].axvspan(17,21,alpha=.12,color='red',label='evening ramp')
ax[0].set(title='CAISO net-load forecast error by local hour (PST)',xlabel='local hour',ylabel='MWh (+ = over-forecast net load)')
ax[0].legend(fontsize=8);ax[0].grid(alpha=.3)
ax[1].plot(hrs,mean_lvl,'-o',color='green')
ax[1].axvspan(17,21,alpha=.12,color='red')
ax[1].set(title='Mean actual net load by hour (the duck curve)',xlabel='local hour',ylabel='net load MWh')
ax[1].grid(alpha=.3)
fig.tight_layout();fig.savefig("modeling/baseline/figures/netload_error.png",dpi=110)
print("saved. Evening-ramp signed error (17-21):")
for h in range(17,22):
    print(f"  hr{h}: mean {np.mean(se[h]):+.0f} MWh, std {np.std(se[h]):.0f}, net_level {np.mean(lvl[h]):.0f}")
print(f"\nMidday (10-13) mean signed error: {np.mean([np.mean(se[h]) for h in range(10,14)]):+.0f} MWh (bias direction)")
print(f"Evening (17-21) mean signed error: {np.mean([np.mean(se[h]) for h in range(17,22)]):+.0f} MWh")
