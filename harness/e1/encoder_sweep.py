"""E1-P4: the encoder sweep. Runs AFTER the prereg-e1 tag (git-verifiable) — scores every
frozen pair at every granularity through Paper A's nine pinned configurations, reusing the
Paper A registry verbatim (Falsifyer/experiments/factorial_pilot/encoders.py) so prefixes,
normalization, and the production router path are measured exactly as audited there.

Output: results/e1_sweep/<config-slug>.json per configuration (resume-safe: completed
configs are skipped), each holding {granularity: {pair_id: cosine}}. Long g3 sections
exceed some encoders' windows; sentence-transformers truncates at model max — that IS the
deployment behavior and is recorded, not corrected (truncation regime, prereg section 2).
Analysis (AUROC, operating points, stratification) is a separate later script; this file
only measures and freezes.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
# Registry location: Wu default, env-overridable for fleet nodes carrying a copy.
REGISTRY_DIR = Path(os.environ.get("PAPER_A_REGISTRY", "c:/Users/poeti/Falsifyer/experiments/factorial_pilot"))
sys.path.insert(0, str(REGISTRY_DIR))

from encoders import REGISTRY  # noqa: E402  (Paper A registry, verbatim)

# SWEEP_ONLY: comma-separated substrings; when set, only matching config names run
# (fleet sharding — e.g. SWEEP_ONLY=nomic on Forge while Wu holds the rest).
ONLY = [s.strip().lower() for s in os.environ.get("SWEEP_ONLY", "").split(",") if s.strip()]

PAIRS_G1G2 = ROOT / "corpus" / "e1_errata" / "pairs_g1g2.jsonl"
PAIRS_G3 = ROOT / "corpus" / "e1_errata" / "pairs_g3.jsonl"
OUT_DIR = ROOT / "results" / "e1_sweep"
LOG = OUT_DIR / "sweep.log"


def slug(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in name)[:80]


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base = [json.loads(l) for l in PAIRS_G1G2.read_text(encoding="utf-8").splitlines()]
    g3 = {r["pair_id"]: r for r in (json.loads(l) for l in PAIRS_G3.read_text(encoding="utf-8").splitlines()) if r["g3_found"]}
    grans = {
        "g1": [(r["pair_id"], r["g1_orig"], r["g1_corr"]) for r in base if r["g1_orig"]],
        "g2": [(r["pair_id"], r["g2_orig"], r["g2_corr"]) for r in base],
        "g3": [(pid, g["g3_orig"], g["g3_corr"]) for pid, g in g3.items()],
    }
    log(f"pairs: g1={len(grans['g1'])} g2={len(grans['g2'])} g3={len(grans['g3'])}; configs={len(REGISTRY)}")

    # cheap-first so partial results land early; production router last (per-pair loop, slowest)
    order = sorted(range(len(REGISTRY)), key=lambda i: (REGISTRY[i].family == "nomic", "mxbai" in REGISTRY[i].family, i))
    for i in order:
        enc = REGISTRY[i]
        if ONLY and not any(s in enc.name.lower() for s in ONLY):
            continue
        out_path = OUT_DIR / (slug(enc.name) + ".json")
        if out_path.exists():
            log(f"SKIP (done): {enc.name}")
            continue
        ok, why = enc.available()
        if not ok:
            log(f"ABSENT: {enc.name} -- {why}")
            (OUT_DIR / (slug(enc.name) + ".ABSENT.txt")).write_text(why)
            continue
        result = {"config": enc.name, "family": enc.family, "note": getattr(enc, "note", ""), "granularities": {}}
        for g, rows in grans.items():
            t0 = time.time()
            cos = enc.cosines([(a, b) for _, a, b in rows])
            result["granularities"][g] = {pid: round(c, 6) for (pid, _, _), c in zip(rows, cos)}
            log(f"{enc.name} :: {g} done ({len(rows)} pairs, {time.time()-t0:.0f}s)")
        out_path.write_text(json.dumps(result) + "\n")
        log(f"FROZEN {out_path.name}")
    log("SWEEP COMPLETE")


if __name__ == "__main__":
    main()
