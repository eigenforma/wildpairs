"""E3 sweep sampler: 2,000 break + 2,000 preserve per source, seed 20260805, from the
frozen pool. Deterministic; run once on the host holding the pool and commit the output
manifest (ids + sha256 of the sampled file) before any encoder scores anything.

  python3 harness/e3/sample_sweep.py /mnt/coldstore/wildpairs/e3_composed
"""
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

N_PER_CLASS = 2000
SEED = 20260805


def main():
    root = Path(sys.argv[1])
    pool = defaultdict(list)
    for i, line in enumerate(open(root / "pairs_pool.jsonl", encoding="utf-8")):
        r = json.loads(line)
        pool[(r["source"], r["label"])].append((i, r))
    rng = random.Random(SEED)
    out = root / "sweep_sample.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for (src, lab), rows in sorted(pool.items()):
            take = rng.sample(rows, min(N_PER_CLASS, len(rows)))
            for i, r in sorted(take, key=lambda x: x[0]):
                r2 = dict(r)
                r2["pool_index"] = i
                f.write(json.dumps(r2, ensure_ascii=False) + "\n")
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    counts = {f"{s}/{l}": min(N_PER_CLASS, len(v)) for (s, l), v in sorted(pool.items())}
    print(json.dumps({"sweep_sample_sha256": sha, "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
