"""Game-level table 2015-2025: one row per game with outcomes, park, teams and game-time weather.
Usage: python 03_game_table.py /path/to/retrosheet   -> data/games.csv.gz"""
import sys, csv, glob, os, numpy as np, pandas as pd
RS = sys.argv[1]; D = os.path.join(os.path.dirname(__file__), '..', 'data'); rows = []
for f in sorted(glob.glob(f'{RS}/seasons/20[12]*/[Gg][Ll]20*.[Tt][Xx][Tt]')):
    if int(os.path.basename(f)[2:6]) < 2015: continue
    for r in csv.reader(open(f, encoding='latin-1')):
        v = lambda i: int(r[i]); o = {}
        for side, b in (('v', 21), ('h', 49)):
            ab, h, d2, d3, hr, sf, hbp, bb, k = v(b), v(b+1), v(b+2), v(b+3), v(b+4), v(b+7), v(b+8), v(b+9), v(b+11)
            o.update({f'{side}_ab': ab, f'{side}_hr': hr, f'{side}_k': k, f'{side}_bb': bb, f'{side}_pa': ab+bb+hbp+sf, f'{side}_xbh': d2+d3, f'{side}_hip': h-hr, f'{side}_bip': ab-k-hr+sf})
        rows.append(dict(id=f'{r[6]}{r[0]}{r[1]}', season=int(r[0][:4]), month=int(r[0][4:6]), vis=r[3], home=r[6], park=r[16], v_r=v(9), h_r=v(10), outs=v(11), **o))
g = pd.DataFrame(rows)
W = []
for f in glob.glob(f'{RS}/seasons/20[12]*/*.EV[AN]'):
    cur = None
    for line in open(f, encoding='latin-1'):
        if line.startswith('id,'):
            if cur: W.append(cur)
            cur = {'id': line.strip().split(',')[1]}
        elif line.startswith('info,'):
            p = line.strip().split(',')
            if len(p) >= 3 and p[1] in ('temp', 'sky', 'windspeed', 'winddir', 'daynight'): cur[p[1]] = p[2]
    if cur: W.append(cur)
w = pd.DataFrame(W); w['temp'] = pd.to_numeric(w.temp, errors='coerce'); w.loc[w.temp <= 0, 'temp'] = np.nan
w['windspeed'] = pd.to_numeric(w.windspeed, errors='coerce'); w.loc[w.windspeed < 0, 'windspeed'] = np.nan
g = g.merge(w, on='id', how='left'); g['dome'] = (g.sky == 'dome').astype(int)
out_ = g.winddir.isin(['tolf', 'tocf', 'torf']); in_ = g.winddir.isin(['fromlf', 'fromcf', 'fromrf'])
g['wind_out'] = np.where(g.dome == 1, 0, np.where(out_, g.windspeed, np.where(in_, -g.windspeed, 0))); g['wind_out'] = g.wind_out.fillna(0)
g.to_csv(f'{D}/games.csv.gz', index=False); print(len(g), 'games; weather matched', g.temp.notna().mean().round(4)); print(g.groupby('season').size().to_string())
