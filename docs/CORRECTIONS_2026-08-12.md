# ⚠ CORRECTIONS LEDGER

- **Round 1 — 2026-08-12, number fidelity.** Seventeen wrong numbers in the prose layer.
- **Round 2 — 2026-08-13, instrument.** Fifteen further defects across the verification, figure and
  voice layers, including an eighteenth wrong number. Ten were inside the three instruments that
  were supposed to catch round 1; each had reported a clean pass over a scope narrower than the one
  it implied. Final section.

The filename keeps its 2026-08-12 date because six files link to it.

---

## Round 1 — 2026-08-12 number-fidelity audit

**Read this before trusting any number quoted in a `docs/findings_*.md` prose file.**

A fidelity audit traced 132 quantitative claims in the manuscript to their source JSONs. **115
matched; 17 did not.** The diagnosis matters more than the count: the errors did not originate in
the analysis. Every frozen JSON under `results/` was correct. The errors were introduced in the
**prose layer** — I wrote the findings docs, rounded or generalized while writing, and then the
manuscript quoted the findings docs instead of re-reading the JSONs. The findings docs were the
contamination vector.

**Standing rule from this point:** any number entering prose is read from `results/*.json` at the
time of writing, never copied from another prose file. Where a prose file and a JSON disagree,
**the JSON wins and the prose is wrong.**

Every item below has been corrected in place in every affected file. This ledger exists so the
corrections are auditable and so no future reader — human or agent — picks up a superseded number
from a diff, a cached copy, or a commit message written before the audit.

## The seventeen

| # | claim as written | true value | where it appeared |
|---|---|---|---|
| 1–2 | degeneracy twin "for all ten, miss exactly 1.000 and false-block exactly 0.000" | **8 of 10 exactly**; mpnet 0.9985 / 0.0007; MiniLM has no within-window bin ≥256 and is not evaluable | findings_e2, draft abstract + §6, Wave-1 emails |
| 3 | "sixteen pre-registered bars, six failed outright" | **21 bars, 12 failed outright** (+1 certification-clause failure, +1 unresolved, +2 vacuity-qualified passes) — see `bar_ledger.md` | draft abstract + §2 + §8, Wave-1 pack |
| 4 | Editorial token-Jaccard median **0.912** | **0.913** (0.912 is the two-source cross-check figure, not the primary) | draft §3.1, Wave-1 email 1 |
| 5 | deployment "8–16× beyond" the last usable length | **6.3–8.0×** — the last L at which any config holds AUROC 0.55 is **128**, not 64 | findings_e2, draft abstract + §6 |
| 6 | H3a "deltas cluster at −0.008 … inside noise" | deltas span **−0.0140 to +0.0150**, median −0.0031, 6 negative / 3 positive / 1 zero, and **6 of 10 CIs exclude zero** — there *is* a position effect, it is just not the predicted one and does not reach the 0.05 bar | findings_e2, draft §6 |
| 7 | operative windows "the rest 510" | **512** (510 is the tokenizer figure that `e2_tokenizer_tables.json` explicitly marks non-operative) | findings_e2, draft §6 |
| 8 | scope breach "θ_max ≈ 99.8°" | 99.796° is **MiniLM on CondaQA only**; the maximum over breaching cells is **106.321°** (mpnet on E3), and **six cells** breach, not the two configurations the prose implied | findings_e4, draft §7 |
| 9 | E3 elicited "naive 0.64–0.93 / caliper 0.59–0.90" | naive max **0.9249**, caliper max **0.9054**; 0.93 was the *stratified* max — a different statistic than the column heading | draft §4, Wave-1 email 4 |
| 10 | H4 "evaluated on 2,019 requirement-strength transitions" | 2,019 is the **positive class**; the evaluation set is **13,780 pairs** (2,019 positive + 11,761 negative) | draft §3.2, §10 |
| 11 | scorecard "E2 H4 — pass" | **PASS_EXCLUDING_NONEVALUABLE** (MiniLM not evaluable) | draft §8 |
| 12 | scorecard "E4 B3 — scope finding" | JSON verdict is **`FAIL (instrument-error investigation per prereg §3)`** with **6 violating cells**; "scope finding" is the *interpretation*, not the verdict | draft §8, findings_e4 |
| 13 | scorecard "E1 H5 — floor-effect magnitude, reported" | `pass: false` — a **FAIL** (g1 0.5733 → g3 0.5546, drop 0.0187 vs the ≥0.10 bar), and it was excluded from the failure count | draft §8 |
| 14 | H6 "69 of 101" | correct, but the **registered denominator was 140** and the rescoring to `ceil(0.9 × evaluable)` is an undisclosed amendment | draft §6, §8 |
| 15 | parity seam "4×10⁻⁴" | **gte 3.626×10⁻⁴, mxbai 4.474×10⁻⁴**; both JSON verdicts read FAIL / "GPU shard NOT admissible", which the prose softened | draft §6 |
| 16 | "reproduced across two GPU architectures" | **true, but was unsourced** — the probe went to `/tmp` and was never frozen. Re-run and frozen 2026-08-12: `results/verification/e4_cross_arch_theta.json`, max delta **0.000°** across all six cells | findings_e4, prereg-e4 A2 |
| 17 | "all nine encoder **architectures** improved" | nine **configurations** over **seven checkpoints** (e5 ×2 and nomic ×2 share weights) | draft abstract |

## Three structural cautions the audit raised (not number errors; each changes a claim)

- **The two nomic-clustering configurations share a config hash and produce byte-identical AUROCs
  at every bin.** "Ten configurations" therefore contains one configuration counted twice. Any
  claim quantified over "all ten" must say so.
- **mxbai carries §6's headline numbers (0.605, L\*=129.6) and is one of the two parity-gate
  FAILs.** Admissible under amendment A1's declared fresh numerics, but the seam must be disclosed
  at the point of use, not only in a methods paragraph.
- **The §6 decay table printed L≥512 cells for seven configurations whose within-window flag is
  false**, unmarked, thirty lines before the vacuity is admitted — and silently omitted gte-base
  and e5-[no prefix]. Any reprint must mark truncated cells and include all ten rows.

## Status

Corrected in place: `docs/findings_e2_2026-08-12.md`, `docs/findings_e4_2026-08-11.md`,
`docs/paper_b_draft_2026-08-12.md`, `PREREGISTRATION_E4.md` (as amendment A3, append-only),
`Falsifyer/docs/outreach/paper_b_wave1_results.md`. Superseded numbers survive only in git history
and in commit messages written before the audit; this ledger is the map to them.

---

## Round 2 — 2026-08-13 instrument audit

Round 1 fixed the numbers and trusted the instruments that found them. This round audited the
instruments. Four of the seven defects were inside `scripts/recompute_headline_numbers.py` and
`harness/figures/make_figures.py`, which means the harness certifying "38 of 38 PASS" was
certifying less than it claimed, and the figure module's promise that a figure cannot disagree
with a JSON was true while the figures still misrepresented them.

The manuscript is now at **45 of 45**, and every new check was tested by corrupting its input and
confirming the check fails before it was accepted. Items 1–3 are the manuscript and the recompute
harness; 4–6 are the figure layer; 7 collects three further harness weaknesses and one number that
had already propagated into an unsent email.

### 1. A check whose name contradicted its assertion — and passed

`recompute_headline_numbers.py` carried:

    check("deployed-default multiple = 6.3x to 8.0x",
          [round(800 / last55, 1), round(1024 / last55, 1)], [6.2, 8.0], tol=0.15)

The name said 6.3, the assertion said 6.2, and it passed. 800/128 = **6.25** exactly, and Python's
`round()` is round-half-to-even, so it returns 6.2 where a reader expects 6.3. `tol=0.15` could not
have separated the two values in any case, so the check could not fail on the quantity it names.

**The provenance is the finding, and it is worse than a mislabel.** Round 1 item 5 above had
already determined the correct figure and written it down: *"deployment 8–16× beyond → **6.3–8.0×**,
the last L at which any config holds AUROC 0.55 is 128."* The check's name is that correct round-1
value. The manuscript, meanwhile, printed 6.2. So when the check was written, the expectation was
set to **match the wrong prose rather than the finding the check was named after** — the one thing
a verification harness must never do. A round-1 correction was silently un-applied by the very
instrument built to enforce round 1.

This is the **third species of lying check** found in this file, after the block that guessed a
JSON path and silently skipped, and the placeholder that asserted a verdict string was one of two
values. All three passed while verifying nothing.

- **Corrected in the manuscript:** abstract and §5 now print **6.3 to 8.0 times**, with the three
  framework defaults attributed individually (LangChain ~800 → 6.3×, kernel-memory 1000 → 7.8×,
  LlamaIndex 1024 → exactly 8×) so the range no longer hides which default sits where.
- **Corrected in the harness:** a `half_up()` helper now rounds the way a reader assumes; the exact
  ratios and the printed figure are asserted separately, at `tol=1e-9`.

### 2. The §5 AUROC table printed 7 of 10 configurations

Round 1 recorded this defect and its remedy — *"silently omitted gte-base and e5-[no prefix]. Any
reprint must mark truncated cells and include all ten rows"* — and the remedy was never applied to
the manuscript. The three omitted rows were gte-base, e5-base-v2 [no prefix], and the duplicate
nomic clustering checkpoint. A silent 7-of-10 selection, in a paper whose §6 is about corpora
selected to flatter the gate.

Only two of that table's sixty numbers were ever verified (mxbai at L=64 and L=512), so 58 cells
and three whole rows were unchecked. **All ten rows now print**, including both nomic entries that
share a checkpoint, so the reader sees the duplication at the table rather than reading about it in
§10. The harness now parses the table out of the manuscript and verifies the row count, the row
labels and their order, and every cell.

### 3. Truncated cells were printed unmarked as points on a length curve

The other half of round 1's requirement, and the more serious half. Seven of the ten configurations
exceed their operative window from 512 tokens up; all-MiniLM-L6-v2 exceeds it from 256. **At 1024
and 4096 those seven are 100% truncated** — the cell re-scores one window-full of text and cannot
express a length effect at all. The table printed those numbers unmarked, thirty lines before the
vacuity was admitted in prose.

Every out-of-window cell now carries **†**, with the reading stated directly beneath the table
rather than at the end of the section. The harness asserts that a dagger appears on a cell **if and
only if** `within_window_bin` is false in the frozen result; the check was verified to fail both on
a missing dagger and on a spurious one.

### 4. Figure 1 was the withdrawn claim, drawn, and cited by nothing

`fig1_coupling_signflip.svg` was titled **"The coupling changes sign across text sources"** — the
claim §8 retires — and subtitled "…and it reverses." Its authored-corpus row was two hardcoded
literals (0.72 / 0.06) transcribed from prose, in direct violation of the figure module's own
stated rule that every number is read from `results/**` at render time. The manuscript cites
Figures 2, 3 and 4 and never Figure 1, so it was an orphan plate asserting a retired claim,
regenerated on every run and sitting in the artifact directory for any reader to find.

Replaced by `fig1_no_source_inverted.svg`, which plots the refutation test that actually survives:
the three sources' coupling gaps with 95% intervals against a marked zero, the authored interval
visibly spanning both directions, and the common-support recomputation beneath. Every value reads
from `crosssource_coupling.json` and `crosssource_truncation_check.json` at render time. §8 had no
figure before this.

### 5. Figure 2 drew truncated cells as a decay curve

The same defect as item 3, one layer over. `make_figures.py` read `pooled.auroc` with no window
test and drew one solid line through every cell, so the seven truncating configurations appeared
to decay smoothly across the plotted "deployed chunk defaults" band — the region where they are
100% truncated and measuring nothing about length. The module's docstring claim, that a figure
disagreeing with a JSON is impossible, was true and beside the point: the figure agreed with the
JSON and still misrepresented it.

Out-of-window runs now render dashed with hollow markers, the boundary is where the style changes,
and a legend states what the dashed segment means. The loop asserts `within_window_bin` is present
rather than defaulting it.

### 6. No figure checked that its text fit on the plate

Added `_bounds_check()`, asserting at render time that every `<text>` stays inside the canvas. It
found two overflows immediately, one of them pre-existing and unrelated to this round: fig3's
subtitle ran 68px past its edge, and fig4's longest scorecard detail ran **158px** off a 700px
plate — a reader of the integrity figure could not read the integrity detail. `svg()` now wraps
subtitles to the plate and shifts the body to match; fig4 widened to 880px.

### 7. Three more harness weaknesses, and one propagation

- **`last55` had no within-window filter.** It ranged over cells the paper now calls inadmissible
  as length measurements, and returned 128 only because no truncated cell happens to reach 0.55 —
  correct by luck, with the 6.3–8.0× headline resting on it. Filtered now, and a paired check
  asserts the filtered and unfiltered answers agree, so a future result where a truncated cell
  crosses 0.55 cannot move the headline silently.
- **The degeneracy check used `.get()` with no default**, so a config missing either key compared
  `None == 1.0`, dropped out of the count, and said nothing. The silent-skip species again. Keys
  are required now.
- **The table regex raised instead of failing.** `.group(0)` on a failed search would kill all 44
  other checks with a traceback the moment the manuscript's header row is edited by hand — which
  is about to happen. It reports a named FAIL now.
- **Propagation into an unsent email.** Wave 1's CondaQA letter read *"0.605 at 64 tokens and 0.512
  at 512"* directly after asserting that length is the only quantity that varies. mxbai's 512 cell
  is truncated, so length was not the only thing varying. Corrected to the last untruncated
  comparison (0.605 at 64, 0.532 at 256) with the ceiling stated.

### 8. The voice linter was scanning 16 surfaces and there were 24

The same defect as items 2 and 6, in the third instrument: a checker whose coverage nobody
checked. `check_voice.py` reported "0 BANNED, 0 FICTIONALISING" across its file list while eight
further surfaces a reader reaches just as easily were never opened. All eight were dirty —
**16 hits**, including `load-bearing` and `hand-waving` inside this ledger, `assessed honestly` in
the scope freeze, and three in the outreach checklist.

The list is now 25 files, and the exclusions are written down as reasons rather than left as
absences: the superseded draft, the pre-registrations above their tag lines, and the frozen
results are the record, and editing them to read better would corrupt what they exist to preserve.

**The pattern across items 1, 2, 6 and 8 is one pattern.** Each instrument reported a clean pass
over a scope narrower than the one it implied — a check that could not fail, a table whose cells
were unread, figures whose text was unmeasured, a linter whose file list was unaudited. A green
result is a claim about coverage, and coverage was the thing none of them verified.

### 9. The manuscript's front matter misstated its own checker

The banner in the first four lines read *"`scripts/recompute_headline_numbers.py`, 38 of 38
PASS"* while the harness reported 45. A paper that gets the count of its own number-checker wrong,
in the first sentence a reader sees, is this round's defect in its purest form. Nothing tied the
two, so the banner could drift on every check added.

The harness now reads the banner out of the manuscript and asserts it against its own live total.
The check caught a discrepancy on its first run — the act of adding it moved the total from 45 to
47 — and the banner now reads 47 of 47.

### 10. Figure 1 was cited by nothing, and the numbering did not match citation order

Item 4 replaced Figure 1's content and left its structural defect standing. The manuscript cited
Figure 3 in §4, Figure 2 in §5, Figure 4 in §9, and Figure 1 nowhere. Renumbered to citation
order: the word-counting baseline is Figure 1, dilution stays Figure 2, the refutation plate is
Figure 3 and is now cited in §8, and the scorecard stays Figure 4. The harness asserts each figure
exists, that no stray figure sits in the directory, and that the manuscript cites each exactly
once in ascending order.

Every cell of one table was verified while the figures' citations were verified by nobody. That is
item 8's pattern for the third time.

### 11. Two more instrument weaknesses, found by adding the checks above

- **`check()` raised on lists of strings.** It applied `abs(a - b)` unconditionally, so a whole
  class of legitimate check would crash the run instead of reporting. Numeric pairs compare within
  tolerance; everything else compares for equality.
- **`_bounds_check` is blind to column collision.** It sees the plate edges, so two elements can
  both sit inside the canvas and print on top of each other. The scorecard's verdict column is now
  asserted against its gap. No verdict currently overruns — the longest is 52.5px in an 86px gap —
  so this one is a guard rather than a repair.

**The carve scenario is now safe.** With the manuscript's table header renamed by hand, the
harness reports three named failures and still runs its other 43 checks, where before it would
have died on an `AttributeError` and reported nothing at all.

### 12. The bar ledger's summary disagreed with its own rows, and two checks blessed it

The scorecard's counts came from three sources that did not agree:

| source | FAIL | QUALIFIED | PASS | UNRESOLVED |
|---|---|---|---|---|
| the 21 individual rows in `bar_ledger.json` | **13** | 4 | **3** | 1 |
| the `counts` block in the same file | 12 | 4 | 4 | 1 |
| the summary in `bar_ledger.md` | 12 | 4 | "5" | 1 |

The markdown summary listed *"5 clean passes (rows 9, 11, 12, 15, and row 2's range clause)"*,
counting row 2 both as the boundary failure and as a clean pass, so its decomposition summed to
**22**. The JSON's `counts` block was a hybrid: it carried the markdown's stale FAIL count and
inflated PASS to 4 so the total would reach 21.

**The rows were right the whole time**, because they already carried two round-1 rulings that never
reached any summary: item 12 ruled that **E4-B3's verdict is FAIL** and the scope finding is its
interpretation (`findings_e4`: "the verdict remains FAIL and is reported as FAIL"), and item 11
ruled that **E2-H4 is a pass qualified by non-evaluability**, not a clean pass.

So the abstract and §9 were wrong on three terms — thirteen failed outright rather than twelve,
three passed by exclusion rather than two, three passed cleanly rather than five. Round 1 corrected
this sentence once already, from "sixteen bars, six failed" to "21 bars, twelve failed". Twelve was
still wrong.

Two checks passed it. `bar counts sum to the total` computed 12+4+4+1 = 21 and was satisfied,
exactly as 13+4+3+1 = 21 would have satisfied it; `21 bars, 12 failed outright` read `counts["FAIL"]`.
Both compared the summary against itself and never counted a row. The harness now tallies the rows,
asserts the stored block against that tally, and parses the abstract's spelled-out decomposition
and holds it to the same numbers.

### 13. Three result files had never been read by any check

`e1_h4_transfer.json`, `e3_analysis.json` and `e3_coupling_stats.json` were opened by nothing,
while this script's header claimed it regenerates every headline number of the paper. That left
**the whole of §6's validity ladder** and **§4's transfer paragraph** unverified.

Fifteen checks were added over those files. One failed on the run that introduced it: §6's table
printed **"0.61 to 0.68" in both PAWS columns**, but the Jaccard-caliper minimum is 0.6045, which
rounds to **0.60** — the caliper column was carrying the naive column's lower bound. That is the
eighteenth wrong number in the manuscript, and it survived round 1's full 132-claim audit because
the file holding its true value was one nobody opened.

### 14. §9 was three lines of counts, and now carries the ledger's actual finding

The scorecard section stated five numbers and outsourced its evidence to a figure. It now reports
what the ledger shows rather than only how it tallies: no bar asserting that the phenomenon occurs
failed, and all thirteen outright failures were claims about magnitude or mechanism. **Five of the
thirteen failed because the gate performed better than we had registered** — E1-H1, E1-H4, E3-HE3-1,
E3-HE3-3 and E3-HE3-4 — each printed with its registered bar beside its measured value. An
investigator steering toward a negative result does not miss in that direction five times in
thirteen. The remaining eight each killed a mechanism this study proposed rather than one it
inherited.

Every figure in that table is now recomputed, and the five cited bar ids are asserted to be FAIL
rows in the ledger.

**Not included, and stated so it is a choice rather than an omission:** a count of pre-registration
amendments. Two reasonable parsings of the four amendment ledgers return 11 and 16, because E3 and
E4 format their entries differently from E1 and E2. The number is not published until one parsing
is defensible.

### 15. "Register" is defined where §7 first uses it

The frozen E4 term was used three times with no definition, so a reader applies the linguistics
sense. It is not renamed — it is the term of `PREREGISTRATION_E4.md` §2 and renaming it would break
the tie to the freeze — it is defined on first use as the three frozen bodies of text the survey
sweeps while the encoder varies: the errata g2 texts, the CondaQA passages, and the E3 brand-name
sentences.

### Status

Corrected in place: `docs/paper_b_draft_v1.md`, `docs/paper_b_draft_2026-08-12.md` (superseded
banner), `scripts/recompute_headline_numbers.py`, `harness/figures/make_figures.py`,
`Falsifyer/docs/outreach/paper_b_wave1_results.md`. Figure `fig1_coupling_signflip.svg` deleted and
replaced by `fig1_no_source_inverted.svg`. No frozen result under `results/` was touched and no
verdict changed: every defect was in the presentation and verification layers. Recompute: **64 of
64 PASS**; voice **0 BANNED, 0 FICTIONALISING**; all four figures bounds-clean.

### The standing rule this round adds

Round 1's rule governs numbers: any number entering prose is read from `results/*.json` at the time
of writing. Round 2 adds the rule that governs checks:

> **A check is not evidence until it has been observed to fail.** Every check added to
> `recompute_headline_numbers.py` must be demonstrated against a deliberately corrupted input
> before it counts toward the PASS total. Three checks in this file passed for weeks while
> verifying nothing, and each was found by reading the check rather than by running it.
