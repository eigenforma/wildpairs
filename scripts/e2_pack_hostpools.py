"""Pack the extracted host texts into the build's host-pool jsonls (Wu side, after
scripts/e2_host_draw.py and the agora extraction/tar steps).

Inputs : results/verification/e2_host_draw.json (frozen draw + native join),
         corpus/e2_dilution/hostpools/articles_text.jsonl ({title, ws_tokens, text}),
         corpus/e2_dilution/hostpools/pmc/ and rfc/ (the needed slice/doc files).
Outputs: corpus/e2_dilution/hostpools/hosts_enwiki.jsonl  {host_id, title, text}
         corpus/e2_dilution/hostpools/native_extended.jsonl {passage_id, extended_text}
           (passage_id == anchor_id, the build's join key)
         corpus/e2_dilution/hostpools/hosts_pmc.jsonl, hosts_rfc.jsonl {host_id, text}
         + hostpools_manifest.json (counts, sha256s, coverage).
Coverage rule: every DRAW candidate must have text (a missing extraction disqualifies
that candidate; an anchor whose entire candidate list is textless is a hard error);
native titles missing from the extraction drop from NATIVE only (counted).
Recompute: python scripts/e2_pack_hostpools.py
"""
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOLS = ROOT / "corpus" / "e2_dilution" / "hostpools"
DRAW = ROOT / "results" / "verification" / "e2_host_draw.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    draw = json.loads(DRAW.read_text(encoding="utf-8"))
    articles = {}
    art_path = POOLS / "articles_text.jsonl"
    for line in art_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            articles[r["title"]] = r["text"]

    manifest = {"inputs": {"draw": {"path": str(DRAW), "sha256": sha256_file(DRAW)},
                           "articles": {"path": str(art_path),
                                        "sha256": sha256_file(art_path),
                                        "n": len(articles)}},
                "outputs": {}, "coverage": {}}

    # ---- enwiki hosts: every candidate that has text; whole-list-missing = hard error
    need = {}
    for d in draw["draws"]:
        if d["domain"] == "enwiki":
            need[d["anchor_id"]] = d["candidates"]
    out = POOLS / "hosts_enwiki.jsonl"
    written, textless = set(), set()
    dead_anchors = []
    with out.open("w", encoding="utf-8") as f:
        for aid, cands in need.items():
            have = [c for c in cands if c in articles]
            if not have:
                dead_anchors.append(aid)
                continue
            for c in have:
                if c not in written:
                    written.add(c)
                    f.write(json.dumps({"host_id": c, "title": c,
                                        "text": articles[c]},
                                       ensure_ascii=False) + "\n")
            textless.update(c for c in cands if c not in articles)
    manifest["coverage"]["enwiki"] = {
        "hosts_written": len(written), "candidates_without_text": sorted(textless),
        "anchors_with_no_textual_candidate": dead_anchors}
    if dead_anchors:
        sys.exit(f"{len(dead_anchors)} anchors have no extracted candidate text "
                 f"(first: {dead_anchors[0]}) - extraction incomplete")
    manifest["outputs"]["hosts_enwiki"] = {"path": str(out), "sha256": sha256_file(out)}

    # ---- native: matched titles only; missing extraction drops from NATIVE (counted)
    out = POOLS / "native_extended.jsonl"
    n_nat, nat_missing = 0, []
    with out.open("w", encoding="utf-8") as f:
        for r in draw["native"]:
            if not r["title"]:
                continue
            text = articles.get(r["title"])
            if text is None:
                nat_missing.append(r["anchor_id"])
                continue
            f.write(json.dumps({"passage_id": r["anchor_id"], "extended_text": text},
                               ensure_ascii=False) + "\n")
            n_nat += 1
    manifest["coverage"]["native"] = {"rows": n_nat,
                                      "matched_but_unextracted": nat_missing}
    manifest["outputs"]["native_extended"] = {"path": str(out),
                                              "sha256": sha256_file(out)}

    # ---- pmc / rfc from the pulled needed files
    for dom in ("pmc", "rfc"):
        src_dir = POOLS / dom
        need_ids = sorted({c for d in draw["draws"] if d["domain"] == dom
                           for c in d["candidates"]})
        out = POOLS / f"hosts_{dom}.jsonl"
        missing = []
        with out.open("w", encoding="utf-8") as f:
            for hid in need_ids:
                p = src_dir / f"{hid}.txt"
                if not p.exists():
                    missing.append(hid)
                    continue
                text = " ".join(p.read_text(encoding="utf-8",
                                            errors="replace").split())
                f.write(json.dumps({"host_id": hid, "text": text},
                                   ensure_ascii=False) + "\n")
        if missing:
            sys.exit(f"{dom}: {len(missing)} needed host files absent under {src_dir} "
                     f"(first: {missing[0]})")
        manifest["coverage"][dom] = {"hosts_written": len(need_ids)}
        manifest["outputs"][f"hosts_{dom}"] = {"path": str(out),
                                               "sha256": sha256_file(out)}

    manifest["created_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest["recompute"] = "python scripts/e2_pack_hostpools.py"
    mp = POOLS / "hostpools_manifest.json"
    mp.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest["coverage"][k] if k != "enwiki" else
                      {kk: (vv if not isinstance(vv, list) else len(vv))
                       for kk, vv in manifest["coverage"][k].items()}
                      for k in manifest["coverage"]}, indent=1))
    print(f"manifest: {mp}")


if __name__ == "__main__":
    main()
