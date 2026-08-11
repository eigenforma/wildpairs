"""E2-P4: sharded embedding sweep over the titrated stimuli (PREREGISTRATION_E2 section 2).

Committed BEFORE the prereg-e2 tag; RUNS only after it, on the encoder-blind stimuli from
harness/e2/titration_build.py. Reads the pinned-config block harness/configs/e2_pinned.json
(nine Paper A registry configs, names verbatim, + the long-context nomic new named config),
embeds every pair member per config on the config's PINNED device/dtype (no silent
fallback: a cuda pin with no cuda is a hard stop), cosine per pair over explicitly
normalized vectors (registry convention), realized token counts per member via the
encoder's OWN tokenizer (prefix included, special tokens INCLUDED), truncated flag =
max realized > effective window. The flag is RECORDED here; the L=512 boundary-bin
dual analysis is decided in harness/e2/e2_analysis.py, never here.

Run (RUNBOOK R6; one shard per node, SWEEP_ONLY selects the node's pinned configs):
  SWEEP_ONLY=bge,e5,nomic python3 harness/e2/titration_sweep.py --shard odd \
      --stimuli corpus/e2_dilution/stimuli --out results/forge/e2_shard.json
Resume-safe per (config, arm, host-domain, L): completed cell files under
<out basename>_partial/ are skipped; a resume under CHANGED numerics (different
checkpoint/device/dtype/library) is rejected, not mixed in. Assembly rebuilds <out>
from every cell present, meta carrying per-config config-hash blocks
{checkpoint_sha_or_rev, device, dtype, sentence_transformers_version} and the
effective-window table - scripts/merge_shards.py verifies these across shards.
Env: SWEEP_ONLY (e1 convention, comma substrings), ST_BATCH (default 32),
PAPER_A_REGISTRY (registry cross-check, e1 convention).
"""
import argparse
import hashlib
import json
import os
import platform
import socket
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")       # encoders.py convention: offline by
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")  # default; uncached = loud, never silent

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG = ROOT / "harness" / "configs" / "e2_pinned.json"
DEFAULT_STIMULI = ROOT / "corpus" / "e2_dilution" / "stimuli"
# Registry location: Wu default, env-overridable for fleet nodes carrying a copy
# (harness/e1/encoder_sweep.py convention).
REGISTRY_DIR = Path(os.environ.get("PAPER_A_REGISTRY",
                                   "c:/Users/poeti/Falsifyer/experiments/factorial_pilot"))
ONLY = [s.strip().lower() for s in os.environ.get("SWEEP_ONLY", "").split(",") if s.strip()]

ARMS = {"splice", "native"}
DOMAINS = {"enwiki", "pmc", "rfc"}

_LOG_PATH = None


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    if _LOG_PATH is not None:
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def slug(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in name)[:80]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def anchor_parity(anchor_id: str) -> str:
    """odd|even by sha256 of the anchor_id string - stable across platforms/sessions
    (Python's own hash() is salted). TWIN in scripts/merge_shards.py: keep byte-identical."""
    return "odd" if int(hashlib.sha256(anchor_id.encode("utf-8")).hexdigest(), 16) & 1 else "even"


def load_pinned(path: Path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    cfgs = doc["configs"]
    required = ("name", "family", "model_id", "prefix", "device", "node", "dtype",
                "dtype_policy", "paper_a_registry_member")
    for c in cfgs:
        missing = [k for k in required if k not in c]
        if missing:
            sys.exit(f"pinned config {c.get('name', '?')!r} missing fields {missing}")
        if c["device"] not in ("cpu", "cuda"):
            sys.exit(f"pinned config {c['name']!r}: unknown device {c['device']!r}")
    names = [c["name"] for c in cfgs]
    if len(set(names)) != len(names):
        sys.exit("duplicate config names in pinned block")
    return cfgs


def registry_crosscheck(cfgs):
    """The nine must match the Paper A registry verbatim (name; model_id/prefix where the
    registry entry exposes them); the long-context config must NOT collide with it."""
    sys.path.insert(0, str(REGISTRY_DIR))
    try:
        from encoders import REGISTRY  # noqa: E402  (Paper A registry, verbatim)
    except Exception as exc:
        sys.exit(f"Paper A registry import failed from {REGISTRY_DIR} "
                 f"({type(exc).__name__}: {exc}); set PAPER_A_REGISTRY (e1 convention)")
    by_name = {e.name: e for e in REGISTRY}
    for c in cfgs:
        if c["paper_a_registry_member"]:
            e = by_name.get(c["name"])
            if e is None:
                sys.exit(f"pinned config {c['name']!r} claims registry membership but the "
                         f"registry has no such name")
            model_id = getattr(e, "model_id", None)
            if model_id is not None and model_id != c["model_id"]:
                sys.exit(f"{c['name']!r}: model_id {c['model_id']!r} != registry {model_id!r}")
            if model_id is not None and getattr(e, "prefix", "") != c["prefix"]:
                sys.exit(f"{c['name']!r}: prefix {c['prefix']!r} != registry "
                         f"{getattr(e, 'prefix', '')!r}")
        elif c["name"] in by_name:
            sys.exit(f"new named config {c['name']!r} collides with a registry name")
    log(f"registry cross-check OK ({sum(c['paper_a_registry_member'] for c in cfgs)} "
        f"registry members verified)")


def checkpoint_rev(model_id: str, pinned_rev):
    """Resolved HF-cache snapshot sha for the checkpoint. refs/main first, else the lone
    snapshot dir; anything else is a loud stop. When the pinned block carries a revision
    (long-context nomic at tag time), the resolved sha must equal it."""
    hub = Path(os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))) / "hub"
    stub = hub / ("models--" + model_id.replace("/", "--"))
    if not stub.exists():
        return None, f"not in local HF cache ({stub.name}); download once with HF_HUB_OFFLINE=0"
    ref = stub / "refs" / "main"
    if ref.exists():
        rev = ref.read_text(encoding="utf-8").strip()
    else:
        snaps = [d.name for d in (stub / "snapshots").iterdir() if d.is_dir()] \
            if (stub / "snapshots").exists() else []
        if len(snaps) != 1:
            return None, f"no refs/main and {len(snaps)} snapshots in {stub.name}"
        rev = snaps[0]
    if pinned_rev and rev != pinned_rev:
        sys.exit(f"{model_id}: cached snapshot {rev} != pinned revision {pinned_rev} "
                 f"(harness/configs/e2_pinned.json)")
    return rev, None


def load_pairs(paths, shard):
    """Stimuli member rows -> per-cell pair lists. Cell = (arm, host_domain, L); pair
    group = (anchor_id, position, pair) with exactly members a and b (else hard stop)."""
    files = []
    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            files.extend(sorted(pp.glob("stimuli_*.jsonl")))
        elif pp.exists():
            files.append(pp)
        else:
            sys.exit(f"stimuli path missing: {pp}")
    if not files:
        sys.exit("no stimuli files found (run harness/e2/titration_build.py first)")
    groups = {}
    for fp in files:
        with fp.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                if r["arm"] not in ARMS or r["host_domain"] not in DOMAINS:
                    sys.exit(f"stimuli schema drift in {fp.name}: arm={r['arm']!r} "
                             f"host_domain={r['host_domain']!r}")
                if anchor_parity(r["anchor_id"]) != shard:
                    continue
                k = (r["arm"], r["host_domain"], int(r["L"]), r["anchor_id"],
                     r["position"], r["pair"])
                g = groups.setdefault(k, {})
                if r["member"] in g:
                    sys.exit(f"duplicate member row for {k} member={r['member']}")
                g[r["member"]] = r["text"]
    bad = [k for k, g in groups.items() if set(g) != {"a", "b"}]
    if bad:
        sys.exit(f"{len(bad)} pair groups missing a member (first: {bad[0]}) - "
                 f"titration_build output is damaged")
    cells = {}
    for (arm, dom, L, aid, pos, pair), g in groups.items():
        cells.setdefault((arm, dom, L), []).append((aid, pos, pair, g["a"], g["b"]))
    for k in cells:
        cells[k].sort(key=lambda t: (t[0], t[1], t[2]))
    return cells, files


def load_model(cfg):
    """Load per the pin block: pinned device (no fallback), dtype policy, window
    override. Returns (model, effective_window, derivation, provenance)."""
    import torch  # runtime dep; lands with the P4 sweep per requirements.txt
    from sentence_transformers import SentenceTransformer
    if cfg["device"] == "cuda" and not torch.cuda.is_available():
        sys.exit(f"{cfg['name']!r} is pinned to cuda ({cfg['node']}) but no cuda device is "
                 f"available here - refusing to fall back silently")
    kwargs = {}
    if cfg.get("trust_remote_code"):
        kwargs["trust_remote_code"] = True
    model = SentenceTransformer(cfg["model_id"], device=cfg["device"], **kwargs)
    if cfg.get("max_seq_length"):
        model.max_seq_length = int(cfg["max_seq_length"])
    if cfg["dtype_policy"] == "force-fp32":
        model = model.float()
    elif cfg["dtype_policy"] == "checkpoint-native":
        pass  # load exactly as the pinned Wu-CPU path loads (no cast) - see e2_pinned.json
    else:
        sys.exit(f"{cfg['name']!r}: unknown dtype_policy {cfg['dtype_policy']!r}")
    eff = int(model.max_seq_length)  # sentence-transformers truncates to this TOTAL
    #                                  length, special tokens included (prereg: window
    #                                  arithmetic includes special tokens)
    der = {"st_max_seq_length": eff}
    try:
        mm = int(model.tokenizer.model_max_length)
        der["tokenizer_model_max_length"] = mm if mm < 10 ** 9 else None
    except Exception:
        der["tokenizer_model_max_length"] = None
    try:
        der["model_max_position_embeddings"] = int(
            model[0].auto_model.config.max_position_embeddings)
    except Exception:
        der["model_max_position_embeddings"] = None
    try:
        observed_dtype = str(next(model.parameters()).dtype)
    except Exception:
        observed_dtype = None
    prov = {"observed_param_dtype": observed_dtype,
            "cuda_device_name": (torch.cuda.get_device_name(0)
                                 if cfg["device"] == "cuda" else None),
            "torch_version": torch.__version__}
    return model, eff, der, prov


def embed_cell(model, cfg, pair_rows, batch):
    """One (arm, host_domain, L) cell: embed unique member texts once (the a member is
    shared across a cell's flip/faithful/scope pairs), cosine per pair, realized tokens
    per member (prefix included, special tokens included), truncated flag recorded."""
    import numpy as np
    prefix = cfg["prefix"]
    uniq = sorted({t for (_a, _p, _pr, ta, tb) in pair_rows for t in (ta, tb)})
    full = [prefix + t for t in uniq]
    emb = model.encode(full, batch_size=batch, normalize_embeddings=True,
                       show_progress_bar=False, convert_to_numpy=True)
    emb = np.asarray(emb, dtype=np.float64)
    if cfg.get("mrl_dim"):
        emb = emb[:, : int(cfg["mrl_dim"])]
        n = np.linalg.norm(emb, axis=1, keepdims=True)
        n[n == 0] = 1.0
        emb = emb / n
    ids = model.tokenizer(full, add_special_tokens=True, truncation=False,
                          padding=False)["input_ids"]
    vec = {t: emb[i] for i, t in enumerate(uniq)}
    ntok = {t: len(ids[i]) for i, t in enumerate(uniq)}
    return vec, ntok


def cell_rows(cfg, pair_rows, vec, ntok, eff, arm, dom, L):
    rows = []
    for (aid, pos, pair, ta, tb) in pair_rows:
        ra, rb = ntok[ta], ntok[tb]
        rows.append({"anchor_id": aid, "arm": arm, "host": dom, "L": L, "position": pos,
                     "encoder": cfg["name"], "pair": pair,
                     "cos": round(float((vec[ta] * vec[tb]).sum()), 6),
                     "realized_tokens": {"a": ra, "b": rb},
                     "truncated": max(ra, rb) > eff})
    return rows


def atomic_write(path: Path, obj) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def assemble(out_path: Path, part_dir: Path, shard: str, run_prov: dict) -> None:
    """Rebuild the shard file from every completed cell present (all configs, not just
    this invocation's SWEEP_ONLY slice)."""
    cfg_hash, windows, deriv, cfg_prov, cells = {}, {}, {}, {}, []
    per_cfg = {}
    for d in sorted(p for p in part_dir.iterdir() if p.is_dir()):
        meta_p = d / "config_meta.json"
        cell_files = sorted(p for p in d.glob("*.json") if p.name != "config_meta.json")
        if not meta_p.exists():
            if cell_files:
                sys.exit(f"{d.name}: cell files without config_meta.json - partial dir "
                         f"is damaged")
            continue
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        name = meta["name"]
        cfg_hash[name] = meta["config_hash"]
        windows[name] = meta["effective_window"]
        deriv[name] = meta["derivation"]
        cfg_prov[name] = meta.get("provenance")
        n = 0
        for cf in cell_files:
            data = json.loads(cf.read_text(encoding="utf-8"))
            if data["shard"] != shard:
                sys.exit(f"{cf} was swept as shard {data['shard']!r}, this run is "
                         f"{shard!r} - one partial dir per shard, never mixed")
            if data["config"] != name:
                sys.exit(f"{cf}: config {data['config']!r} under dir for {name!r}")
            cells.extend(data["cells"])
            n += len(data["cells"])
        per_cfg[name] = n
    atomic_write(out_path, {
        "meta": {"shard": shard, "provenance": run_prov, "config_hash": cfg_hash,
                 "config_provenance": cfg_prov, "effective_windows": windows,
                 "effective_window_derivation": deriv},
        "cells": cells})
    log(f"SHARD ASSEMBLED {out_path} ({len(cells)} cells; " +
        "; ".join(f"{k}={v}" for k, v in sorted(per_cfg.items())) + ")")


def main(argv=None):
    global _LOG_PATH
    ap = argparse.ArgumentParser(description="E2 titration sweep (sharded)")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--stimuli", nargs="+", default=[str(DEFAULT_STIMULI)],
                    help="stimuli jsonl files and/or directories of stimuli_*.jsonl")
    ap.add_argument("--shard", required=True, choices=["odd", "even"],
                    help="anchor_id sha256 parity (RUNBOOK R6: odd->Forge, even->Agora)")
    ap.add_argument("--out", required=True, help="results/<host>/e2_shard.json")
    ap.add_argument("--assemble-only", action="store_true",
                    help="rebuild the shard file from completed cells; embed nothing")
    args = ap.parse_args(argv)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _LOG_PATH = out_path.parent / "e2_sweep.log"
    part_dir = out_path.parent / (out_path.stem + "_partial")
    part_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = Path(args.config)
    cfgs = load_pinned(cfg_path)
    registry_crosscheck(cfgs)

    run_prov = {
        "hostname": socket.gethostname(), "platform": platform.platform(),
        "python": sys.version.split()[0], "shard": args.shard,
        "pinned_config": {"path": str(cfg_path), "sha256": sha256_file(cfg_path)},
        "sweep_only": ONLY or None,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if args.assemble_only:
        assemble(out_path, part_dir, args.shard, run_prov)
        return

    cells, stim_files = load_pairs(args.stimuli, args.shard)
    run_prov["stimuli"] = [{"path": str(f), "sha256": sha256_file(f)} for f in stim_files]
    n_pairs = sum(len(v) for v in cells.values())
    log(f"shard={args.shard}: {n_pairs} pairs across {len(cells)} cells "
        f"(arm, domain, L); configs={len(cfgs)}"
        + (f"; SWEEP_ONLY={ONLY}" if ONLY else ""))
    if n_pairs == 0:
        sys.exit("no pairs on this shard - wrong stimuli path or wrong parity")

    batch = int(os.environ.get("ST_BATCH", "32"))
    import sentence_transformers  # runtime dep; version pinned into every hash block
    st_version = sentence_transformers.__version__

    # cheap-first ordering, e1 convention (nomic family last: heaviest)
    order = sorted(range(len(cfgs)),
                   key=lambda i: (cfgs[i]["family"] == "nomic",
                                  "mxbai" in cfgs[i]["family"], i))
    for i in order:
        cfg = cfgs[i]
        name = cfg["name"]
        if ONLY and not any(s in name.lower() for s in ONLY):
            continue
        pdir = part_dir / slug(name)
        rev, why = checkpoint_rev(cfg["model_id"], cfg.get("revision"))
        if rev is None:
            log(f"ABSENT: {name} -- {why}")
            (part_dir / (slug(name) + ".ABSENT.txt")).write_text(why, encoding="utf-8")
            continue
        block = {"checkpoint_sha_or_rev": rev, "device": cfg["device"],
                 "dtype": cfg["dtype"], "sentence_transformers_version": st_version}
        meta_p = pdir / "config_meta.json"
        todo = sorted(cells.keys())
        missing = [c for c in todo
                   if not (pdir / f"{c[0]}__{c[1]}__L{c[2]}.json").exists()]
        if meta_p.exists():
            prev = json.loads(meta_p.read_text(encoding="utf-8"))["config_hash"]
            if prev != block:
                sys.exit(f"{name!r}: resume under CHANGED numerics - stored {prev} vs "
                         f"now {block}; wipe {pdir} deliberately or fix the environment")
            if not missing:
                log(f"SKIP (done): {name}")
                continue
        log(f"{name} :: loading on {cfg['device']} ({cfg['node']} pin, dtype "
            f"{cfg['dtype']}/{cfg['dtype_policy']}); {len(missing)} of {len(todo)} "
            f"cells to embed")
        model, eff, der, prov = load_model(cfg)
        pdir.mkdir(parents=True, exist_ok=True)
        if not meta_p.exists():
            atomic_write(meta_p, {"name": name, "config_hash": block,
                                  "effective_window": eff, "derivation": der,
                                  "provenance": prov})
        for (arm, dom, L) in missing:
            t0 = time.time()
            pair_rows = cells[(arm, dom, L)]
            vec, ntok = embed_cell(model, cfg, pair_rows, batch)
            rows = cell_rows(cfg, pair_rows, vec, ntok, eff, arm, dom, L)
            atomic_write(pdir / f"{arm}__{dom}__L{L}.json",
                         {"config": name, "shard": args.shard, "arm": arm, "host": dom,
                          "L": L, "cells": rows})
            n_tr = sum(r["truncated"] for r in rows)
            log(f"{name} :: {arm}/{dom}/L={L} done ({len(rows)} pairs, {n_tr} truncated, "
                f"{time.time() - t0:.0f}s)")
        del model
        log(f"FROZEN config {name} (window={eff})")

    run_prov["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    assemble(out_path, part_dir, args.shard, run_prov)
    log("SWEEP COMPLETE")


if __name__ == "__main__":
    main()
