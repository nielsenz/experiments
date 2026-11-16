# Auditing the Minoan books: what arithmetic alone proves about Linear A

Linear A is undeciphered, but its numbers are not: the numerals were worked out decades ago and most surviving tablets are
accounts. That makes arithmetic the one tool that can test a reading without knowing the language. This project uses it three
ways on the full corpus (1,712 inscriptions, 1,714 written quantities, from [lineara.xyz](https://github.com/mwenge/lineara.xyz)):

1. Can the word for "total" be found from the numbers alone, with no prior reading?
2. How often did the scribes' totals actually add up?
3. Which fraction signs can be valued by arithmetic, and do the published values survive a check against the corpus?

## Answers

**1. Yes. One word, and only one, marks sums.** For every whole number in the corpus the script asks whether it equals the sum
of the run of numbers just before it, then groups the results by the word written before the number. KU-RO is followed by a
run-sum 8 times in 17; shuffling the numbers within each inscription gives 1.2 by chance. In 20,000 shuffles no word of the
229 tested ever reached 8 (the most was 7), so the chance that any word scores this high is below 1 in 20,000. After every
other word combined there are 12 run-sums against 14.6 expected: no sign of a second total word or of unmarked totals.

**2. About three totals in four balance.** Of 37 totals (35 KU-RO, 2 PO-TO-KU-RO "grand total"), 15 are intact enough to
check. 11 balance exactly and 4 do not (73%; 95% interval 48–89%).

| Outcome | Totals | Tablets |
|---|---|---|
| Balances exactly | 11 | HT 9b, 11b, 25b, 88, 89, 94b, 104, 117a, 122b, 123+124a, 127b |
| Does not balance | 4 | HT 9a (stated total ¾ above the sum), HT 94a (1 below), HT 119 (1 above), HT 118 (5 below) |
| Balances as read, but the total itself is damaged | 1 | HT 85a |
| Too damaged to check | 21 | |

Three of the four misses are off by a single stroke or a single fraction group, the kind of slip a tally makes. The largest total that
balances is 292 (HT 127b), carried forward from an earlier subtotal of 156.

**3. Four fraction signs can be fixed by arithmetic alone; two tentative published values run into trouble.**

| Sign | Value | Tablet | Arithmetic |
|---|---|---|---|
| J | 1/2 | HT 104 | 45 J + 20 J + 29 = 95 balances only if J = 1/2 |
| J | 1/2 (cross-check) | PE 1 | 72 people get 36 grain; at that rate 26 J grain feeds exactly 53 people, matching a damaged "5x" |
| E | 1/4 | HT Zd 157+156 | 1, 1 J, 2 E, 3 E F is a progression where each term is 1.5 times the last |
| F | 1/8 | HT Zd 157+156 | same progression, third step |
| B | 1/5 | KH 7a | 10 people get J, 4 people get B, at the same ration |

The progression does not even need HT 104: among unit fractions from 1/2 to 1/120, J = 1/2 is the only value that makes it
come out with legal values for E and F. These match the values Corazza et al. (2021) adopt for J, E, F and propose for B.

Checking two published systems against all 25 fraction combinations written in the corpus (rules: a combination is written
largest sign first, and adds up to less than 1):

| System | Combinations it can value | Written smallest-first | Add up to 1 or more |
|---|---|---|---|
| Bennett 1950 | 12 of 25 | 1 (E J) | 3 (D D, D D D D, J J) |
| Corazza et al. 2021 | 22 of 25 | 3 (E J, H K, A B B) | 1 (J J) |

- **Corazza's system fits far better** and covers nearly everything. Bennett's D = 2/3 fails on D D, which is written 13 times.
- **Its two tentative signs are the ones that fail.** H = 1/16 and A = 1/24 (both marked "?" by the authors) each produce an
  ordering violation: H K on HT 34 needs H > K, and A B B on KH 86 needs A ≥ B. Each is a single instance.
- **A third hint points the same way.** As read, the oil total on HT 123+124a gives 8 E + 8 J E + 4 A + 4 E = 25 H, which
  requires H − A = 1/4. Both the A and the total are damaged, so this is weak, but it also says H is large, not small.
- E J (ZA 8) and J J (PH 9b) break the rules under any values; they are scribal oddities or misreadings.

## Values implied by totals for damaged entries

If the scribe's total was right (about three times in four), these follow. `results/kuro_audit.csv` has all of them.

| Tablet | Damaged or lost entry | Value the total implies | Plausible? |
|---|---|---|---|
| HT 100 | entry lost after *304+PA | 4 | Yes |
| HT 122b | read as 7 | 57 | Yes: five ten-strokes lost, units agree |
| HT 13 | read as 5 J, J uncertain | 5 | Yes: the total balances if the doubtful J is not there |
| HT 102 | read as 33 | 23 | Possible; or the 10 for WI was left out of the total |
| HT 27a, HT 11a, HT 39 | read as 50, 3, 10 | 63, 7, 82 | No: more is missing than one entry |

## What was checked

- **Numbers come from the glyphs.** Whole numbers and fraction signs are decoded from the Unicode numerals in the source, not
  from the site's English gloss layer, so no fraction values are assumed in parts 1 and 2 beyond J, E, F in the audit.
- **The blind test uses no readings.** It never looks at what a word is thought to mean, and the p-value is corrected for
  having tested 229 words.
- **Hand check.** I added up HT 9b, 11b, 85a, 89, 94a, 104, 117a, 119, 122 and 127b by hand from the transliteration; all agree
  with the script.
- **Exact arithmetic.** All fraction work uses rational numbers, not floating point.

## Weaknesses

- **Choice of summands.** Seven of the eleven balancing totals balance under the plainest rule (everything since the previous
  total). The other four need a structural rule: entries under a KI-RO heading (HT 88), one commodity (HT 123+124a), a
  carried-forward subtotal (HT 127b), a grand total across both sides (HT 122). The script tries each and keeps the best, which
  favours "balances". The sums involved (6, 93½, 292, 97) are specific enough that chance is not a serious worry, but the 73%
  is an upper-leaning estimate.
- **Fifteen checkable totals is a small sample,** all from one site (Haghia Triada), so the accuracy rate says little
  about Minoan scribes in general.
- **Nothing here is new to specialists in outline.** KU-RO as "total", J = 1/2 from HT 104 and the misses on HT 9a and HT 94a
  are in the literature. What this adds is the blind significance test, a complete machine-checked audit, and the observation
  that the two tentative Corazza values each conflict with an attested combination.
- **I depend on one transcription.** Readings follow lineara.xyz (after GORILA). A different reading of a damaged sign changes
  individual rows; 9 of 1,721 inscriptions were dropped because their sign and transliteration layers did not line up.
- **The fraction derivations assume the tablets mean what they appear to:** that HT Zd 157+156 is a deliberate progression and
  KH 7a a constant ration. Each rests on one tablet.
- **H and A remain open.** I show the tentative values conflict with three single observations; I do not propose replacements.

## Files

| Path | What |
|---|---|
| `src/fetch_data.py` | Downloads the source file at a pinned commit into `data/raw/` (git-ignored) |
| `src/corpus.py` | Parses it as text into `data/tokens.csv` |
| `src/ledger.py` | Quantities with their labels, per inscription |
| `src/blind_totals.py` | Part 1: blind search for a total word, permutation test |
| `src/audit.py` | Part 2: every total, checked |
| `src/fraction_signs.py` | Part 3: derivations and the test of published systems |
| `results/` | `blind_total_words.csv`, `kuro_audit.csv`, `fraction_derivations.csv`, `fraction_systems.csv` and supporting tables |

Reproduce: `pip install -r requirements.txt`, then from `src/` run `fetch_data.py`, `corpus.py`, `blind_totals.py`, `audit.py`,
`fraction_signs.py` (under a minute).

## Sources

- [lineara.xyz](https://github.com/mwenge/lineara.xyz) inscription data, commit `9c81beb` (transcriptions after GORILA)
- [Corazza, Ferrara, Montecchi, Tamburini & Valério (2021), "The mathematical values of fraction signs in the Linear A script", Journal of Archaeological Science 125](https://cris.unibo.it/retrieve/e1dcb336-9b0e-7715-e053-1705fe0a6cc9/Montecchi_JAS_125_2021.pdf), including Bennett's 1950 values as tabulated there
