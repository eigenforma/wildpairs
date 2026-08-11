"""E4: the Floor Lemma survey (PREREGISTRATION_E4.md, FROZEN at tag prereg-e4 - the
embedding pass is post-tag legal). Vectors RETAINED across three frozen registers x the
nine pinned configurations under the E3 fresh-fp32 pins (PREREGISTRATION_E3 section 2:
fp32 everywhere, one pinned device per config, E3-P2 assignments; floors are geometry
claims about the embedding cloud, not score-parity claims - no cross-regime comparison).

Registers (frozen; deduped by exact text, first-occurrence order):
  errata_g2 : corpus/e1_errata/pairs_g1g2.jsonl - g2_orig + g2_corr of the Verified-prose
              primary (status==Verified, code_primary==false)
  condaqa   : corpus/e2_dilution/condaqa_{train,dev,test}.json - unique (split, PassageID,
              PassageEditID) -> sentence1 variant texts (build_anchors.py extraction verbatim)
  e3        : corpus/e3_composed_sweep_sample.jsonl - text_a + text_b (frozen sample)

Per (config, register): unit-normalize (fp64), mu_hat = normalized mean, theta_u =
arccos(clip(<u, mu_hat>)); report theta max/p99/p90/median; HARD floor = cos(2*theta_max),
PRACTICAL floor = cos(2*theta_p99); vacuity verdicts vs {0.30, 0.40, 0.60, 0.80, 0.85,
0.95}; observed min pairwise cosine (EXACT when n <= 6000, else a documented subsample of
6000 with seed 20260805); scope condition theta_max <= pi/2 recorded (lemma scope).
Machine check (a): synthetic spherical-cap sampling verifying the bound and its tightness
(constructed antipodal-residual pair achieves cos 2*theta exactly); (b): empirical min >=
hard floor in every cell. B1-B3 scorecard per the frozen bars.

Vectors: <vectors-dir>/<config-slug>__<register>.npy (fp16) + .meta.json sidecar. ALL
statistics are computed FROM the retained fp16 vectors (single source of truth; any
reviewer recomputation reads the same npy). Frozen JSON: results/e4_floor_survey.json.

Run per node (E3-P2 pins; SWEEP_ONLY selects the node's configs, e1/e3 convention):
  ST_DEVICE=cuda ST_FP32=1 SWEEP_ONLY=mxbai,bge,e5 python3 harness/e4/floor_survey.py \
      --vectors-dir results/<host>/e4_vectors
then collect all cells into results/e4_vectors/ on Wu and freeze:
  python harness/e4/floor_survey.py --stats-only --vectors-dir results/e4_vectors
Env: SWEEP_ONLY, ST_DEVICE (default cpu), ST_FP32 (force float32), ST_BATCH (default 64),
PAPER_A_REGISTRY (registry location, e1 convention). The production-router config runs
ONLY through intern.pipeline.embedding_router on the pinned Wu-CPU path - no lookalike.
"""
import argparse
import hashlib
import json
import math
import os
import platform
import socket
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY_DIR = Path(os.environ.get("PAPER_A_REGISTRY",
                                   "c:/Users/poeti/Falsifyer/experiments/factorial_pilot"))
ONLY = [s.strip().lower() for s in os.environ.get("SWEEP_ONLY", "").split(",") if s.strip()]

DEFAULT_VDIR = ROOT / "results" / "e4_vectors"
DEFAULT_OUT = ROOT / "results" / "e4_floor_survey.json"
ERRATA = ROOT / "corpus" / "e1_errata" / "pairs_g1g2.jsonl"
CONDAQA = [ROOT / "corpus" / "e2_dilution" / f"condaqa_{s}.json"
           for s in ("train", "dev", "test")]
E3_SAMPLE = ROOT / "corpus" / "e3_composed_sweep_sample.jsonl"

REGISTERS = ("errata_g2", "condaqa", "e3")
OPS = [0.30, 0.40, 0.60, 0.80, 0.85, 0.95]
SEED = 20260805
SUBSAMPLE_N = 6000
SYNTH_THETAS_DEG = [15, 30, 45, 60, 75, 89]
SYNTH_N = 2000
SYNTH_DIM = 768
TOL = 1e-9


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def slug(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in name)[:80]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dedupe(texts):
    seen, out = set(), []
    for t in texts:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def load_registers():
    regs = {}
    rows = [json.loads(l) for l in ERRATA.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    texts = []
    for r in rows:
        if r["status"] == "Verified" and not r["code_primary"]:
            texts.extend([r["g2_orig"], r["g2_corr"]])
    regs["errata_g2"] = (dedupe(texts), [{"path": str(ERRATA), "sha256": sha256_file(ERRATA)}])
    variants, srcs = {}, []
    for p in CONDAQA:
        split = p.stem.split("_")[1]
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                variants.setdefault((split, r["PassageID"], str(r["PassageEditID"])),
                                    r["sentence1"])
        srcs.append({"path": str(p), "sha256": sha256_file(p)})
    regs["condaqa"] = (dedupe(list(variants.values())), srcs)
    texts = []
    for line in E3_SAMPLE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            texts.extend([r["text_a"], r["text_b"]])
    regs["e3"] = (dedupe(texts), [{"path": str(E3_SAMPLE), "sha256": sha256_file(E3_SAMPLE)}])
    return regs


def registry():
    sys.path.insert(0, str(REGISTRY_DIR))
    try:
        from encoders import REGISTRY  # noqa: E402  (Paper A registry, verbatim)
    except Exception as exc:
        sys.exit(f"Paper A registry import failed from {REGISTRY_DIR} "
                 f"({type(exc).__name__}: {exc}); set PAPER_A_REGISTRY (e1 convention)")
    if len(REGISTRY) != 9:
        sys.exit(f"registry carries {len(REGISTRY)} configs, expected the nine pinned")
    return REGISTRY


def is_production(enc) -> bool:
    return getattr(enc, "model_id", None) is None


def embed_texts(enc, texts, device, fp32, batch):
    """Fresh-fp32 E3 regime embedding, unit vectors out. Production config: the audited
    router on the pinned Wu-CPU path only (E3-P2); everything else: sentence-transformers
    on ST_DEVICE, model.float() when ST_FP32 is set."""
    import numpy as np
    if is_production(enc):
        if device != "cpu":
            sys.exit(f"{enc.name!r} is pinned to the Wu-CPU production-router path "
                     f"(E3-P2); refusing ST_DEVICE={device!r}")
        try:
            from intern.pipeline.embedding_router import MRLEmbeddingRouter
        except Exception as exc:
            sys.exit(f"production router import failed ({type(exc).__name__}: {exc}) - "
                     f"this config runs on Wu only, never a lookalike")
        router = MRLEmbeddingRouter()
        chunks = [np.asarray(router.batch_embed(texts[i:i + batch]))
                  for i in range(0, len(texts), batch)]
        emb = np.vstack(chunks)
        runtime = {"path": "intern.pipeline.embedding_router.MRLEmbeddingRouter"}
    else:
        from sentence_transformers import SentenceTransformer
        import sentence_transformers
        model = SentenceTransformer(enc.model_id, device=device)
        if fp32:
            model = model.float()
        emb = model.encode([enc.prefix + t for t in texts], batch_size=batch,
                           normalize_embeddings=True, show_progress_bar=False,
                           convert_to_numpy=True)
        runtime = {"path": "sentence_transformers",
                   "sentence_transformers_version": sentence_transformers.__version__,
                   "prefix": enc.prefix}
    emb = np.asarray(emb, dtype=np.float64)
    n = np.linalg.norm(emb, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return emb / n, runtime


def min_pairwise(X, rng_seed=SEED, cap=SUBSAMPLE_N):
    """Observed minimum pairwise cosine. Exact when n <= cap; else exact over a
    seeded subsample of cap vectors (documented in the returned block)."""
    import numpy as np
    n = X.shape[0]
    if n > cap:
        idx = np.random.default_rng(rng_seed).choice(n, size=cap, replace=False)
        Xs = X[np.sort(idx)]
        block = {"exact": False, "n_total": int(n), "n_subsample": int(cap), "seed": rng_seed}
    else:
        Xs = X
        block = {"exact": True, "n_total": int(n)}
    m = math.inf
    step = 1024
    for i in range(0, Xs.shape[0], step):
        G = Xs[i:i + step] @ Xs.T
        for r in range(G.shape[0]):
            G[r, i + r] = math.inf   # exclude self-cosine
        m = min(m, float(G.min()))
    block["min_cos"] = m
    return block


def cell_stats(vec_path: Path):
    """All statistics from the RETAINED fp16 vectors (single source of truth)."""
    import numpy as np
    X = np.load(vec_path).astype(np.float64)
    nrm = np.linalg.norm(X, axis=1, keepdims=True)
    nrm[nrm == 0] = 1.0
    X = X / nrm
    mean = X.mean(axis=0)
    mean_norm = float(np.linalg.norm(mean))
    mu = mean / mean_norm if mean_norm > 0 else mean
    theta = np.arccos(np.clip(X @ mu, -1.0, 1.0))
    tmax = float(theta.max())
    p99 = float(np.percentile(theta, 99))
    p90 = float(np.percentile(theta, 90))
    med = float(np.median(theta))
    hard = math.cos(2 * tmax)
    practical = math.cos(2 * p99)
    mp = min_pairwise(X)
    scope_ok = tmax <= math.pi / 2
    return {
        "n_vectors": int(X.shape[0]), "dim": int(X.shape[1]),
        "mu_mean_norm_before_normalization": round(mean_norm, 6),
        "theta_rad": {"max": round(tmax, 6), "p99": round(p99, 6),
                      "p90": round(p90, 6), "median": round(med, 6)},
        "theta_deg": {"max": round(math.degrees(tmax), 3),
                      "p99": round(math.degrees(p99), 3),
                      "p90": round(math.degrees(p90), 3),
                      "median": round(math.degrees(med), 3)},
        "scope_condition_theta_max_le_pi_over_2": bool(scope_ok),
        "hard_floor_cos_2theta_max": round(hard, 6),
        "practical_floor_cos_2theta_p99": round(practical, 6),
        "observed_min_pairwise": {k: (round(v, 6) if isinstance(v, float) else v)
                                  for k, v in mp.items()},
        "vacuity": {str(t): {"hard_floor_vacuous": bool(scope_ok and hard > t),
                             "practical_floor_vacuous": bool(scope_ok and practical > t)}
                    for t in OPS},
        "machine_check_b_min_ge_hard_floor":
            bool(scope_ok and mp["min_cos"] >= hard - TOL),
    }


def synthetic_check():
    """Machine check (a): vectors sampled in spherical caps at several theta; bound
    cos(u,v) >= cos 2*theta verified; tightness shown by the constructed antipodal-
    residual pair u = cos(t)mu + sin(t)e, v = cos(t)mu - sin(t)e with <u,v> = cos 2t."""
    import numpy as np
    out = []
    for tdeg in SYNTH_THETAS_DEG:
        t = math.radians(tdeg)
        rng = np.random.default_rng([SEED, tdeg])
        mu = np.zeros(SYNTH_DIM)
        mu[0] = 1.0
        W = rng.standard_normal((SYNTH_N, SYNTH_DIM))
        W[:, 0] = 0.0
        W /= np.linalg.norm(W, axis=1, keepdims=True)
        phi = rng.uniform(0.0, t, size=SYNTH_N)
        U = np.cos(phi)[:, None] * mu[None, :] + np.sin(phi)[:, None] * W
        e = np.zeros(SYNTH_DIM)
        e[1] = 1.0
        tight = np.stack([math.cos(t) * mu + math.sin(t) * e,
                          math.cos(t) * mu - math.sin(t) * e])
        X = np.vstack([U, tight])
        X /= np.linalg.norm(X, axis=1, keepdims=True)
        G = X @ X.T
        np.fill_diagonal(G, np.inf)
        mn = float(G.min())
        bound = math.cos(2 * t)
        pair_cos = float((tight[0] * tight[1]).sum())
        out.append({"theta_deg": tdeg, "n": SYNTH_N + 2, "dim": SYNTH_DIM,
                    "bound_cos_2theta": round(bound, 9),
                    "min_pairwise": round(mn, 9),
                    "bound_holds": bool(mn >= bound - TOL),
                    "tightness_pair_cos": round(pair_cos, 9),
                    "tightness_gap": round(pair_cos - bound, 9),
                    "tight": bool(abs(pair_cos - bound) <= 1e-6)})
    return out


def scorecard(cells, nine_names):
    missing = [f"{c}::{r}" for c in nine_names for r in REGISTERS
               if r not in cells.get(c, {})]
    complete = not missing
    b1_hits = [c for c in nine_names
               if cells.get(c, {}).get("errata_g2", {})
               .get("practical_floor_cos_2theta_p99", -1) > 0.40]
    b2_hits = [c for c in nine_names
               if cells.get(c, {}).get("errata_g2", {})
               .get("practical_floor_cos_2theta_p99", -1) > 0.60]
    viol = [f"{c}::{r}" for c in cells for r in cells[c]
            if not cells[c][r]["machine_check_b_min_ge_hard_floor"]]
    card = {
        "complete": complete, "missing_cells": missing,
        "B1": {"bar": "practical floor > 0.40 for >= 7 of 9 configs on the errata register",
               "hits": len(b1_hits), "of": 9, "configs": b1_hits,
               "verdict": ("PENDING_CELLS" if not complete else
                           "PASS" if len(b1_hits) >= 7 else "FAIL")},
        "B2": {"bar": "practical floor > 0.60 (audited drift cut) for >= 5 of 9 configs "
                      "[register: errata, per B1's frame - module pin]",
               "hits": len(b2_hits), "of": 9, "configs": b2_hits,
               "verdict": ("PENDING_CELLS" if not complete else
                           "PASS" if len(b2_hits) >= 5 else "FAIL")},
        "B3": {"bar": "observed min pairwise cosine >= hard floor in 100% of cells",
               "violations": viol,
               "verdict": ("PENDING_CELLS" if not complete else
                           "PASS" if not viol else
                           "FAIL (instrument-error investigation per prereg section 3)")},
    }
    return card


def main(argv=None):
    ap = argparse.ArgumentParser(description="E4 floor survey (prereg-e4)")
    ap.add_argument("--vectors-dir", default=str(DEFAULT_VDIR))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--stats-only", action="store_true",
                    help="embed nothing; compute the survey from retained vectors")
    args = ap.parse_args(argv)
    vdir = Path(args.vectors_dir)
    vdir.mkdir(parents=True, exist_ok=True)

    REG = registry()
    nine_names = [e.name for e in REG]
    device = os.environ.get("ST_DEVICE", "cpu")
    fp32 = bool(os.environ.get("ST_FP32"))
    batch = int(os.environ.get("ST_BATCH", "64"))

    if not args.stats_only:
        regs = load_registers()
        for r in REGISTERS:
            log(f"register {r}: {len(regs[r][0])} unique texts")
        for enc in REG:
            if ONLY and not any(s in enc.name.lower() for s in ONLY):
                continue
            ok, why = enc.available()
            if not ok:
                log(f"ABSENT: {enc.name} -- {why}")
                (vdir / (slug(enc.name) + ".ABSENT.txt")).write_text(why, encoding="utf-8")
                continue
            for r in REGISTERS:
                npy = vdir / f"{slug(enc.name)}__{r}.npy"
                meta_p = vdir / f"{slug(enc.name)}__{r}.meta.json"
                if npy.exists() and meta_p.exists():
                    log(f"SKIP (done): {enc.name} :: {r}")
                    continue
                import numpy as np
                t0 = time.time()
                texts, srcs = regs[r]
                X, runtime = embed_texts(enc, texts, device, fp32, batch)
                np.save(npy, X.astype(np.float16))
                meta_p.write_text(json.dumps({
                    "config": enc.name, "register": r, "n_texts": len(texts),
                    "device": device, "fp32_forced": fp32, "runtime": runtime,
                    "hostname": socket.gethostname(), "platform": platform.platform(),
                    "sources": srcs, "vector_dtype": "float16",
                    "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }, indent=1), encoding="utf-8")
                log(f"{enc.name} :: {r} embedded ({len(texts)} texts, "
                    f"{time.time() - t0:.0f}s) -> {npy.name}")

    # ---- survey pass: every cell whose vectors are present
    cells, cell_meta = {}, {}
    for meta_p in sorted(vdir.glob("*__*.meta.json")):
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        npy = meta_p.with_name(meta_p.name.replace(".meta.json", ".npy"))
        if not npy.exists():
            sys.exit(f"{meta_p.name} has no matching npy - vectors dir is damaged")
        c, r = meta["config"], meta["register"]
        log(f"stats: {c} :: {r}")
        cells.setdefault(c, {})[r] = cell_stats(npy)
        cell_meta.setdefault(c, {})[r] = {k: meta[k] for k in
                                          ("device", "fp32_forced", "runtime", "hostname",
                                           "n_texts", "sources")}
    if not cells:
        sys.exit(f"no vector cells under {vdir} - run the embedding pass first")

    survey = {
        "meta": {
            "prereg": "PREREGISTRATION_E4.md (frozen at tag prereg-e4)",
            "numerics_regime": "E3 fresh-fp32 pins (PREREGISTRATION_E3 section 2, E3-P2 "
                               "assignments); no cross-regime comparison",
            "seed": SEED, "operating_points": OPS,
            "registers": list(REGISTERS), "nine_configs": nine_names,
            "vectors_dir": str(vdir),
            "stats_source": "retained fp16 vectors (recompute reads the same npy)",
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cell_provenance": cell_meta,
        },
        "machine_check_a_synthetic": synthetic_check(),
        "cells": cells,
        "scorecard": scorecard(cells, nine_names),
    }
    bad_synth = [s for s in survey["machine_check_a_synthetic"]
                 if not (s["bound_holds"] and s["tight"])]
    survey["machine_check_a_verdict"] = "PASS" if not bad_synth else \
        f"FAIL at theta_deg={[s['theta_deg'] for s in bad_synth]}"
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(survey, indent=1), encoding="utf-8")
    log(f"FROZEN {out_path} ({sum(len(v) for v in cells.values())} cells; "
        f"scorecard: B1={survey['scorecard']['B1']['verdict']} "
        f"B2={survey['scorecard']['B2']['verdict']} "
        f"B3={survey['scorecard']['B3']['verdict']}; "
        f"check(a)={survey['machine_check_a_verdict']})")


if __name__ == "__main__":
    main()
