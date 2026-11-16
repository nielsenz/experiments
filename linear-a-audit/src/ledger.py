"""Turn the token table into ledgers: for each inscription, the ordered list of quantities with their labels."""
from fractions import Fraction
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TOTAL_WORDS = ("KU-RO", "PO-TO-KU-RO")


def ledgers(path=ROOT / "data" / "tokens.csv"):
    t = pd.read_csv(path, dtype={"frac": str, "text": str})
    out = {}
    for name, g in t.groupby("inscription", sort=False):
        items, labels, section, lost, prev_kind = [], [], 0, False, None
        for r in g.itertuples():
            if r.kind == "word":
                if r.text == "—":
                    section += 1
                    labels = []          # a ruled divider ends whatever heading came before it
                else:
                    labels.append(r.text)
                    if r.text == "\U0001076b":      # a lost line or sign group
                        lost = True
            elif r.kind == "qty":
                frac = r.frac.split() if isinstance(r.frac, str) else []
                if prev_kind == "qty" and not r.has_int and items and not items[-1]["frac"]:
                    # a fraction written straight after a whole number belongs to that number
                    items[-1]["frac"] = frac
                    items[-1]["damaged"] = items[-1]["damaged"] or bool(r.damaged)
                else:
                    items.append(dict(i=len(items), int=int(r.int), has_int=bool(r.has_int), frac=frac,
                                      damaged=bool(r.damaged), labels=labels, label=labels[-1] if labels else None,
                                      section=section, lost_before=lost))
                    labels, lost = [], False
            prev_kind = r.kind
        out[name] = dict(items=items, site=g.site.iloc[0], support=g.support.iloc[0], scribe=g.scribe.iloc[0],
                         trailing_labels=labels)
    return out


def clean(q):
    """An intact whole number with no fraction signs."""
    return q["has_int"] and not q["damaged"] and not q["frac"]


def value(q, vals):
    """Numeric value of a quantity under a sign->Fraction assignment (None if a sign is unvalued)."""
    v = Fraction(q["int"])
    for s in q["frac"]:
        if s not in vals:
            return None
        v += vals[s]
    return v
