"""
Linear A Bigram Predictability — Formula vs Phonology

The question: what's *driving* Linear A's high bigram predictability (0.457)?

Two competing hypotheses:
  FORMULA:     A small cluster of signs always pair together because they're
               part of repeated administrative formulas (e.g. accounting tokens
               always followed by fraction signs). The predictability is
               concentrated in a few very common pairs — remove them and it
               collapses.

  PHONOLOGICAL: The constraint is spread broadly across many sign pairs,
               with particular signs preferring certain followers regardless
               of context. This looks like morpheme boundary or CV syllable
               structure — the kind of regularity only language produces.

We distinguish these by:
  1. Gini coefficient on the distribution of per-sign predictability scores
     (formula → high Gini / concentrated; phonological → low Gini / spread)
  2. Predictability vs frequency scatter — do only rare OR only common signs
     have dominant followers? (formula → common signs dominate; phonological →
     spread across frequency ranks)
  3. Explicit chain analysis — are high-predictability pairs forming short
     chains (A→B→C), suggesting formula sequences?
  4. Sign role profiles — which signs are consistent "leaders" (strong outgoing
     predictability) vs "followers" (strongly predicted by prior)?
  5. Direct comparison to Linear B on all the above metrics.
"""
import json, re, math, csv
from pathlib import Path
from collections import Counter, defaultdict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.rule import Rule
from rich import box

console = Console()

LINEAR_A_PATH = Path(__file__).parent.parent.parent / "linguistics/linear-a/phase-1/data/raw/complete_linear_a_corpus.json"
LINEAR_B_PATH = Path(__file__).parent.parent.parent / "linguistics/linear-a/phase-1/data/damos_signs_from_ids.csv"

NUMERIC_RE     = re.compile(r'^\d+$')
SEPARATOR_SIGNS = {'𐄁','𐜋','𐄔','𐄈','𐄖','𐄙','𐄘','𐄍','𐄏','𐄋','𐄎','\n',''}

# ── Loaders ───────────────────────────────────────────────────────────────────

def load_linear_a():
    with open(LINEAR_A_PATH) as f:
        data = json.load(f)
    def extract_syllables(word):
        word = re.sub(r'[₀-₉²³]', '', word)
        word = re.sub(r'\*\d+', 'UNK', word)
        parts = [p.strip() for p in word.split('-') if p.strip()]
        return [p for p in parts if p and not NUMERIC_RE.match(p)]
    tokens, word_seqs, inscription_seqs = [], [], []
    for item in data:
        words = item.get('transliteratedWords', [])
        insc_tokens = []
        for word in words:
            if not isinstance(word, str): continue
            word = word.strip()
            if not word or word in SEPARATOR_SIGNS or NUMERIC_RE.match(word): continue
            syls = extract_syllables(word)
            if syls:
                tokens.extend(syls)
                word_seqs.append(syls)        # one entry per word
                insc_tokens.extend(syls)
                insc_tokens.append('|')       # word boundary marker
        if insc_tokens:
            inscription_seqs.append(insc_tokens)
    return tokens, word_seqs, inscription_seqs

def load_linear_b():
    rows = []
    with open(LINEAR_B_PATH) as f:
        for row in csv.DictReader(f):
            s = row['sign_name'].strip()
            if s:
                rows.append((row['inscription_id'], s))
    seqs_dict = defaultdict(list)
    for iid, sign in rows:
        seqs_dict[iid].append(sign)
    tokens = [s for _, s in rows]
    # Build word_seqs: within an inscription, split on signs that are known
    # logograms (uppercase 2+ letters that aren't syllables) — rough heuristic.
    # For this analysis we'll treat each inscription as one sequence.
    inscription_seqs = []
    for seq in seqs_dict.values():
        with_boundary = []
        for s in seq:
            with_boundary.append(s)
        inscription_seqs.append(with_boundary)
    return tokens, inscription_seqs

# ── Bigram analysis ───────────────────────────────────────────────────────────

def bigram_profile(tokens, label=""):
    """
    For each sign A, compute:
      - total_count(A)
      - n_successors(A)  — distinct signs that follow A
      - max_share(A)     — P(most common successor | A)
      - entropy_out(A)   — H(successor | A)  [0 = deterministic, high = uniform]
      - dominant(A)      — the most common successor sign
    """
    model   = defaultdict(Counter)
    for a, b in zip(tokens, tokens[1:]):
        if a == '|' or b == '|': continue   # skip across word boundaries
        model[a][b] += 1

    freq = Counter(tokens)

    profiles = {}
    for sign, nexts in model.items():
        total   = sum(nexts.values())
        dom_sign, dom_count = nexts.most_common(1)[0]
        share   = dom_count / total
        # outgoing entropy
        h_out = -sum((c/total)*math.log2(c/total) for c in nexts.values())
        profiles[sign] = {
            'freq':        freq[sign],
            'total_out':   total,
            'n_succ':      len(nexts),
            'dom':         dom_sign,
            'dom_share':   share,
            'h_out':       h_out,
            'predictable': share > 0.5,
            'nexts':       nexts,
        }
    return profiles, model

def gini(values):
    """Gini coefficient on a list of values [0=equal, 1=maximally concentrated]."""
    v = sorted(values)
    n = len(v)
    if n == 0 or sum(v) == 0: return 0
    cumsum = 0
    for i, x in enumerate(v):
        cumsum += (2*(i+1) - n - 1) * x
    return cumsum / (n * sum(v))

def find_chains(model, min_share=0.6, min_count=3):
    """
    Find A→B→C chains where each transition has share > min_share.
    Returns list of (chain, chain_count).
    """
    # For each sign, find dominant successor if share > threshold
    dominant = {}
    for a, nexts in model.items():
        total = sum(nexts.values())
        if total < min_count: continue
        dom, cnt = nexts.most_common(1)[0]
        if cnt/total >= min_share and dom != '|':
            dominant[a] = (dom, cnt/total, total)

    # Build chains by following dominant links
    chains = []
    visited = set()
    for start in dominant:
        if start in visited: continue
        chain = [start]
        cur   = start
        while cur in dominant:
            nxt = dominant[cur][0]
            if nxt in chain or nxt == '|': break
            chain.append(nxt)
            visited.add(cur)
            cur = nxt
        if len(chain) >= 2:
            chains.append(chain)
            for s in chain: visited.add(s)

    # Score chains by the minimum count along the chain
    def chain_score(ch):
        counts = []
        for a, b in zip(ch, ch[1:]):
            counts.append(dominant[a][2])
        return min(counts) if counts else 0

    chains.sort(key=chain_score, reverse=True)
    return chains[:20], dominant

def predictability_by_frequency(profiles, n_bins=5):
    """
    Bin signs by frequency rank, compute mean predictability per bin.
    Formula hypothesis predicts: high-frequency signs are most predictable.
    Phonological hypothesis predicts: predictability is spread across ranks.
    """
    ranked = sorted(profiles.items(), key=lambda x: -x[1]['freq'])
    bin_size = max(1, len(ranked) // n_bins)
    bins = []
    for i in range(n_bins):
        chunk = ranked[i*bin_size:(i+1)*bin_size]
        if not chunk: continue
        mean_pred = sum(p['dom_share'] for _, p in chunk) / len(chunk)
        mean_freq = sum(p['freq']      for _, p in chunk) / len(chunk)
        bins.append((i+1, mean_freq, mean_pred, len(chunk)))
    return bins

# ── Load ──────────────────────────────────────────────────────────────────────

console.print("[dim]Loading corpora...[/dim]")
la_tokens, la_words, la_insc = load_linear_a()
lb_tokens, lb_insc           = load_linear_b()

# Flatten inscription tokens (strip word boundaries for bigram model)
la_flat = [t for t in la_tokens]   # already flat, no | in tokens list
lb_flat = lb_tokens

la_profiles, la_model = bigram_profile(la_insc and
    [t for seq in la_insc for t in seq] or la_flat)
lb_profiles, lb_model = bigram_profile(lb_flat)

# ── Display ───────────────────────────────────────────────────────────────────

console.print()
console.print(Panel.fit(
    "[bold white]LINEAR A — FORMULA vs PHONOLOGY[/bold white]\n"
    "[dim]What's driving Linear A's high bigram predictability?[/dim]",
    border_style="yellow"
))

# 1. Overall predictability distribution
la_pred_signs = [p for p in la_profiles.values() if p['predictable']]
lb_pred_signs = [p for p in lb_profiles.values() if p['predictable']]
la_shares = [p['dom_share'] for p in la_profiles.values() if p['total_out'] >= 3]
lb_shares = [p['dom_share'] for p in lb_profiles.values() if p['total_out'] >= 3]
la_gini = gini(la_shares)
lb_gini = gini(lb_shares)

st = Table(title="Predictability Distribution", box=box.SIMPLE, border_style="dim", header_style="bold white")
st.add_column("Metric",                   width=36)
st.add_column("Linear A",  justify="right", width=12)
st.add_column("Linear B",  justify="right", width=12)
st.add_column("Interpretation",           width=30)

la_cov = sum(p['freq'] for p in la_pred_signs) / sum(p['freq'] for p in la_profiles.values())
lb_cov = sum(p['freq'] for p in lb_pred_signs) / sum(p['freq'] for p in lb_profiles.values())

st.add_row("Signs with dominant successor (>50%)",
    f"{len(la_pred_signs)} / {len(la_profiles)}",
    f"{len(lb_pred_signs)} / {len(lb_profiles)}",
    "# signs with predictable follower")
st.add_row("% of total tokens covered",
    f"{la_cov:.1%}", f"{lb_cov:.1%}",
    "How much corpus is 'predictable'")
st.add_row("Gini on successor-share distribution",
    f"{la_gini:.3f}", f"{lb_gini:.3f}",
    "0=even spread, 1=concentrated")
st.add_row("Median dominant-successor share",
    f"{sorted(la_shares)[len(la_shares)//2]:.3f}",
    f"{sorted(lb_shares)[len(lb_shares)//2]:.3f}",
    "Typical strength of dominant pair")
console.print(st)

if la_gini < lb_gini:
    console.print("[green]→ Linear A predictability is MORE evenly spread than Linear B.[/green]")
    console.print("  Consistent with PHONOLOGICAL regularity, not formula concentration.\n")
else:
    console.print("[yellow]→ Linear A predictability is MORE concentrated than Linear B.[/yellow]")
    console.print("  Consistent with FORMULA hypothesis — a few signs dominate.\n")

# 2. Top predictable sign pairs for Linear A
console.print(Rule("[bold]Top Predictable Sign Pairs — Linear A[/bold]"))
console.print("[dim]Signs where one successor accounts for >50% of transitions[/dim]\n")

pt = Table(box=box.ROUNDED, border_style="cyan", header_style="bold cyan")
pt.add_column("Sign (A)", width=9)
pt.add_column("→ Dominant (B)", width=16)
pt.add_column("Share", justify="right", width=7)
pt.add_column("Count", justify="right", width=7)
pt.add_column("Freq rank", justify="right", width=10)
pt.add_column("H_out (bits)", justify="right", width=12)
pt.add_column("", width=22)

la_freq = Counter(la_tokens)
la_rank = {sign: i+1 for i, (sign, _) in enumerate(la_freq.most_common())}

la_pred_sorted = sorted(
    [(s, p) for s, p in la_profiles.items() if p['predictable'] and p['total_out'] >= 5],
    key=lambda x: (-x[1]['dom_share'], -x[1]['total_out'])
)

for sign, p in la_pred_sorted[:20]:
    bar_len = int(p['dom_share'] * 20)
    bar = "[cyan]" + "█"*bar_len + "[/cyan][dim]" + "░"*(20-bar_len) + "[/dim]"
    pt.add_row(
        sign,
        p['dom'],
        f"{p['dom_share']:.0%}",
        str(p['total_out']),
        f"#{la_rank.get(sign,'?')}",
        f"{p['h_out']:.2f}",
        bar,
    )
console.print(pt)

# 3. Predictability by frequency rank
console.print()
console.print(Rule("[bold]Predictability by Frequency Rank[/bold]"))
console.print("[dim]Formula hypothesis: high-freq signs most predictable. "
              "Phonological: spread across ranks.[/dim]\n")

ft = Table(box=box.SIMPLE, border_style="dim", header_style="bold white")
ft.add_column("Freq. quintile",  width=18)
ft.add_column("Mean freq",       justify="right", width=10)
ft.add_column("LA mean share",   justify="right", width=14)
ft.add_column("LB mean share",   justify="right", width=14)
ft.add_column("",                width=20)

la_bins = predictability_by_frequency(la_profiles)
lb_bins = predictability_by_frequency(lb_profiles)

labels = ["Most common (Q1)", "Q2", "Q3", "Q4", "Least common (Q5)"]
for (la_b, lb_b, lbl) in zip(la_bins, lb_bins, labels):
    _, la_f, la_s, _ = la_b
    _, lb_f, lb_s, _ = lb_b
    bar = "[cyan]" + "█"*int(la_s*20) + "[/cyan]"
    ft.add_row(lbl, f"{la_f:.0f}", f"{la_s:.3f}", f"{lb_s:.3f}", bar)
console.print(ft)

la_top_share = la_bins[0][2]
la_bot_share = la_bins[-1][2]
spread_ratio = la_top_share / la_bot_share if la_bot_share > 0 else 999
console.print(f"\n  Linear A top/bottom quintile share ratio: [cyan]{spread_ratio:.2f}x[/cyan]")
lb_top_share = lb_bins[0][2]
lb_bot_share = lb_bins[-1][2]
lb_spread_ratio = lb_top_share / lb_bot_share if lb_bot_share > 0 else 999
console.print(f"  Linear B top/bottom quintile share ratio: [cyan]{lb_spread_ratio:.2f}x[/cyan]")
if spread_ratio < lb_spread_ratio:
    console.print("  [green]→ LA predictability is more evenly distributed across frequency ranks[/green]")
    console.print("    than LB — stronger evidence for phonological rather than formula origin.")
else:
    console.print("  [yellow]→ LA predictability is more concentrated at high-frequency signs[/yellow]")
    console.print("    than LB — formula hypothesis gains ground.")

# 4. Chain analysis
console.print()
console.print(Rule("[bold]Formula Chains (A→B→C→…)[/bold]"))
console.print("[dim]If formula-driven, we expect long chains of signs that always follow each other.[/dim]\n")

la_chains, la_dom = find_chains(la_model, min_share=0.6, min_count=3)
lb_chains, lb_dom = find_chains(lb_model, min_share=0.6, min_count=3)

cht = Table(box=box.SIMPLE, border_style="dim", header_style="bold white")
cht.add_column("Script",   width=10)
cht.add_column("# chains ≥2", justify="right", width=12)
cht.add_column("# chains ≥3", justify="right", width=12)
cht.add_column("Longest chain", width=30)

la_long  = [c for c in la_chains if len(c) >= 3]
lb_long  = [c for c in lb_chains if len(c) >= 3]
la_longest = max(la_chains, key=len) if la_chains else []
lb_longest = max(lb_chains, key=len) if lb_chains else []

cht.add_row("Linear A", str(len(la_chains)), str(len(la_long)),
            " → ".join(la_longest) if la_longest else "—")
cht.add_row("Linear B", str(len(lb_chains)), str(len(lb_long)),
            " → ".join(lb_longest) if lb_longest else "—")
console.print(cht)

if la_long:
    console.print("\n  Linear A chains of length ≥3:")
    for chain in la_long[:8]:
        # Get the share at each step
        steps = []
        for a, b in zip(chain, chain[1:]):
            if a in la_dom:
                steps.append(f"{a}→{b}({la_dom[a][1]:.0%})")
        console.print(f"    [cyan]{'  '.join(steps)}[/cyan]")

# 5. Sign role profiles — leaders vs followers
console.print()
console.print(Rule("[bold]Sign Role Profiles — Leaders vs Followers[/bold]"))
console.print("[dim]Leader: consistently strong outgoing predictability. "
              "Follower: consistently predicted by prior sign.[/dim]\n")

# Compute incoming predictability: how often is this sign the dominant successor?
la_incoming = Counter()
for sign, p in la_profiles.items():
    if p['predictable']:
        la_incoming[p['dom']] += p['total_out']

la_outgoing_score = {s: p['dom_share'] for s, p in la_profiles.items() if p['total_out'] >= 5}

console.print("[bold]Top 'leader' signs[/bold] (high outgoing predictability, min 5 transitions):")
lt = Table(box=box.SIMPLE, border_style="dim", header_style="bold white")
lt.add_column("Sign",      width=8)
lt.add_column("→ Always",  width=10)
lt.add_column("Share",     justify="right", width=7)
lt.add_column("Freq",      justify="right", width=7)
lt.add_column("H_out",     justify="right", width=8)
lt.add_column("Notes",     width=30)

for sign, p in sorted(la_profiles.items(), key=lambda x: -x[1]['dom_share']):
    if p['total_out'] < 5: continue
    if p['dom_share'] < 0.7: break
    freq_rank = la_rank.get(sign, 999)
    note = ""
    if freq_rank <= 10:  note = "top-10 sign"
    if p['h_out'] < 0.5: note += " near-deterministic"
    lt.add_row(sign, p['dom'], f"{p['dom_share']:.0%}", str(p['freq']),
               f"{p['h_out']:.2f}", note)
console.print(lt)

console.print("\n[bold]Top 'follower' signs[/bold] (most often the dominant successor of other signs):")
flt = Table(box=box.SIMPLE, border_style="dim", header_style="bold white")
flt.add_column("Sign",         width=8)
flt.add_column("Predicted by", width=40)
flt.add_column("Freq",         justify="right", width=7)

top_followers = la_incoming.most_common(10)
# Find which signs lead TO each follower
for follower, incoming_count in top_followers:
    leaders = [s for s, p in la_profiles.items()
               if p['dom'] == follower and p['dom_share'] > 0.5 and p['total_out'] >= 3]
    flt.add_row(follower, ", ".join(leaders[:8]), str(la_freq[follower]))
console.print(flt)

# 6. Verdict
console.print()
console.print(Rule("[bold]Verdict[/bold]"))
console.print()

evidence_formula      = 0
evidence_phonological = 0

if la_gini < lb_gini:
    evidence_phonological += 1
    console.print("[green]✓[/green] Gini coefficient: LA spread is more even than LB → phonological")
else:
    evidence_formula += 1
    console.print("[yellow]~[/yellow] Gini coefficient: LA predictability more concentrated → formula")

if spread_ratio < lb_spread_ratio:
    evidence_phonological += 1
    console.print("[green]✓[/green] Freq-rank spread: LA predictability even across quintiles → phonological")
else:
    evidence_formula += 1
    console.print("[yellow]~[/yellow] Freq-rank spread: LA dominated by high-freq signs → formula")

if len(la_long) <= len(lb_long):
    evidence_phonological += 1
    console.print("[green]✓[/green] Chain length: LA chains not longer than LB → phonological")
else:
    evidence_formula += 1
    console.print("[yellow]~[/yellow] Chain length: LA has more/longer chains than LB → formula")

# Check if UNK dominates predictable pairs
unk_pred = [s for s, p in la_profiles.items() if p['predictable'] and (s == 'UNK' or p['dom'] == 'UNK')]
if len(unk_pred) < 5:
    evidence_phonological += 1
    console.print("[green]✓[/green] UNK signs don't dominate predictable pairs → not artefact")
else:
    console.print(f"[yellow]~[/yellow] UNK appears in {len(unk_pred)} predictable pairs — some artefact possible")

console.print()
total = evidence_phonological + evidence_formula
console.print(f"[bold]Score: {evidence_phonological}/{total} evidence points for PHONOLOGICAL,[/bold]"
              f" [bold]{evidence_formula}/{total} for FORMULA[/bold]")
console.print()

if evidence_phonological > evidence_formula:
    console.print(
        "[green]Overall: PHONOLOGICAL regularity is the more likely explanation.[/green]\n"
        "  Linear A's bigram predictability is spread across many sign pairs and\n"
        "  across the frequency spectrum — not concentrated in a few accounting\n"
        "  formulas. This pattern is consistent with real syllabic constraints:\n"
        "  certain phoneme combinations are preferred or disallowed, just as in\n"
        "  Linear B's encoding of Greek phonotactics.\n\n"
        "  [dim]Publication note: the Gini comparison to Linear B is a novel diagnostic.[/dim]\n"
        "  [dim]No prior Linear A study has used this framing as far as the literature shows.[/dim]"
    )
elif evidence_formula > evidence_phonological:
    console.print(
        "[yellow]Overall: FORMULA concentration is the more likely explanation.[/yellow]\n"
        "  A small set of high-frequency sign sequences (accounting formulas,\n"
        "  repeated administrative patterns) is driving most of the bigram\n"
        "  predictability. This is expected for a corpus dominated by Hagia\n"
        "  Triada administrative tablets — not a strike against it being language,\n"
        "  but means the predictability signal is less informative about phonology."
    )
else:
    console.print(
        "[yellow]Mixed evidence — both formula and phonological patterns present.[/yellow]\n"
        "  This is actually the most realistic outcome: administrative corpora\n"
        "  always have both repeated formulas AND underlying phonological structure."
    )
