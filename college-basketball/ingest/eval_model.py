"""
Build and evaluate first-to-10 model on 2025-2026 data.
- All 1158 scraped games for team stats
- Hold out 20% of completed tournament games for evaluation
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SEASON_PBP, TOURNAMENT_PBP, MODEL_2026, MODELS_DIR

import json, numpy as np
from collections import defaultdict
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_score
from sklearn.metrics import brier_score_loss, roc_auc_score, accuracy_score
import pickle

# ── Load data ──────────────────────────────────────────────────────────────────
with open(SEASON_PBP) as f:
    all_games = json.load(f)
with open(MODEL_2026, 'rb') as f:
    old = pickle.load(f)
old_model = old['model']
t2024 = old['team_pts']
print(f"Loaded {len(all_games)} games, 2024 model AUC (old): 0.638")

# ── Build 2025-26 team stats ──────────────────────────────────────────────────
ts = defaultdict(list)   # team -> home scores
tp = defaultdict(list)   # team -> away scores
name_map = {}

for gid, game in all_games.items():
    plays = game.get('plays', [])
    if not plays: continue
    box = game.get('boxscore', {}); teams = box.get('teams', [])
    if len(teams) != 2: continue
    tinfo = {}
    for tt in teams:
        ha = tt['homeAway']; tid = tt['team']['id']
        tn = tt['team'].get('shortDisplayName', tt['team'].get('displayName', 'UNK'))
        tinfo[ha] = {'id': tid, 'name': tn}
        if tid not in name_map: name_map[tid] = tn
    scored = [p for p in plays if p.get('scoringPlay')]
    if not scored: continue
    fin = scored[-1]; af, hf = fin.get('awayScore', 0), fin.get('homeScore', 0)
    if af == 0 and hf == 0: continue
    if 'home' in tinfo:
        ts[tinfo['home']['id']].append(hf); tp[tinfo['home']['id']].append(af)
    if 'away' in tinfo:
        ts[tinfo['away']['id']].append(af); tp[tinfo['away']['id']].append(hf)

t2026 = {}
for tid, sc in ts.items():
    if len(sc) < 3: continue
    pace = float(np.mean([sc[i]+tp[tid][i] for i in range(len(sc))]))
    t2026[tid] = {'name': name_map.get(tid,'UNK'), 'pts': float(np.mean(sc)), 'pace': pace}

lap = float(np.mean([v['pace'] for v in t2026.values() if v['pace']>0])) or 150.0
for v in t2026.values(): v['pr'] = v['pace'] / lap if v['pace']>0 else 1.0
print(f"2025-26: {len(t2026)} teams, league avg pace={lap:.1f}")

# ── Load tournament data ──────────────────────────────────────────────────────
with open(TOURNAMENT_PBP) as f:
    tourn = json.load(f)

def ef10(plays):
    for p in plays:
        if p.get('scoringPlay'):
            a = p.get('awayScore',0); h = p.get('homeScore',0); pts = p.get('scoreValue',0)
            if a >= 10 and (a-pts) < 10: return 'away', a, h
            if h >= 10 and (h-pts) < 10: return 'home', a, h
    return None, 0, 0

def safe(s): return str(s).strip() if s else ''

def get_first_word(name):
    words = safe(name).replace('.','').split()
    return words[0] if words else ''

def lkup(name):
    n = safe(name)
    if not n or n.upper() in ('TBD','NONE','UNK',''): return None, None
    fw = get_first_word(n)
    for tid, v in t2026.items():
        if v['name'].lower() == n.lower(): return v['pts'], v['pr']
    if fw:
        for tid, v in t2026.items():
            if fw.lower() == v['name'].lower() or fw.lower() == v['name'].lower().split()[0]:
                return v['pts'], v['pr']
        if fw in t2024: return t2024[fw], None
        for tn, tp2 in t2024.items():
            if fw.lower() == tn.lower() or fw.lower() == tn.lower().split()[0]:
                return tp2, None
    return None, None

# Extract completed tournament games
tourn_games = []
for gid, game in tourn.items():
    h = game.get('header', {})
    comp = h.get('competitions', [{}])[0]
    comps = comp.get('competitors', [])
    status = comp.get('status', {}); plays = game.get('plays', [])
    hc = next((c for c in comps if c.get('homeAway')=='home'), None)
    ac = next((c for c in comps if c.get('homeAway')=='away'), None)
    if not hc or not ac: continue
    hn = safe(hc['team'].get('shortDisplayName', hc['team'].get('displayName','UNK')))
    an = safe(ac['team'].get('shortDisplayName', ac['team'].get('displayName','UNK')))
    gs = status.get('type',{}).get('name','UNKNOWN')
    if plays and gs == 'STATUS_FINAL':
        w, af, hf = ef10(plays)
        tourn_games.append({'gid':gid,'home':hn,'away':an,'winner':w,'af':af,'hf':hf})

print(f"Tournament completed games: {len(tourn_games)}")
np.random.seed(42)
np.random.shuffle(tourn_games)
n_holdout = max(5, int(len(tourn_games)*0.20))
holdout = tourn_games[:n_holdout]
train_tourn = tourn_games[n_holdout:]
print(f"Holdout: {n_holdout} | Train tourn: {len(train_tourn)}")

# ── Build training set from 2025-26 season ────────────────────────────────────
X_train, y_train = [], []
for gid, game in all_games.items():
    plays = game.get('plays', [])
    if not plays: continue
    box = game.get('boxscore', {}); teams = box.get('teams', [])
    if len(teams) != 2: continue
    tinfo = {}
    for tt in teams:
        ha = tt['homeAway']; tid = tt['team']['id']
        tn = tt['team'].get('shortDisplayName', tt['team'].get('displayName', 'UNK'))
        tinfo[ha] = {'id': tid, 'name': tn}
    scored = [p for p in plays if p.get('scoringPlay')]
    if not scored: continue
    fin = scored[-1]; af, hf = fin.get('awayScore', 0), fin.get('homeScore', 0)
    if af == 0 and hf == 0: continue
    # Get first-to-10 from PBP plays
    f10w = None
    for p in scored:
        a = p.get('awayScore',0); h = p.get('homeScore',0); pts = p.get('scoreValue',0)
        if a >= 10 and (a-pts) < 10: f10w = 'away'; break
        if h >= 10 and (h-pts) < 10: f10w = 'home'; break
    if not f10w: continue
    if 'home' not in tinfo or 'away' not in tinfo: continue
    hn, an = tinfo['home']['name'], tinfo['away']['name']
    hp, hr = lkup(hn); ap, ar = lkup(an)
    if hp and ap:
        pr = (hr + ar) / 2 if (hr and ar) else 1.0
        pd2 = (hr - ar) if (hr and ar) else 0.0
        X_train.append([pr, pd2, hp, ap])
        y_train.append(1 if f10w == 'home' else 0)

X_train = np.array(X_train); y_train = np.array(y_train)
print(f"\nTraining set: {len(X_train)} games | Home F10: {y_train.sum()}/{len(y_train)} = {y_train.mean():.1%}")

# ── Train new 2026 model ───────────────────────────────────────────────────────
model26 = GradientBoostingClassifier(n_estimators=200, max_depth=3, min_samples_leaf=20,
                                     learning_rate=0.05, subsample=0.8, random_state=42)
model26.fit(X_train, y_train)
cv_auc = cross_val_score(model26, X_train, y_train, cv=5, scoring='roc_auc').mean()
print(f"2026 Model CV AUC: {cv_auc:.4f}")

# ── Holdout evaluation ─────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"HOLDOUT EVALUATION ({n_holdout} tournament games)")
print(f"{'='*60}")

probs, labels, preds, games_used = [], [], [], 0
for g in holdout:
    hp, hr = lkup(g['home']); ap, ar = lkup(g['away'])
    if hp and ap:
        pr = (hr+ar)/2 if (hr and ar) else 1.0
        pd2 = (hr-ar) if (hr and ar) else 0.0
        X = np.array([[pr, pd2, hp, ap]])
        prob = float(model26.predict_proba(X)[0][1])
        pred = 'home' if prob > 0.5 else 'away'
        correct = pred == g['winner']
        label = 1 if g['winner'] == 'home' else 0
        probs.append(prob); labels.append(label); preds.append(pred)
        print(f"  {'✓' if correct else '✗'} {g['home']} vs {g['away']}: P(home)={prob:.1%} | {g['winner'].upper()} won F10 ({g['hf']}-{g['af']})")
        games_used += 1

if games_used >= 3:
    acc = accuracy_score(labels, preds)
    auc = roc_auc_score(labels, probs)
    brier = brier_score_loss(labels, probs)
    print(f"\nHoldout Accuracy: {acc:.1%} ({sum(p==l for p,l in zip(preds,labels))}/{games_used})")
    print(f"Holdout AUC: {auc:.4f}")
    print(f"Brier Score: {brier:.4f}")
    print(f"Avg predicted prob (home): {np.mean(probs):.1%}")
    print(f"Actual home rate: {np.mean(labels):.1%}")
    cal_err = abs(np.mean(probs) - np.mean(labels))
    print(f"Calibration error: {cal_err:.1%}")

    # Also evaluate old 2024 model on same holdout
    probs24, labels24 = [], []
    for g in holdout:
        hp, hr = lkup(g['home']); ap, ar = lkup(g['away'])
        if hp and ap:
            pr = (hr+ar)/2 if (hr and ar) else 1.0
            pd2 = (hr-ar) if (hr and ar) else 0.0
            X = np.array([[pr, pd2, hp, ap]])
            prob = float(old_model.predict_proba(X)[0][1])
            probs24.append(prob); labels24.append(1 if g['winner']=='home' else 0)
    auc24 = roc_auc_score(labels24, probs24)
    brier24 = brier_score_loss(labels24, probs24)
    print(f"\n2024 Model on same holdout:")
    print(f"  AUC: {auc24:.4f} | Brier: {brier24:.4f}")
    print(f"\n2026 model improvement: AUC +{auc-auc24:.4f}, Brier {brier24-brier:.4f} better")

# ── Show remaining scheduled tournament games ─────────────────────────────────
print(f"\n{'='*60}")
print("REMAINING TOURNAMENT GAMES (predicted with 2025-26 stats)")
print(f"{'='*60}")
sched = []
for gid, game in tourn.items():
    h = game.get('header', {})
    comp = h.get('competitions', [{}])[0]
    comps = comp.get('competitors', [])
    status = comp.get('status', {}); plays = game.get('plays', [])
    hc = next((c for c in comps if c.get('homeAway')=='home'), None)
    ac = next((c for c in comps if c.get('homeAway')=='away'), None)
    if not hc or not ac: continue
    gs = status.get('type',{}).get('name','UNKNOWN')
    if plays and gs == 'STATUS_FINAL': continue  # already done
    hn = safe(hc['team'].get('shortDisplayName', hc['team'].get('displayName','UNK')))
    an = safe(ac['team'].get('shortDisplayName', ac['team'].get('displayName','UNK')))
    date = comp.get('date','')[:10] or '2026-03-01'
    hp, hr = lkup(hn); ap, ar = lkup(an)
    sc = '—'
    try:
        hs = int(hc.get('score',{}).get('value',0) or 0)
        aus = int(ac.get('score',{}).get('value',0) or 0)
        if hs+aus > 0: sc = f'{hs}-{aus}'
    except: pass
    pb = None
    if hp and ap:
        pr = (hr+ar)/2 if (hr and ar) else 1.0
        pd2 = (hr-ar) if (hr and ar) else 0.0
        X = np.array([[pr, pd2, hp, ap]])
        pb = float(model26.predict_proba(X)[0][1])
    sched.append({'date':date,'home':hn,'away':an,'score':sc,'hp':hp,'ap':ap,'prob':pb})

sched.sort(key=lambda x: x['date'])
print(f"{'Date':<12} {'Home':<22} {'Away':<22} {'Score':>6}  {'P(Home)':>8} {'H PPG':>6} {'A PPG':>6}")
for g in sched:
    if g['prob'] is not None:
        pb_str = f"{g['prob']:.1%}"
        hp_str = f"{g['hp']:.0f}" if g['hp'] else "—"
        ap_str = f"{g['ap']:.0f}" if g['ap'] else "—"
        print(f"{g['date']:<12} {g['home']:<22} {g['away']:<22} {g['score']:>6}  {pb_str:>8} {hp_str:>6} {ap_str:>6}")
