"""Recompute every headline number of Paper B from the frozen artifacts. One command, offline.

The standard this enforces: no number appears in the manuscript, the abstract, a figure, or an
email unless this script regenerates it from `results/**` and it matches. A FAIL here is not a
formatting problem. It means a claim in the paper is not supported by the frozen evidence, and
the claim comes out.

Paper A shipped with the same instrument (`recompute_headline_counts.py`, 12/12 ALL PASS). This
is its Paper B counterpart, and it is deliberately stricter: it checks ranges by recomputing the
min and max rather than by trusting a stated interval, because three of this paper's stated
ranges were found wrong by an external audit on 2026-08-12.

Run: python scripts/recompute_headline_numbers.py
"""
import json, re, statistics, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


def half_up(x, nd=1):
    """Round the way a reader assumes. Python's round() is round-half-to-even, which turned
    800/128 = 6.25 into 6.2 and put a wrong figure in the abstract for a day."""
    return float(Decimal(repr(x)).quantize(Decimal("1." + "0" * nd), rounding=ROUND_HALF_UP))


ROOT = Path(__file__).resolve().parent.parent
R, V = ROOT / "results", ROOT / "results" / "verification"
j = lambda p: json.loads((R / p).read_text(encoding="utf-8"))

checks, fails = [], 0


def check(claim, got, want, tol=0.0005):
    global fails
    if isinstance(want, (list, tuple)) and isinstance(got, (list, tuple)):
        # NOTE 2026-08-13: this formerly did abs(a - b) unconditionally and raised TypeError on a
        # list of strings, so a whole class of legitimate check would crash the run rather than
        # report. Numeric pairs compare within tol; everything else compares for equality.
        ok = len(got) == len(want) and all(
            abs(a - b) <= tol if isinstance(a, (int, float)) and isinstance(b, (int, float))
            else a == b
            for a, b in zip(got, want))
    elif isinstance(want, (int, float)) and isinstance(got, (int, float)):
        ok = abs(got - want) <= tol
    else:
        ok = got == want
    checks.append((ok, claim, got, want))
    if not ok:
        fails += 1


# ── E1: the institutional audit ───────────────────────────────────────────────────────────
e1 = j("e1_analysis.json")
# NOTE: this block formerly guessed a JSON path, found nothing, and SILENTLY SKIPPED, so the
# harness reported a pass count that included a check it never ran. A harness that can skip is
# worse than none. The path is asserted before use, here and everywhere below.
g2 = {k: v["granularities"]["g2"] for k, v in e1["configs"].items()}
assert len(g2) == 9, f"expected 9 configurations in e1_analysis.json, found {len(g2)}"
strat = [c["auroc_stratified"] for c in g2.values()]
check("E1 stratified AUROC at g2 spans [0.5024, 0.5237]",
      [round(min(strat), 4), round(max(strat), 4)], [0.5024, 0.5237])
appr = [c["operating_points"]["0.8"]["technical_above_threshold"] for c in g2.values()]
check("Verified-Technical approval at the 0.80 operating point spans 89-98%",
      [round(min(appr) * 100), round(max(appr) * 100)], [89, 98])

aud = json.loads((V / "errata_audit_final.json").read_text(encoding="utf-8"))
check("errata audit kappa(A,B) = 0.6813", aud["kappa_AB"], 0.6813)
check("Technical construct precision = 95.2%",
      round(aud["construct_vs_institution"]["technical_confirmed_changing"]["rate"] * 100, 1), 95.2)
check("Editorial construct leak = 66.0%",
      round(aud["construct_vs_institution"]["editorial_adjudicated_changing_LEAK"]["rate"] * 100, 1), 66.0)
check("institution-label AUROC ceiling = 0.646",
      round(aud["auroc_machinery"]["max_observable_auroc_ceiling"], 3), 0.646)

pp = json.loads((V / "promoted_primary_auroc.json").read_text(encoding="utf-8"))
g1 = [v["g1"]["auroc"] for v in pp["configs"].values()]
check("promoted-primary g1 AUROC range = [0.714, 0.804]", [round(min(g1), 3), round(max(g1), 3)], [0.714, 0.804])
check("token-Jaccard baseline g1 = 0.772", round(pp["jaccard_baseline_g1"]["auroc"], 3), 0.772)
prod = [v["g1"]["auroc"] for k, v in pp["configs"].items() if "PRODUCTION" in k][0]
check("production path sits BELOW the Jaccard baseline",
      prod < pp["jaccard_baseline_g1"]["auroc"], True)

rw = json.loads((V / "promoted_primary_auroc_reweighted.json").read_text(encoding="utf-8"))
rg = [v["g1"] for v in rw["configs"].values()]
check("reweighted g1 range = [0.669, 0.761]", [round(min(rg), 3), round(max(rg), 3)], [0.669, 0.761])
check("reweighted Jaccard baseline = 0.730", round(rw["jaccard_baseline_g1"], 3), 0.730)

bis = json.loads((V / "bis_true_label_coupling.json").read_text(encoding="utf-8"))
check("bis audit kappa = 0.6622", bis["checksums"]["kappa_AB"], 0.6622)
check("bis label precision = 84/99", bis["checksums"]["precision_transitions"], "84/99")
check("bis negative-class leak = 37/100", bis["checksums"]["leak_rewordings"], "37/100")
check("bis true-label orientation aligned", bis["orientation"], "aligned")

h3 = json.loads((V / "h3_five_class_refinement.json").read_text(encoding="utf-8"))
check("H3 five-class hits = 0/9", h3["h3_style_hits_five_class"], "0/9")
check("H3 three-class hits = 0/9", h3["h3_style_hits_three_class_recomputed"], "0/9")
p_ = h3["regex_precision_vs_semantic"]
check("regex number precision = 48.0%",
      round(p_["regex_number_confirmed"] / p_["regex_number_n"] * 100, 1), 48.0)
check("polarity class n = 36", h3["class_sizes_five"]["polarity-negation"], 36)

# ── E2: the dilution result ───────────────────────────────────────────────────────────────
e2 = j("e2_analysis.json")
ls = {k: v["full_set"]["0.75"]["lstar"] for k, v in e2["lstar"].items()}
check("L*(0.75) is left-censored for ALL ten configurations",
      all(x == "<=64" for x in ls.values()) and len(ls) == 10, True)
gt = e2["descriptives"]["gate_term_critical_length"]["per_config"]
check("gate-term critical length = 64 for every configuration",
      set(gt.values()) == {64} and len(gt) == 10, True)
dt = e2["descriptives"]["degeneracy_twin"]["per_config"]
# NOTE 2026-08-13: this formerly used v.get(...) with no default, so a config missing either key
# compared None == 1.0, dropped out of `exact` silently, and shifted the count with nothing said.
# That is the silent-skip species again. The keys are now required.
assert len(dt) == 10, f"degeneracy_twin covers {len(dt)} configs, expected 10"
for _k, _v in dt.items():
    assert "min_miss" in _v and "max_false_block" in _v, f"{_k}: degeneracy keys missing"
exact = [k for k, v in dt.items() if v["min_miss"] == 1.0 and v["max_false_block"] == 0.0]
check("degeneracy exact (miss 1.000 / false-block 0.000) in 8 of 10", len(exact), 8)
cells = e2["cells"]
mx = [k for k in cells if "mxbai" in k][0]
sp = cells[mx]["splice"]["enwiki"]
check("mxbai at L=64 = 0.605", round(sp["L=64"]["pooled"]["auroc"], 3), 0.605)
check("mxbai at L=512 = 0.512", round(sp["L=512"]["pooled"]["auroc"], 3), 0.512)
# NOTE 2026-08-13: this formerly had no within-window filter, so it ranged over cells the
# manuscript now declares inadmissible as length measurements. It returned 128 only because no
# truncated cell happens to reach 0.55 - correct by luck, and the 6.3-8.0x headline rests on it.
# The filter makes the number earned, and the paired check below asserts the two agree, so a
# future result where a truncated cell crosses 0.55 cannot silently move the headline.
def _cell(k, L):
    return cells[k]["splice"]["enwiki"].get(f"L={L}", {})

BINS = (64, 96, 128, 256, 512, 1024, 2048, 4096)
last55 = max(L for L in BINS for k in cells
             if isinstance(_cell(k, L).get("pooled"), dict)
             and _cell(k, L)["within_window_bin"]
             and _cell(k, L)["pooled"]["auroc"] >= 0.55)
last55_unfiltered = max(L for L in BINS for k in cells
                        if isinstance(_cell(k, L).get("pooled"), dict)
                        and _cell(k, L)["pooled"]["auroc"] >= 0.55)
check("no truncated cell reaches AUROC 0.55, so the window filter does not move the answer",
      last55_unfiltered, last55)
check("last L at which any configuration holds AUROC 0.55 = 128", last55, 128)
# NOTE 2026-08-13: this check formerly read
#     check("deployed-default multiple = 6.3x to 8.0x",
#           [round(800 / last55, 1), round(1024 / last55, 1)], [6.2, 8.0], tol=0.15)
# Its NAME said 6.3 and its ASSERTION said 6.2, and it passed anyway: 800/128 = 6.25 exactly,
# and Python's round() is round-half-to-even, so it returns 6.2. tol=0.15 could not have
# separated 6.2 from 6.3 in any case, so the check could not fail on the thing it names. Third
# species of lying check found in this file, after the silent skip and the un-failable string
# compare. The manuscript printed 6.2. Both are fixed: assert the exact ratios, and separately
# assert the printed figure under half-up rounding, the convention a reader applies.
check("deployed-default multiples, exact = 6.25 / 7.8125 / 8.0",
      [n / last55 for n in (800, 1000, 1024)], [6.25, 7.8125, 8.0], tol=1e-9)
check("printed range in the abstract and section 5 = 6.3x to 8.0x",
      [half_up(800 / last55), half_up(1024 / last55)], [6.3, 8.0], tol=1e-9)

# ── The section 5 table: every printed cell, not two of sixty ─────────────────────────────
# NOTE 2026-08-13: the manuscript table printed 7 of the 10 frozen configurations and disclosed
# that nowhere, in a paper whose section 6 is about corpora selected to flatter the gate. Only
# mxbai's L=64 and L=512 were ever checked, so 58 of its 60 numbers were unverified and three
# whole rows were missing without anything noticing. This now reads the table out of the
# manuscript and verifies the row count, the row labels, and every cell.
TABLE_ROWS = [
    ("mxbai-embed-large-v1",                lambda k: "mxbai" in k),
    ("e5-base-v2 [query:]",                 lambda k: "e5-base-v2" in k and "query:" in k),
    ("bge-base-en-v1.5",                    lambda k: "bge-base" in k),
    ("nomic clustering, long-context 8192", lambda k: "LONG-CONTEXT" in k),
    ("nomic clustering (same checkpoint)",  lambda k: "clustering:" in k and "LONG-CONTEXT" not in k),
    ("e5-base-v2 [no prefix]",              lambda k: "e5-base-v2" in k and "NO prefix" in k),
    ("all-mpnet-base-v2",                   lambda k: "mpnet" in k),
    ("gte-base",                            lambda k: "gte-base" in k),
    ("nomic-MRL-256, production",           lambda k: "MRL-256" in k),
    ("all-MiniLM-L6-v2",                    lambda k: "MiniLM" in k),
]
COLS = (64, 128, 256, 512, 1024, 4096)
# NOTE 2026-08-26: the manuscript target moved to v3, the live draft; v2 is the superseded record.
_v3 = ROOT / "docs" / "paper_b_draft_v3.md"
md = _v3.read_text(encoding="utf-8") if _v3.exists() else (ROOT / "docs" / "paper_b_draft_v2.md").read_text(encoding="utf-8")
# NOTE 2026-08-13: .group(0) on a failed search raises AttributeError and kills every remaining
# check with a traceback instead of reporting one FAIL. The manuscript is about to be edited by
# hand, so a reflowed or renamed header must degrade to a named failure. If a benign rename
# breaks this, the fix is to update TABLE_ROWS - never to loosen the match.
# NOTE 2026-08-26: editors reflow tables with column padding; padding is formatting, not content,
# so the header match tolerates whitespace. Labels, cells, and daggers are still compared exactly.
_m = re.search(r"\| configuration\s+\| 64\s+\|.*?\n\n", md, re.S)
check("section 5 table found in the manuscript (header row intact)", _m is not None, True)
tbl = _m.group(0) if _m else ""
rows = [ln for ln in tbl.splitlines() if ln.startswith("|") and "---" not in ln][1:]
check("section 5 table prints all 10 frozen configurations", len(rows), 10)
check("section 5 table row labels match the frozen set, in order",
      [r.split("|")[1].strip() for r in rows] == [lbl for lbl, _ in TABLE_ROWS], True)
mismatched, mismarked = [], []
for (lbl, matches), row in zip(TABLE_ROWS, rows):
    keys = [k for k in cells if matches(k)]
    raw = [x.strip() for x in row.split("|")[2:8]]
    printed = [float(x.rstrip("†")) for x in raw]
    marked = [x.endswith("†") for x in raw]
    if len(keys) != 1:
        mismatched.append((lbl, "matched %d frozen keys" % len(keys)))
        continue
    sp = cells[keys[0]]["splice"]["enwiki"]
    frozen = [round(sp[f"L={L}"]["pooled"]["auroc"], 3) for L in COLS]
    truncated = [not sp[f"L={L}"]["within_window_bin"] for L in COLS]
    if any(abs(p - f) > 1e-9 for p, f in zip(printed, frozen)):
        mismatched.append((lbl, printed, frozen))
    if marked != truncated:
        mismarked.append((lbl, "marked=%s frozen=%s" % (marked, truncated)))
check("section 5 table: all 60 printed cells match the frozen AUROCs", mismatched, [])
# The 2026-08-12 ledger required that any reprint of this table "mark truncated cells and include
# all ten rows". The ten rows went in and the marks did not, so this check now enforces the
# second half: a dagger appears on a cell if and only if within_window_bin is false in the frozen
# result. Seven configurations are 100% truncated at 1024 and 4096, where the cell re-scores one
# window-full of text and cannot express a length effect.
check("section 5 table: truncation daggers match within_window_bin exactly", mismarked, [])
# NOTE: this was formerly a placeholder that asserted a verdict string was one of two values,
# i.e. a check that could not fail. It now counts cells in the tracked gzipped node shards,
# which are the irreplaceable sweep output.
import gzip
n_cells, shards = 0, sorted(R.glob("*/e2_shard_*.json.gz"))
assert len(shards) == 4, f"expected 4 node shards, found {len(shards)}"
for sh in shards:
    with gzip.open(sh, "rt", encoding="utf-8") as fh:
        n_cells += len(json.load(fh)["cells"])
check("E2 scored-pair count = 2,184,150", n_cells, 2184150)
pg = json.loads((V / "e2_parity_gates.json").read_text(encoding="utf-8"))
passed = [k for k, v in pg["configs"].items() if v["verdict"] == "PASS"]
check("parity gate: 8 of 10 configurations match the pinned path", len(passed), 8)

# ── E4 and the cross-source test ──────────────────────────────────────────────────────────
e4 = j("e4_floor_survey.json")
check("E4 B1 hits = 1 of 9", e4["scorecard"]["B1"]["hits"], 1)
check("E4 B2 hits = 0 of 9", e4["scorecard"]["B2"]["hits"], 0)
xa = json.loads((V / "e4_cross_arch_theta.json").read_text(encoding="utf-8"))
check("cross-architecture theta reproduces to 0.000 deg", xa["max_abs_delta_deg"], 0.0)
check("true max theta = 106.321 deg", xa["true_theta_max_across_all_cells_deg"], 106.321)

cs = json.loads((V / "crosssource_coupling.json").read_text(encoding="utf-8"))
check("cross-source kappa = 0.6842", cs["kappa_AB_overall"], 0.6842)
check("no source came back inverted",
      not any(v["orientation"] == "inverted" for v in cs["by_source"].values()), True)
tc = json.loads((V / "crosssource_truncation_check.json").read_text(encoding="utf-8"))
check("magnitude difference survives the common-support check",
      tc["verdict"].startswith("MAGNITUDE DIFFERENCE SURVIVES"), True)

# ── the bar ledger, which every N-of-M statement must match ───────────────────────────────
led = json.loads((V / "bar_ledger.json").read_text(encoding="utf-8"))
c = led["counts"]
# NOTE 2026-08-13: all three checks here formerly read `counts` against `counts` and never touched
# the rows it summarizes. The stored block said FAIL 12 / PASS 4 while the 21 rows tallied FAIL 13
# / PASS 3, and "bar counts sum to the total" passed because 12+4+4+1 = 21 exactly as 13+4+3+1
# does. A summary checked only against itself is not checked. The rows already carried the
# 2026-08-12 rulings that E4-B3's verdict is FAIL and E2-H4 is qualified; neither had reached the
# summary, the markdown ledger, the abstract, or §9. Counts are tallied from the rows now.
import collections as _collections
_tally = _collections.Counter(b["verdict"] for b in led["bars"])
VERDICTS = ("FAIL", "QUALIFIED", "PASS", "UNRESOLVED")
check("bar ledger has 21 rows", len(led["bars"]), 21)
check("every row carries a known verdict", set(_tally) <= set(VERDICTS), True)
check("rows tally 13 FAIL / 4 QUALIFIED / 3 PASS / 1 UNRESOLVED",
      [_tally[v] for v in VERDICTS], [13, 4, 3, 1])
check("the stored counts block equals the tally of the rows",
      [c[v] for v in VERDICTS] + [c["total"]],
      [_tally[v] for v in VERDICTS] + [len(led["bars"])])

# The manuscript states the decomposition in words. Parse it and hold it to the same tally, so a
# hand edit to the abstract cannot drift from the ledger it is describing.
_W = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
      "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14}
# NOTE 2026-08-26: the operator re-ruled the sentence's form to numerals for numbers over 10
# (ledger form_note, same date). Two checks now do what one did: the manuscript must carry the
# ledger's canonical sentence verbatim (submission checklist box 0), and the sentence's own
# numbers, digits or words, must match the row tally, total included.
_canon = re.sub(r"\s+", " ", led["canonical_sentence"]).strip()
check("manuscript carries the ledger's canonical sentence verbatim",
      _canon in re.sub(r"\s+", " ", md), True)
_ab = re.search(r"Of (\w+) pre-registered bars, (\w+) failed outright, (\w+) failed at its\s+"
                r"certification\s+clause, (\w+) is unresolved, and (\w+) passed only", md)
_n = lambda g: int(g) if g.isdigit() else _W.get(g.lower())
check("the canonical sentence's decomposition matches the row tally",
      [_n(g) for g in _ab.groups()] if _ab else None,
      [len(led["bars"]), _tally["FAIL"], 1, _tally["UNRESOLVED"], _tally["QUALIFIED"] - 1])

# ── E1 H4: the transfer that failed by improving (§4) ─────────────────────────────────────
# NOTE 2026-08-13: e1_h4_transfer.json, e3_analysis.json and e3_coupling_stats.json were read by
# NO check in this file. That left §4's whole transfer paragraph and the entirety of §6's validity
# ladder unverified while the header of this script claimed it regenerates every headline number.
# The harness had 49 checks and had never opened three of the study's result files.
h4 = j("e1_h4_transfer.json")
check("H4 evaluation set = 13,780 bis pairs, 2,019 positive",
      [h4["n_bis"], h4["n_bis_positive"]], [13780, 2019])
_thr = [-v["threshold"]["drop"] for v in h4["configs"].values()]
_log = [-v["logistic_cos_jac"]["drop"] for v in h4["configs"].values()]
_lau = [v["logistic_cos_jac"]["auroc_bis"] for v in h4["configs"].values()]
check("H4: all nine configurations improved rather than dropped",
      [len(h4["configs"]), sum(1 for d in _thr if d > 0), sum(1 for d in _log if d > 0)], [9, 9, 9])
check("H4 threshold gain spans 0.03 to 0.06",
      [round(min(_thr), 2), round(max(_thr), 2)], [0.03, 0.06], tol=0.005)
check("H4 logistic gain spans 0.14 to 0.17",
      [round(min(_log), 2), round(max(_log), 2)], [0.14, 0.17], tol=0.005)
check("H4 logistic reaches AUROC 0.71 to 0.74",
      [round(min(_lau), 2), round(max(_lau), 2)], [0.71, 0.74], tol=0.005)

# ── E3: the validity ladder (§6) and the five bars §9 cites ───────────────────────────────
e3 = j("e3_analysis.json")
_cfg = e3["configs"]
assert len(_cfg) == 9, f"e3 covers {len(_cfg)} configurations, expected 9"
_el_naive = [_cfg[k][c]["auroc_naive"] for k in _cfg for c in ("snli", "mnli", "qqp")]
_el_cal = [_cfg[k][c]["auroc_caliper"] for k in _cfg for c in ("snli", "mnli", "qqp")]
_pw_naive = [_cfg[k]["paws"]["auroc_naive"] for k in _cfg]
_pw_cal = [_cfg[k]["paws"]["auroc_caliper"] for k in _cfg]
check("§6 elicited tier, naive AUROC spans 0.64 to 0.92",
      [round(min(_el_naive), 2), round(max(_el_naive), 2)], [0.64, 0.92], tol=0.005)
check("§6 elicited tier, caliper AUROC spans 0.59 to 0.91",
      [round(min(_el_cal), 2), round(max(_el_cal), 2)], [0.59, 0.91], tol=0.005)
# The manuscript printed "0.61 to 0.68" in BOTH PAWS columns. The caliper minimum is 0.6045,
# which rounds to 0.60 - the caliper column was carrying the naive column's lower bound. Caught
# by this check on the run that introduced it, because nothing had ever read e3_analysis.json.
check("§6 PAWS tier: naive 0.61-0.68, caliper 0.60-0.68",
      [round(min(_pw_naive), 2), round(max(_pw_naive), 2),
       round(min(_pw_cal), 2), round(max(_pw_cal), 2)], [0.61, 0.68, 0.60, 0.68], tol=0.005)
check("§6 PAWS caliper invariance is 0.003 or less",
      round(max(abs(a - b) for a, b in zip(_pw_naive, _pw_cal)), 3) <= 0.003, True)
_qqp = [_cfg[k]["qqp"]["auroc_naive"] for k in _cfg]
check("§6 every configuration clears 0.80 on QQP, at 0.85 to 0.90",
      [sum(1 for x in _qqp if x >= 0.80), round(min(_qqp), 2), round(max(_qqp), 2)],
      [9, 0.85, 0.90], tol=0.005)

# §9 names five bars that failed because the gate outperformed the registered prediction. Each
# cited id must actually be a FAIL row, and each measured value must come from its own result.
_by_id = {b["id"]: b for b in led["bars"]}
GATE_FAVOURING = ["E1-H1", "E1-H4", "E3-HE3-1", "E3-HE3-3", "E3-HE3-4"]
check("§9: the five bars it cites are all FAIL rows",
      [_by_id[i]["verdict"] for i in GATE_FAVOURING], ["FAIL"] * 5)
_prod_paws = [v["paws"]["auroc_naive"] for k, v in _cfg.items() if "PRODUCTION" in k][0]
check("§9: production PAWS = 0.679, and it is the highest of the nine",
      [round(_prod_paws, 3), round(max(_pw_naive), 3)], [0.679, 0.679])
check("§9: HE3-4 counts 28 violating cells", e3["hypotheses"]["HE3-4"]["violations"], 28)
check("§9: HE3-1 met the bar on 0 of 9 for every aligned source",
      list(e3["hypotheses"]["HE3-1"]["configs_meeting"].values()), [0, 0, 0])
check("§9: HE3-5 ranked correctly on 1 of 9", e3["hypotheses"]["HE3-5"]["n"], 1)

# ── the manuscript's claims ABOUT this harness and its figures ────────────────────────────
# NOTE 2026-08-13: nothing tied the banner to the harness, so the paper's first sentence said
# "38 of 38 PASS" while the harness reported 45. A paper that misstates the count of its own
# number-checker, in its front matter, is the defect this whole round is about. It is asserted
# here, last, against the live total including this check.
_figdir = ROOT / "docs" / "figures"
FIGS = ["fig1_word_counting_baseline", "fig2_dilution_decay",
        "fig3_no_source_inverted", "fig4_scorecard",
        "fig5_llm_judge_dilution"]
for _f in FIGS:
    assert (_figdir / f"{_f}.svg").exists(), f"missing figure {_f}.svg"
assert len(list(_figdir.glob("fig*.svg"))) == 5, "stray or missing figure in docs/figures"

# Every figure cited exactly once, in ascending order. Until today the word-counting plate was
# Figure 3 but cited first, and Figure 1 was cited nowhere: the table's cells were all verified
# and the figures' citations were verified by nobody.
_cites = re.findall(r"Figure (\d)", md)
check("every figure cited exactly once, in ascending order", _cites, ["1", "2", "3", "4", "5"], tol=0)

_expected = len(checks) + 1
_b = re.search(r"recompute_headline_numbers\.py`, (\d+) of (\d+) PASS", md)
check(f"manuscript banner states this harness's real check count ({_expected})",
      [int(_b.group(1)), int(_b.group(2))] if _b else None, [_expected, _expected])

# ── report ────────────────────────────────────────────────────────────────────────────────
for ok, claim, got, want in checks:
    print(f"  {'PASS' if ok else 'FAIL'}  {claim}" + ("" if ok else f"   got {got!r}, expected {want!r}"))
print()
print(f"{len(checks) - fails} of {len(checks)} headline numbers recompute from the frozen artifacts.")
if fails:
    print("SOME HEADLINE NUMBERS DO NOT RECOMPUTE. The claims they support do not go in the paper.")
    sys.exit(1)
print("ALL HEADLINE NUMBERS RECOMPUTE.")
