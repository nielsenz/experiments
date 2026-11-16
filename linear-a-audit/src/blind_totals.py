"""Study 1: find the word for "total" from arithmetic alone.

For every whole number in the corpus, ask: does it equal the sum of the run of numbers immediately before it
(at least two of them)?  Then group by the word written just before the number.  Nothing about any word's
meaning is used.  Significance comes from shuffling the numbers within each inscription.
"""
import numpy as np
import pandas as pd
from ledger import ledgers, clean, ROOT

RES = ROOT / "results"


def hits_for(vals, ok):
    """vals: list of ints; ok: list of bool (clean).  Returns list of (i, run_length) where vals[i] is a run-sum."""
    out = []
    for i in range(2, len(vals)):
        if not ok[i]:
            continue
        s = 0
        for j in range(i - 1, -1, -1):
            if not ok[j]:
                break
            s += vals[j]
            if i - j >= 2 and s == vals[i]:
                out.append((i, i - j)); break
            if s > vals[i]:
                break
    return out


def main(n_perm=20000, seed=0):
    L = ledgers()
    rows = []
    for name, led in L.items():
        it = led["items"]
        vals = [q["int"] for q in it]; ok = [clean(q) for q in it]
        hit = dict(hits_for(vals, ok))
        for i, q in enumerate(it):
            if i >= 2 and ok[i] and ok[i - 1] and ok[i - 2]:
                rows.append(dict(inscription=name, i=i, label=q["label"] or "(none)", value=q["int"],
                                 hit=i in hit, run=hit.get(i, 0)))
    c = pd.DataFrame(rows)
    tab = c.groupby("label").agg(numbers=("hit", "size"), run_sums=("hit", "sum")).reset_index()
    tab["share"] = tab.run_sums / tab.numbers

    # permutation null: shuffle the numbers within each inscription, keep words where they are
    rng = np.random.default_rng(seed)
    labels = sorted(c.label.unique()); idx = {l: k for k, l in enumerate(labels)}
    perm = np.zeros((n_perm, len(labels)), dtype=np.int32)
    prep = []
    for name, led in L.items():
        it = led["items"]
        if len(it) < 3:
            continue
        prep.append((np.array([q["int"] for q in it]), [clean(q) for q in it], [idx.get(q["label"] or "(none)") for q in it]))
    for b in range(n_perm):
        for vals, ok, lab in prep:
            okpos = [k for k, o in enumerate(ok) if o]
            v = vals.copy(); v[okpos] = rng.permutation(vals[okpos])
            for i, _ in hits_for(v.tolist(), ok):
                if lab[i] is not None and ok[i - 1] and ok[i - 2]:
                    perm[b, lab[i]] += 1
    tab["expected_by_chance"] = [perm[:, idx[l]].mean() for l in tab.label]
    tab["p_value"] = [(1 + (perm[:, idx[l]] >= h).sum()) / (n_perm + 1) for l, h in zip(tab.label, tab.run_sums)]
    best = int(tab.run_sums.max())
    familywise = (1 + (perm.max(axis=1) >= best).sum()) / (n_perm + 1)   # chance that ANY word scores this high
    tab = tab.sort_values(["run_sums", "share"], ascending=False)
    tab.round(4).to_csv(RES / "blind_total_words.csv", index=False)
    print(tab.head(12).round(4).to_string(index=False))

    is_tot = c.label.isin(["KU-RO", "PO-TO-KU-RO"])
    other_obs = int(c[~is_tot].hit.sum())
    other_cols = [idx[l] for l in labels if l not in ("KU-RO", "PO-TO-KU-RO")]
    other_perm = perm[:, other_cols].sum(axis=1)
    print("numbers tested", len(c), "| labels", c.label.nunique())
    print("run-sums after other words: observed", other_obs, "expected", other_perm.mean().round(2),
          "p", (1 + (other_perm >= other_obs).sum()) / (n_perm + 1))
    c[c.hit & ~is_tot].to_csv(RES / "unmarked_run_sums.csv", index=False)
    print(c[c.hit & ~is_tot].to_string(index=False))
    print("family-wise p for the top word:", familywise, "| max run-sums by any word in any shuffle:", perm.max())
    pd.DataFrame([dict(top_word=tab.label.iloc[0], top_word_run_sums=best, familywise_p=familywise,
                       max_any_word_any_shuffle=int(perm.max()), numbers_tested=len(c), labels=c.label.nunique(), other_word_run_sums=other_obs,
                       other_word_expected=other_perm.mean(), other_word_p=(1 + (other_perm >= other_obs).sum()) / (n_perm + 1),
                       permutations=n_perm)]).to_csv(RES / "blind_summary.csv", index=False)


if __name__ == "__main__":
    main()
