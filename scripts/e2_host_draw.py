"""E2 host draw - the frozen section-2 "Host assignment" pin, executed (PREREGISTRATION_E2,
tag prereg-e2): ONE host document per (anchor x domain), drawn once with seed 20260805,
reused across all (L, position) cells. Pools: enwiki = ns-0 non-redirect articles with
ws_tokens >= 3151 (W(4096)) from the scan's articles_index.tsv, EXCLUDING every article
matched to a CondaQA passage (any non-null title in the scan results); PMC = the frozen
2,000-article slice (qualifies by construction); RFC = frozen rfc-text rfc<N>.txt docs
>= 3151 ws. The payload/source-passage contamination exclusion is applied by the build
(it needs text): each draw carries K=4 seeded backup candidates and the build takes the
FIRST qualifying candidate, recording every substitution - so the operative host is a
deterministic function of (seed, anchor_id, domain, pool order) alone.

Also emits the NATIVE join (not a draw): anchor -> matched enwiki title, via exact
passage-text equality against the scan's condaqa_passages.jsonl (ids 1..1289) joined to
results/verification/e2_native_scan_results.jsonl; unmatched anchors drop from NATIVE
only (disclosed).

Recompute: python scripts/e2_host_draw.py   (pool indices pulled from agora coldstore:
  corpus/e2_dilution/hostpools/{enwiki_hostpool_ge3151.tsv, pmc_list.txt, rfc_wc.txt,
  condaqa_passages.jsonl})
Frozen:    results/verification/e2_host_draw.json (+ needed_*.txt work lists for the
  agora extraction step). Refuses to overwrite the frozen draw without --force.
"""
import argparse
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOLS = ROOT / "corpus" / "e2_dilution" / "hostpools"
ANCHORS = ROOT / "corpus" / "e2_dilution" / "anchors_frozen.jsonl"
SCAN = ROOT / "results" / "verification" / "e2_native_scan_results.jsonl"
OUT = ROOT / "results" / "verification" / "e2_host_draw.json"

SEED = 20260805
K = 4
MIN_WS = 3151          # W(4096) = ceil(4096/1.3), the pinned pool length rule
RFC_NAME = re.compile(r"^rfc\d+\.txt$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collapse(s: str) -> str:
    return " ".join(s.split())


def load_pools(scan_titles):
    pools, meta = {}, {}
    p = POOLS / "enwiki_hostpool_ge3151.tsv"
    titles, n_raw, n_excl, n_short = [], 0, 0, 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        n_raw += 1
        title, ws, _off = line.split("\t")
        if int(ws) < MIN_WS:      # pre-filtered upstream; verified here, never trusted
            n_short += 1
            continue
        if title in scan_titles:
            n_excl += 1
            continue
        titles.append(title)
    pools["enwiki"] = titles
    meta["enwiki"] = {"source": str(p), "sha256": sha256_file(p), "order": "dump order",
                      "rows": n_raw, "below_min_ws": n_short,
                      "excluded_condaqa_matched": n_excl, "n_pool": len(titles)}
    p = POOLS / "pmc_list.txt"
    pmc = sorted(l.strip()[:-4] for l in p.read_text(encoding="utf-8").splitlines()
                 if l.strip().endswith(".txt"))
    pools["pmc"] = pmc
    meta["pmc"] = {"source": str(p), "sha256": sha256_file(p), "order": "lexicographic",
                   "n_pool": len(pmc),
                   "note": "frozen 2,000-article slice qualifies by construction"}
    if len(pmc) != 2000:
        sys.exit(f"PMC pool is {len(pmc)} files, expected the frozen 2,000")
    p = POOLS / "rfc_wc.txt"
    rfc, n_rfc_short = [], 0
    for line in p.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2 or not RFC_NAME.match(parts[1]):
            continue
        if int(parts[0]) >= MIN_WS:
            rfc.append(parts[1][:-4])
        else:
            n_rfc_short += 1
    rfc.sort()
    pools["rfc"] = rfc
    meta["rfc"] = {"source": str(p), "sha256": sha256_file(p), "order": "lexicographic",
                   "n_pool": len(rfc), "below_min_ws": n_rfc_short}
    return pools, meta


def draw_candidates(pool, anchor_id, domain):
    rng = random.Random(int(hashlib.sha256(
        f"{SEED}|{anchor_id}|{domain}".encode("utf-8")).hexdigest(), 16))
    picks, seen = [], set()
    while len(picks) < min(K, len(pool)):
        i = rng.randrange(len(pool))
        if i not in seen:
            seen.add(i)
            picks.append(pool[i])
    return picks


def native_join(anchors):
    passages = {}
    for line in (POOLS / "condaqa_passages.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            passages[collapse(r["text"])] = r["passage_id"]
    scan = {}
    for line in SCAN.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            scan[r["passage_id"]] = (r["tier"], r.get("title"))
    rows, unmapped = [], []
    for a in anchors:
        pid = passages.get(collapse(a["passage"]))
        if pid is None:
            unmapped.append(a["anchor_id"])
            rows.append({"anchor_id": a["anchor_id"], "passage_pid": None,
                         "tier": "unmapped", "title": None})
            continue
        tier, title = scan.get(pid, ("none", None))
        rows.append({"anchor_id": a["anchor_id"], "passage_pid": pid, "tier": tier,
                     "title": title if tier != "none" else None})
    return rows, unmapped


def main(argv=None):
    ap = argparse.ArgumentParser(description="E2 frozen host draw (seed 20260805)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting an existing frozen draw")
    args = ap.parse_args(argv)
    out_path = Path(args.out)
    if out_path.exists() and not args.force:
        sys.exit(f"{out_path} exists - the frozen draw is never overwritten silently")

    anchors = [json.loads(l) for l in ANCHORS.read_text(encoding="utf-8").splitlines()
               if l.strip()]
    if len(anchors) != 959:
        sys.exit(f"{len(anchors)} anchors, expected the frozen 959")
    scan_titles = set()
    for line in SCAN.read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line).get("title")
            if t:
                scan_titles.add(t)
    pools, pool_meta = load_pools(scan_titles)

    draws = []
    for a in anchors:
        for domain in ("enwiki", "pmc", "rfc"):
            cand = draw_candidates(pools[domain], a["anchor_id"], domain)
            draws.append({"anchor_id": a["anchor_id"], "domain": domain,
                          "host_id": cand[0], "candidates": cand})
    native_rows, unmapped = native_join(anchors)
    n_native = sum(1 for r in native_rows if r["title"])

    doc = {
        "meta": {
            "prereg": "PREREGISTRATION_E2.md section 2 'Host assignment, pinned' "
                      "(tag prereg-e2)",
            "seed": SEED, "candidates_per_draw": K, "min_ws_tokens": MIN_WS,
            "rule": "one host per (anchor x domain), reused across all (L, position); "
                    "operative host = first candidate passing the build's contamination "
                    "exclusion, substitutions recorded in the build manifest",
            "anchors": {"path": str(ANCHORS), "sha256": sha256_file(ANCHORS), "n": 959},
            "scan_exclusion": {"path": str(SCAN), "sha256": sha256_file(SCAN),
                               "titles_excluded": len(scan_titles)},
            "pools": pool_meta,
            "native_join": {"matched_anchors": n_native, "of": len(anchors),
                            "unmapped_passages": unmapped},
            "recompute": "python scripts/e2_host_draw.py",
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "draws": draws,
        "native": native_rows,
    }
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")

    need_titles = sorted({c for d in draws if d["domain"] == "enwiki"
                          for c in d["candidates"]}
                         | {r["title"] for r in native_rows if r["title"]})
    (POOLS / "needed_enwiki_titles.txt").write_text(
        "\n".join(need_titles) + "\n", encoding="utf-8", newline="\n")  # LF: lists are
    for dom, suffix in (("pmc", ".txt"), ("rfc", ".txt")):              # consumed on linux
        need = sorted({c for d in draws if d["domain"] == dom for c in d["candidates"]})
        (POOLS / f"needed_{dom}.txt").write_text(
            "\n".join(n + suffix for n in need) + "\n", encoding="utf-8", newline="\n")
        print(f"{dom}: {len(need)} unique hosts needed")
    print(f"enwiki: {len(need_titles)} unique articles needed "
          f"(candidates + {n_native} native)")
    print(f"FROZEN {out_path} ({len(draws)} draws over {len(anchors)} anchors x 3 domains; "
          f"native matched {n_native}/{len(anchors)})")


if __name__ == "__main__":
    main()
