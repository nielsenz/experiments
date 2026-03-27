import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import TOURNAMENT_PBP, MODEL_2026, PROCESSED_DIR

import json, pandas as pd, numpy as np, pickle, requests

with open(TOURNAMENT_PBP) as f:
    all_games = json.load(f)
with open(MODEL_2026, 'rb') as f:
    ma = pickle.load(f)
team_pts_2024 = ma['team_pts']

def extract_first_to_10(plays):
    if not plays: return None
    df = pd.DataFrame([{'away':p.get('awayScore',0) or 0,'home':p.get('homeScore',0) or 0} for p in plays])
    if df.empty: return None
    df['prev_away'] = df['away'].shift(1, fill_value=0)
    df['prev_home'] = df['home'].shift(1, fill_value=0)
    df['fr10'] = ((df['prev_away']<10)&(df['away']>=10))|((df['prev_home']<10)&(df['home']>=10))
    idx = df[df['fr10']].index
    if idx.empty: return None
    row = df.loc[idx[0]]
    return 'home' if (row['prev_home']<10 and row['home']>=10) else 'away'

def get_score(c):
    s = c.get('score',{})
    v = s.get('value') if isinstance(s,dict) else s
    try: return int(v or 0)
    except: return 0

winners = set()
for gid, game in all_games.items():
    comps = game.get('header',{}).get('competitions',[])
    if not comps: continue
    comp = comps[0]
    if comp.get('status',{}).get('type',{}).get('name') != 'STATUS_FINAL': continue
    competitors = [c for c in comp.get('competitors',[]) if isinstance(c,dict)]
    if len(competitors)!=2: continue
    hc = next((c for c in competitors if c.get('homeAway')=='home'),None)
    ac = next((c for c in competitors if c.get('homeAway')=='away'),None)
    if not hc or not ac: continue
    sh,sa = get_score(hc),get_score(ac)
    winners.add(hc.get('team',{}).get('displayName','') if sh>sa else ac.get('team',{}).get('displayName',''))

recent_stats = {}
url = 'https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard'
for date in ['20260301','20260308','20260315','20260316','20260317','20260318','20260319']:
    resp = requests.get(url, params={'dates':date,'limit':300}, timeout=10)
    if resp.status_code!=200: continue
    for event in resp.json().get('events',[]):
        if event.get('status',{}).get('type',{}).get('name')!='STATUS_FINAL': continue
        comp = event.get('competitions',[{}])[0]
        for c in comp.get('competitors',[]):
            tid = c.get('team',{}).get('id')
            sv = get_score(c)
            if tid and sv>0: recent_stats.setdefault(tid,[]).append(sv)

def get_ppg(tid):
    s=recent_stats.get(tid,[]); return (round(np.mean(s),1),len(s)) if s else (None,0)

def match(name, teams):
    n=name.lower()
    for t in teams:
        if n in t.lower() or t.lower() in n: return t
    manual={'UConn':'Connecticut','UNC':'North Carolina','UVA':'Virginia','UNLV':'Nevada',
            'LSU':'Louisiana State','USC':'Southern California','SMU':'Southern Methodist',
            'UAB':'Alabama-Birmingham','UTSA':'Texas-San Antonio','CSU':'Colorado State'}
    if name in manual:
        for t in teams:
            if manual[name].lower() in t.lower(): return t
    return None

teams_2024=team_pts_2024['team_name'].tolist()
rows=[]

for gid, game in all_games.items():
    comps = game.get('header',{}).get('competitions',[])
    if not comps: continue
    comp = comps[0]
    status = comp.get('status',{}).get('type',{}).get('name','') or ''
    competitors = [c for c in comp.get('competitors',[]) if isinstance(c,dict)]
    if len(competitors)!=2: continue
    hc = next((c for c in competitors if c.get('homeAway')=='home'),None)
    ac = next((c for c in competitors if c.get('homeAway')=='away'),None)
    if not hc or not ac: continue
    ht = hc.get('team',{}).get('displayName','') or 'TBD'
    at = ac.get('team',{}).get('displayName','') or 'TBD'
    hid = hc.get('team',{}).get('id',''); aid = ac.get('team',{}).get('id','')
    date_str = game.get('header',{}).get('date','')[:10]
    f10 = extract_first_to_10(game.get('plays',[])) if status=='STATUS_FINAL' and game.get('plays') else None

    hp_pg,hn = get_ppg(hid); ap_pg,an = get_ppg(aid)
    if hp_pg and ap_pg and hn>=2 and an>=2:
        hp,ap,src = hp_pg,ap_pg,f"2026({hn}g/{an}g)"
    else:
        hm=match(ht,teams_2024); am=match(at,teams_2024)
        if hm and am:
            hr=team_pts_2024[team_pts_2024['team_name']==hm].iloc[0]
            ar=team_pts_2024[team_pts_2024['team_name']==am].iloc[0]
            hp,ap,src = hr['avg_pts'],ar['avg_pts'],'2024'
        else:
            hp,ap,src = 74.4,74.4,'avg'

    pace_diff = hp-ap
    prob = round(max(30,min(75,50+(pace_diff/147.4)*15+5.9)),1)
    round_label = ''
    if status=='STATUS_FINAL': round_label='R1-DONE'
    elif status=='STATUS_IN_PROGRESS': round_label='R1-LIVE'
    elif ht!='TBD' and at!='TBD' and ht in winners and at in winners: round_label='R2'
    elif ht!='TBD' and at!='TBD': round_label='LATER'
    else: round_label='TBD'

    rows.append({'game_id':gid,'date':date_str,'round':round_label,'status':status,
        'home_team':ht,'away_team':at,'home_id':hid,'away_id':aid,
        'home_score':get_score(hc),'away_score':get_score(ac),
        'first_to_10':f10,'home_pts_pg':round(hp,1),'away_pts_pg':round(ap,1),
        'pace_ratio':round((hp+ap)/147.4,3),'home_f10_prob':prob,'stats_source':src})

df = pd.DataFrame(rows)
df.to_csv(PROCESSED_DIR / 'first_to_10_2026.csv', index=False)

completed = df[df['round']=='R1-DONE']
live = df[df['round']=='R1-LIVE']
r2 = df[df['round']=='R2']
later = df[df['round'].isin(['LATER','TBD'])]

print("="*82)
print("2026 NCAA TOURNAMENT — FIRST TO 10")
print(f"Round 1: {len(completed)} done | {len(live)} live | R2+: {len(r2)+len(later)} pending")
if len(completed)>0:
    hf=completed['first_to_10'].eq('home').mean()*100
    print(f"Home F10 rate: {completed['first_to_10'].eq('home').sum()}/{len(completed)} = {hf:.1f}%")
print("="*82)

print("\n✅ ROUND 1 — COMPLETED")
print("-"*82)
for _,r in completed.sort_values('date').iterrows():
    icon='🏠' if r['first_to_10']=='home' else '👕'
    f10=str(r['first_to_10']).upper() if r['first_to_10'] else '?'
    print(f"  {icon} {r['home_team']:<28} {r['home_score']:>3}-{r['away_score']:<3} {r['away_team']:<28}  → F10:{f10}")

if len(live)>0:
    print(f"\n🔴 ROUND 1 — LIVE")
    print("-"*82)
    for _,r in live.iterrows():
        f10=f" → F10:{str(r['first_to_10']).upper()}" if r['first_to_10'] else ''
        print(f"  {r['home_team']:<28} {r['home_score']:>3}-{r['away_score']:<3} {r['away_team']}{f10}  [{r['status'].replace('STATUS_','')}]")

print(f"\n📅 ROUND 2+ — UPCOMING ({len(r2)} CONFIRMED, {len(later)} TBD)")
print("-"*82)
print(f"  {'ROUND':<6} {'HOME':<28} {'AWAY':<28} {'P(HOME)':>7} {'H PPG':>6} {'A PPG':>6}  SRC")
print("-"*82)
for _,r in r2.sort_values('home_team').iterrows():
    print(f"  R2     {r['home_team']:<28} {r['away_team']:<28} {r['home_f10_prob']:>6.1f}% {r['home_pts_pg']:>6.1f} {r['away_pts_pg']:>6.1f}  {r['stats_source']}")

for _,r in later.sort_values(['round','home_team']).iterrows():
    print(f"  {r['round']:<6} {r['home_team']:<28} {r['away_team']:<28} {r['home_f10_prob']:>6.1f}% {r['home_pts_pg']:>6.1f} {r['away_pts_pg']:>6.1f}  {r['stats_source']}")

print(f"\nSaved → {str(PROCESSED_DIR / 'first_to_10_2026.csv')}")
