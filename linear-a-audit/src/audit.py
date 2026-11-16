"""Study 2: audit every KU-RO ("total") in the corpus.  Does the number after it equal the sum of the entries?

For each total, four ways of choosing the summands are tried and the best is reported:
  section    every entry since the previous total (or the start of the side / a ruled divider)
  running    the same, plus the previous total (a carried-forward grand total)
  commodity  only entries under the same commodity sign as the total (KU-RO OLIV 93 sums the OLIV entries)
  main       excluding sub-entries that carry the same label as the entry right after the total
  after KI-RO  only the entries listed under a KI-RO heading inside the section
  grand      for PO-TO-KU-RO: every earlier total on the tablet (both sides) plus entries not covered by one
Fractions are valued with J = 1/2, E = 1/4, F = 1/8 (see fraction_signs.py); other signs make a total uncheckable.
"""
from collections import Counter
from fractions import Fraction
import pandas as pd
from ledger import ledgers, value, TOTAL_WORDS, ROOT

RES = ROOT / "results"
VALS = {"J": Fraction(1, 2), "E": Fraction(1, 4), "F": Fraction(1, 8)}


def fmt(q):
    s = (str(q["int"]) if q["has_int"] else "") + ("".join(f" {x}" for x in q["frac"]))
    return s.strip() + ("?" if q["damaged"] else "")


def sides(name, L):
    """All sides of the same tablet, in order (HT122a, HT122b)."""
    stem = name[:-1] if name[-1] in "ab" else name
    return [n for n in (stem + "a", stem + "b", stem) if n in L]


def audit():
    rows = []
    L = ledgers()
    for name, led in L.items():
        it = led["items"]
        prev_total = None
        for k, q in enumerate(it):
            word = next((w for w in q["labels"] if w in TOTAL_WORDS), None)
            if not word:
                continue
            start = prev_total + 1 if prev_total is not None else 0
            sec = [x for x in it[start:k] if x["section"] == q["section"]] or it[start:k]
            commodity = [w for w in q["labels"] if w not in TOTAL_WORDS]
            cands = {"section": sec}
            if prev_total is not None:
                cands["running"] = [it[prev_total]] + sec
            if commodity:
                same = [x for x in it[:k] if commodity[-1] in x["labels"] and not any(w in TOTAL_WORDS for w in x["labels"])]
                if len(same) >= 2:
                    cands["commodity"] = same
            if k + 1 < len(it) and it[k + 1]["label"]:
                sub = it[k + 1]["label"]
                main = [x for x in sec if x["label"] != sub]
                if 2 <= len(main) < len(sec):
                    cands["main"] = main
            heads = [j for j, x in enumerate(sec) if "KI-RO" in x["labels"][:-1] or (x["labels"] and x["labels"][0] == "KI-RO" and len(x["labels"]) > 1)]
            if heads and len(sec) - heads[-1] >= 2 and heads[-1] > 0:
                cands["after KI-RO"] = sec[heads[-1]:]
            if word == "PO-TO-KU-RO":
                g = []
                for side in sides(name, L):
                    its = L[side]["items"]; last = -1
                    stop = k if side == name else len(its)
                    for j in range(stop):
                        if any(w in TOTAL_WORDS for w in its[j]["labels"]):
                            g.append(its[j]); last = j
                    if last >= 0:
                        g += its[last + 1:stop]
                if len(g) >= 2:
                    cands["grand"] = g
            tv = value(q, VALS)
            best = None
            for rule, xs in cands.items():
                bad = [x for x in xs if x["damaged"] or not (x["has_int"] or x["frac"])]
                lost = any(x["lost_before"] for x in xs) or q["lost_before"]
                vs = [value(x, VALS) for x in xs]
                unknown = any(v is None for v in vs)
                r = dict(rule=rule, n_entries=len(xs), n_damaged=len(bad), lost_lines=lost, unknown_sign=unknown,
                         entries=" + ".join(fmt(x) for x in xs))
                if not unknown and tv is not None:
                    r["sum"] = sum(vs); r["diff"] = r["sum"] - tv
                key = (r["n_damaged"] > 0 or lost or unknown, abs(r.get("diff", Fraction(10**6))))
                if best is None or key < best[0]:
                    best = (key, r)
            r = best[1]
            checkable = (not q["damaged"]) and q["has_int"] and r["n_damaged"] == 0 and not r["lost_lines"] \
                and not r["unknown_sign"] and r["n_entries"] >= 2
            status = "uncheckable"
            if checkable:
                status = "balances" if r["diff"] == 0 else "does not balance"
            elif r["n_entries"] >= 2 and r.get("diff") == 0 and not r["lost_lines"]:
                status = "balances as read (damaged signs)"
            implied = ""
            xs = cands[r["rule"]]
            dm = [x for x in xs if x["damaged"]]
            if status == "uncheckable" and not q["damaged"] and q["has_int"] and not r["unknown_sign"] and r["n_entries"] >= 2:
                if r["lost_lines"] and not dm and r["diff"] < 0:
                    implied = f"lost entry = {-r['diff']}"
                elif len(dm) == 1 and not r["lost_lines"]:
                    need = tv - sum(value(x, VALS) for x in xs if not x["damaged"])
                    if need > 0:
                        implied = f"entry read as {fmt(dm[0])} = {need}"
            rows.append(dict(inscription=name, scribe=led["scribe"], word=word, commodity=" ".join(commodity),
                             total=fmt(q), status=status, rule=r["rule"], n_entries=r["n_entries"],
                             sum=str(r.get("sum", "")), diff=str(r.get("diff", "")), n_damaged=r["n_damaged"],
                             lost_lines=r["lost_lines"], total_damaged=q["damaged"], implied_missing=implied, entries=r["entries"],
                             has_fractions=bool(q["frac"]) or any(c.isalpha() for c in r["entries"])))
            prev_total = k
            # an entry straight after the total that repeats a sub-entry label acts as a second total (HT118: KI)
            if k + 1 < len(it) and it[k + 1]["label"]:
                sub = [x for x in sec if x["label"] == it[k + 1]["label"]]
                if len(sub) >= 2 and all(not x["damaged"] and not x["frac"] for x in sub + [it[k + 1]]):
                    d = sum(x["int"] for x in sub) - it[k + 1]["int"]
                    rows.append(dict(inscription=name, scribe=led["scribe"], word="(sub-entry total)",
                                     commodity=it[k + 1]["label"], total=fmt(it[k + 1]),
                                     status="balances" if d == 0 else "does not balance", rule="sub-entries",
                                     n_entries=len(sub), sum=str(sum(x["int"] for x in sub)), diff=str(d), n_damaged=0,
                                     lost_lines=False, total_damaged=False, implied_missing="",
                                     entries=" + ".join(fmt(x) for x in sub), has_fractions=False))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    a = audit()
    a.to_csv(RES / "kuro_audit.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 70)
    print(a[["inscription", "word", "total", "status", "rule", "n_entries", "sum", "diff", "n_damaged", "lost_lines", "implied_missing", "entries"]].to_string(index=False))
    print(Counter(a.status))
