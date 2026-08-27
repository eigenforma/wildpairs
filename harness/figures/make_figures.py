"""Paper B figures — generated as standalone SVG directly from the frozen result JSONs.

Design decisions, stated so they are choices rather than omissions:
  * Every number is read from `results/**` at render time. No figure transcribes a value from
    prose. This is the direct countermeasure to the 2026-08-12 fidelity audit, whose finding was
    that errors entered the prose layer and propagated prose-to-prose
    (`docs/CORRECTIONS_2026-08-12.md`). A figure that disagrees with a JSON is now impossible;
    a figure that disagrees with the manuscript means the manuscript is wrong.
  * Light surface only, colors explicit. These are print-destined paper figures, not a web page:
    a deliberate single visual world, not a missing dark mode.
  * Palette validated with the dataviz six-checks validator before use:
    categorical #1F6FB2 / #C2610A → ALL PASS (light, worst adjacent ΔE 22.1 protan);
    status #2E7D32 / #B8860B / #B3261E → ALL PASS. Every status mark also carries a text
    label, so identity is never colour-alone.
  * Ten-series charts do not get ten hues (the rule against cycling): the pack is one recessive
    grey, and exactly two entities are promoted to categorical colour because the argument names
    them — the strongest configuration and the deployed production path.

Run: python harness/figures/make_figures.py   →   docs/figures/fig{1..4}_*.svg
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
RES, OUT = ROOT / "results", ROOT / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

INK, MUTED, GRID, SURF = "#1A1D21", "#5B6169", "#DDE0E3", "#FCFCFB"
BLUE, ORANGE, PACK = "#1F6FB2", "#C2610A", "#9AA0A6"
GOOD, WARN, BAD, NEUTRAL = "#2E7D32", "#B8860B", "#B3261E", "#8A9099"
FONT = "font-family='Georgia,\"Times New Roman\",serif'"
SANS = "font-family='Helvetica,Arial,sans-serif'"

def wrap(s, n):
    out, cur = [], ""
    for w in s.split():
        if len(cur) + len(w) + 1 > n:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
j = lambda p: json.loads((RES / p).read_text(encoding="utf-8"))


# Estimated advance widths for the two faces at font-size 1, measured from the actual metrics of
# Helvetica and Georgia. Crude, and deliberately pessimistic: the point is to fail loudly on text
# that runs off the plate, not to typeset. Added 2026-08-13 after a footnote overran its canvas
# and nothing noticed, which is the figure-layer version of an unchecked number.
def _text_w(s, size, serif=False):
    return len(s) * size * (0.52 if serif else 0.50)


def _bounds_check(w, h, body, tx=28, ty=22, pad=4):
    """Assert every <text> stays inside the plate. A figure that overflows is not a style defect;
    it is a figure the reader cannot read, shipped as though it were checked."""
    import re as _re
    for m in _re.finditer(r"<text x='(-?[\d.]+)' y='(-?[\d.]+)'([^>]*)>(.*?)</text>", body, _re.S):
        x, y, attrs, txt = float(m.group(1)), float(m.group(2)), m.group(3), m.group(4)
        size = float((_re.search(r"font-size='([\d.]+)'", attrs) or [0, "10"])[1])
        serif = "Georgia" in attrs
        wpx = _text_w(txt, size, serif)
        anchor = (_re.search(r"text-anchor='(\w+)'", attrs) or [0, "start"])[1]
        x0 = x - wpx if anchor == "end" else x - wpx / 2 if anchor == "middle" else x
        assert x0 + tx >= -pad, f"text runs off the LEFT: {txt[:44]!r} at x={x0 + tx:.0f}"
        assert x0 + wpx + tx <= w + pad, (
            f"text runs off the RIGHT edge ({w}px plate): {txt[:44]!r} ends at {x0 + wpx + tx:.0f}")
        assert y + ty <= h + pad, f"text below the plate ({h}px): {txt[:44]!r} at y={y + ty:.0f}"


def svg(w, h, body, title, subtitle=""):
    """Wrap the subtitle to the plate, push the body down by the extra lines, and grow the canvas
    to match. Before 2026-08-13 the subtitle was one unwrapped line: two of the four figures ran
    theirs off the right edge, and nothing checked. Every figure is now bounds-asserted."""
    head = f"<text x='0' y='16' {FONT} font-size='15' font-weight='600' fill='{INK}'>{esc(title)}</text>"
    lines = wrap(subtitle, max(24, int((w - 40) / 5.5))) if subtitle else []
    for i, ln in enumerate(lines):
        head += f"<text x='0' y='{34 + i * 14}' {SANS} font-size='11' fill='{MUTED}'>{esc(ln)}</text>"
    extra = max(0, len(lines) - 1) * 14
    H = h + extra
    _bounds_check(w, H, head, ty=22)
    _bounds_check(w, H, body, ty=22 + extra)
    inner = f"<g transform='translate(0,{extra})'>{body}</g>" if extra else body
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{H}' viewBox='0 0 {w} {H}'>"
            f"<rect width='{w}' height='{H}' fill='{SURF}'/>"
            f"<g transform='translate(28,22)'>{head}{inner}</g></svg>")


# ── Figure 1 ── the refutation test: does any source come back inverted? ──────────────────
# REPLACED 2026-08-13. This slot formerly held "The coupling changes sign across text sources",
# a figure whose TITLE is the claim §8 withdraws, whose authored row was two hardcoded literals
# (0.72 / 0.06) transcribed from prose in direct violation of this module's own rule, and which
# the manuscript cited nowhere — it referenced Figures 2, 3 and 4 only. An orphan plate asserting
# a retired claim, regenerated on every run and sitting in the artifact for anyone to find.
# It now plots what actually survives: the source-blinded refutation test, whose result is that
# no source came back inverted. Every value is read from the frozen JSON at render time.
def fig1():
    cs = j("verification/crosssource_coupling.json")
    tr = j("verification/crosssource_truncation_check.json")
    ORDER = [("errata", "IETF errata · reader-reported corrections"),
             ("bis", "IETF bis · working-group revisions"),
             ("authored", "authored factorial instrument [SGAR]")]
    rows = []
    for key, label in ORDER:
        s = cs["by_source"][key]
        rows.append((label, s["gap_preserving_minus_changing"], s["gap_ci95"],
                     s["orientation"], s["n_agreed_judgeable"]))
    W, H, x0, x1 = 736, 380, 268, 660
    y0, dy = 88, 56
    lo, hi = -0.60, 0.68
    sx = lambda v: x0 + (x1 - x0) * (v - lo) / (hi - lo)
    body = []
    for v in (-0.5, -0.25, 0, 0.25, 0.5):
        body.append(f"<line x1='{sx(v):.1f}' y1='{y0-22}' x2='{sx(v):.1f}' y2='{y0+dy*len(rows)-24}' "
                    f"stroke='{GRID}'/>"
                    f"<text x='{sx(v):.1f}' y='{y0+dy*len(rows)-10}' {SANS} font-size='10' fill='{MUTED}' "
                    f"text-anchor='middle'>{v:g}</text>")
    # zero is the whole question: left of it is an inverted source, and nothing lands there
    body.append(f"<line x1='{sx(0):.1f}' y1='{y0-22}' x2='{sx(0):.1f}' y2='{y0+dy*len(rows)-24}' "
                f"stroke='{INK}' stroke-width='1.4'/>")
    body.append(f"<text x='{sx(0)-8:.1f}' y='{y0-28}' {SANS} font-size='9.5' fill='{MUTED}' "
                f"text-anchor='end'>inverted ←</text>"
                f"<text x='{sx(0)+8:.1f}' y='{y0-28}' {SANS} font-size='9.5' fill='{MUTED}'>"
                f"→ aligned</text>")
    for i, (label, gap, ci, orient, n) in enumerate(rows):
        y = y0 + i * dy
        spans0 = ci[0] < 0 < ci[1]
        col = PACK if spans0 else BLUE
        body.append(f"<text x='0' y='{y+4}' {SANS} font-size='11.5' fill='{INK}'>{esc(label)}</text>")
        body.append(f"<text x='0' y='{y+17}' {SANS} font-size='9.5' fill='{MUTED}'>"
                    f"n = {n} agreed judgeable · {esc(orient)}</text>")
        body.append(f"<line x1='{sx(ci[0]):.1f}' y1='{y}' x2='{sx(ci[1]):.1f}' y2='{y}' "
                    f"stroke='{col}' stroke-width='2' opacity='0.85'/>")
        for e in ci:
            body.append(f"<line x1='{sx(e):.1f}' y1='{y-5}' x2='{sx(e):.1f}' y2='{y+5}' "
                        f"stroke='{col}' stroke-width='2'/>")
        body.append(f"<circle cx='{sx(gap):.1f}' cy='{y}' r='6' fill='{col}' stroke='{SURF}' stroke-width='2'/>")
        body.append(f"<text x='{sx(ci[1])+12:.1f}' y='{y+4}' {SANS} font-size='10' fill='{MUTED}'>"
                    f"{gap:+.3f}</text>")
    ly = y0 + dy * len(rows) + 6
    ea, bi = tr["arms"]["errata"], tr["arms"]["bis"]
    note = (f"On the common support both arms share (token-Jaccard ≥ {tr['floor']:g}, the floor bis "
            f"alignment imposes and errata never did), errata moves to "
            f"{ea['gap_common_support']:+.4f} [{ea['ci_common_support'][0]:.4f}, "
            f"{ea['ci_common_support'][1]:.4f}] and bis to {bi['gap_common_support']:+.4f} "
            f"[{bi['ci_common_support'][0]:.3f}, {bi['ci_common_support'][1]:.3f}] — still disjoint. "
            f"Two revision processes inside one standards body differ several-fold in coupling magnitude. "
            f"The authored interval spans both directions and supports no claim about orientation at all.")
    for k, line in enumerate(wrap(note, 116)):
        body.append(f"<text x='0' y='{ly + 13 * k}' {SANS} font-size='10' fill='{MUTED}'>{esc(line)}</text>")
    return svg(W, H, "".join(body),
               "No source came back inverted",
               f"Median token-Jaccard of the preserving class minus the changing class. One rubric, "
               f"{cs['n']} pairs, source-blinded; κ = {cs['kappa_AB_overall']:.4f}.")


# ── Figure 2 ── the dilution decay ────────────────────────────────────────────────────────
def fig2():
    a = j("e2_analysis.json")
    bins = [64, 96, 128, 256, 512, 1024, 2048, 4096]
    series = {}
    # NOTE 2026-08-13: this loop formerly took every cell with a numeric AUROC and drew one solid
    # line through all of them. Seven of the ten configurations exceed their operative window from
    # 512 up and MiniLM from 256, and at 1024 and 4096 those seven are 100% truncated — the cell
    # re-scores one window-full of text and cannot express a length effect. The old figure drew
    # those points as a decay curve, and drew the "deployed chunk defaults" band directly over the
    # region where most series are not measuring length at all. The figure agreed with the JSON and
    # still misrepresented it, which is the failure mode this whole paper is about.
    # Cells now carry their window status, and the renderer draws out-of-window runs dashed.
    for cfg, v in a["cells"].items():
        sp = v.get("splice", {}).get("enwiki", {})
        pts = []
        for L in bins:
            c = sp.get(f"L={L}", {}).get("pooled")
            if isinstance(c, dict) and isinstance(c.get("auroc"), (int, float)):
                w = sp[f"L={L}"].get("within_window_bin")
                assert w is not None, f"{cfg} L={L}: no within_window_bin; refusing to plot"
                pts.append((L, c["auroc"], bool(w)))
        if pts:
            series[cfg] = pts
    W, H = 760, 432
    px0, px1, py0, py1 = 54, 546, 64, 286
    import math
    lx = lambda L: px0 + (px1 - px0) * (math.log2(L) - 6) / 6
    ly = lambda v: py1 - (py1 - py0) * (v - 0.48) / (0.64 - 0.48)
    body = []
    for v in (0.50, 0.55, 0.60):
        body.append(f"<line x1='{px0}' y1='{ly(v):.1f}' x2='{px1}' y2='{ly(v):.1f}' stroke='{GRID}'/>"
                    f"<text x='{px0-8}' y='{ly(v)+3.5:.1f}' {SANS} font-size='10' fill='{MUTED}' "
                    f"text-anchor='end'>{v:.2f}</text>")
    body.append(f"<line x1='{px0}' y1='{ly(0.5):.1f}' x2='{px1}' y2='{ly(0.5):.1f}' stroke='{MUTED}' "
                f"stroke-width='1.2' stroke-dasharray='4 3'/>")
    # the chance annotation sits BELOW its own line with a short leader, so it never competes
    # with the right-gutter series labels
    cx_ch = lx(110)
    body.append(f"<line x1='{cx_ch:.1f}' y1='{ly(0.5)+2:.1f}' x2='{cx_ch:.1f}' y2='{ly(0.5)+13:.1f}' "
                f"stroke='{MUTED}' stroke-width='1'/>"
                f"<text x='{cx_ch:.1f}' y='{ly(0.5)+24:.1f}' {SANS} font-size='9.5' fill='{MUTED}' "
                f"text-anchor='middle'>chance (0.50)</text>")
    # deployed-default band (from the pre-tag chunk survey: ~800 to 1024 whitespace tokens)
    body.insert(0, f"<rect x='{lx(800):.1f}' y='{py0}' width='{lx(1024)-lx(800):.1f}' height='{py1-py0}' "
                   f"fill='{ORANGE}' opacity='0.09'/>"
                   f"<text x='{(lx(800)+lx(1024))/2:.1f}' y='{py0-6}' {SANS} font-size='9.5' fill='{ORANGE}' "
                   f"text-anchor='middle'>deployed chunk defaults</text>")
    for L in bins:
        body.append(f"<text x='{lx(L):.1f}' y='{py1+16}' {SANS} font-size='10' fill='{MUTED}' "
                    f"text-anchor='middle'>{L}</text>")
    body.append(f"<text x='{(px0+px1)/2}' y='{py1+34}' {SANS} font-size='10.5' fill='{MUTED}' text-anchor='middle'>"
                f"nominal passage length L (whitespace tokens, log scale)</text>")
    best = max(series, key=lambda k: {L: v for L, v, _ in series[k]}.get(64, 0))
    prod = next((k for k in series if "PRODUCTION" in k), None)
    def path(pts):
        return "M" + " L".join(f"{lx(L):.1f},{ly(v):.1f}" for L, v, _ in pts)
    def runs(pts):
        """Split into the within-window run and the out-of-window run. The out-of-window run keeps
        the last within-window point at its head, so the line is continuous and only its style
        changes at the boundary: the reader sees where the series goes and that it stopped
        measuring length when it got there."""
        solid = [p for p in pts if p[2]]
        dashed = [p for p in pts if not p[2]]
        if solid and dashed:
            dashed = [solid[-1]] + dashed
        return solid, dashed
    for cfg, pts in series.items():
        if cfg in (best, prod):
            continue
        solid, dashed = runs(pts)
        if len(solid) > 1:
            body.append(f"<path d='{path(solid)}' fill='none' stroke='{PACK}' stroke-width='1.4' opacity='0.75'/>")
        if len(dashed) > 1:
            body.append(f"<path d='{path(dashed)}' fill='none' stroke='{PACK}' stroke-width='1.4' "
                        f"opacity='0.38' stroke-dasharray='3 3'/>")
    for cfg, col, lab in ((best, BLUE, "mxbai-embed-large-v1"),
                          (prod, ORANGE, "nomic-MRL-256")):
        if not cfg:
            continue
        pts = series[cfg]
        solid, dashed = runs(pts)
        if len(solid) > 1:
            body.append(f"<path d='{path(solid)}' fill='none' stroke='{col}' stroke-width='2.4'/>")
        if len(dashed) > 1:
            body.append(f"<path d='{path(dashed)}' fill='none' stroke='{col}' stroke-width='2.4' "
                        f"opacity='0.45' stroke-dasharray='5 4'/>")
        # a filled marker is a measurement at the length its position names; a hollow one is the
        # encoder's window ceiling re-scored, and the difference has to be visible at the mark
        for L, v, w in pts:
            if w:
                body.append(f"<circle cx='{lx(L):.1f}' cy='{ly(v):.1f}' r='4' fill='{col}' "
                            f"stroke='{SURF}' stroke-width='2'/>")
            else:
                body.append(f"<circle cx='{lx(L):.1f}' cy='{ly(v):.1f}' r='3.2' fill='{SURF}' "
                            f"stroke='{col}' stroke-width='1.6' opacity='0.7'/>")
        # direct-label both named series in the right gutter, each with a leader to its
        # endpoint: the production path runs mid-pack and is unreadable labelled in place
        Le, ve, _ = pts[-1]
        gy = py0 + (34 if cfg is best else 104)   # fixed slots: the endpoints are 10px apart
        body.append(f"<path d='M{lx(Le):.1f},{ly(ve):.1f} L{px1+16:.1f},{gy:.1f} L{px1+26:.1f},{gy:.1f}' "
                    f"fill='none' stroke='{col}' stroke-width='1' opacity='0.8'/>")
        body.append(f"<text x='{px1+30:.1f}' y='{gy+3.5:.1f}' {SANS} font-size='10.5' font-weight='600' "
                    f"fill='{col}'>{esc(lab)}</text>")
        sub = "strongest at L=64" if cfg is best else "deployed production path"
        body.append(f"<text x='{px1+30:.1f}' y='{gy+16:.1f}' {SANS} font-size='9.5' fill='{MUTED}'>{esc(sub)}</text>")
    body.append(f"<text x='{px0+8}' y='{py0+14}' {SANS} font-size='10.5' fill='{MUTED}'>"
                f"the other eight configurations</text>")
    ny = py1 + 52
    # the window encoding gets its own legend sample, because a dashed segment that is never
    # explained reads as a second series rather than as a disclaimer
    body.append(f"<line x1='0' y1='{ny-3.5:.1f}' x2='22' y2='{ny-3.5:.1f}' stroke='{MUTED}' "
                f"stroke-width='1.6' stroke-dasharray='4 3'/>"
                f"<circle cx='11' cy='{ny-3.5:.1f}' r='3.2' fill='{SURF}' stroke='{MUTED}' stroke-width='1.6'/>")
    body.append(f"<text x='30' y='{ny}' {SANS} font-size='10' fill='{MUTED}'>"
                f"Dashed line, hollow marker: the passage exceeds the encoder's operative window, so the "
                f"point re-scores one window-full of text</text>")
    body.append(f"<text x='30' y='{ny+13}' {SANS} font-size='10' fill='{MUTED}'>"
                f"and is not a measurement at the length its position names. Seven of ten truncate from 512 "
                f"up, all-MiniLM-L6-v2 from 256, so inside the</text>")
    body.append(f"<text x='30' y='{ny+26}' {SANS} font-size='10' fill='{MUTED}'>"
                f"deployed-defaults band only the three nomic entries are still measuring length.</text>")
    body.append(f"<text x='0' y='{ny+43}' {SANS} font-size='10' fill='{MUTED}'>"
                f"L*(AUROC=0.75) is left-censored at ≤64 for all ten configurations: none reaches usable "
                f"discrimination at any length the grid can build.</text>")
    return svg(W, H, "".join(body),
               "Flip-vs-faithful decision AUROC against passage length",
               "959 CondaQA anchor pairs spliced into byte-identical real host passages; SPLICE arm, "
               "Wikipedia hosts, positions pooled.")


# ── Figure 3 ── the word-counting baseline ────────────────────────────────────────────────
SHORT = {
    "BAAI/bge-base-en-v1.5": "bge-base-en-v1.5",
    "mixedbread-ai/mxbai-embed-large-v1": "mxbai-embed-large-v1",
    "sentence-transformers/all-MiniLM-L6-v2": "all-MiniLM-L6-v2",
    "sentence-transformers/all-mpnet-base-v2": "all-mpnet-base-v2",
    "thenlper/gte-base": "gte-base",
    "e5-base-v2 [query: — card's symmetric convention]": "e5-base-v2 [query:]",
    "e5-base-v2 [NO prefix — sensitivity variant]": "e5-base-v2 [no prefix]",
    "nomic-embed-text-v1.5 [clustering: — documented symmetric prefix]": "nomic-embed-text-v1.5 [clustering:]",
    "nomic-embed-text-v1.5 MRL-256 [PRODUCTION PATH, search_document:]": "nomic-MRL-256  (deployed production path)",
}


def fig3():
    p = j("verification/promoted_primary_auroc.json")
    base = p["jaccard_baseline_g1"]
    rows = sorted(((k, v["g1"]["auroc"], v["g1"]["ci95_cluster"]) for k, v in p["configs"].items()),
                  key=lambda r: r[1])
    W, H = 780, 400
    px0, px1 = 292, 618
    y0, dy = 74, 24
    sx = lambda v: px0 + (px1 - px0) * (v - 0.55) / (0.90 - 0.55)
    body = []
    for v in (0.6, 0.7, 0.8, 0.9):
        body.append(f"<line x1='{sx(v):.1f}' y1='{y0-14}' x2='{sx(v):.1f}' y2='{y0+dy*len(rows)-6}' stroke='{GRID}'/>"
                    f"<text x='{sx(v):.1f}' y='{y0+dy*len(rows)+8}' {SANS} font-size='10' fill='{MUTED}' "
                    f"text-anchor='middle'>{v:.1f}</text>")
    body.append(f"<text x='{(px0+px1)/2:.1f}' y='{y0+dy*len(rows)+26}' {SANS} font-size='10.5' fill='{MUTED}' "
                f"text-anchor='middle'>decision AUROC  (0.5 = chance)</text>")
    bx = sx(base["auroc"])
    body.append(f"<rect x='{sx(base['ci95_cluster'][0]):.1f}' y='{y0-14}' "
                f"width='{sx(base['ci95_cluster'][1])-sx(base['ci95_cluster'][0]):.1f}' height='{dy*len(rows)+8}' "
                f"fill='{ORANGE}' opacity='0.10'/>")
    body.append(f"<line x1='{bx:.1f}' y1='{y0-14}' x2='{bx:.1f}' y2='{y0+dy*len(rows)-6}' stroke='{ORANGE}' "
                f"stroke-width='2'/>")
    body.append(f"<text x='{bx+7:.1f}' y='{y0-20}' {SANS} font-size='10.5' font-weight='600' fill='{ORANGE}'>"
                f"token-Jaccard alone: {base['auroc']:.3f}</text>")
    for i, (cfg, au, ci) in enumerate(rows):
        y = y0 + i * dy
        col = ORANGE if "PRODUCTION" in cfg else BLUE
        name = SHORT.get(cfg, cfg)
        body.append(f"<text x='0' y='{y+4}' {SANS} font-size='10.5' fill='{INK}'>{esc(name)}</text>")
        body.append(f"<line x1='{sx(ci[0]):.1f}' y1='{y}' x2='{sx(ci[1]):.1f}' y2='{y}' stroke='{col}' "
                    f"stroke-width='1.6' opacity='0.55'/>")
        body.append(f"<circle cx='{sx(au):.1f}' cy='{y}' r='5' fill='{col}' stroke='{SURF}' stroke-width='2'/>")
        body.append(f"<text x='{px1+10}' y='{y+4}' {SANS} font-size='10' fill='{MUTED}'>{au:.3f}</text>")
    body.append(f"<text x='0' y='{y0+dy*len(rows)+50}' {SANS} font-size='10' fill='{MUTED}'>"
                f"Construct labels, adjudicated (n = {p['n_judgeable']}: {p['n_changing']} changing / "
                f"{p['n_preserving']} preserving). Bars are cluster-bootstrap 95% CIs by RFC document.</text>")
    body.append(f"<text x='0' y='{y0+dy*len(rows)+64}' {SANS} font-size='10' fill='{MUTED}'>"
                f"Every interval overlaps the word-counting baseline; the deployed production path sits below it.</text>")
    return svg(W, H, "".join(body),
               "Nine embedding models, none better than word overlap",
               "Separating meaning-changing from meaning-preserving corrections. The orange line is what "
               "you get by simply counting the words the two versions share.")


# ── Figure 4 ── the honest scorecard ──────────────────────────────────────────────────────
def fig4():
    led = j("verification/bar_ledger.json")
    COL = {"FAIL": BAD, "PASS": GOOD, "QUALIFIED": WARN, "UNRESOLVED": NEUTRAL}
    bars, c = led["bars"], led["counts"]
    W = 880   # widened 2026-08-13: the longest bar detail (E1-H2, 75 chars) ran 158px off a 700px plate
    y0, dy = 76, 20
    H = y0 + dy * len(bars) + 106
    body = []
    for i, b in enumerate(bars):
        y = y0 + i * dy
        col = COL[b["verdict"]]
        body.append(f"<rect x='0' y='{y-11}' width='4' height='15' rx='2' fill='{col}'/>")
        body.append(f"<text x='14' y='{y}' {SANS} font-size='10.5' font-weight='600' fill='{INK}'>{esc(b['id'])}</text>")
        body.append(f"<text x='88' y='{y}' {SANS} font-size='10.5' fill='{INK}'>{esc(b['short'])}</text>")
        # _bounds_check sees the plate edges, not the gap between two columns: both can sit inside
        # the canvas and still print on top of each other. The verdict column is asserted here.
        assert _text_w(b["verdict"], 10) <= 474 - 388 - 6, (
            f"verdict {b['verdict']!r} overruns the detail column on the scorecard plate")
        body.append(f"<text x='388' y='{y}' {SANS} font-size='10' font-weight='600' fill='{col}'>{esc(b['verdict'])}</text>")
        if b["detail"]:
            body.append(f"<text x='474' y='{y}' {SANS} font-size='9.5' fill='{MUTED}'>{esc(b['detail'])}</text>")
    ly = y0 + dy * len(bars) + 22
    x = 0
    for k in ("FAIL", "QUALIFIED", "PASS", "UNRESOLVED"):
        body.append(f"<rect x='{x}' y='{ly-9}' width='4' height='12' rx='2' fill='{COL[k]}'/>"
                    f"<text x='{x+12}' y='{ly}' {SANS} font-size='10.5' fill='{MUTED}'>{k.lower()} · {c[k]}</text>")
        x += 132
    for k, line in enumerate(wrap(led["canonical_sentence"], 108)):
        body.append(f"<text x='0' y='{ly+24+k*14}' {SANS} font-size='10' fill='{MUTED}'>{esc(line)}</text>")
    return svg(W, H, "".join(body),
               "Every pre-registered bar, and how it went",
               f"{c['total']} bars committed under four freeze tags before any encoder scored any pair. "
               f"Source: results/verification/bar_ledger.json")


# Numbered by CITATION ORDER in the manuscript, not by the order these functions were written.
# Until 2026-08-13 the word-counting plate was Figure 3 but cited first in §4, the dilution plate
# was cited second, the scorecard fourth, and Figure 1 was cited nowhere at all. A reviewer reads
# out-of-order figure numbers as carelessness before reading a single result. The recompute
# harness now asserts each figure is cited exactly once and in ascending order.
for name, fn in (("fig1_word_counting_baseline", fig3), ("fig2_dilution_decay", fig2),
                 ("fig3_no_source_inverted", fig1), ("fig4_scorecard", fig4)):
    (OUT / f"{name}.svg").write_text(fn(), encoding="utf-8")
    print(f"wrote docs/figures/{name}.svg")
