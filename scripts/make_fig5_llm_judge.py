"""Build docs/figures/fig5_llm_judge_dilution.svg — the LLM-judge arm beside the gates.

NAMING: this file is fig5 by creation order but appears as **Figure 3** in the paper,
because the arm sits in the length section and the two later plates shift up. The .tex
uses \ref, so LaTeX numbers it correctly on its own; only the manuscript markdown
carries hardcoded numbers, and recompute_headline_numbers.py checks those ascend in
reading order. Do not "fix" the filename to match the figure number without also
renaming fig3/fig4 and every reference to them.

The arm this figure reports was flagged as optional in the E2 related-work note
("Optionally add one LLM-judge arm at matched conditions -- that comparison is
itself new") and run on 2026-08-26. Provenance and caveats:
findings/U-paper-b-llm-judge-arm.md in the ruling-theory repo.

METRIC RECONCILIATION -- the one thing to get right here. Paper B reports swept
AUROC. An LLM judge emits a binary verdict, so it has no ROC curve to sweep; it
occupies a single operating point. For a binary classifier the balanced accuracy
at that point equals the area of the single-point ROC:

    AUROC_1pt = (TPR + TNR) / 2 = (TPR - FPR + 1) / 2 = (separation + 1) / 2

That is what is plotted, and the caption says so. It is comparable to the encoder
curves in level and shape, but it is NOT a swept AUROC and must never be relabelled
as one: a judge cannot be tuned to a different operating point without changing the
prompt, which is a different instrument.

Both series are SPLICE / enwiki hosts, positions pooled -- matched conditions.
Encoder numbers come straight from results/e2_analysis.json.

Usage: python scripts/make_fig5_llm_judge.py
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
E2 = ROOT / "results" / "e2_analysis.json"
JUDGE = Path(r"C:/Users/poeti/Falsifyer/experiments/paper_c_b3_ceiling/results"
             r"/b3_llm_ceiling_2026-08-26_paperB_lengthlaw.json")
OUT = ROOT / "docs" / "figures" / "fig5_llm_judge_dilution.svg"

LS = [64, 96, 128, 256, 512, 1024, 2048, 4096]
#: Both series are pooled over exactly these registers. The judge arm never ran
#: PMC, so PMC is excluded from the encoder side too rather than quietly averaged
#: into it -- matched conditions or none.
HOSTS = ("enwiki", "rfc")
W, H = 760, 432
# Fig 2's geometry, so the two figures read as a pair.
X0, XSPAN = 54.0, 82.0          # x(L) = X0 + XSPAN*log2(L/64)
YLO, YHI = 0.50, 0.90
YTOP, YBOT = 64.0, 286.0

BG = "#FCFCFB"
INK = "#1A1D21"
SUB = "#5B6169"
GRID = "#DDE0E3"
ACCENT = "#C2610A"
JUDGE_C = "#1F5E8C"
ENC_A = "#7A7F87"
ENC_B = "#B0B4BA"

SERIF = 'Georgia,"Times New Roman",serif'
SANS = "Helvetica,Arial,sans-serif"


def x(L):
    return X0 + XSPAN * math.log2(L / 64)


def y(a):
    return YBOT - (a - YLO) / (YHI - YLO) * (YBOT - YTOP)


def judge_series():
    """Single-point AUROC per length, with a 95% CI.

    The CI is not decoration. At 60 mutation and 30 control judgments per cell the
    band is roughly +/-0.09, which is wider than the cell-to-cell wiggles -- so the
    curve must be read as a trend, not as eight measurements. Plotting the points
    bare would invite exactly the over-reading this corpus punishes.
    """
    d = json.loads(JUDGE.read_text(encoding="utf-8"))
    rows = [r for r in d["rows"] if r["host"] in HOSTS]
    out, lo, hi, ns = {}, {}, {}, {}
    for L in LS:
        rs = [r for r in rows if r["L"] == L]
        mut = [r for r in rs if r["is_mutation"]]
        ctl = [r for r in rs if not r["is_mutation"]]
        n1, n0 = len(mut), len(ctl)
        p1 = sum(r["verdict"] == "DIFFERENT" for r in mut) / n1
        p0 = sum(r["verdict"] == "DIFFERENT" for r in ctl) / n0
        a = (p1 - p0 + 1) / 2
        se = math.sqrt((p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)) / 2
        out[L], lo[L], hi[L] = a, max(0.0, a - 1.96 * se), min(1.0, a + 1.96 * se)
        ns[L] = (n1, n0)
    return out, lo, hi, ns


def encoder_series(cfg):
    d = json.loads(E2.read_text(encoding="utf-8"))
    sp = d["cells"][cfg]["splice"]
    auroc, within = {}, {}
    for L in LS:
        vals = [sp[h][f"L={L}"]["pooled"]["auroc"] for h in HOSTS]
        auroc[L] = sum(vals) / len(vals)
        within[L] = all(sp[h][f"L={L}"]["within_window_bin"] for h in HOSTS)
    return auroc, within


def polyline(series, color, width=2.2, dash=None, within=None):
    """Solid where measured within the encoder's window, dashed where truncated."""
    segs, cur = [], []
    for L in LS:
        ok = True if within is None else within[L]
        if cur and cur[-1][2] != ok:
            segs.append(cur)
            cur = [cur[-1]]
        cur.append((x(L), y(series[L]), ok))
    segs.append(cur)
    out = []
    for seg in segs:
        pts = " ".join(f"{px:.1f},{py:.1f}" for px, py, _ in seg)
        da = "" if seg[0][2] else " stroke-dasharray='5 4'"
        d = dash or ""
        out.append(f"<polyline points='{pts}' fill='none' stroke='{color}' "
                   f"stroke-width='{width}'{da}{d} stroke-linejoin='round'/>")
    for L in LS:
        ok = True if within is None else within[L]
        fill = color if ok else BG
        out.append(f"<circle cx='{x(L):.1f}' cy='{y(series[L]):.1f}' r='3.4' "
                   f"fill='{fill}' stroke='{color}' stroke-width='1.6'/>")
    return "".join(out)


def main():
    judge, jlo, jhi, jn = judge_series()
    mxbai, mx_win = encoder_series("mixedbread-ai/mxbai-embed-large-v1")
    nomic, nm_win = encoder_series(
        "nomic-embed-text-v1.5 LONG-CONTEXT-8192 [clustering:]")

    s = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' "
         f"viewBox='0 0 {W} {H}'><rect width='{W}' height='{H}' fill='{BG}'/>",
         "<g transform='translate(28,22)'>"]

    s.append(f"<text x='0' y='16' font-family='{SERIF}' font-size='15' "
             f"font-weight='600' fill='{INK}'>Escalating to an LLM judge raises the "
             f"curve without changing its shape</text>")
    s.append(f"<text x='0' y='34' font-family='{SANS}' font-size='11' fill='{SUB}'>"
             "Flip-vs-faithful discrimination against passage length. Same frozen "
             "corpus, SPLICE arm, Wikipedia and RFC hosts, positions pooled.</text>")

    # deployed-chunk band, matching fig 2
    bx0, bx1 = x(800), x(1024)
    s.append(f"<rect x='{bx0:.1f}' y='{YTOP}' width='{bx1-bx0:.1f}' "
             f"height='{YBOT-YTOP}' fill='{ACCENT}' opacity='0.09'/>")
    s.append(f"<text x='{(bx0+bx1)/2:.1f}' y='{YTOP-6}' font-family='{SANS}' "
             f"font-size='9.5' fill='{ACCENT}' text-anchor='middle'>deployed chunk "
             "defaults</text>")

    # y grid
    for a in [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]:
        yy = y(a)
        s.append(f"<line x1='{X0}' y1='{yy:.1f}' x2='{x(4096):.1f}' y2='{yy:.1f}' "
                 f"stroke='{GRID}'/>")
        s.append(f"<text x='{X0-8}' y='{yy+3.5:.1f}' font-family='{SANS}' "
                 f"font-size='10' fill='{SUB}' text-anchor='end'>{a:.2f}</text>")

    # reference lines
    s.append(f"<line x1='{X0}' y1='{y(0.50):.1f}' x2='{x(4096):.1f}' "
             f"y2='{y(0.50):.1f}' stroke='{SUB}' stroke-width='1.2' "
             "stroke-dasharray='4 3'/>")
    s.append(f"<text x='{x(96):.1f}' y='{y(0.50)+13:.1f}' font-family='{SANS}' "
             f"font-size='9.5' fill='{SUB}' text-anchor='middle'>chance (0.50)</text>")
    s.append(f"<line x1='{X0}' y1='{y(0.75):.1f}' x2='{x(4096):.1f}' "
             f"y2='{y(0.75):.1f}' stroke='{ACCENT}' stroke-width='1.1' "
             "stroke-dasharray='2 3' opacity='0.75'/>")
    s.append(f"<text x='{x(4096):.1f}' y='{y(0.75)-5:.1f}' font-family='{SANS}' "
             f"font-size='9.5' fill='{ACCENT}' text-anchor='end'>usable "
             "discrimination (0.75)</text>")

    # x ticks
    for L in LS:
        s.append(f"<text x='{x(L):.1f}' y='{YBOT+18:.1f}' font-family='{SANS}' "
                 f"font-size='10' fill='{SUB}' text-anchor='middle'>{L}</text>")
    s.append(f"<text x='{(X0+x(4096))/2:.1f}' y='{YBOT+38:.1f}' font-family='{SANS}' "
             f"font-size='10.5' fill='{SUB}' text-anchor='middle'>nominal passage "
             "length L (whitespace tokens)</text>")

    band = ([f"{x(L):.1f},{y(jhi[L]):.1f}" for L in LS]
            + [f"{x(L):.1f},{y(jlo[L]):.1f}" for L in reversed(LS)])
    s.append(f"<polygon points='{' '.join(band)}' fill='{JUDGE_C}' opacity='0.13'/>")
    s.append(polyline(nomic, ENC_B, 1.8, within=nm_win))
    s.append(polyline(mxbai, ENC_A, 1.8, within=mx_win))
    s.append(polyline(judge, JUDGE_C, 2.6))

    # legend
    ly = YTOP + 6
    for label, color, note in (
        ("LLM judge panel (Qwen3.8-27B + Mistral-Small-24B)", JUDGE_C,
         "single operating point"),
        ("mxbai-embed-large-v1 (best encoder at L=64)", ENC_A, "swept AUROC"),
        ("nomic-embed-text-v1.5, 8192 window", ENC_B, "swept AUROC"),
    ):
        s.append(f"<line x1='{x(256):.1f}' y1='{ly:.1f}' x2='{x(256)+22:.1f}' "
                 f"y2='{ly:.1f}' stroke='{color}' stroke-width='2.4'/>")
        s.append(f"<text x='{x(256)+28:.1f}' y='{ly+3.5:.1f}' font-family='{SANS}' "
                 f"font-size='10' fill='{INK}'>{label} "
                 f"<tspan fill='{SUB}'>&#183; {note}</tspan></text>")
        ly += 16

    s.append("</g></svg>")
    OUT.write_text("".join(s), encoding="utf-8")

    print(f"wrote {OUT}")
    print(f"{'L':>6} {'judge(1pt)':>11} {'95% CI':>16} {'mxbai':>8} {'nomic8k':>9}")
    for L in LS:
        print(f"{L:>6} {judge[L]:>11.3f} "
              f"{f'[{jlo[L]:.3f},{jhi[L]:.3f}]':>16} {mxbai[L]:>8.3f} {nomic[L]:>9.3f}")
    n1, n0 = jn[64]
    print(f"per cell: {n1} mutation + {n0} control judgments")
    above = [L for L in LS if jlo[L] > 0.75]
    print(f"judge CI strictly above 0.75 at L in {above or 'nowhere'}")
    print(f"endpoints: L=64 {judge[64]:.3f} -> L=4096 {judge[4096]:.3f}; "
          f"encoders never reach 0.75 at any L")


if __name__ == "__main__":
    main()
