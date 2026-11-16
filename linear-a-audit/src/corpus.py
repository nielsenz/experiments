"""Parse the lineara.xyz inscription file into a flat token table.

The source file (LinearAInscriptions.js from github.com/mwenge/lineara.xyz) is read as text and never
executed.  Numbers and fraction signs are decoded from the Unicode glyphs themselves (Aegean numerals
U+10107-10133, Linear A fraction signs U+10740-10755), not from the site's English "translation" layer,
so no fraction values are assumed here.

Output: data/tokens.csv, one row per token:
  kind = word | qty | newline | sep ;  for qty: integer part, fraction signs, flags.
"""
import json, re, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FRAC = {0x10740: "A", 0x10741: "B", 0x10742: "D", 0x10743: "E", 0x10744: "F", 0x10745: "H", 0x10746: "J",
        0x10747: "K", 0x10748: "L", 0x10749: "L2", 0x1074A: "L3", 0x1074B: "L4", 0x1074C: "L6", 0x1074D: "W",
        0x1074E: "X", 0x1074F: "Y", 0x10750: "OMEGA", 0x10751: "A B", 0x10752: "B B", 0x10753: "D D",
        0x10754: "E E", 0x10755: "J E"}   # the last five are ligatures of two signs
DAMAGE = "\U0001076b"


def numval(c):
    o = ord(c)
    for lo, mult in ((0x10107, 1), (0x10110, 10), (0x10119, 100), (0x10122, 1000), (0x1012B, 10000)):
        if lo <= o <= lo + 8:
            return (o - lo + 1) * mult
    return None


def load_source(path):
    s = Path(path).read_text(encoding="utf8")
    t = s[s.index("new Map(") + len("new Map("):]
    t = re.sub(r",(\s*[\]}])", r"\1", t)                                             # trailing commas
    t = re.sub(r"\\u\{([0-9a-fA-F]+)\}", lambda m: chr(int(m.group(1), 16)), t)      # JS code-point escapes
    return dict(json.JSONDecoder().raw_decode(t.lstrip())[0])


def tokens(d):
    rows = []
    for name, v in d.items():
        words, tw = v["words"], v["transliteratedWords"]
        if len(words) != len(tw):
            continue
        for pos, (w, t) in enumerate(zip(words, tw)):
            base = dict(inscription=name, site=v.get("site"), support=v.get("support"), scribe=v.get("scribe"), pos=pos)
            core = w.replace(DAMAGE, "")
            dmg = DAMAGE in w
            if w == "\n":
                rows.append({**base, "kind": "newline"})
            elif w in ("\U00010101", "\U00010100", ""):
                rows.append({**base, "kind": "sep"})
            elif core and all(numval(c) is not None or ord(c) in FRAC for c in core):
                has_int = any(numval(c) is not None for c in core)
                rows.append({**base, "kind": "qty", "int": sum(numval(c) or 0 for c in core), "has_int": has_int,
                             "frac": " ".join(FRAC[ord(c)] for c in core if ord(c) in FRAC), "damaged": dmg})
            else:
                rows.append({**base, "kind": "word", "text": t, "damaged": dmg or DAMAGE in t or not core})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ROOT / "data" / "raw" / "LinearAInscriptions.js"
    t = tokens(load_source(src))
    t.to_csv(ROOT / "data" / "tokens.csv", index=False)
    print(t.inscription.nunique(), "inscriptions;", (t.kind == "qty").sum(), "quantities;",
          (t.kind == "word").sum(), "words;", t[t.kind == "qty"].frac.fillna("").ne("").sum(), "quantities with fractions")
