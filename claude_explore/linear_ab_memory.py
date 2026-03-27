"""
Linear A vs Linear B — Effective Memory Length Comparison

The question: how much sequential context does each script "remember"?

We train Markov chains at orders 1–5 on both corpora and measure how quickly
the fake-generated metrics converge to the real corpus metrics. The order at
which convergence plateaus is the "effective memory length" — a proxy for how
much morphological/grammatical context is encoded in sign transitions.

Hypothesis:
- Linear B encodes Mycenaean Greek (inflected, rich morphology) → longer memory
- Linear A may be more administrative/logographic → shorter or similar memory
- A divergence in memory profiles would be an independent piece of evidence
  about the underlying linguistic complexity of Linear A

We compare three convergence metrics:
  1. Zipf R² (frequency structure)
  2. Conditional entropy H(sign | prev^n) (predictability)
  3. Bigram predictability on the generated sequence
"""
import json, re, math, random, csv, sys
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

NUMERIC_RE  = re.compile(r'^\d+$')
SEPARATOR_SIGNS = {'𐄁','𐜋','𐄔','𐄈','𐄖','𐄙','𐄘','𐄍','𐄏','𐄋','𐄎','\n',''}

# ── Loaders ───────────────────────────────────────────────────────────────────

def load_linear_a():
    console.print("[dim]Loading Linear A (GORILA)...[/dim]")
    with open(LINEAR_A_PATH) as f:
        data = json.load(f)

    def extract_syllables(word):
        word = re.sub(r'[₀-₉²³]', '', word)
        word = re.sub(r'\*\d+', 'UNK', word)
        parts = [p.strip() for p in word.split('-') if p.strip()]
        return [p for p in parts if p and not NUMERIC_RE.match(p)]

    all_signs, seqs = [], []
    for item in data:
        words = item.get('transliteratedWords', [])
        insc = []
        for word in words:
            if not isinstance(word, str): continue
            word = word.strip()
            if not word or word in SEPARATOR_SIGNS or NUMERIC_RE.match(word): continue
            syllables = extract_syllables(word)
            if syllables:
                all_signs.extend(syllables)
                insc.extend(syllables)
        if insc:
            seqs.append(insc)

    console.print(f"[dim]Linear A: {len(all_signs):,} tokens | {len(set(all_signs))} unique | {len(seqs)} inscriptions[/dim]")
    return all_signs, seqs


def load_linear_b():
    console.print("[dim]Loading Linear B (DAMOS)...[/dim]")
    rows = []
    with open(LINEAR_B_PATH) as f:
        for row in csv.DictReader(f):
            s = row['sign_name'].strip()
            if s:
                rows.append((row['inscription_id'], s))

    # Group into inscription sequences
    seqs_dict = defaultdict(list)
    for iid, sign in rows:
        seqs_dict[iid].append(sign)

    all_signs = [s for _, s in rows]
    seqs = list(seqs_dict.values())
    console.print(f"[dim]Linear B: {len(all_signs):,} tokens | {len(set(all_signs))} unique | {len(seqs)} inscriptions[/dim]")
    return all_signs, seqs


# ── Information-theory helpers ────────────────────────────────────────────────

def entropy(tokens):
    counts = Counter(tokens)
    total  = len(tokens)
    return -sum((c/total)*math.log2(c/total) for c in counts.values() if c > 0)


def conditional_entropy_order(tokens, order=1):
    """H(sign | prev^order)"""
    ngrams   = Counter(zip(*[tokens[i:] for i in range(order+1)]))
    contexts = Counter(zip(*[tokens[i:] for i in range(order)]))
    total    = len(tokens) - order
    h = 0.0
    for gram, count in ngrams.items():
        ctx = gram[:-1]
        p_gram = count / total
        p_ctx  = contexts[ctx] / (len(tokens) - order + 1)
        if p_ctx > 0:
            h -= p_gram * math.log2(p_gram / p_ctx)
    return h


def zipf_r2(tokens):
    freq   = Counter(tokens)
    ranked = sorted(freq.values(), reverse=True)
    if len(ranked) < 5: return 0.0, 0.0
    log_r = [math.log(i+1) for i in range(len(ranked))]
    log_f = [math.log(f)   for f in ranked]
    n  = len(log_r)
    mr, mf = sum(log_r)/n, sum(log_f)/n
    cov   = sum((r-mr)*(f-mf) for r,f in zip(log_r,log_f))
    var_r = sum((r-mr)**2 for r in log_r)
    slope = cov / var_r if var_r > 0 else 0
    ss_res = sum((f-mf - slope*(r-mr))**2 for r,f in zip(log_r,log_f))
    ss_tot = sum((f-mf)**2 for f in log_f)
    r2     = (1 - ss_res/ss_tot) if ss_tot > 0 else 0
    return r2, slope


def bigram_pred(tokens):
    model = defaultdict(Counter)
    for a, b in zip(tokens, tokens[1:]):
        model[a][b] += 1
    if not model: return 0
    return sum(1 for nexts in model.values()
               if max(nexts.values())/sum(nexts.values()) > 0.5) / len(model)


# ── Markov chain (variable order) ─────────────────────────────────────────────

class MarkovChain:
    def __init__(self, order):
        self.order  = order
        self.model  = defaultdict(Counter)
        self.starts = []

    def train(self, sequences):
        for seq in sequences:
            if len(seq) < self.order + 1: continue
            for i in range(len(seq) - self.order):
                gram = tuple(seq[i:i+self.order])
                self.model[gram][seq[i+self.order]] += 1
            self.starts.append(tuple(seq[:self.order]))

    def generate(self, length, rng):
        if not self.starts or not self.model: return []
        state  = rng.choice(self.starts)
        tokens = list(state)
        for _ in range(length - self.order):
            nexts = self.model.get(state)
            if not nexts:
                state = rng.choice(list(self.model.keys()))
                continue
            total = sum(nexts.values())
            r, cum = rng.random() * total, 0
            chosen = None
            for sign, count in nexts.items():
                cum += count
                if r <= cum:
                    chosen = sign
                    break
            if chosen is None:
                chosen = max(nexts, key=nexts.get)
            tokens.append(chosen)
            state = tuple(tokens[-self.order:])
        return tokens


# ── Convergence experiment ─────────────────────────────────────────────────────

def run_convergence(name, all_signs, seqs, orders=(1,2,3,4,5), gen_seed=42):
    console.print(f"\n[bold cyan]Running convergence experiment: {name}[/bold cyan]")

    real_h1    = entropy(all_signs)
    real_zipf, real_slope = zipf_r2(all_signs)
    real_pred  = bigram_pred(all_signs)
    # Conditional entropy at each order for real corpus
    real_hcond = {}
    for o in orders:
        real_hcond[o] = conditional_entropy_order(all_signs, o)
        console.print(f"  [dim]Real H(sign|prev^{o}) = {real_hcond[o]:.4f}[/dim]")

    results = []
    rng = random.Random(gen_seed)
    gen_len = min(len(all_signs), 5000)  # cap to keep Linear B manageable

    for order in orders:
        console.print(f"  [dim]Training order-{order} Markov...[/dim]")
        mc = MarkovChain(order)
        mc.train(seqs)
        fake = mc.generate(gen_len, rng=random.Random(gen_seed + order))
        if not fake:
            results.append({'order': order})
            continue

        fh     = entropy(fake)
        fzipf, _ = zipf_r2(fake)
        fpred  = bigram_pred(fake)
        fhcond = conditional_entropy_order(fake, 1)

        # Delta from real (smaller = converged)
        d_h    = abs(fh    - real_h1)
        d_zipf = abs(fzipf - real_zipf)
        d_pred = abs(fpred - real_pred)
        d_hc   = abs(fhcond - real_hcond[1])

        results.append({
            'order': order,
            'fake_h': fh,
            'fake_zipf': fzipf,
            'fake_pred': fpred,
            'fake_hcond': fhcond,
            'd_h': d_h,
            'd_zipf': d_zipf,
            'd_pred': d_pred,
            'd_hc': d_hc,
        })

    return real_h1, real_hcond[1], real_zipf, real_slope, real_pred, results


# ── Main ──────────────────────────────────────────────────────────────────────

la_signs, la_seqs = load_linear_a()
lb_signs, lb_seqs = load_linear_b()

ORDERS = (1, 2, 3, 4, 5)

la_h1, la_hc, la_zipf, la_slope, la_pred, la_results = run_convergence("Linear A", la_signs, la_seqs, ORDERS)
lb_h1, lb_hc, lb_zipf, lb_slope, lb_pred, lb_results = run_convergence("Linear B", lb_signs, lb_seqs, ORDERS)


# ── Display ───────────────────────────────────────────────────────────────────

console.print()
console.print(Panel.fit(
    "[bold white]LINEAR A vs LINEAR B — EFFECTIVE MEMORY LENGTH[/bold white]\n"
    "[dim]How fast does a Markov chain of order n reproduce each corpus's statistics?[/dim]\n"
    "[dim]Convergence plateau order = 'effective memory length' of the script[/dim]",
    border_style="yellow"
))

# Real corpus baseline table
bt = Table(title="Real Corpus Baselines", box=box.SIMPLE, border_style="dim", header_style="bold white")
bt.add_column("Metric",          width=28)
bt.add_column("Linear A",        justify="right", width=12)
bt.add_column("Linear B",        justify="right", width=12)
bt.add_column("Interpretation",  width=34)

bt.add_row("Tokens",          f"{len(la_signs):,}", f"{len(lb_signs):,}", "Corpus size")
bt.add_row("Unique signs",    str(len(set(la_signs))), str(len(set(lb_signs))), "Sign inventory size")
bt.add_row("Entropy H₁ (bits)", f"{la_h1:.3f}", f"{lb_h1:.3f}", "Higher = more uniform distribution")
bt.add_row("Cond. H (bits)", f"{la_hc:.3f}", f"{lb_hc:.3f}", "Lower = next sign more predictable")
bt.add_row("H reduction %",
    f"{(1-la_hc/la_h1)*100:.1f}%",
    f"{(1-lb_hc/lb_h1)*100:.1f}%",
    "How much context helps (grammar signal)")
bt.add_row("Zipf R²",         f"{la_zipf:.4f}", f"{lb_zipf:.4f}", "Power-law fit (>0.97 = natural lang)")
bt.add_row("Zipf slope",      f"{la_slope:.3f}", f"{lb_slope:.3f}", "≈ −1.0 for balanced natural language")
bt.add_row("Bigram pred.",    f"{la_pred:.3f}", f"{lb_pred:.3f}", "Frac. signs with >50% dominant follower")
console.print(bt)

# Convergence table — Zipf R²
console.print()
console.print(Rule("[bold]Convergence: |fake Zipf R² − real|  (lower = fake matches real)[/bold]"))
console.print("[dim]Plateau order reveals effective memory length[/dim]")
console.print()

ct = Table(box=box.ROUNDED, border_style="yellow", header_style="bold yellow")
ct.add_column("Markov order", justify="center", width=14)
ct.add_column("Linear A Δ Zipf", justify="right", width=16)
ct.add_column("Linear B Δ Zipf", justify="right", width=16)
ct.add_column("Linear A Δ H",    justify="right", width=14)
ct.add_column("Linear B Δ H",    justify="right", width=14)
ct.add_column("Linear A Δ pred", justify="right", width=16)
ct.add_column("Linear B Δ pred", justify="right", width=16)

def fmt_delta(v, prev=None):
    """Format delta; green if improved from previous order."""
    if v is None: return "[dim]—[/dim]"
    s = f"{v:.4f}"
    if prev is not None and v < prev:
        return f"[green]{s}[/green]"
    elif prev is not None and v > prev * 1.05:
        return f"[yellow]{s}[/yellow]"
    return s

la_prev_z = la_prev_h = la_prev_p = None
lb_prev_z = lb_prev_h = lb_prev_p = None

for la_r, lb_r in zip(la_results, lb_results):
    o = la_r['order']
    la_dz = la_r.get('d_zipf')
    lb_dz = lb_r.get('d_zipf')
    la_dh = la_r.get('d_hc')
    lb_dh = lb_r.get('d_hc')
    la_dp = la_r.get('d_pred')
    lb_dp = lb_r.get('d_pred')

    ct.add_row(
        f"order {o}",
        fmt_delta(la_dz, la_prev_z),
        fmt_delta(lb_dz, lb_prev_z),
        fmt_delta(la_dh, la_prev_h),
        fmt_delta(lb_dh, lb_prev_h),
        fmt_delta(la_dp, la_prev_p),
        fmt_delta(lb_dp, lb_prev_p),
    )
    la_prev_z, la_prev_h, la_prev_p = la_dz, la_dh, la_dp
    lb_prev_z, lb_prev_h, lb_prev_p = lb_dz, lb_dh, lb_dp

console.print(ct)

# Find effective memory lengths
def find_plateau(results, key, threshold=0.005):
    """Return the order where improvements drop below threshold."""
    prev = None
    for r in results:
        v = r.get(key)
        if v is None: continue
        if prev is not None and abs(prev - v) < threshold:
            return r['order'] - 1
        prev = v
    return results[-1]['order']

la_mem_zipf = find_plateau(la_results, 'd_zipf')
lb_mem_zipf = find_plateau(lb_results, 'd_zipf')
la_mem_h    = find_plateau(la_results, 'd_hc')
lb_mem_h    = find_plateau(lb_results, 'd_hc')

console.print()
console.print(Rule("[bold]Interpretation[/bold]"))
console.print()

console.print(f"[bold]Effective memory length (Zipf convergence):[/bold]")
console.print(f"  Linear A: order [cyan]{la_mem_zipf}[/cyan]  |  Linear B: order [cyan]{lb_mem_zipf}[/cyan]")
console.print()
console.print(f"[bold]Effective memory length (entropy convergence):[/bold]")
console.print(f"  Linear A: order [cyan]{la_mem_h}[/cyan]  |  Linear B: order [cyan]{lb_mem_h}[/cyan]")
console.print()

# Compute H reduction ratio — how much does grammar help vs random?
la_ratio = (1 - la_hc / la_h1) * 100
lb_ratio = (1 - lb_hc / lb_h1) * 100

console.print("[bold]Conditional entropy reduction (grammar signal strength):[/bold]")
console.print(f"  Linear A: knowing prev sign reduces uncertainty by [cyan]{la_ratio:.1f}%[/cyan]")
console.print(f"  Linear B: knowing prev sign reduces uncertainty by [cyan]{lb_ratio:.1f}%[/cyan]")
console.print()

if la_ratio > lb_ratio:
    console.print(
        "[yellow]→[/yellow] Linear A has [bold]stronger[/bold] local sign constraints than Linear B.\n"
        "  This could indicate: tighter administrative formula repetition, fewer\n"
        "  free-order constructions, or higher syllabic regularity per word."
    )
elif lb_ratio > la_ratio:
    console.print(
        "[yellow]→[/yellow] Linear B has [bold]stronger[/bold] local sign constraints than Linear A.\n"
        "  Consistent with Linear B encoding a morphologically rich language (Mycenaean\n"
        "  Greek) with regular inflectional endings driving sign-pair predictability."
    )
else:
    console.print("[yellow]→[/yellow] Both scripts show similar local constraint strength.")

console.print()
console.print("[bold]What the memory length tells us:[/bold]")
console.print(
    "  If Linear A's effective memory ≥ Linear B's, it encodes at least as much\n"
    "  sequential linguistic structure — inconsistent with a purely logographic or\n"
    "  accounting-tally interpretation. The script appears to be encoding language\n"
    "  with real grammatical/morphological context, not just a list of numbers.\n\n"
    "  [dim]Caveat: Linear A corpus is ~12x smaller than Linear B, so higher-order\n"
    "  Markov estimates are noisier. The order-1/2 results are most reliable.[/dim]"
)
