"""Verify-and-merge the two E2 sweep shards (RUNBOOK R6 integrity handshake).

Run: python3 scripts/merge_shards.py results/forge/e2_shard.json results/agora/e2_shard.json \
        --verify-config-hash --out results/e2_scores_merged.json

Verification is ALWAYS performed - the flag is the registered spelling
(PREREGISTRATION_E2 section 2: "shards merge only through merge_shards.py
--verify-config-hash"), not an option to decline. Per config, the config-hash block
{checkpoint_sha_or_rev, device, dtype, sentence_transformers_version} must match
EXACTLY across the two shards; any mismatch rejects the merge naming the config and
every differing field with both values. Also enforced: shard labels are one odd + one
even; every cell's anchor_id sha256-parity matches its shard's label; cell keys are
disjoint across shards; the config sets and effective-window tables agree.

Output (this exact schema - harness/e2/e2_analysis.py consumes it):
  results/e2_scores_merged.json = {"meta": {config_hash, shard_provenance,
      effective_windows, ...}, "cells": [{anchor_id, arm, host, L, position, encoder,
      pair, cos, realized_tokens: {a, b}, truncated: bool}]}
Stdlib only; nothing is overwritten silently (refuses an existing --out).
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "results" / "e2_scores_merged.json"
HASH_FIELDS = ("checkpoint_sha_or_rev", "device", "dtype", "sentence_transformers_version")
CELL_KEY = ("encoder", "arm", "host", "L", "position", "anchor_id", "pair")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def anchor_parity(anchor_id: str) -> str:
    """TWIN of harness/e2/titration_sweep.py:anchor_parity - keep byte-identical."""
    return "odd" if int(hashlib.sha256(anchor_id.encode("utf-8")).hexdigest(), 16) & 1 else "even"


def load_shard(path: Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = d.get("meta") or {}
    for k in ("shard", "config_hash", "effective_windows"):
        if k not in meta:
            sys.exit(f"{path}: shard meta missing {k!r} - not a titration_sweep shard file")
    if meta["shard"] not in ("odd", "even"):
        sys.exit(f"{path}: unknown shard label {meta['shard']!r}")
    return d


def verify_config_hash(shards):
    """Exact per-config equality of the four-field hash blocks across shards; reject
    naming every differing field. Config sets must be identical."""
    (la, a), (lb, b) = shards
    ca, cb = a["meta"]["config_hash"], b["meta"]["config_hash"]
    if set(ca) != set(cb):
        only_a = sorted(set(ca) - set(cb))
        only_b = sorted(set(cb) - set(ca))
        sys.exit("REJECT: config sets differ between shards\n"
                 + (f"  only in {la}: {only_a}\n" if only_a else "")
                 + (f"  only in {lb}: {only_b}" if only_b else ""))
    problems = []
    for name in sorted(ca):
        for field in HASH_FIELDS:
            va, vb = ca[name].get(field), cb[name].get(field)
            if va != vb:
                problems.append(f"  {name} :: {field}: {la}={va!r} != {lb}={vb!r}")
        extra = (set(ca[name]) | set(cb[name])) - set(HASH_FIELDS)
        if extra:
            problems.append(f"  {name} :: unregistered hash-block fields {sorted(extra)}")
    wa, wb = a["meta"]["effective_windows"], b["meta"]["effective_windows"]
    for name in sorted(ca):
        if wa.get(name) != wb.get(name):
            problems.append(f"  {name} :: effective_window: {la}={wa.get(name)!r} != "
                            f"{lb}={wb.get(name)!r}")
    if problems:
        sys.exit("REJECT: config-hash verification failed (an unpinned triple entered a "
                 "shard - PREREGISTRATION_E2 section 2):\n" + "\n".join(problems))
    return {name: dict(ca[name]) for name in ca}, dict(wa)


def verify_cells(shards):
    """Parity of every cell's anchor vs its shard label; cross-shard key disjointness."""
    seen = {}
    ordered = []
    for label, d in shards:
        for i, r in enumerate(d["cells"]):
            missing = [k for k in CELL_KEY if k not in r]
            if missing:
                sys.exit(f"REJECT: {label} cell #{i} missing fields {missing}")
            if anchor_parity(r["anchor_id"]) != d["meta"]["shard"]:
                sys.exit(f"REJECT: {label} carries anchor {r['anchor_id']!r} whose parity "
                         f"is {anchor_parity(r['anchor_id'])!r}, shard label "
                         f"{d['meta']['shard']!r} - shard was mis-assembled")
            key = tuple(r[k] for k in CELL_KEY)
            if key in seen:
                sys.exit(f"REJECT: duplicate cell across shards: {key} "
                         f"(in {seen[key]} and {label})")
            seen[key] = label
        ordered.extend(d["cells"])
    return ordered


def main(argv=None):
    ap = argparse.ArgumentParser(description="E2 shard verify-and-merge")
    ap.add_argument("shard_a", help="results/forge/e2_shard.json (odd)")
    ap.add_argument("shard_b", help="results/agora/e2_shard.json (even)")
    ap.add_argument("--verify-config-hash", action="store_true",
                    help="the registered spelling; verification runs regardless")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting an existing --out (a frozen merge is "
                         "otherwise never clobbered)")
    args = ap.parse_args(argv)
    if not args.verify_config_hash:
        print("note: --verify-config-hash not passed; verification runs unconditionally "
              "(the flag exists to match the registered command line)")

    pa, pb = Path(args.shard_a), Path(args.shard_b)
    da, db = load_shard(pa), load_shard(pb)
    labels = {da["meta"]["shard"], db["meta"]["shard"]}
    if labels != {"odd", "even"}:
        sys.exit(f"REJECT: need one odd + one even shard, got "
                 f"{da['meta']['shard']!r} + {db['meta']['shard']!r}")
    # deterministic order: odd first, regardless of argv order
    shards = sorted([("odd" if da["meta"]["shard"] == "odd" else "even", da),
                     ("odd" if db["meta"]["shard"] == "odd" else "even", db)],
                    key=lambda t: t[0] != "odd")
    paths = {da["meta"]["shard"]: pa, db["meta"]["shard"]: pb}

    config_hash, windows = verify_config_hash(shards)
    cells = verify_cells(shards)

    out_path = Path(args.out)
    if out_path.exists() and not args.force:
        sys.exit(f"{out_path} already exists - a frozen merge is never overwritten "
                 f"silently (pass --force deliberately)")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    shard_prov = {}
    for label, d in shards:
        m = d["meta"]
        shard_prov[label] = {"path": str(paths[label]), "sha256": sha256_file(paths[label]),
                             "n_cells": len(d["cells"]),
                             "provenance": m.get("provenance"),
                             "config_provenance": m.get("config_provenance"),
                             "effective_window_derivation":
                                 m.get("effective_window_derivation")}
    digest = {name: hashlib.sha256(
        json.dumps(block, sort_keys=True).encode("utf-8")).hexdigest()
        for name, block in config_hash.items()}

    merged = {"meta": {"config_hash": config_hash, "config_hash_digest": digest,
                       "shard_provenance": shard_prov, "effective_windows": windows,
                       "hash_fields": list(HASH_FIELDS),
                       "merged_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "n_cells": len(cells)},
              "cells": cells}
    out_path.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")

    per_enc = {}
    for r in cells:
        per_enc[r["encoder"]] = per_enc.get(r["encoder"], 0) + 1
    print(f"MERGED {len(cells)} cells -> {out_path}")
    for name in sorted(per_enc):
        print(f"  {per_enc[name]:>8d}  {name}")
    print("config-hash verification: PASS (blocks identical across shards for "
          f"{len(config_hash)} configs)")


if __name__ == "__main__":
    main()
