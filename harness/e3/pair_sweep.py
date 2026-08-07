"""E3-P3: score the frozen sweep sample with one or more pinned configurations on this
node's pinned device (PREREGISTRATION_E3 §2). Resume-safe per config; output files are
the cross-node coordination protocol, as in E1.

  PAPER_A_REGISTRY=~/paperA-registry ST_DEVICE=cuda ST_FP32=1 SWEEP_ONLY=bge,mxbai,e5 \
    python3 harness/e3/pair_sweep.py <sweep_sample.jsonl> <out_dir>

Env: SWEEP_ONLY (comma substrings; empty = all), ST_DEVICE, ST_FP32, ST_BATCH (default 64).
"""
import json
import os
import sys
import time
from pathlib import Path

REGISTRY_DIR = Path(os.environ.get("PAPER_A_REGISTRY", "c:/Users/poeti/Falsifyer/experiments/factorial_pilot"))
sys.path.insert(0, str(REGISTRY_DIR))
from encoders import REGISTRY  # noqa: E402

ONLY = [s.strip().lower() for s in os.environ.get("SWEEP_ONLY", "").split(",") if s.strip()]


def slug(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in name)[:80]


def main():
    sample_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in sample_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    pairs = [(r["text_a"], r["text_b"]) for r in rows]
    print(f"[{time.strftime('%H:%M:%S')}] sample: {len(pairs)} pairs; configs={len(REGISTRY)}", flush=True)
    for enc in REGISTRY:
        if ONLY and not any(s in enc.name.lower() for s in ONLY):
            continue
        out = out_dir / (slug(enc.name) + ".json")
        if out.exists():
            print(f"SKIP (done): {enc.name}", flush=True)
            continue
        ok, why = enc.available()
        if not ok:
            print(f"ABSENT: {enc.name} :: {why}", flush=True)
            continue
        t0 = time.time()
        cos = enc.cosines(pairs)
        out.write_text(json.dumps({
            "config": enc.name, "n": len(cos),
            "device": os.environ.get("ST_DEVICE", "cpu"), "fp32_forced": bool(os.environ.get("ST_FP32")),
            "sample_file": sample_path.name, "cos": [round(float(c), 6) for c in cos],
        }))
        print(f"[{time.strftime('%H:%M:%S')}] FROZEN {out.name} ({len(cos)} pairs, {time.time()-t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
