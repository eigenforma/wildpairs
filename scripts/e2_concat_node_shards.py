"""Concatenate the two nodes' shards for one parity, so `merge_shards.py` can run its
integrity handshake on exactly one odd + one even file (its registered contract).

Why this step exists: PREREGISTRATION_E2 §2 (as amended) pins TWO orthogonal axes — anchors
shard by id parity AND each node sweeps only its own pinned config slice. So each node
produced both parities for its own configs, and a parity's full config set is the union of
the nodes. This script performs that union and nothing else; every downstream integrity check
in merge_shards.py runs unchanged on its output.

Enforced here (rejects, never repairs):
  - both inputs carry the same shard label,
  - their config sets are DISJOINT (a config swept on two nodes would violate the
    one-pinned-device-per-config pin and is caught here, not averaged),
  - effective-window tables agree wherever both define a config,
  - cell keys are disjoint.
Config-hash blocks are carried through per config for merge_shards to verify.

Run: python scripts/e2_concat_node_shards.py results/forge/e2_shard_odd.json \
         results/agora/e2_shard_odd.json --out results/odd/e2_shard.json
"""
import argparse, json, sys
from pathlib import Path

CELL_KEY = ("anchor_id", "arm", "host", "L", "position", "encoder", "pair")


def load(p):
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    if "cells" not in d or "meta" not in d:
        sys.exit(f"{p}: not a shard file")
    return d


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("shards", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    ds = [load(p) for p in a.shards]
    labels = {d["meta"].get("shard") for d in ds}
    if len(labels) != 1:
        sys.exit(f"shard-label mismatch across inputs: {labels}")

    sets = [set(c["encoder"] for c in d["cells"]) for d in ds]
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            dup = sets[i] & sets[j]
            if dup:
                sys.exit(f"config swept on two nodes (violates the per-config device pin): {dup}")

    windows = {}
    for p, d in zip(a.shards, ds):
        for k, v in (d["meta"].get("effective_windows") or {}).items():
            if k in windows and windows[k] != v:
                sys.exit(f"effective-window disagreement for {k}: {windows[k]} vs {v} ({p})")
            windows[k] = v

    cells, seen = [], set()
    for d in ds:
        for c in d["cells"]:
            k = tuple(c[f] for f in CELL_KEY)
            if k in seen:
                sys.exit(f"duplicate cell across node shards: {k}")
            seen.add(k)
            cells.append(c)

    meta = {"shard": labels.pop(), "concat_of": [str(p) for p in a.shards],
            "effective_windows": windows,
            "config_hash": {k: v for d in ds for k, v in (d["meta"].get("config_hash") or {}).items()},
            "config_provenance": {k: v for d in ds
                                  for k, v in (d["meta"].get("config_provenance") or {}).items()},
            "node_provenance": [d["meta"].get("provenance") for d in ds],
            "effective_window_derivation": [d["meta"].get("effective_window_derivation") for d in ds]}
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": meta, "cells": cells}), encoding="utf-8")
    print(f"{out}: {len(cells)} cells, {len(set(c['encoder'] for c in cells))} configs, "
          f"shard={meta['shard']}")


if __name__ == "__main__":
    main()
