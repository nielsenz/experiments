"""Study 3: what the arithmetic on the tablets says about the fraction signs.

Part A derives values from four tablets using exact rational arithmetic and nothing else.
Part B checks two published value systems against every fraction combination in the corpus.
"""
from collections import Counter
from fractions import Fraction as Fr
import pandas as pd
from ledger import ledgers, ROOT

RES = ROOT / "results"
SYSTEMS = {
    "Bennett 1950": {"J": Fr(1, 2), "E": Fr(1, 4), "F": Fr(1, 8), "D": Fr(2, 3), "H": Fr(1, 3), "B": Fr(1, 12), "X": Fr(9, 20)},
    "Corazza et al. 2021": {"J": Fr(1, 2), "E": Fr(1, 4), "F": Fr(1, 8), "B": Fr(1, 5), "D": Fr(1, 6), "K": Fr(1, 10),
                            "L2": Fr(1, 20), "L3": Fr(1, 30), "L4": Fr(1, 40), "L6": Fr(1, 60),
                            "H": Fr(1, 16), "A": Fr(1, 24), "X": Fr(1, 12)},
}


def find(L, name, label):
    return [q for q in L[name]["items"] if label in q["labels"]]


def part_a(L):
    out = []
    # HT104: 45 J + 20 J + 29 = 95
    it = L["HT104"]["items"]
    ints = sum(q["int"] for q in it[:-1]); nJ = sum(q["frac"].count("J") for q in it[:-1])
    J = Fr(it[-1]["int"] - ints, nJ)
    out.append(("HT104", "45 J + 20 J + 29 = KU-RO 95", "J", J, "total balances only if J = 1/2"))
    # PE1: grain per person
    pe = L["PE1"]["items"]
    rate = Fr(pe[3]["int"], pe[2]["int"])                      # 36 grain / 72 people
    people = (pe[1]["int"] + J) / rate
    out.append(("PE1", f"{pe[2]['int']} people : {pe[3]['int']} grain, and a damaged 5x people : {pe[1]['int']} J grain",
                "J (cross-check)", J, f"at the same rate, {pe[1]['int']} J grain feeds {people} people, a whole number in the 50s as the damaged sign requires"))
    # HT Zd 157+156: 1, 1 J, 2 E, 3 E F in constant ratio
    r = 1 + J
    E = r ** 2 - 2
    F = r ** 3 - 3 - E
    out.append(("HTZd157+156", "1 : 1 J : 2 E : 3 E F, each 1.5 times the last", "E", E, "second step of the progression, given J"))
    out.append(("HTZd157+156", "same", "F", F, "third step of the progression, given J and E"))
    # KH7a: 10 workers : J, 4 workers : B
    B = J * 4 / 10
    out.append(("KH7a", "10 people : J of CYP+D, 4 people : B of CYP+D", "B", B, "same ration per person"))
    a = pd.DataFrame(out, columns=["tablet", "arithmetic", "sign", "value", "why"])
    a["value"] = a.value.astype(str)

    # without assuming J: which unit fractions for J make the Zd progression give legal E and F (0 < F < E < J)?
    legal = []
    for n in range(2, 121):
        j = Fr(1, n); e = (1 + j) ** 2 - 2; f = (1 + j) ** 3 - 3 - e
        if 0 < f < e < j:
            legal.append((str(j), str(e), str(f)))
    return a, legal


def combos(L):
    """Every multi-sign fraction group written on one quantity."""
    c = Counter()
    for name, led in L.items():
        for q in led["items"]:
            if len(q["frac"]) >= 2 and not q["damaged"]:
                c[tuple(q["frac"])] += 1
    return c


def part_b(L):
    c = combos(L)
    rows, detail = [], []
    for sysname, v in SYSTEMS.items():
        tested = order_bad = sum_bad = n_tok = 0
        for combo, n in c.items():
            if not all(s in v for s in combo):
                continue
            vals = [v[s] for s in combo]
            tested += 1; n_tok += n
            ob = any(vals[i] < vals[i + 1] for i in range(len(vals) - 1))
            sb = sum(vals) >= 1
            order_bad += ob; sum_bad += sb
            if ob or sb:
                detail.append(dict(system=sysname, combination=" ".join(combo), times_written=n, sum=str(sum(vals)),
                                   problem=" and ".join(p for p, b in (("smaller sign written first", ob), ("adds up to 1 or more", sb)) if b)))
        rows.append(dict(system=sysname, signs_valued=len(v), combinations_testable=tested, of_combinations=len(c),
                         written_instances=n_tok, ascending_order=order_bad, reach_one=sum_bad))
    return pd.DataFrame(rows), pd.DataFrame(detail), c


def ht123(L):
    """The oil total on HT 123+124a as read: 8 E + 8 J E + 4 A + 4 E = 25 H  ->  H - A = ?"""
    V = SYSTEMS["Corazza et al. 2021"]
    oil = [q for q in L["HT123+124a"]["items"] if q["label"] == "*308" and "KU-RO" not in q["labels"]]
    known = sum(Fr(q["int"]) + sum(V[s] for s in q["frac"] if s in ("J", "E")) for q in oil)
    tot = [q for q in L["HT123+124a"]["items"] if "KU-RO" in q["labels"] and "*308" in q["labels"]][0]
    return known - tot["int"], [(" ".join([str(q["int"])] + q["frac"]), q["damaged"]) for q in oil], tot["damaged"]


if __name__ == "__main__":
    L = ledgers()
    a, legal = part_a(L)
    a.to_csv(RES / "fraction_derivations.csv", index=False)
    print(a.to_string(index=False)); print("unit-fraction J values giving a legal progression:", legal)
    s, d, c = part_b(L)
    s.to_csv(RES / "fraction_systems.csv", index=False); d.to_csv(RES / "fraction_system_violations.csv", index=False)
    pd.DataFrame([dict(combination=" ".join(k), times_written=n) for k, n in c.most_common()]).to_csv(RES / "fraction_combinations.csv", index=False)
    print(s.to_string(index=False)); print(d.to_string(index=False))
    print("HT123+124a oil: H - A =", ht123(L))
