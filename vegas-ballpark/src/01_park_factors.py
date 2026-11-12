"""Build park factors and game-weather summaries from Retrosheet (GitHub mirror: chadwickbureau/retrosheet).
Usage: python 01_park_factors.py /path/to/retrosheet
Outputs data/park_season.csv (one row per home-team/park/season) and data/park_weather.csv
"""
import sys, csv, glob, os, collections
import pandas as pd, numpy as np
RS = sys.argv[1]; OUT = os.path.join(os.path.dirname(__file__), '..', 'data')
# Retrosheet game-log columns (0-indexed)
C = dict(date=0, vis=3, home=6, vr=9, hr_=10, park=16,
         v_ab=21, v_h=22, v_2b=23, v_3b=24, v_hr=25, v_sf=28, v_hbp=29, v_bb=30, v_k=32,
         h_ab=49, h_h=50, h_2b=51, h_3b=52, h_hr=53, h_sf=56, h_hbp=57, h_bb=58, h_k=60)
rows = []
for f in sorted(glob.glob(f'{RS}/seasons/20*/GL20*.TXT')):
    for r in csv.reader(open(f, encoding='latin-1')):
        try:
            d = {k: r[i] for k, i in C.items()}
            for k in d:
                if k not in ('date', 'vis', 'home', 'park'): d[k] = int(d[k])
        except (ValueError, IndexError):
            continue
        d['season'] = int(d['date'][:4]); rows.append(d)
g = pd.DataFrame(rows)
st = ['ab', 'h', '2b', '3b', 'hr', 'sf', 'hbp', 'bb', 'k']
for s in st: g[s] = g['v_' + s] + g['h_' + s]
g['r'] = g['vr'] + g['hr_']; g['g'] = 1
g['pa'] = g['ab'] + g['bb'] + g['hbp'] + g['sf']
g['bip'] = g['ab'] - g['k'] - g['hr'] + g['sf']            # balls in play
g['hip'] = g['h'] - g['hr']                                # hits in play
agg = ['g', 'r', 'pa', 'ab', 'h', '2b', '3b', 'hr', 'bb', 'k', 'bip', 'hip']
out = []
for (season, team), th in g.groupby(['season', 'home']):
    road = g[(g.season == season) & (g.vis == team)]
    if len(road) < 20: continue
    R = road[agg].sum()
    for park, hp in th.groupby('park'):
        if len(hp) < 20: continue          # skip neutral-site / series games
        H = hp[agg].sum(); d = dict(season=season, team=team, park=park)
        for k in agg: d['home_' + k] = H[k]; d['road_' + k] = R[k]
        out.append(d)
ps = pd.DataFrame(out)
ps.to_csv(f'{OUT}/park_season.csv', index=False)
print('park-seasons', len(ps), 'games', len(g))
# game-time weather from event files
W = []
for f in glob.glob(f'{RS}/seasons/20[12]*/*.EV[AN]'):
    season = int(os.path.basename(f)[:4]); cur = {}
    for line in open(f, encoding='latin-1'):
        if line.startswith('id,'):
            if cur: W.append(cur)
            cur = dict(season=season)
        elif line.startswith('info,'):
            p = line.strip().split(',')
            if len(p) >= 3 and p[1] in ('site', 'temp', 'windspeed', 'winddir', 'sky', 'daynight'): cur[p[1]] = p[2]
    if cur: W.append(cur)
w = pd.DataFrame(W)
w['temp'] = pd.to_numeric(w.temp, errors='coerce'); w.loc[w.temp <= 0, 'temp'] = np.nan
w['windspeed'] = pd.to_numeric(w.windspeed, errors='coerce'); w.loc[w.windspeed < 0, 'windspeed'] = np.nan
w['dome'] = (w.sky == 'dome').astype(float)
ws = w.groupby(['site', 'season']).agg(games=('temp', 'size'), temp=('temp', 'mean'), wind=('windspeed', 'mean'), dome=('dome', 'mean')).reset_index()
ws.to_csv(f'{OUT}/park_weather.csv', index=False)
print(ws[ws.season == 2025].round(1).to_string())
