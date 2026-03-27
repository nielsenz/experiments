"""
Markov Chain Text Generator + Information Theory Analyzer

Learns the statistical structure of any text and:
  1. Generates new text in the same style (variable-order n-gram model)
  2. Shows the text's "information fingerprint":
       - Per-character entropy (how predictable is the next letter?)
       - Zipf's law fit (does word frequency follow the power law?)
       - Vocabulary richness (type-token ratio, hapax legomena)
       - Average sentence entropy (surprising vs. formulaic sentences)
  3. Lets you compare two texts side by side

Built-in corpora (use --corpus <name>):
  plays     — NCAA basketball play descriptions (from season PBP)
  alice     — Alice in Wonderland (fetched from Project Gutenberg)
  shakes    — Shakespeare's Hamlet (fetched from Project Gutenberg)

Usage:
  uv run python markov_writer.py                        # basketball plays
  uv run python markov_writer.py --corpus alice         # Alice in Wonderland
  uv run python markov_writer.py --corpus shakes        # Hamlet
  uv run python markov_writer.py --file mytext.txt      # any file
  uv run python markov_writer.py --compare alice shakes # side-by-side
  uv run python markov_writer.py --order 3 --length 200 # tune generation
"""
import sys, re, math, json, random, argparse, requests
from pathlib import Path
from collections import defaultdict, Counter
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box

console = Console()

# ── Corpus loaders ─────────────────────────────────────────────────────────────
def load_plays():
    pbp_path = Path(__file__).parent.parent / "college-basketball/data/raw/season_pbp_2026.json"
    if not pbp_path.exists():
        console.print("[red]PBP file not found. Run from college-basketball project first.[/red]")
        sys.exit(1)
    console.print("[dim]Loading basketball play descriptions...[/dim]")
    with open(pbp_path) as f:
        data = json.load(f)
    plays = []
    for game in data.values():
        for p in game.get('plays', []):
            text = p.get('text', '').strip()
            if text and len(text) > 5:
                plays.append(text)
    random.shuffle(plays)
    return " | ".join(plays[:3000])  # 3k plays, pipe-separated

def fetch_gutenberg(url: str, name: str) -> str:
    cache = Path(__file__).parent / f".cache_{name}.txt"
    if cache.exists():
        return cache.read_text()
    console.print(f"[dim]Fetching {name} from Project Gutenberg...[/dim]")
    r = requests.get(url, timeout=15)
    text = r.text
    # Strip Gutenberg header/footer
    start = text.find("*** START OF")
    end   = text.find("*** END OF")
    if start != -1:
        text = text[text.find('\n', start)+1:]
    if end != -1:
        text = text[:end]
    cache.write_text(text)
    return text

CORPORA = {
    'plays':  load_plays,
    'alice':  lambda: fetch_gutenberg(
        "https://www.gutenberg.org/files/11/11-0.txt", "alice"),
    'shakes': lambda: fetch_gutenberg(
        "https://www.gutenberg.org/files/1524/1524-0.txt", "hamlet"),
}

# ── Text cleaning ──────────────────────────────────────────────────────────────
def tokenize_words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+|[.!?]", text.lower())

def clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()

# ── Variable-order Markov chain ────────────────────────────────────────────────
class MarkovChain:
    def __init__(self, order: int = 2):
        self.order = order
        self.model: dict[tuple, Counter] = defaultdict(Counter)
        self.starts: list[tuple] = []

    def train(self, tokens: list[str]):
        for i in range(len(tokens) - self.order):
            gram = tuple(tokens[i:i + self.order])
            nxt  = tokens[i + self.order]
            self.model[gram][nxt] += 1
            # Track sentence starts
            if i == 0 or tokens[i-1] in '.!?|':
                self.starts.append(gram)

    def generate(self, length: int = 120, seed: tuple = None,
                 rng: random.Random = None) -> str:
        if rng is None:
            rng = random.Random(42)
        if not self.model:
            return ""

        if seed and seed in self.model:
            state = seed
        elif self.starts:
            state = rng.choice(self.starts)
        else:
            state = rng.choice(list(self.model.keys()))

        words = list(state)
        for _ in range(length - self.order):
            choices = self.model.get(state)
            if not choices:
                # Dead end — jump to a random known state
                state = rng.choice(list(self.model.keys()))
                continue
            total = sum(choices.values())
            r = rng.random() * total
            cumulative = 0
            chosen = None
            for word, count in choices.items():
                cumulative += count
                if r <= cumulative:
                    chosen = word
                    break
            if chosen is None:
                chosen = max(choices, key=choices.get)
            words.append(chosen)
            state = tuple(words[-self.order:])

        # Format: capitalize after sentence endings, join nicely
        out = []
        cap_next = True
        for w in words:
            if w in '.!?|':
                if out:
                    out[-1] += ('.' if w == '|' else w)
                cap_next = True
            else:
                out.append(w.capitalize() if cap_next else w)
                cap_next = False
        return ' '.join(out)

# ── Information theory metrics ─────────────────────────────────────────────────
def char_entropy(text: str) -> float:
    """Shannon entropy of characters in the text (bits per character)."""
    counts = Counter(text)
    total  = len(text)
    return -sum((c/total) * math.log2(c/total) for c in counts.values() if c > 0)

def bigram_entropy(text: str) -> float:
    """Conditional entropy H(char | prev_char) — how predictable is next char?"""
    bigrams = Counter(zip(text, text[1:]))
    unigrams = Counter(text)
    total = len(text) - 1
    h = 0.0
    for (a, b), count in bigrams.items():
        p_ab = count / total
        p_a  = unigrams[a] / len(text)
        h   -= p_ab * math.log2(p_ab / p_a)
    return h

def zipf_score(words: list[str]) -> float:
    """
    How well does the word frequency distribution follow Zipf's law?
    Returns R² of log(rank) vs log(frequency) regression.
    Closer to 1.0 = more Zipfian (natural language ≈ 0.97+).
    """
    freq = Counter(words)
    ranked = sorted(freq.values(), reverse=True)[:200]
    if len(ranked) < 10:
        return 0.0
    log_ranks = [math.log(i+1) for i in range(len(ranked))]
    log_freqs = [math.log(f) for f in ranked]
    n = len(log_ranks)
    mean_r = sum(log_ranks) / n
    mean_f = sum(log_freqs) / n
    ss_tot = sum((f - mean_f)**2 for f in log_freqs)
    ss_res = sum((f - mean_f - (r - mean_r) * sum((rr-mean_r)*(ff-mean_f) for rr,ff in zip(log_ranks,log_freqs)) / sum((rr-mean_r)**2 for rr in log_ranks))**2 for r,f in zip(log_ranks,log_freqs))
    return max(0.0, 1 - ss_res/ss_tot) if ss_tot > 0 else 0.0

def vocab_richness(words: list[str]) -> dict:
    unique    = set(words)
    hapax     = sum(1 for w, c in Counter(words).items() if c == 1)
    return {
        'ttr':         len(unique) / len(words),      # type-token ratio
        'hapax_ratio': hapax / len(unique),            # words appearing only once
        'vocab_size':  len(unique),
        'token_count': len(words),
    }

def avg_sentence_length(text: str) -> float:
    sentences = re.split(r'[.!?]+', text)
    lengths   = [len(s.split()) for s in sentences if s.strip()]
    return sum(lengths) / len(lengths) if lengths else 0

def sentence_entropy(words: list[str], order: int = 2) -> float:
    """Average per-token entropy of the n-gram model — how surprising is each word?"""
    model: dict[tuple, Counter] = defaultdict(Counter)
    for i in range(len(words) - order):
        gram = tuple(words[i:i+order])
        model[gram][words[i+order]] += 1
    entropies = []
    for gram, nexts in model.items():
        total = sum(nexts.values())
        h = -sum((c/total)*math.log2(c/total) for c in nexts.values() if c > 0)
        entropies.append(h)
    return sum(entropies) / len(entropies) if entropies else 0

def analyze(text: str, name: str) -> dict:
    words = tokenize_words(text)
    vr    = vocab_richness(words)
    return {
        'name':            name,
        'char_entropy':    char_entropy(text[:50000]),
        'bigram_entropy':  bigram_entropy(text[:50000]),
        'ngram_entropy':   sentence_entropy(words),
        'zipf':            zipf_score(words),
        'ttr':             vr['ttr'],
        'hapax_ratio':     vr['hapax_ratio'],
        'vocab_size':      vr['vocab_size'],
        'token_count':     vr['token_count'],
        'avg_sent_len':    avg_sentence_length(text),
        'words':           words,
        'text':            text,
    }

# ── Display ────────────────────────────────────────────────────────────────────
def bar(v, lo=0, hi=1, width=18, color='cyan'):
    p = max(0, min(1, (v - lo) / (hi - lo))) if hi > lo else 0
    filled = int(p * width)
    return f"[{color}]{'█'*filled}[/{color}][dim]{'░'*(width-filled)}[/dim]"

def show_analysis(a: dict):
    console.print(Panel.fit(
        f"[bold white]Text Analysis: {a['name']}[/bold white]\n"
        f"[dim]{a['token_count']:,} tokens | {a['vocab_size']:,} unique words[/dim]",
        border_style="yellow"
    ))

    t = Table(box=box.SIMPLE, show_header=False, padding=(0,1))
    t.add_column("Metric",  style="bold", width=26)
    t.add_column("Value",   justify="right", width=8)
    t.add_column("",        width=22)
    t.add_column("Notes",   style="dim", width=32)

    t.add_row("Char entropy (bits/char)",
        f"{a['char_entropy']:.3f}",
        bar(a['char_entropy'], 3.5, 5.5),
        "English prose ≈ 4.0–4.5; code ≈ 5+")

    t.add_row("Bigram entropy (conditional)",
        f"{a['bigram_entropy']:.3f}",
        bar(a['bigram_entropy'], 2.5, 4.5),
        "Lower = more predictable next char")

    t.add_row("N-gram surprise (bits/word)",
        f"{a['ngram_entropy']:.3f}",
        bar(a['ngram_entropy'], 0, 4),
        "Higher = less formulaic writing")

    zipf_color = 'green' if a['zipf'] > 0.95 else ('yellow' if a['zipf'] > 0.90 else 'red')
    t.add_row("Zipf's law fit (R²)",
        f"{a['zipf']:.4f}",
        bar(a['zipf'], 0.8, 1.0, color=zipf_color),
        "Natural language ≈ 0.97+")

    ttr_color = 'green' if a['ttr'] < 0.15 else 'yellow'
    t.add_row("Type-token ratio",
        f"{a['ttr']:.4f}",
        bar(a['ttr'], 0, 0.3, color=ttr_color),
        "Lower = more repetitive style")

    t.add_row("Hapax ratio (unique words)",
        f"{a['hapax_ratio']:.3f}",
        bar(a['hapax_ratio'], 0.3, 0.8),
        "% of vocab appearing just once")

    t.add_row("Avg sentence length (words)",
        f"{a['avg_sent_len']:.1f}",
        bar(a['avg_sent_len'], 5, 30),
        "Hemingway ≈ 8; James ≈ 20+")

    console.print(t)

def show_generated(text: str, name: str, order: int):
    console.print(Panel(
        f"[italic]{text}[/italic]",
        title=f"[bold cyan]Generated ({name}, order={order})[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

def show_comparison(analyses: list[dict]):
    console.print()
    console.print(Panel.fit("[bold white]Side-by-Side Comparison[/bold white]", border_style="magenta"))

    metrics = [
        ("Char entropy",        'char_entropy',   "{:.3f}", 3.5, 5.5),
        ("Bigram entropy",      'bigram_entropy',  "{:.3f}", 2.5, 4.5),
        ("N-gram surprise",     'ngram_entropy',   "{:.3f}", 0,   4),
        ("Zipf R²",             'zipf',            "{:.4f}", 0.8, 1.0),
        ("Type-token ratio",    'ttr',             "{:.4f}", 0,   0.3),
        ("Hapax ratio",         'hapax_ratio',     "{:.3f}", 0.3, 0.8),
        ("Avg sentence length", 'avg_sent_len',    "{:.1f}", 5,   30),
    ]

    t = Table(box=box.ROUNDED, border_style="magenta", header_style="bold magenta")
    t.add_column("Metric", width=22)
    for a in analyses:
        t.add_column(a['name'], justify="right", width=12)
    t.add_column("More X →", style="dim", width=18)

    labels = ["predictable","predictable","formulaic","Zipfian","repetitive","unique words","verbose"]
    for (label, key, fmt, lo, hi), lbl in zip(metrics, labels):
        vals = [fmt.format(a[key]) for a in analyses]
        winner_idx = max(range(len(analyses)), key=lambda i: analyses[i][key])
        row = [label]
        for i, v in enumerate(vals):
            row.append(f"[bold green]{v}[/bold green]" if i == winner_idx else v)
        row.append(f"← {lbl}")
        t.add_row(*row)

    console.print(t)

# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Markov text generator + info theory analysis")
    parser.add_argument('--corpus',  default='plays', choices=list(CORPORA.keys()))
    parser.add_argument('--file',    default=None,    help="Path to a .txt file")
    parser.add_argument('--order',   type=int, default=2, help="N-gram order (1-4)")
    parser.add_argument('--length',  type=int, default=100, help="Words to generate")
    parser.add_argument('--compare', nargs=2,  metavar='CORPUS', help="Compare two corpora")
    parser.add_argument('--seed',    type=int, default=99)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    if args.compare:
        analyses, chains = [], []
        for name in args.compare:
            loader = CORPORA.get(name)
            if not loader:
                console.print(f"[red]Unknown corpus: {name}[/red]"); sys.exit(1)
            text = clean(loader())
            a = analyze(text, name)
            analyses.append(a)
            mc = MarkovChain(order=args.order)
            mc.train(a['words'])
            chains.append(mc)

        for a, mc in zip(analyses, chains):
            show_analysis(a)
            console.print()
            show_generated(mc.generate(args.length, rng=rng), a['name'], args.order)
            console.print()

        show_comparison(analyses)

    else:
        if args.file:
            text = clean(Path(args.file).read_text())
            name = Path(args.file).stem
        else:
            loader = CORPORA.get(args.corpus)
            if not loader:
                console.print(f"[red]Unknown corpus: {args.corpus}[/red]"); sys.exit(1)
            text = clean(loader())
            name = args.corpus

        a = analyze(text, name)
        show_analysis(a)
        console.print()

        mc = MarkovChain(order=args.order)
        mc.train(a['words'])

        # Generate with a few different seeds to show variety
        for seed_val in [args.seed, args.seed+7, args.seed+42]:
            show_generated(mc.generate(args.length, rng=random.Random(seed_val)), name, args.order)
            console.print()
