"""E2 analysis: executable form of PREREGISTRATION_E2 sections 2-4 (fits, L*, H1-H6 bars).

COMMITTED BEFORE THE prereg-e2 TAG AND BEFORE ANY SWEEP DATA EXISTS (verify: this file's
first commit predates results/e2_scores_merged.json in git history; at commit time no
titrated passage had been embedded by any encoder). The fits, censoring rules, bar
scorings, and bootstrap discipline below are frozen by the tag; every place where the
prereg text left a definition open, the pin taken here is enumerated in
meta.pinned_by_module of the output JSON (those pins are the amendment candidates).

Input contract (produced by the sweep merge):
  results/e2_scores_merged.json = {"meta": {...}, "cells": [
      {anchor_id, arm ("splice"|"native"), host ("enwiki"|"pmc"|"rfc"), L,
       position ("early"|"middle"|"late"), encoder, pair ("flip"|"faithful"|"scope"),
       cos, realized_tokens: {a, b}, truncated: bool}]}
Anchor-side inputs: corpus/e2_dilution/anchors_frozen.jsonl (j_para/j_affirm/j_scope,
payload texts) and results/verification/e2_attrition_tables.json (cross-checked).

Optional inputs (TBD at tag time, PENDING verdicts when absent):
  --stimuli   jsonl of constructed pair members, rows either
              {anchor_id, L, text_orig, text_para, text_affirm[, text_scope]
               [, host="enwiki"][, arm="splice"][, position]}
              or {anchor_id, L, pair, text_a, text_b[, ...]}. Drives Delta_lex(L),
              alpha_lex, and H5 observed r(L).
  --membership json {"mean_pooled": [names], "nevir_at_below_random": [names],
              "production": name} — the section-6 membership lists.
  --relabel   jsonl {anchor_id, annotator_a, annotator_b} — E2-P5 relabel; Cohen kappa
              label-noise ceiling.
  --windows   json {config_name: effective_window_int} — per-encoder effective windows
              (special tokens included), the pre-tag table.

Decision direction (matches E1/E3): a flip pair should score LOWER cosine than a
faithful pair; decision AUROC = P(cos_flip < cos_faithful), ties 0.5. Gate fires
("blocks") when cos < t: flip miss = cos_flip >= t; faithful false-block = cos_faithful < t.

All CIs and tests bootstrap over ANCHORS (the repeated unit), never over cells:
10,000 resamples, seed 20260805, refit per resample for L*/alpha. One frozen-JSON
output (results/e2_analysis.json; --out to redirect). Offline, one command.
Real-run wall-clock note: the caliper-refit bootstrap on the H2b cells and the pooled
caliper CIs put this in the tens-of-minutes range on Forge-class CPU; everything else
is vectorized (weighted-prefix-sum AUROC bootstrap, O(n) per resample).
"""
import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SCORES = ROOT / "results" / "e2_scores_merged.json"
DEFAULT_OUT = ROOT / "results" / "e2_analysis.json"
ANCHORS = ROOT / "corpus" / "e2_dilution" / "anchors_frozen.jsonl"
ATTRITION = ROOT / "results" / "verification" / "e2_attrition_tables.json"

SEED = 20260805
N_BOOT_REGISTERED = 10_000
GRID = [64, 96, 128, 256, 512, 1024, 2048, 4096]
LEVELS = [0.75, 0.55]                      # dilution-L*(A) levels
OPS = [0.30, 0.40, 0.60, 0.80, 0.85, 0.95] # Paper A section 5 + audited-guard 0.60
CALIPER_TOL = 0.05                          # payload-Jaccard +/- 0.05
MIN_BINS_POWER = 5                          # parametric fit only where >=5 within-window bins
COHORT_FLOOR_N = 400                        # section 2 floor rule
H6_FRAC = 0.90
H6_REGISTERED_CELLS = 140                   # 10 configs x 7 bins x 2 hosts as registered
H6_REGISTERED_PER_CONFIG = 14
H6_CONFIG_CAP = 3
TOKEN_RE = __import__("re").compile(r"[a-z0-9]+")


# ----------------------------------------------------------------------------- lexical
def toks(s):
    return set(TOKEN_RE.findall(s.lower()))


def jaccard(a, b):
    ta, tb = toks(a), toks(b)
    return len(ta & tb) / len(ta | tb) if (ta or tb) else 1.0


def ws_count(s):
    return len(s.split())


def W_of(L):
    return math.ceil(L / 1.3)


def eligible(anchor, L):
    """Pinned drop rule (section 2): drop when max ws-tokens over (orig, para, affirm)
    > W(L)/2."""
    m = max(ws_count(anchor["payload_orig"]), ws_count(anchor["payload_para"]),
            ws_count(anchor["payload_affirm"]))
    return m <= W_of(L) / 2.0


# ----------------------------------------------------------------------- boot machinery
def weight_matrix(rng_key, n, n_boot):
    """Anchor-resample counts: each row is a multinomial(n, uniform) draw = one
    with-replacement resample of the population's n anchors."""
    rng = np.random.default_rng(rng_key)
    if n == 0:
        return np.zeros((n_boot, 0), dtype=np.int64)
    return rng.multinomial(n, np.full(n, 1.0 / n), size=n_boot)


def wboot_auroc(cosf, af, cosp, ap, Wm, chunk=2048):
    """AUROC_b = P_w(cos_flip < cos_faithful) under anchor-resample weights, per row of
    Wm. Ties 0.5. O(n) per resample via prefix sums in flip-sorted order. Returns (B,)."""
    B = Wm.shape[0]
    out = np.full(B, np.nan)
    if len(cosf) == 0 or len(cosp) == 0:
        return out
    order = np.argsort(cosf, kind="mergesort")
    fs = cosf[order]
    afo = af[order]
    lo = np.searchsorted(fs, cosp, side="left")
    hi = np.searchsorted(fs, cosp, side="right")
    for s in range(0, B, chunk):
        Wc = Wm[s:s + chunk]
        wf = Wc[:, afo].astype(np.float64)
        cum = np.concatenate([np.zeros((wf.shape[0], 1)), np.cumsum(wf, axis=1)], axis=1)
        lt = cum[:, lo]
        eq = cum[:, hi] - cum[:, lo]
        wp = Wc[:, ap].astype(np.float64)
        num = (wp * (lt + 0.5 * eq)).sum(axis=1)
        den = wf.sum(axis=1) * wp.sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[s:s + chunk] = num / den
    return out


def point_auroc(cosf, af, cosp, ap, n_pop):
    return float(wboot_auroc(cosf, af, cosp, ap, np.ones((1, n_pop), dtype=np.int64))[0])


def wboot_mean(x, a, Wm, chunk=4096):
    B = Wm.shape[0]
    out = np.full(B, np.nan)
    if len(x) == 0:
        return out
    for s in range(0, B, chunk):
        w = Wm[s:s + chunk][:, a].astype(np.float64)
        with np.errstate(invalid="ignore", divide="ignore"):
            out[s:s + chunk] = (w * x).sum(axis=1) / w.sum(axis=1)
    return out


def ci95(v):
    v = v[~np.isnan(v)]
    if len(v) == 0:
        return [None, None]
    return [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]


# ------------------------------------------------------------------ monotone spline / L*
def pav_nonincreasing(Y):
    """Pool-adjacent-violators onto a non-increasing sequence, uniform knot weights
    (pin: prereg does not weight knots). Y is (R, k); returns same shape."""
    R, k = Y.shape
    out = np.empty_like(Y)
    for r in range(R):
        row = Y[r]
        if np.isnan(row).any():
            out[r] = np.nan
            continue
        vals, wts = [], []
        for xv in row:
            vals.append(float(xv)); wts.append(1)
            while len(vals) > 1 and vals[-2] < vals[-1]:   # violates non-increasing
                w = wts[-1] + wts[-2]
                vals[-2] = (vals[-1] * wts[-1] + vals[-2] * wts[-2]) / w
                wts[-2] = w
                vals.pop(); wts.pop()
        flat = []
        for v, w in zip(vals, wts):
            flat.extend([v] * w)
        out[r] = flat
    return out


def _slopes(x, Y):
    """Fritsch-Carlson-style monotone Hermite slopes for monotone knot data (vectorized
    over rows). Endpoints take the adjacent secant (shape-preserving since |m|<=3|d|)."""
    d = np.diff(Y, axis=1) / np.diff(x)
    M = np.zeros_like(Y)
    M[:, 0] = d[:, 0]
    M[:, -1] = d[:, -1]
    if Y.shape[1] > 2:
        a, b = d[:, :-1], d[:, 1:]
        prod = a * b
        s = a + b
        with np.errstate(invalid="ignore", divide="ignore"):
            hm = np.where(prod > 0, 2 * prod / np.where(s == 0, 1.0, s), 0.0)
        M[:, 1:-1] = hm
    return M


def _hermite(xl, xr, yl, yr, ml, mr, xq):
    h = xr - xl
    t = (xq - xl) / h
    t2, t3 = t * t, t * t * t
    return ((2 * t3 - 3 * t2 + 1) * yl + h * (t3 - 2 * t2 + t) * ml
            + (-2 * t3 + 3 * t2) * yr + h * (t3 - t2) * mr)


def spline_crossings(bins, Y, level):
    """First within-domain crossing of the monotone spline through PAV knots at
    x=log2(L). Returns (L*_values (nan where censored), code) with code:
    0=numeric, 1=at/below level at first bin ("<=FIRST"), 2=no crossing in domain
    (">4096" or ">window"), 3=undefined (NaN knots)."""
    x = np.log2(np.asarray(bins, dtype=np.float64))
    R, k = Y.shape
    vals = np.full(R, np.nan)
    valid = ~np.isnan(Y).any(axis=1)
    left = valid & (Y[:, 0] <= level)
    if k == 1:
        code = np.select([~valid, left], [3, 1], default=2)
        return vals, code
    below = Y[:, 1:] <= level
    has = valid & ~left & below.any(axis=1)
    code = np.select([~valid, left, has], [3, 1, 0], default=2)
    rows = np.flatnonzero(has)
    if len(rows):
        idx = np.argmax(below[rows], axis=1)          # interval [idx, idx+1]
        M = _slopes(x, Y[rows])
        ar = np.arange(len(rows))
        xl, xr = x[idx], x[idx + 1]
        yl, yr = Y[rows, idx], Y[rows, idx + 1]
        ml, mr = M[ar, idx], M[ar, idx + 1]
        lo, hi = xl.copy(), xr.copy()
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            above = _hermite(xl, xr, yl, yr, ml, mr, mid) > level
            lo = np.where(above, mid, lo)
            hi = np.where(above, hi, mid)
        vals[rows] = 2.0 ** hi
    return vals, code


def censor_label(code, bins):
    if code == 1:
        return f"<={bins[0]}"
    if code == 2:
        return ">4096" if bins[-1] == 4096 else ">window"
    return None


def lstar_block(bins, knots_point, knots_boot, level):
    """L*(level) with censoring code and anchor-bootstrap CI (refit per resample).
    Censored resamples enter the percentile order as bins[0] (left) / +inf (right);
    a CI endpoint landing on +inf is reported as the right-censor code."""
    v, c = spline_crossings(bins, knots_point[None, :], level)
    point_code = int(c[0])
    point = None if point_code != 0 else round(float(v[0]), 1)
    bv, bc = spline_crossings(bins, knots_boot, level)
    usable = bc != 3
    ext = np.where(bc == 1, float(bins[0]), np.where(bc == 2, np.inf, bv))
    ext = ext[usable]
    notes = {
        "boot_left_censored_frac": round(float((bc == 1).mean()), 4),
        "boot_right_censored_frac": round(float((bc == 2).mean()), 4),
        "boot_undefined_frac": round(float((bc == 3).mean()), 4),
    }
    right_lab = ">4096" if bins[-1] == 4096 else ">window"
    if len(ext) == 0:
        ci = [None, None]
    else:
        lo, hi = np.percentile(ext, 2.5), np.percentile(ext, 97.5)
        ci = [f"<={bins[0]}" if lo <= bins[0] else round(float(lo), 1),
              right_lab if np.isinf(hi) else round(float(hi), 1)]
    return {"level": level, "lstar": point if point is not None else censor_label(point_code, bins),
            "censored": point_code != 0, "ci95": ci, "censored_notes": notes}


# --------------------------------------------------------------------------- power law
def power_fit_rows(bins, D):
    """Delta(L) = Delta0 * (64/L)^alpha, k pinned to 64; least squares in log space on
    bins with positive mean Delta. Returns (alpha, Delta0, n_pos_bins) per row."""
    Lb = np.asarray(bins, dtype=np.float64)
    X = np.log(64.0 / Lb)
    ok = np.isfinite(D) & (D > 0)
    n = ok.sum(axis=1)
    enough = n >= 3
    nf = np.where(n == 0, 1, n).astype(np.float64)
    Yl = np.where(ok, np.log(np.where(ok, D, 1.0)), 0.0)
    Xb = np.where(ok, X, 0.0)
    mx = Xb.sum(axis=1) / nf
    my = Yl.sum(axis=1) / nf
    cxx = (ok * (X - mx[:, None]) ** 2).sum(axis=1)
    cxy = (ok * (X - mx[:, None]) * (Yl - my[:, None])).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        alpha = np.where(enough & (cxx > 0), cxy / cxx, np.nan)
    d0 = np.exp(my - alpha * mx)
    return alpha, d0, n


# ------------------------------------------------------------------------------ caliper
def caliper_match(jf, jp, rng):
    """Greedy 1:1 two-pointer match on payload Jaccard within +/-CALIPER_TOL after a
    seeded permutation for order ties (E3 house convention). Returns index arrays."""
    pf, pp = rng.permutation(len(jf)), rng.permutation(len(jp))
    of = pf[np.argsort(jf[pf], kind="mergesort")]
    op = pp[np.argsort(jp[pp], kind="mergesort")]
    sf, sp = jf[of], jp[op]
    i = j = 0
    kf, kp = [], []
    while i < len(sf) and j < len(sp):
        d = sf[i] - sp[j]
        if abs(d) <= CALIPER_TOL:
            kf.append(of[i]); kp.append(op[j]); i += 1; j += 1
        elif d > CALIPER_TOL:
            j += 1
        else:
            i += 1
    return np.array(kf, dtype=np.int64), np.array(kp, dtype=np.int64)


def plain_auroc(f, p):
    """Classic two-sample AUROC P(f < p), ties 0.5 (rank method)."""
    if len(f) == 0 or len(p) == 0:
        return float("nan")
    order = np.argsort(f, kind="mergesort")
    fs = f[order]
    lo = np.searchsorted(fs, p, side="left")
    hi = np.searchsorted(fs, p, side="right")
    return float((lo + 0.5 * (hi - lo)).sum() / (len(f) * len(p)))


def caliper_boot(cosf, af, jf, cosp, ap, jp, Wm, rng):
    """Caliper AUROC with the match REFIT per anchor resample (weights expand to repeat
    counts; repeating j-sorted arrays preserves order, so the two-pointer walk stays
    O(n) per resample)."""
    of = np.argsort(jf, kind="mergesort")
    op = np.argsort(jp, kind="mergesort")
    jfs, cfs, afs = jf[of], cosf[of], af[of]
    jps, cps, aps = jp[op], cosp[op], ap[op]
    B = Wm.shape[0]
    out = np.full(B, np.nan)
    for b in range(B):
        wf = Wm[b][afs]
        wp = Wm[b][aps]
        rjf, rcf = np.repeat(jfs, wf), np.repeat(cfs, wf)
        rjp, rcp = np.repeat(jps, wp), np.repeat(cps, wp)
        i = j = 0
        mf, mp = [], []
        nf, npr = len(rjf), len(rjp)
        while i < nf and j < npr:
            d = rjf[i] - rjp[j]
            if abs(d) <= CALIPER_TOL:
                mf.append(rcf[i]); mp.append(rcp[j]); i += 1; j += 1
            elif d > CALIPER_TOL:
                j += 1
            else:
                i += 1
        if len(mf) >= 30:
            out[b] = plain_auroc(np.array(mf), np.array(mp))
    return out


# ------------------------------------------------------------------------- small stats
def point_biserial(x, y01):
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y01, dtype=np.float64)
    if len(x) < 3 or x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def cohen_kappa(a, b):
    a, b = list(a), list(b)
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    labels = sorted(set(a) | set(b))
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    if pe == 1.0:
        return 1.0 if po == 1.0 else None
    return (po - pe) / (1 - pe)


def r4(x):
    if x is None:
        return None
    x = float(x)
    return None if (math.isnan(x) or math.isinf(x)) else round(x, 4)


def sanitize(o):
    if isinstance(o, dict):
        return {str(k): sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [sanitize(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------------------ loading
def load_anchors():
    anchors = []
    for line in ANCHORS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            anchors.append(json.loads(line))
    idx = {a["anchor_id"]: i for i, a in enumerate(anchors)}
    elig = {L: np.array([eligible(a, L) for a in anchors]) for L in GRID}
    cohort_mask = np.logical_and.reduce([elig[L] for L in GRID])
    return anchors, idx, elig, cohort_mask


def load_scores(path, anchor_index):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = d["cells"]
    merged = {}
    dupes = 0
    for r in rows:
        if r["anchor_id"] not in anchor_index:
            sys.exit(f"scores reference unknown anchor_id {r['anchor_id']} — contract violation")
        key = (r["encoder"], r["arm"], r["host"], int(r["L"]), r["position"],
               r["anchor_id"], r["pair"])
        rt = r.get("realized_tokens") or {}
        rmax = max(rt.get("a", 0) or 0, rt.get("b", 0) or 0)
        if key in merged:
            dupes += 1
            m = merged[key]
            m[0].append(float(r["cos"]))
            m[1] = max(m[1], rmax)
            m[2] = m[2] or bool(r.get("truncated", False))
        else:
            merged[key] = [[float(r["cos"])], rmax, bool(r.get("truncated", False))]
    per_enc = defaultdict(lambda: defaultdict(list))
    for (enc, arm, host, L, pos, aid, pair), (cs, rmax, trunc) in merged.items():
        per_enc[enc][(arm, host, L)].append(
            (pos, anchor_index[aid], pair, float(np.mean(cs)), rmax, trunc))
    return d.get("meta", {}), per_enc, dupes


def load_stimuli(path):
    """Tolerant reader for the (TBD) titration stimuli metadata. Returns
    {(anchor_id, L): {"orig": text, "para": text, "affirm": text, "scope"?: text}}
    restricted to arm=splice, host=enwiki (the fit domain for H1/H5)."""
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("arm", "splice") != "splice" or r.get("host", "enwiki") != "enwiki":
            continue
        key = (r["anchor_id"], int(r["L"]))
        slot = out.setdefault(key, {})
        if "text_orig" in r:
            slot["orig"] = r["text_orig"]
            slot["para"] = r.get("text_para", slot.get("para"))
            slot["affirm"] = r.get("text_affirm", slot.get("affirm"))
            if "text_scope" in r:
                slot["scope"] = r["text_scope"]
        elif "pair" in r and "text_a" in r:
            slot.setdefault("orig", r["text_a"])
            slot[{"faithful": "para", "flip": "affirm", "scope": "scope"}.get(
                r["pair"], r["pair"])] = r["text_b"]
    return {k: v for k, v in out.items() if "orig" in v and "para" in v and "affirm" in v}


# --------------------------------------------------------------------------- main logic
def main(argv=None):
    ap = argparse.ArgumentParser(description="E2 analysis (executable preregistration)")
    ap.add_argument("--scores", default=str(DEFAULT_SCORES))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--stimuli", default=None)
    ap.add_argument("--membership", default=None)
    ap.add_argument("--relabel", default=None)
    ap.add_argument("--windows", default=None)
    ap.add_argument("--n-boot", type=int, default=N_BOOT_REGISTERED,
                    help="registered value 10000; any override is recorded in meta")
    args = ap.parse_args(argv)
    n_boot = args.n_boot

    if not Path(args.scores).exists():
        sys.exit("scores file not present — the sweep has not run; this module is the "
                 "frozen analysis plan (see PREREGISTRATION_E2.md)")

    anchors, anchor_index, elig, cohort_mask = load_anchors()
    n_cohort_all = int(cohort_mask.sum())
    fit_floor = 64 if n_cohort_all >= COHORT_FLOOR_N else 96   # section 2 floor rule

    attr_check = {"computed_constant_cohort": n_cohort_all, "frozen": None, "match": None}
    if ATTRITION.exists():
        frozen = json.loads(ATTRITION.read_text(encoding="utf-8"))
        attr_check["frozen"] = frozen.get("constant_cohort_all_bins_incl_64")
        attr_check["match"] = attr_check["frozen"] == n_cohort_all
        attr_check["per_bin_eligible"] = {
            str(L): {"computed": int(elig[L].sum()),
                     "frozen": (frozen.get("per_bin", {}).get(str(L)) or {}).get("eligible")}
            for L in GRID}

    sweep_meta, per_enc, dupes = load_scores(args.scores, anchor_index)
    configs = sorted(per_enc.keys())

    windows = {}
    if args.windows:
        windows.update(json.loads(Path(args.windows).read_text(encoding="utf-8")))
    elif isinstance(sweep_meta.get("effective_windows"), dict):
        windows.update(sweep_meta["effective_windows"])

    membership = {}
    if args.membership:
        membership = json.loads(Path(args.membership).read_text(encoding="utf-8"))
    production = membership.get("production") or next(
        (c for c in configs if "PRODUCTION" in c), None)

    stimuli = load_stimuli(args.stimuli) if args.stimuli else None

    j_para = np.array([a["j_para"] for a in anchors])
    j_affirm = np.array([a["j_affirm"] for a in anchors])

    pinned_by_module = [
        "bin-level within-window: an (encoder,bin) is a truncation bin when truncated fraction >= 0.5 over its splice cells; 0<frac<0.5 is a boundary bin analyzed both ways with the excluding-truncated variant feeding fits (prereg pins only the L=512 both-ways case)",
        "H2 primary host = enwiki (prereg names arm but not host for H2a/H2b; PMC/RFC stay held out for H6); per-host statistics reported alongside",
        "H2/H4 positions pooled where the clause does not name positions (H4 pins pooling explicitly; H2 left it open)",
        "H2a/H2b evaluability: bins beyond a config's window are outside the scoring convention's within-window set; configs with no qualifying bin are listed as vacuous, never counted as passes",
        "power-law fit: both parameters (Delta0, alpha) by least squares in log space; measured Delta(64) reported beside fitted Delta0 (prereg's 'Delta0 == Delta(64)' read as identifiability statement, not a parameter pin)",
        "spline carrier: isotonic (PAV, uniform knot weights) non-increasing regression on per-bin AUROC over x=log2(L), monotone cubic Hermite (Fritsch-Carlson harmonic slopes, secant endpoints) through the isotonic knots; L*(A)=infimum L with spline<=A",
        "L* CI: censored resamples enter the percentile order at first-bin / +inf; a CI endpoint on a censored mass is reported as the censoring code",
        "power-law alpha CI: refit per anchor resample on the same weight draws as the spline (shared resample stream per (config, population))",
        "caliper CIs (match refit per resample) computed for H2b bar cells; caliper point estimates + n_matched reported for every cell (E3 precedent reports caliper without CI)",
        "H3a aggregation: single pooled AUROC(early)-AUROC(late) over all bins with L <= window/2 (window unknown -> L <= max_within_window_bin/2); config counts as a hit on the point estimate, CI reported",
        "H5 population: splice/enwiki, grid bins >= 512 present in stimuli; closed-form r uses per-anchor payload intersection/union sizes with a single per-bin host-set-size scalar (measured median from stimuli; ws-budget TTR=1 approximation when stimuli absent, labeled)",
        "Delta_lex(L) = mean anchor-level Jaccard DISTANCE (1 - whole-passage token Jaccard) of the pair members; alpha_lex fit on the flip pair (faithful reported); H1 sharp test vs constant 1.0 always, vs measured alpha_lex when stimuli exist (unpaired resample streams, disclosed)",
        "H6 bands: per held-out cell, D_b = AUROC_heldout_b - wiki_spline_b(L) on SHARED anchor resamples (same anchors underlie fit and held-out hosts); inside <=> 0 in [pct2.5, pct97.5] of D; scoring curve = full-set population, constant-cohort variant reported",
        "H6 denominators: registered 140 (10x7x2) does not match the 8-bin grid (96 added 2026-08-08) or per-config windows; scored on evaluable cells with ceil(0.90*n) and the per-config cap kept at 3; mismatch disclosed in the block",
        "duplicate (anchor,cell) rows in the merged scores are averaged (cos), OR-ed (truncated), max-ed (realized); count reported in meta",
        "constant cohort and the 400 floor are computed on the full frozen anchor file (not the subset present in scores), so the fit floor is a property of the frozen population",
        "gate-term critical length population: splice/enwiki, positions pooled, full set",
        "NevIR bridge: pairwise accuracy = mean over (anchor,position) matched flip/faithful pairs of 1[cos_flip<cos_faithful] (ties 0.5) at L=64, splice/enwiki, with anchor-bootstrap CI",
    ]

    report = {
        "meta": {
            "seed": SEED, "n_boot": n_boot, "n_boot_registered": N_BOOT_REGISTERED,
            "prereg": "PREREGISTRATION_E2.md sections 2-4 (frozen by tag prereg-e2)",
            "inputs": {"scores": str(args.scores), "scores_sha256": sha256(args.scores),
                       "anchors": str(ANCHORS), "anchors_sha256": sha256(ANCHORS),
                       "stimuli": args.stimuli, "membership": args.membership,
                       "relabel": args.relabel, "windows": args.windows},
            "sweep_meta": sweep_meta, "duplicate_rows_merged": dupes,
            "configs": configs, "windows_used": windows or None,
            "production_config": production,
            "constant_cohort_n": n_cohort_all, "fit_floor": fit_floor,
            "pinned_by_module": pinned_by_module,
        },
        "attrition_crosscheck": attr_check,
        "cells": {}, "fits": {}, "lstar": {},
        "hypotheses": {}, "descriptives": {}, "nevir_bridge": {},
        "label_noise_ceiling": None,
    }

    POS = ["early", "middle", "late"]
    PAIRC = {"flip": 0, "faithful": 1, "scope": 2}

    # Per-config working state used by the hypothesis assembly.
    S = {}

    for ci_idx, enc in enumerate(configs):
        groups = per_enc[enc]
        present = sorted({a for cell in groups.values() for (_, a, *_r) in cell})
        pres_arr = np.array(present, dtype=np.int64)
        g2p_full = {g: i for i, g in enumerate(present)}
        cohort = [g for g in present if cohort_mask[g]]
        g2p_coh = {g: i for i, g in enumerate(cohort)}
        pops = {"full_set": (present, g2p_full,
                             weight_matrix([SEED, 11, ci_idx, 0], len(present), n_boot))}
        if cohort:
            pops["constant_cohort"] = (cohort, g2p_coh,
                                       weight_matrix([SEED, 11, ci_idx, 1], len(cohort), n_boot))
        window = windows.get(enc)

        # ------- organize obs per (arm, host, L): arrays
        cellarr = {}
        for (arm, host, L), lst in groups.items():
            pos = np.array([POS.index(p) if p in POS else -1 for (p, *_r) in lst])
            aid = np.array([a for (_, a, *_r) in lst])
            pair = np.array([PAIRC.get(pr, -1) for (_, _, pr, *_r) in lst])
            cos = np.array([c for (*_x, c, _rm, _t) in lst])
            rmax = np.array([rm for (*_x, rm, _t) in lst])
            trunc = np.array([t for (*_x, t) in lst], dtype=bool)
            cellarr[(arm, host, L)] = (pos, aid, pair, cos, rmax, trunc)

        # window-consistency check
        mism = 0
        if window:
            for (arm, host, L), (pos, aid, pair, cos, rmax, trunc) in cellarr.items():
                mism += int((( rmax > window) != trunc).sum())

        # ------- bin-level truncation regime per (arm, host)
        bin_frac = {}
        for (arm, host, L), (_p, _a, _pr, _c, _rm, trunc) in cellarr.items():
            bin_frac[(arm, host, L)] = float(trunc.mean()) if len(trunc) else 0.0

        def cell_metrics(arm, host, L, pos_sel, pop_key="full_set", excl_trunc=True,
                         with_ci=True):
            """AUROC / Delta / operating points for one cell. pos_sel: list of position
            codes or None for pooled."""
            plist, g2p, Wm = pops[pop_key]
            arrs = cellarr.get((arm, host, L))
            if arrs is None:
                return None
            pos, aid, pair, cos, rmax, trunc = arrs
            sel = np.ones(len(pos), dtype=bool)
            if pos_sel is not None:
                sel &= np.isin(pos, pos_sel)
            if excl_trunc:
                sel &= ~trunc
            popmask = np.isin(aid, np.array(plist, dtype=np.int64))
            sel &= popmask
            fm = sel & (pair == 0)
            pm = sel & (pair == 1)
            sm = sel & (pair == 2)
            if fm.sum() == 0 or pm.sum() == 0:
                return None
            af = np.array([g2p[g] for g in aid[fm]])
            ap = np.array([g2p[g] for g in aid[pm]])
            cf, cp = cos[fm], cos[pm]
            out = {"n_flip": int(fm.sum()), "n_faithful": int(pm.sum()),
                   "n_anchors": int(len(np.unique(aid[fm])))}
            out["auroc"] = r4(point_auroc(cf, af, cp, ap, len(plist)))
            if with_ci:
                boots = wboot_auroc(cf, af, cp, ap, Wm)
                out["auroc_ci95"] = ci95(boots)
            # per-anchor Delta = mean faithful - mean flip within the cell scope
            dmap = defaultdict(lambda: [[], []])
            for g, c in zip(aid[fm], cf):
                dmap[g][0].append(c)
            for g, c in zip(aid[pm], cp):
                dmap[g][1].append(c)
            danch, dgi = [], []
            for g, (fl, fa) in sorted(dmap.items()):
                if fl and fa:
                    danch.append(float(np.mean(fa)) - float(np.mean(fl)))
                    dgi.append(g2p[g])
            danch = np.array(danch)
            dgi = np.array(dgi, dtype=np.int64)
            if len(danch):
                dd = {"mean": r4(danch.mean()), "median": r4(np.median(danch)),
                      "p10": r4(np.percentile(danch, 10)), "p90": r4(np.percentile(danch, 90))}
                if with_ci:
                    dd["mean_ci95"] = ci95(wboot_mean(danch, dgi, Wm))
                out["delta"] = dd
            ops = {}
            for t in OPS:
                miss = (cf >= t).astype(np.float64)
                fb = (cp < t).astype(np.float64)
                e = {"miss": r4(miss.mean()), "false_block": r4(fb.mean())}
                if with_ci:
                    e["miss_ci95"] = ci95(wboot_mean(miss, af, Wm))
                    e["false_block_ci95"] = ci95(wboot_mean(fb, ap, Wm))
                ops[str(t)] = e
            out["ops"] = ops
            # caliper point estimate (payload-Jaccard within +/-0.05)
            jf = j_affirm[aid[fm]]
            jp = j_para[aid[pm]]
            rng = np.random.default_rng([SEED, 5, ci_idx, GRID.index(L) if L in GRID else 99])
            kf, kp = caliper_match(jf, jp, rng)
            out["caliper"] = {"auroc": r4(plain_auroc(cf[kf], cp[kp])) if len(kf) >= 30 else None,
                              "n_matched": int(len(kf))}
            if sm.sum() and pm.sum():
                asc = np.array([g2p[g] for g in aid[sm]])
                out["scope_control"] = {"auroc": r4(point_auroc(cos[sm], asc, cp, ap, len(plist))),
                                        "n_scope": int(sm.sum())}
            out["_arrs"] = (cf, af, cp, ap, jf, jp)   # stripped before dump
            return out

        # ------- cells table (full set), position grain + pooled
        enc_cells = {}
        for (arm, host, L) in sorted(cellarr.keys(), key=lambda k: (k[0], k[1], k[2])):
            frac = bin_frac[(arm, host, L)]
            ww = frac < 0.5
            entry = {"truncated_frac": r4(frac), "within_window_bin": bool(ww)}
            rmaxs = cellarr[(arm, host, L)][4]
            entry["realized_tokens_median"] = float(np.median(rmaxs)) if len(rmaxs) else None
            for pcode, pname in [(None, "pooled"), (0, "early"), (1, "middle"), (2, "late")]:
                cm = cell_metrics(arm, host, L, None if pcode is None else [pcode],
                                  excl_trunc=ww, with_ci=(pcode is None))
                if cm:
                    cm.pop("_arrs", None)
                    entry[pname] = cm
            if 0.0 < frac < 0.5:   # boundary bin: both-ways analysis
                alt = cell_metrics(arm, host, L, None, excl_trunc=False, with_ci=False)
                if alt:
                    alt.pop("_arrs", None)
                    entry["pooled_incl_truncated"] = {
                        "auroc": alt["auroc"], "delta_mean": (alt.get("delta") or {}).get("mean"),
                        "n_flip": alt["n_flip"]}
            enc_cells.setdefault(arm, {}).setdefault(host, {})[f"L={L}"] = entry
        report["cells"][enc] = enc_cells

        # ------- fit domain (splice, enwiki) and curves per population
        wiki_bins_all = sorted(L for (arm, host, L) in cellarr if arm == "splice" and host == "enwiki")
        domain = [L for L in wiki_bins_all if bin_frac[("splice", "enwiki", L)] < 0.5]
        boundary = [L for L in domain if bin_frac[("splice", "enwiki", L)] > 0.0]
        excluded = [L for L in wiki_bins_all if L not in domain]

        enc_fits, enc_lstar = {}, {}
        curves = {}
        for pop_key in pops:
            plist, g2p, Wm = pops[pop_key]
            dom = [L for L in domain if L >= fit_floor] if pop_key == "constant_cohort" else domain
            per_bin = []
            for L in dom:
                cm = cell_metrics("splice", "enwiki", L, None, pop_key=pop_key,
                                  excl_trunc=True, with_ci=False)
                per_bin.append((L, cm))
            per_bin = [(L, cm) for (L, cm) in per_bin if cm is not None]
            if not per_bin:
                continue
            bins = [L for (L, _) in per_bin]
            au_pt = np.array([cm["auroc"] for (_, cm) in per_bin], dtype=np.float64)
            de_pt = np.array([(cm.get("delta") or {}).get("mean") or np.nan
                              for (_, cm) in per_bin], dtype=np.float64)
            au_boot = np.empty((n_boot, len(bins)))
            de_boot = np.empty((n_boot, len(bins)))
            for k, (L, cm) in enumerate(per_bin):
                cf, af, cp, ap, jf, jp = cm["_arrs"]
                au_boot[:, k] = wboot_auroc(cf, af, cp, ap, Wm)
                dmap = defaultdict(lambda: [[], []])
                for g, c in zip(af, cf):
                    dmap[g][0].append(c)
                for g, c in zip(ap, cp):
                    dmap[g][1].append(c)
                dv, di = [], []
                for g, (fl, fa) in sorted(dmap.items()):
                    if fl and fa:
                        dv.append(float(np.mean(fa)) - float(np.mean(fl)))
                        di.append(g)
                de_boot[:, k] = wboot_mean(np.array(dv), np.array(di, dtype=np.int64), Wm)
            knots_pt = pav_nonincreasing(au_pt[None, :])[0]
            knots_boot = pav_nonincreasing(au_boot)
            fits = {"domain_bins": bins, "boundary_bins": boundary, "excluded_bins": excluded,
                    "auroc_by_bin": {str(L): r4(v) for L, v in zip(bins, au_pt)},
                    "spline_knots": {str(L): r4(v) for L, v in zip(bins, knots_pt)},
                    "delta_by_bin": {str(L): r4(v) for L, v in zip(bins, de_pt)},
                    "measured_delta_64": r4(de_pt[0]) if bins and bins[0] == 64 else None}
            if len(bins) >= MIN_BINS_POWER:
                a_pt, d0_pt, npos = power_fit_rows(bins, de_pt[None, :])
                a_bt, d0_bt, _ = power_fit_rows(bins, de_boot)
                fits["power_law"] = {
                    "alpha": r4(a_pt[0]), "alpha_ci95": ci95(a_bt),
                    "delta0": r4(d0_pt[0]), "delta0_ci95": ci95(d0_bt),
                    "n_positive_bins": int(npos[0]),
                    "boot_undefined_frac": r4(float(np.isnan(a_bt).mean()))}
            else:
                fits["power_law"] = None
                fits["spline_only_reason"] = (f"{len(bins)} within-window bins < {MIN_BINS_POWER}")
            enc_fits[pop_key] = fits
            enc_lstar[pop_key] = {str(a): lstar_block(bins, knots_pt, knots_boot, a)
                                  for a in LEVELS}
            enc_lstar[pop_key]["truncation_Lstar_window_edge"] = window
            curves[pop_key] = {"bins": bins, "knots_pt": knots_pt, "knots_boot": knots_boot,
                               "alpha_boot": (a_bt if len(bins) >= MIN_BINS_POWER else None),
                               "alpha_pt": (float(a_pt[0]) if len(bins) >= MIN_BINS_POWER else None),
                               "Wm": Wm, "plist": plist, "g2p": g2p}
        report["fits"][enc] = enc_fits
        report["lstar"][enc] = enc_lstar

        # realized-token secondary axis (splice/enwiki, all obs)
        if enc_fits:
            for pop_key in enc_fits:
                enc_fits[pop_key]["realized_tokens_median_by_bin"] = {
                    str(L): float(np.median(cellarr[("splice", "enwiki", L)][4]))
                    for L in enc_fits[pop_key]["domain_bins"]
                    if ("splice", "enwiki", L) in cellarr}

        S[enc] = {"pops": pops, "cellarr": cellarr, "bin_frac": bin_frac,
                  "curves": curves, "window": window, "domain": domain,
                  "cell_metrics": cell_metrics, "window_flag_mismatches": mism,
                  "wiki_bins_all": wiki_bins_all}

    # ---------------------------------------------------------------- Delta_lex / H5 (lexical)
    lex = None
    if stimuli:
        lex_bins = sorted({L for (_a, L) in stimuli})
        by_bin = defaultdict(list)
        for (aidn, L), t in stimuli.items():
            by_bin[L].append((aidn, t))
        anchors_lex = sorted({aidn for (aidn, _L) in stimuli})
        la2i = {a: i for i, a in enumerate(anchors_lex)}
        Wm_lex = weight_matrix([SEED, 9, 0, 0], len(anchors_lex), n_boot)
        dflip = np.full((len(anchors_lex), len(lex_bins)), np.nan)
        dfaith = np.full_like(dflip, np.nan)
        jflip_pass = np.full_like(dflip, np.nan)   # whole-passage J per class (H5 observed)
        jfaith_pass = np.full_like(dflip, np.nan)
        s_host = np.full_like(dflip, np.nan)       # measured host set size
        payload = {}
        for k, L in enumerate(lex_bins):
            for aidn, t in by_bin[L]:
                i = la2i[aidn]
                jf = jaccard(t["orig"], t["affirm"])
                jp = jaccard(t["orig"], t["para"])
                dflip[i, k] = 1.0 - jf
                dfaith[i, k] = 1.0 - jp
                jflip_pass[i, k] = jf
                jfaith_pass[i, k] = jp
                if aidn not in payload:
                    a = anchors[anchor_index[aidn]]
                    P = toks(a["payload_orig"])
                    Qa, Qp = toks(a["payload_affirm"]), toks(a["payload_para"])
                    payload[aidn] = (P, Qa, Qp)
                P, Qa, Qp = payload[aidn]
                s_host[i, k] = len(toks(t["orig"]) - (P | Qa | Qp))
        # Delta_lex means + alpha_lex (flip primary)
        mflip = np.nanmean(dflip, axis=0)[None, :]
        mfaith = np.nanmean(dfaith, axis=0)[None, :]
        a_lex_pt, _d0, _n = power_fit_rows(lex_bins, mflip)
        # boot: weighted bin means per resample
        mb = np.empty((n_boot, len(lex_bins)))
        for k in range(len(lex_bins)):
            col = dflip[:, k]
            okm = ~np.isnan(col)
            mb[:, k] = wboot_mean(col[okm], np.flatnonzero(okm), Wm_lex)
        a_lex_bt, _d0b, _nb = power_fit_rows(lex_bins, mb)
        a_faith_pt, _d, _n2 = power_fit_rows(lex_bins, mfaith)
        # H5 observed + closed-form prediction per bin
        h5 = {}
        for k, L in enumerate(lex_bins):
            okm = ~np.isnan(jflip_pass[:, k])
            n_a = int(okm.sum())
            if n_a < 3:
                continue
            xs = np.concatenate([jflip_pass[okm, k], jfaith_pass[okm, k]])
            ys = np.concatenate([np.ones(n_a), np.zeros(n_a)])
            r_obs = point_biserial(xs, ys)
            aidx = np.concatenate([np.flatnonzero(okm), np.flatnonzero(okm)])
            rb = np.full(n_boot, np.nan)
            for s0 in range(0, n_boot, 4096):
                w = Wm_lex[s0:s0 + 4096][:, aidx].astype(np.float64)
                sw = w.sum(axis=1)
                mx = (w * xs).sum(1) / sw
                my2 = (w * ys).sum(1) / sw
                vx = (w * (xs - mx[:, None]) ** 2).sum(1) / sw
                vy = (w * (ys - my2[:, None]) ** 2).sum(1) / sw
                cxy = (w * (xs - mx[:, None]) * (ys - my2[:, None])).sum(1) / sw
                with np.errstate(invalid="ignore", divide="ignore"):
                    rb[s0:s0 + 4096] = cxy / np.sqrt(vx * vy)
            sbar = float(np.nanmedian(s_host[:, k]))
            pf, pp = [], []
            for aidn in (anchors_lex[i] for i in np.flatnonzero(okm)):
                P, Qa, Qp = payload[aidn]
                pf.append((sbar + len(P & Qa)) / (sbar + len(P | Qa)))
                pp.append((sbar + len(P & Qp)) / (sbar + len(P | Qp)))
            r_pred = point_biserial(np.concatenate([pf, pp]),
                                    np.concatenate([np.ones(len(pf)), np.zeros(len(pp))]))
            h5[str(L)] = {"n_anchors": n_a, "r_obs": r4(r_obs), "r_obs_ci95": ci95(rb),
                          "s_host_median": r4(sbar), "s_host_source": "measured",
                          "r_pred_closed_form": r4(r_pred),
                          "deviation": r4(r_obs - r_pred)}
        lex = {"bins": lex_bins, "n_anchors": len(anchors_lex),
               "delta_lex_flip_by_bin": {str(L): r4(v) for L, v in zip(lex_bins, mflip[0])},
               "delta_lex_faithful_by_bin": {str(L): r4(v) for L, v in zip(lex_bins, mfaith[0])},
               "alpha_lex_flip": r4(a_lex_pt[0]) if len(lex_bins) >= MIN_BINS_POWER else None,
               "alpha_lex_flip_ci95": ci95(a_lex_bt) if len(lex_bins) >= MIN_BINS_POWER else None,
               "alpha_lex_faithful": r4(a_faith_pt[0]) if len(lex_bins) >= MIN_BINS_POWER else None,
               "alpha_lex_boot": a_lex_bt if len(lex_bins) >= MIN_BINS_POWER else None,
               "h5_by_bin": h5}
        report["descriptives"]["delta_lex_overlay"] = {
            k: v for k, v in lex.items() if k not in ("alpha_lex_boot",)}

    # ------------------------------------------------------------------------ hypotheses
    def within_window_bins(enc, arm, host, lo=None):
        st = S[enc]
        bins = [L for (a, h, L) in st["cellarr"] if a == arm and h == host
                and st["bin_frac"][(a, h, L)] < 0.5]
        bins = sorted(set(bins))
        return [L for L in bins if lo is None or L >= lo]

    def bar_auroc_upper(enc, pop_key, arm, host, bins):
        """Per-bin AUROC bootstrap 95% upper bounds (intersection-test ingredient)."""
        st = S[enc]
        outs = {}
        for L in bins:
            cm = st["cell_metrics"](arm, host, L, None, pop_key=pop_key,
                                    excl_trunc=True, with_ci=True)
            if cm is None:
                continue
            outs[str(L)] = {"auroc": cm["auroc"], "ci95": cm["auroc_ci95"]}
        return outs

    hyp = report["hypotheses"]

    # ---- H1
    h1_blocks = []
    for pop_key in ("full_set", "constant_cohort"):
        stat = {}
        for enc in configs:
            f = report["fits"].get(enc, {}).get(pop_key)
            if not f or not f.get("power_law"):
                stat[enc] = {"alpha": None, "note": "spline_only"}
                continue
            pl = f["power_law"]
            e = {"alpha": pl["alpha"], "alpha_ci95": pl["alpha_ci95"], "delta0": pl["delta0"],
                 "in_band_0.8_1.2": (pl["alpha"] is not None and 0.8 <= pl["alpha"] <= 1.2),
                 "alpha_vs_1": ("DEPARTS" if (pl["alpha_ci95"][0] is not None and
                                              (pl["alpha_ci95"][0] > 1.0 or pl["alpha_ci95"][1] < 1.0))
                                else "CONSISTENT")}
            if lex and lex.get("alpha_lex_boot") is not None:
                ab = S[enc]["curves"].get(pop_key, {}).get("alpha_boot")
                if ab is not None:
                    dif = ab - lex["alpha_lex_boot"]
                    e["alpha_minus_alpha_lex_ci95"] = ci95(dif)
                    lo_, hi_ = e["alpha_minus_alpha_lex_ci95"]
                    e["alpha_vs_lex"] = ("DEPARTS" if lo_ is not None and (lo_ > 0 or hi_ < 0)
                                         else "CONSISTENT")
            stat[enc] = e
        mp = membership.get("mean_pooled")
        if mp:
            missing = [c for c in mp if c not in configs]
            inset = [c for c in mp if c in configs]
            ok = [stat[c].get("in_band_0.8_1.2") for c in inset]
            verdict = ("PASS" if inset and all(v is True for v in ok)
                       else "FAIL" if any(v is False for v in ok) else "PENDING_FITS")
            note = f"membership={inset}; unknown={missing}" if missing else f"membership={inset}"
        else:
            verdict, note = "PENDING_MEMBERSHIP", "mean-pooled list not provided (section 6 tag-time item)"
        h1_blocks.append({"bar": "alpha in [0.8,1.2] for the mean-pooled set; alpha tested vs alpha_lex=1",
                          "population": pop_key, "statistic": stat,
                          "ci": "per-config alpha_ci95 above", "verdict": verdict,
                          "censored_notes": [note] + ([] if lex else ["Delta_lex overlay PENDING_STIMULI"])})
    hyp["H1"] = h1_blocks

    # ---- H2a / H2b / H2c
    for pop_key in ("full_set", "constant_cohort"):
        pass  # populations handled inside each clause below

    def h2a_block(pop_key, arm, host, confirmatory=False):
        per, vac = {}, []
        allpass = True
        for enc in configs:
            bins = within_window_bins(enc, arm, host, lo=512)
            if not bins:
                vac.append(enc)
                per[enc] = {"evaluable_bins": [], "verdict": "NO_WITHIN_WINDOW_BIN_>=512"}
                continue
            tab = bar_auroc_upper(enc, pop_key, arm, host, bins)
            uppers = [v["ci95"][1] for v in tab.values() if v["ci95"][1] is not None]
            ok = bool(uppers) and all(u < 0.60 for u in uppers)
            per[enc] = {"evaluable_bins": bins, "per_bin": tab,
                        "max_upper": max(uppers) if uppers else None,
                        "pass": ok}
            allpass &= ok
        verdict = "PASS" if allpass and not vac else ("FAIL" if not allpass else "PASS")
        if confirmatory:
            verdict = f"CONFIRMATORY_{verdict}"
        return {"bar": "every config: anchor-boot 95% upper bound of flip-vs-faithful AUROC < 0.60 "
                       "at L=512 and every larger within-window bin (SPLICE raw)",
                "population": pop_key, "statistic": per, "ci": "per-bin ci95 in statistic",
                "verdict": verdict,
                "censored_notes": ([f"vacuous (no within-window bin >=512): {vac}"] if vac else [])
                + [f"host={host}, arm={arm} (host pin: see meta.pinned_by_module)"]}

    hyp["H2a"] = [h2a_block(pk, "splice", "enwiki") for pk in ("full_set", "constant_cohort")]

    def h2b_block(pop_key):
        per, vac = {}, []
        allpass = True
        for enc in configs:
            st = S[enc]
            bins = within_window_bins(enc, "splice", "enwiki", lo=1024)
            if not bins:
                vac.append(enc)
                per[enc] = {"evaluable_bins": [], "verdict": "VACUOUS_FOR_CONFIG"}
                continue
            plist, g2p, Wm = st["pops"][pop_key]
            rows = {}
            uppers = []
            for L in bins:
                cm = st["cell_metrics"]("splice", "enwiki", L, None, pop_key=pop_key,
                                        excl_trunc=True, with_ci=False)
                if cm is None:
                    continue
                cf, af, cp, ap, jf, jp = cm["_arrs"]
                rng = np.random.default_rng([SEED, 6, configs.index(enc), GRID.index(L)])
                cb = caliper_boot(cf, af, jf, cp, ap, jp, Wm, rng)
                kf, kp = caliper_match(jf, jp, rng)
                pt = plain_auroc(cf[kf], cp[kp]) if len(kf) >= 30 else float("nan")
                c = ci95(cb)
                rows[str(L)] = {"auroc_caliper": r4(pt), "ci95": c, "n_matched": int(len(kf)),
                                "boot_undefined_frac": r4(float(np.isnan(cb).mean()))}
                if c[1] is not None:
                    uppers.append(c[1])
            ok = bool(uppers) and all(u < 0.65 for u in uppers)
            per[enc] = {"evaluable_bins": bins, "per_bin": rows,
                        "max_upper": max(uppers) if uppers else None, "pass": ok}
            allpass &= ok
        return {"bar": "every config: caliper-matched (payload-Jaccard +/-0.05) anchor-boot 95% "
                       "upper bound < 0.65 at L=1024 and every larger within-window bin",
                "population": pop_key, "statistic": per, "ci": "per-bin ci95 in statistic",
                "verdict": "PASS" if allpass else "FAIL",
                "censored_notes": ([f"vacuous (window < 1024): {vac} — bar binds only "
                                    "long-context configs; flagged as amendment candidate"] if vac else [])}

    hyp["H2b"] = [h2b_block(pk) for pk in ("full_set", "constant_cohort")]

    def h2c_block(pop_key):
        if not production or production not in configs:
            return {"bar": "production nomic-MRL-256: 95% CI containing or below 0.55 in every "
                           "within-window SPLICE cell (all hosts, all positions, incl L=64)",
                    "population": pop_key, "statistic": None, "ci": None,
                    "verdict": "PENDING_MEMBERSHIP",
                    "censored_notes": ["production config not identified"]}
        st = S[production]
        cellsb, worst = {}, None
        ok = True
        for (arm, host, L) in sorted(st["cellarr"].keys()):
            if arm != "splice" or st["bin_frac"][(arm, host, L)] >= 0.5:
                continue
            for pcode, pname in [(0, "early"), (1, "middle"), (2, "late")]:
                cm = st["cell_metrics"](arm, host, L, [pcode], pop_key=pop_key,
                                        excl_trunc=True, with_ci=True)
                if cm is None:
                    continue
                lo_ = cm["auroc_ci95"][0]
                cellsb[f"{host}/L={L}/{pname}"] = {"auroc": cm["auroc"], "ci95": cm["auroc_ci95"]}
                if lo_ is not None:
                    if worst is None or lo_ > worst:
                        worst = lo_
                    ok &= lo_ <= 0.55
        return {"bar": "production path <=0.55 at every bin incl L=64 (CI lower bound <=0.55 "
                       "in every within-window SPLICE cell)",
                "population": pop_key, "statistic": {"config": production, "cells": cellsb,
                                                     "max_ci_lower": worst},
                "ci": "per-cell ci95 in statistic", "verdict": "PASS" if ok else "FAIL",
                "censored_notes": ["short-L failure is reported as such, not absorbed (prereg scoring note)"]}

    hyp["H2c"] = [h2c_block(pk) for pk in ("full_set", "constant_cohort")]

    # ---- H3a
    def h3a_block(pop_key):
        per = {}
        hits, evaluable = 0, 0
        for enc in configs:
            st = S[enc]
            wmax = st["window"]
            ww = within_window_bins(enc, "splice", "enwiki")
            if not ww:
                per[enc] = {"eligible_bins": [], "note": "no within-window bins"}
                continue
            lim = (wmax / 2.0) if wmax else (max(ww) / 2.0)
            bins = [L for L in ww if L <= lim]
            if not bins:
                per[enc] = {"eligible_bins": [], "note": f"no bins <= window/2 ({lim})"}
                continue
            plist, g2p, Wm = st["pops"][pop_key]
            def pooled(pos_codes):
                cf_l, af_l, cp_l, ap_l = [], [], [], []
                for L in bins:
                    cm = st["cell_metrics"]("splice", "enwiki", L, pos_codes,
                                            pop_key=pop_key, excl_trunc=True, with_ci=False)
                    if cm is None:
                        continue
                    cf, af, cp, ap, _jf, _jp = cm["_arrs"]
                    cf_l.append(cf); af_l.append(af); cp_l.append(cp); ap_l.append(ap)
                if not cf_l:
                    return None
                return (np.concatenate(cf_l), np.concatenate(af_l),
                        np.concatenate(cp_l), np.concatenate(ap_l))
            e = pooled([0]); l = pooled([2])
            if e is None or l is None:
                per[enc] = {"eligible_bins": bins, "note": "missing early/late cells"}
                continue
            a_e = point_auroc(*e, len(plist)); a_l = point_auroc(*l, len(plist))
            d_boot = wboot_auroc(*e, Wm) - wboot_auroc(*l, Wm)
            delta = a_e - a_l
            evaluable += 1
            hit = delta >= 0.05
            hits += int(hit)
            per[enc] = {"eligible_bins": bins, "auroc_early": r4(a_e), "auroc_late": r4(a_l),
                        "delta": r4(delta), "delta_ci95": ci95(d_boot), "hit": bool(hit),
                        "window_source": "table" if wmax else "max_ww_bin/2 (window unknown)"}
        need = math.ceil(evaluable / 2) if evaluable else None
        verdict = ("PASS" if evaluable and hits >= need else
                   "FAIL" if evaluable else "PENDING_DATA")
        return {"bar": "AUROC(early)-AUROC(late) >= 0.05 at L <= window/2 for >= half the configs",
                "population": pop_key,
                "statistic": {"per_config": per, "hits": hits, "evaluable": evaluable,
                              "needed": need},
                "ci": "per-config delta_ci95", "verdict": verdict, "censored_notes": []}

    hyp["H3a"] = [h3a_block(pk) for pk in ("full_set", "constant_cohort")]

    # ---- H4 + degeneracy twin + gate-term critical length
    def h4_block(pop_key, arm="splice", host="enwiki", confirmatory=False):
        per = {}
        allpass = True
        for enc in configs:
            st = S[enc]
            ww = within_window_bins(enc, arm, host)
            b256 = [L for L in ww if L >= 256]
            b128 = [L for L in ww if L >= 128]
            det = {"clause_085": {}, "clause_095": {}}
            ok1 = ok2 = True
            have1 = have2 = False
            for L in b256:
                cm = st["cell_metrics"](arm, host, L, None, pop_key=pop_key,
                                        excl_trunc=True, with_ci=False)
                if cm:
                    m = cm["ops"]["0.85"]["miss"]
                    det["clause_085"][str(L)] = m
                    ok1 &= (m is not None and m >= 0.95); have1 = True
            for L in b128:
                cm = st["cell_metrics"](arm, host, L, None, pop_key=pop_key,
                                        excl_trunc=True, with_ci=False)
                if cm:
                    m = cm["ops"]["0.95"]["miss"]
                    det["clause_095"][str(L)] = m
                    ok2 &= (m is not None and m >= 0.90); have2 = True
            cfg_pass = (ok1 and have1) and (ok2 and have2)
            per[enc] = {"miss_0.85_by_bin_L>=256": det["clause_085"],
                        "miss_0.95_by_bin_L>=128": det["clause_095"],
                        "evaluable": bool(have1 and have2), "pass": bool(cfg_pass)}
            allpass &= cfg_pass
        v = "PASS" if allpass else "FAIL"
        return {"bar": "miss@0.85 >= 0.95 for every config at every within-window bin >=256; "
                       "miss@0.95 >= 0.90 at every within-window bin >=128 (SPLICE, positions pooled)",
                "population": pop_key, "statistic": per, "ci": None,
                "verdict": f"CONFIRMATORY_{v}" if confirmatory else v,
                "censored_notes": [f"host={host} (pin)"]}

    hyp["H4"] = [h4_block(pk) for pk in ("full_set", "constant_cohort")]

    degen, gate_term = {}, {}
    for enc in configs:
        st = S[enc]
        ww = within_window_bins(enc, "splice", "enwiki")
        reg = [L for L in ww if L >= 256]
        mm, mfb = None, None
        for L in reg:
            cm = st["cell_metrics"]("splice", "enwiki", L, None, excl_trunc=True, with_ci=False)
            if not cm:
                continue
            for t in ("0.3", "0.4", "0.6", "0.8", "0.85"):
                m = cm["ops"][t]["miss"]; fb = cm["ops"][t]["false_block"]
                mm = m if mm is None else min(mm, m)
                mfb = fb if mfb is None else max(mfb, fb)
        degen[enc] = {"region": "L>=256, thresholds<=0.85", "min_miss": mm, "max_false_block": mfb}
        crit = None
        for L in ww:
            cm = st["cell_metrics"]("splice", "enwiki", L, None, excl_trunc=True, with_ci=False)
            if cm and all(cm["ops"][t]["miss"] is not None and cm["ops"][t]["miss"] >= 0.99
                          for t in ("0.3", "0.4", "0.6", "0.8", "0.85")):
                crit = L
                break
        gate_term[enc] = crit
    report["descriptives"]["degeneracy_twin"] = {
        "definition": "by L>=256 at thresholds <=0.85 the gate converges to (miss->1, false_block->0); "
                      "descriptive, no pass/fail", "per_config": degen}
    report["descriptives"]["gate_term_critical_length"] = {
        "definition": "smallest within-window L with flip miss >= 0.99 at every operating point <= 0.85",
        "per_config": gate_term}

    # ---- H3b (deployment fact, zero confirmatory weight)
    h3b = {}
    for enc in configs:
        st = S[enc]
        rows = {}
        for (arm, host, L) in sorted(st["cellarr"].keys()):
            if arm != "splice" or host != "enwiki":
                continue
            if st["bin_frac"][(arm, host, L)] < 0.5:
                continue
            pos, aid, pair, cos, rmax, trunc = st["cellarr"][(arm, host, L)]
            m = (pos == 2) & (pair == 0) & trunc
            if m.sum():
                rows[str(L)] = {"n": int(m.sum()),
                                **{f"miss@{t}": r4(float((cos[m] >= t).mean())) for t in OPS}}
        h3b[enc] = {"effective_window": S[enc]["window"], "late_flip_beyond_window": rows}
    report["descriptives"]["H3b"] = {
        "status": "reported deployment fact — carries zero confirmatory weight", "per_config": h3b}

    # ---- H5
    def h5_block():
        if not stimuli:
            return {"bar": "|point-biserial r(whole-passage token-Jaccard, class)| < 0.10 by L=512",
                    "population": "lexical (encoder-blind), splice/enwiki",
                    "statistic": None, "ci": None, "verdict": "PENDING_STIMULI",
                    "censored_notes": ["whole-passage Jaccard needs the titration stimuli"]}
        tab = lex["h5_by_bin"]
        need = [L for L in GRID if L >= 512]
        have = [L for L in need if str(L) in tab]
        missing = [L for L in need if str(L) not in tab]
        ok = bool(have) and all(abs(tab[str(L)]["r_obs"]) < 0.10 for L in have
                                if tab[str(L)]["r_obs"] is not None)
        verdict = "PASS" if ok and not missing else ("FAIL" if have and not ok else "PENDING_STIMULI_BINS")
        if ok and missing:
            verdict = "PASS_ON_AVAILABLE_BINS"
        return {"bar": "|r| < 0.10 at L=512 and every larger bin; observed r reported against "
                       "its closed-form prediction from payload Jaccards (deviation is the finding)",
                "population": "lexical (encoder-blind), splice/enwiki",
                "statistic": {"by_bin": tab, "bins_scored": have, "bins_missing_stimuli": missing},
                "ci": "per-bin r_obs_ci95", "verdict": verdict,
                "censored_notes": []}

    hyp["H5"] = [h5_block()]

    # ---- H6
    def h6_block(pop_key):
        cells_out, not_eval = {}, []
        inside_n = total = 0
        per_cfg_out = defaultdict(int)
        per_cfg_tot = defaultdict(int)
        for enc in configs:
            st = S[enc]
            cur = st["curves"].get(pop_key)
            if not cur:
                not_eval.append(f"{enc}: no wiki curve")
                continue
            bins = cur["bins"]
            for host in ("pmc", "rfc"):
                for L in within_window_bins(enc, "splice", host):
                    if L not in bins:
                        not_eval.append(f"{enc}/{host}/L={L}: bin outside wiki fit domain")
                        continue
                    cm = st["cell_metrics"]("splice", host, L, None, pop_key=pop_key,
                                            excl_trunc=True, with_ci=False)
                    if cm is None:
                        not_eval.append(f"{enc}/{host}/L={L}: no data")
                        continue
                    cf, af, cp, ap, _jf, _jp = cm["_arrs"]
                    obs_b = wboot_auroc(cf, af, cp, ap, cur["Wm"])
                    k = bins.index(L)
                    D = obs_b - cur["knots_boot"][:, k]
                    dci = ci95(D)
                    pred = r4(cur["knots_pt"][k])
                    inside = (dci[0] is not None and dci[0] <= 0 <= dci[1])
                    cells_out[f"{enc}/{host}/L={L}"] = {
                        "obs_auroc": cm["auroc"], "pred_wiki_spline": pred,
                        "diff_ci95": dci, "inside": bool(inside)}
                    total += 1
                    per_cfg_tot[enc] += 1
                    if inside:
                        inside_n += 1
                    else:
                        per_cfg_out[enc] += 1
        need = math.ceil(H6_FRAC * total) if total else None
        cap_viol = {c: n for c, n in per_cfg_out.items() if n > H6_CONFIG_CAP}
        verdict = ("PENDING_DATA" if total == 0 else
                   "PASS" if inside_n >= need and not cap_viol else "FAIL")
        misses = [k for k, v in cells_out.items() if not v["inside"]]
        return {"bar": f">= {H6_REGISTERED_CELLS * H6_FRAC:.0f}/{H6_REGISTERED_CELLS} held-out cells inside "
                       "the wiki curves' 95% prediction bands AND no config > 3/14 outside; every miss listed",
                "population": pop_key,
                "statistic": {"cells": cells_out, "inside": inside_n, "evaluable": total,
                              "needed_at_0.90": need, "per_config_outside": dict(per_cfg_out),
                              "config_cap_violations": cap_viol, "misses": misses,
                              "registered_cell_count": H6_REGISTERED_CELLS,
                              "registered_vs_evaluable_mismatch": total != H6_REGISTERED_CELLS,
                              "not_evaluable": not_eval},
                "ci": "per-cell diff_ci95 (obs - predicted curve, shared anchor resamples)",
                "verdict": verdict,
                "censored_notes": (["registered denominator 140 does not match evaluable "
                                    f"count {total}; scored at ceil(0.90*evaluable) with the "
                                    "per-config cap kept at 3 — amendment candidate"]
                                   if total and total != H6_REGISTERED_CELLS else [])}

    hyp["H6"] = [h6_block(pk) for pk in ("full_set", "constant_cohort")]

    # ---- external anchor (NevIR)
    def ext_anchor_block():
        nset = membership.get("nevir_at_below_random")
        if not nset:
            return {"bar": "NevIR at/below-random set: Delta(64) < 0.05 (measured first bin)",
                    "population": "full_set", "statistic": None, "ci": None,
                    "verdict": "PENDING_MEMBERSHIP",
                    "censored_notes": ["set enumerated in section 6 at tag time, with citation"]}
        stat, ok = {}, True
        for enc in nset:
            if enc not in configs:
                stat[enc] = {"note": "config not in sweep"}
                ok = False
                continue
            f = report["fits"].get(enc, {}).get("full_set", {})
            d64 = f.get("measured_delta_64")
            cm = S[enc]["cell_metrics"]("splice", "enwiki", 64, None, with_ci=True) \
                if ("splice", "enwiki", 64) in S[enc]["cellarr"] else None
            ci_ = (cm.get("delta") or {}).get("mean_ci95") if cm else None
            stat[enc] = {"delta_64": d64, "delta_64_ci95": ci_}
            ok &= (d64 is not None and d64 < 0.05)
        return {"bar": "Delta(64) < 0.05 for every config NevIR scores at/below random",
                "population": "full_set", "statistic": stat, "ci": "per-config delta_64_ci95",
                "verdict": "PASS" if ok else "FAIL", "censored_notes": []}

    hyp["external_anchor"] = [ext_anchor_block()]

    # ---- NATIVE arm confirmatory (same bars, ecological)
    native_hosts = sorted({h for enc in configs for (a, h, _L) in S[enc]["cellarr"] if a == "native"})
    if native_hosts:
        report["descriptives"]["native_confirmatory"] = {
            "H2a": [h2a_block("full_set", "native", native_hosts[0], confirmatory=True)],
            "H4": [h4_block("full_set", arm="native", host=native_hosts[0], confirmatory=True)]}
    else:
        report["descriptives"]["native_confirmatory"] = {"status": "no native-arm cells present"}

    # ---- scope control (descriptive)
    scope_tab = {}
    for enc in configs:
        st = S[enc]
        rows = {}
        for (arm, host, L) in sorted(st["cellarr"].keys()):
            if arm != "splice":
                continue
            cm = st["cell_metrics"](arm, host, L, None, excl_trunc=True, with_ci=False)
            if cm and "scope_control" in cm:
                rows[f"{host}/L={L}"] = cm["scope_control"]
        if rows:
            scope_tab[enc] = rows
    report["descriptives"]["scope_control"] = {
        "definition": "scope-vs-faithful AUROC (high-overlap flip control), descriptive",
        "per_config": scope_tab}

    # ---- NevIR bridge (L=64 cell)
    nevir = {}
    for enc in configs:
        st = S[enc]
        key = ("splice", "enwiki", 64)
        if key not in st["cellarr"]:
            continue
        pos, aid, pair, cos, rmax, trunc = st["cellarr"][key]
        pmap = {}
        for i in range(len(pos)):
            if pair[i] in (0, 1) and not trunc[i]:
                pmap.setdefault((aid[i], pos[i]), {})[int(pair[i])] = cos[i]
        acc, ga = [], []
        for (g, _p), d in sorted(pmap.items()):
            if 0 in d and 1 in d:
                acc.append(1.0 if d[0] < d[1] else (0.5 if d[0] == d[1] else 0.0))
                ga.append(g)
        if not acc:
            continue
        plist, g2p, Wm = st["pops"]["full_set"]
        gi = np.array([g2p[g] for g in ga], dtype=np.int64)
        accv = np.array(acc)
        nevir[enc] = {"pairwise_accuracy": r4(accv.mean()),
                      "ci95": ci95(wboot_mean(accv, gi, Wm)),
                      "n_pairs": len(acc)}
    report["nevir_bridge"] = {
        "definition": "NevIR-style pairwise accuracy on the L=64 splice/enwiki cell: "
                      "1[cos_flip < cos_faithful] per (anchor, position), ties 0.5",
        "per_config": nevir}

    # ---- label-noise ceiling (kappa)
    if args.relabel:
        rows = [json.loads(l) for l in Path(args.relabel).read_text(encoding="utf-8").splitlines()
                if l.strip()]
        ka = cohen_kappa([r["annotator_a"] for r in rows], [r["annotator_b"] for r in rows])
        agree = (sum(1 for r in rows if r["annotator_a"] == r["annotator_b"]) / len(rows)
                 if rows else None)
        report["label_noise_ceiling"] = {
            "kappa": r4(ka) if ka is not None else None, "percent_agreement": r4(agree),
            "n": len(rows),
            "note": "E2-P5 two-annotator relabel, standalone semantics, annotators blind to "
                    "all hypotheses; reported beside every decision-axis figure"}
    else:
        report["label_noise_ceiling"] = {"status": "PENDING_RELABEL (E2-P5 arm runs post-tag)"}

    # ---- window flag consistency
    report["meta"]["window_flag_mismatches"] = {
        enc: S[enc]["window_flag_mismatches"] for enc in configs if S[enc]["window"]}

    # ------------------------------------------------------------------------- output
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(sanitize(report), indent=2) + "\n", encoding="utf-8")

    print(f"configs analyzed: {len(configs)}")
    for h in ("H1", "H2a", "H2b", "H2c", "H3a", "H4", "H5", "H6", "external_anchor"):
        for blk in hyp.get(h, []):
            print(f"  {h:16s} [{blk['population']:15s}] {blk['verdict']}")
    for enc in configs:
        for pop_key, tab in report["lstar"].get(enc, {}).items():
            if not isinstance(tab, dict):
                continue
            parts = []
            for lv in LEVELS:
                b = tab.get(str(lv))
                if b:
                    parts.append(f"L*({lv})={b['lstar']}")
            if parts:
                print(f"  {enc[:44]:44s} [{pop_key:15s}] " + "  ".join(parts))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
