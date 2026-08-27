"""E2 parity gate (PREREGISTRATION_E2 §2): no GPU shard is admitted until its config
re-passes the frozen-probe gate — max |Δcos| ≤ 1e-5 against the pinned reference path —
with titrated-length probes at L ∈ {64, 512, 4096}.

Cosines, not raw vectors, are the compared quantity (the H4 parity lesson: fp16-native
checkpoints differ in the last bits of a vector while their cosines agree, or not).

Probe set: seeded (20260805) sample of 8 stimulus texts per L-bin from the enwiki SPLICE
stimuli, paired consecutively into 4 cosines per bin, 12 per config; the probe text list is
frozen by sha256 in every output so reference and target provably scored the same strings.

  # reference (Wu, pinned CPU path):
  python scripts/e2_parity_gate.py --side reference --out results/verification/e2_parity_ref.json
  # target (on each GPU node, its own config slice):
  SWEEP_ONLY=... python3 scripts/e2_parity_gate.py --side target --out results/<node>/e2_parity_target.json
  # compare (Wu, after collecting the targets):
  python scripts/e2_parity_gate.py --compare results/verification/e2_parity_ref.json <targets...> \
      --out results/verification/e2_parity_gates.json
"""
import argparse
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.e2 import titration_sweep as ts  # noqa: E402  (single loading path, by design)

PROBE_BINS = (64, 512, 4096)
PER_BIN = 8
SEED = 20260805
TOL = 1e-5


def probe_texts(stimuli_dir: Path):
    """Deterministic probe texts: the first PER_BIN texts of a seeded shuffle per L bin,
    drawn from the enwiki SPLICE stimuli only (one domain keeps the gate cheap and fixed)."""
    buckets = {L: [] for L in PROBE_BINS}
    files = sorted(Path(stimuli_dir).glob("stimuli_enwiki_splice*.jsonl"))
    if not files:
        sys.exit(f"no enwiki splice stimuli under {stimuli_dir}")
    for fp in files:
        with open(fp, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                if r["L"] in buckets:
                    buckets[r["L"]].append((r["stim_id"], r["text"]))
    rng = random.Random(SEED)
    probes = []
    for L in PROBE_BINS:
        rows = sorted(buckets[L], key=lambda t: t[0])
        if len(rows) < PER_BIN:
            sys.exit(f"bin L={L} has only {len(rows)} stimuli, need {PER_BIN}")
        rng.shuffle(rows)
        probes.extend({"L": L, "stim_id": sid, "text": txt} for sid, txt in rows[:PER_BIN])
    return probes


def cosines(vec):
    """Consecutive pairs (0,1), (2,3), … as cosines of already-unit-normalized rows."""
    out = []
    for i in range(0, len(vec) - 1, 2):
        out.append(float(sum(a * b for a, b in zip(vec[i], vec[i + 1]))))
    return out


def score_side(side: str, out_path: Path, cfg_path: Path, stimuli_dir: Path):
    cfgs = ts.load_pinned(cfg_path)
    only = [s.strip().lower() for s in os.environ.get("SWEEP_ONLY", "").split(",") if s.strip()]
    if only:
        cfgs = [c for c in cfgs if any(o in c["name"].lower() or o in c["model_id"].lower()
                                       for o in only)]
    if not cfgs:
        sys.exit("SWEEP_ONLY matched no configs")
    probes = probe_texts(stimuli_dir)
    texts = [p["text"] for p in probes]
    rec = {"side": side, "seed": SEED, "tol": TOL,
           "probes": [{"L": p["L"], "stim_id": p["stim_id"]} for p in probes],
           "probe_sha256": ts.hashlib.sha256("".join(texts).encode("utf-8")).hexdigest(),
           "host": ts.socket.gethostname(), "configs": {}}
    for cfg in cfgs:
        if side == "reference":
            # the pinned Paper A/E1 reference path: CPU, checkpoint-native dtype (no cast —
            # forcing fp32 on the fp16-native checkpoints is what broke parity in H4)
            cfg = dict(cfg, device="cpu", dtype_policy="checkpoint-native")
        ts.log(f"[{side}] {cfg['name']} on {cfg['device']}")
        model, eff, _deriv, prov = ts.load_model(cfg)
        # pair_rows contract of embed_cell: (anchor_id, position, pair, text_a, text_b);
        # consecutive probe texts form the gate's pairs, so the same loading and
        # MRL/normalization path serves reference and target with no second implementation.
        pair_rows = [(f"probe{i//2}", "gate", "probe", texts[i], texts[i + 1])
                     for i in range(0, len(texts) - 1, 2)]
        vec, _ntok = ts.embed_cell(model, cfg, pair_rows,
                                   int(os.environ.get("ST_BATCH", "8")))
        by_bin = {}
        for L in PROBE_BINS:
            idx = [i for i, p in enumerate(probes) if p["L"] == L]
            by_bin[str(L)] = [float((vec[texts[a]] * vec[texts[b]]).sum())
                              for a, b in zip(idx[0::2], idx[1::2])]
        rec["configs"][cfg["name"]] = {"provenance": prov, "effective_window": eff,
                                       "cosines_by_bin": by_bin}
        del model
    ts.atomic_write(out_path, rec)
    ts.log(f"[{side}] wrote {out_path}")


def compare(ref_path: Path, target_paths, out_path: Path):
    ref = json.loads(Path(ref_path).read_text(encoding="utf-8"))
    report = {"tol": TOL, "reference": str(ref_path), "probe_sha256": ref["probe_sha256"],
              "configs": {}, "verdict": "PASS"}
    for tp in target_paths:
        tgt = json.loads(Path(tp).read_text(encoding="utf-8"))
        if tgt["probe_sha256"] != ref["probe_sha256"]:
            sys.exit(f"probe-set mismatch: {tp} scored different texts than the reference")
        for name, tc in tgt["configs"].items():
            rc = ref["configs"].get(name)
            if rc is None:
                report["configs"][name] = {"verdict": "NO_REFERENCE", "target_host": tgt["host"]}
                report["verdict"] = "FAIL"
                continue
            per_bin, worst = {}, 0.0
            for L in PROBE_BINS:
                a = rc["cosines_by_bin"][str(L)]
                b = tc["cosines_by_bin"][str(L)]
                d = max((abs(x - y) for x, y in zip(a, b)), default=0.0)
                per_bin[str(L)] = d
                worst = max(worst, d)
            ok = worst <= TOL
            report["configs"][name] = {
                "target_host": tgt["host"], "target_device": tc["provenance"].get("device"),
                "max_abs_dcos": worst, "by_bin": per_bin,
                "verdict": "PASS" if ok else "FAIL",
                "note": "" if ok else "GPU shard NOT admissible for this config (§2); "
                                      "re-pin by dated amendment or run it on the reference path"}
            if not ok:
                report["verdict"] = "FAIL"
    ts.atomic_write(out_path, report)
    print(json.dumps({k: (v if k != "configs" else
                          {n: {"max_abs_dcos": c.get("max_abs_dcos"), "verdict": c["verdict"]}
                           for n, c in v.items()}) for k, v in report.items()}, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", choices=("reference", "target"))
    ap.add_argument("--compare", nargs="+", metavar=("REF", "TARGET"))
    ap.add_argument("--config", default=str(ts.DEFAULT_CONFIG))
    ap.add_argument("--stimuli", default=str(ts.DEFAULT_STIMULI))
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.compare:
        compare(Path(a.compare[0]), [Path(p) for p in a.compare[1:]], Path(a.out))
    elif a.side:
        score_side(a.side, Path(a.out), Path(a.config), Path(a.stimuli))
    else:
        ap.error("give --side or --compare")


if __name__ == "__main__":
    main()
