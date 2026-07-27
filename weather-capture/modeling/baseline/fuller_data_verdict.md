# Would fuller data change the verdict? — NO (tested, not assumed)

Question after the negative step-3 result: does pulling "full data" rescue any
edge? Broke it into the three things "full data" could mean and tested the only
one with a real case.

## The oracle bound (the argument that makes sample size irrelevant)

Give the strategy PERFECT ex-ante knowledge of the net-load surprise sign — an
omniscient trader. Trade sign(surprise) every ramp hour, collect the spread.
This is the CEILING no data or model can beat.

  Hub SP15, ramp hours: oracle P&L = **+$1.47–1.55/MWh/hr**, win rate ~54%.
  After a realistic ~$2/MWh round-trip DA↔RT cost: **NEGATIVE.**

Even the omniscient trader loses money after costs. So:
- More price history (2× sample): makes a trivially-small number more precisely
  small. Verdict is structural, not statistical. No change.
- Higher time resolution (5-min RT): oracle is computed on the realized spread;
  finer bars can't manufacture P&L that isn't in the price. No change.

## Nodal test — the one candidate with a real case (DONE)

Hypothesis: the SP15 hub is the most-arbitraged point; a congestion-prone node
might have larger, less-efficient spreads → higher oracle ceiling. Pulled DA+RT
LMP at MIRALOMA_6_N001 (LA-basin load node), 2026 H1, and recomputed the ramp
oracle head-to-head vs the hub on the identical 905 ramp hours:

| metric | Hub SP15 | Node MIRALOMA |
|---|---|---|
| spread std | $27.7 | $29.8 |
| surprise→spread corr | +0.056 | +0.051 |
| quintile Q5−Q1 | +$5.07 | +$5.13 |
| **oracle P&L/hr** | **+$1.55** | **+$1.55** |
| after $2 cost | −$0.45 | −$0.45 |

**MIRALOMA is indistinguishable from the hub.** Nodal congestion added ~$2 of
spread-std dispersion but ZERO predictability — the oracle bound is identical to
two decimals and still sub-cost. The DA congestion basis at this node was only
±$2.48 std (a well-behaved node, not heavily congested).

## Conclusion

Pulling fuller versions of the existing data would NOT change the verdict. The
negative rests on the oracle bound (perfect foresight still loses after costs),
which is already at ample sample size. The only genuinely different question —
nodal congestion — was tested directly at a real node and came back the same.

Caveat kept honest: one node (MIRALOMA) is not all nodes. A pathologically
congested node (e.g. behind a chronic transmission constraint) COULD differ. But
that's a targeted search for a specific market defect, not "more data," and its
prior is low. The general thesis — net-load surprise as a tradeable ramp signal
at liquid points — is closed.
