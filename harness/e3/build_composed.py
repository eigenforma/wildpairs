"""E3-P1: build the composed corpus from the four frozen brand-name sources, encoder-blind.

Runs ON the host holding the frozen files (agora):
  python3 harness/e3/build_composed.py /mnt/coldstore/wildpairs/e3_composed

Extraction (evaluation splits only — no training-split text enters the corpus):
  SNLI  : snli_1.0_dev.jsonl + snli_1.0_test.jsonl        gold_label entailment -> preserve, contradiction -> break
  MNLI  : multinli_1.0_dev_matched.jsonl + _mismatched     same mapping
  QQP   : dev.tsv from QQP-clean.zip                       is_duplicate 1 -> preserve, 0 -> break
  PAWS  : labeled_final validation+test parquet            label 1 -> preserve, 0 -> break (adversarial high-overlap)

Emits pairs_pool.jsonl (full pools, one record per pair: source, label, text_a, text_b,
token-Jaccard) and results/e3_coupling_stats.json (per-source class Jaccard medians/means,
Cliff's delta, orientation verdict) — the three-regime table's brand-name rows, measured
before any encoder loads. Sampling for the sweep is fixed later at prereg-e3; this build
is population-level and deterministic. No caps: full splits parsed, exclusions counted.
"""
import io
import json
import re
import statistics
import sys
import zipfile
from bisect import bisect_left, bisect_right
from collections import defaultdict
from pathlib import Path

TOKEN = re.compile(r"[a-z0-9]+")


def jac(a: str, b: str) -> float:
    ta, tb = set(TOKEN.findall(a.lower())), set(TOKEN.findall(b.lower()))
    return len(ta & tb) / len(ta | tb) if (ta or tb) else 1.0


def cliffs(xs, ys):
    xs_s = sorted(xs)
    gt = lt = 0
    for y in ys:
        lt += bisect_left(xs_s, y)
        gt += len(xs_s) - bisect_right(xs_s, y)
    return (gt - lt) / (len(xs) * len(ys))


def emit(out, source, label, a, b):
    a, b = a.strip(), b.strip()
    if not a or not b or a == b:
        return None
    r = {"source": source, "label": label, "text_a": a, "text_b": b, "jaccard": round(jac(a, b), 4)}
    out.write(json.dumps(r, ensure_ascii=False) + "\n")
    return r


def main():
    root = Path(sys.argv[1])
    out_path = root / "pairs_pool.jsonl"
    stats_path = root / "e3_coupling_stats.json"
    out = out_path.open("w", encoding="utf-8")
    J = defaultdict(lambda: defaultdict(list))
    counts = defaultdict(int)

    def nli_rows(zf_name, members):
        with zipfile.ZipFile(root / zf_name) as z:
            for m in members:
                with z.open(m) as f:
                    for line in io.TextIOWrapper(f, encoding="utf-8"):
                        yield json.loads(line)

    for src, zf, members in [
        ("snli", "snli_1.0.zip", ["snli_1.0/snli_1.0_dev.jsonl", "snli_1.0/snli_1.0_test.jsonl"]),
        ("mnli", "multinli_1.0.zip", ["multinli_1.0/multinli_1.0_dev_matched.jsonl", "multinli_1.0/multinli_1.0_dev_mismatched.jsonl"]),
    ]:
        for r in nli_rows(zf, members):
            g = r.get("gold_label")
            if g == "entailment":
                lab = "preserve"
            elif g == "contradiction":
                lab = "break"
            else:
                counts[f"{src}_skipped_neutral_or_unlabeled"] += 1
                continue
            rec = emit(out, src, lab, r["sentence1"], r["sentence2"])
            if rec:
                J[src][lab].append(rec["jaccard"])
                counts[f"{src}_{lab}"] += 1

    with zipfile.ZipFile(root / "QQP-clean.zip") as z:
        name = next(n for n in z.namelist() if n.endswith("dev.tsv"))
        with z.open(name) as f:
            lines = io.TextIOWrapper(f, encoding="utf-8")
            header = next(lines).rstrip("\n").split("\t")
            qi, q2i, li = header.index("question1"), header.index("question2"), header.index("is_duplicate")
            for line in lines:
                p = line.rstrip("\n").split("\t")
                if len(p) <= max(qi, q2i, li):
                    counts["qqp_malformed"] += 1
                    continue
                lab = "preserve" if p[li] == "1" else "break"
                rec = emit(out, "qqp", lab, p[qi], p[q2i])
                if rec:
                    J["qqp"][lab].append(rec["jaccard"])
                    counts[f"qqp_{lab}"] += 1

    try:
        import pyarrow.parquet as pq
    except ImportError:
        sys.exit("pyarrow required: pip install pyarrow")
    for split in ("validation", "test"):
        t = pq.read_table(root / f"paws_labeled_final_{split}.parquet").to_pylist()
        for r in t:
            lab = "preserve" if r["label"] == 1 else "break"
            rec = emit(out, "paws", lab, r["sentence1"], r["sentence2"])
            if rec:
                J["paws"][lab].append(rec["jaccard"])
                counts[f"paws_{lab}"] += 1
    out.close()

    stats = {"counts": dict(sorted(counts.items()))}
    for src, cls in J.items():
        b, p = cls["break"], cls["preserve"]
        d = cliffs(b, p)
        stats[src] = {
            "n_break": len(b), "n_preserve": len(p),
            "jaccard_break": {"median": round(statistics.median(b), 4), "mean": round(statistics.mean(b), 4)},
            "jaccard_preserve": {"median": round(statistics.median(p), 4), "mean": round(statistics.mean(p), 4)},
            "cliffs_delta_break_vs_preserve": round(d, 4),
            "orientation": ("aligned (break less similar in wording -- confounder helps a low-cosine gate)" if d < -0.05
                            else "inverted (break MORE similar in wording -- confounder fights the gate)" if d > 0.05
                            else "near-matched"),
        }
    stats_path.write_text(json.dumps(stats, indent=2) + "\n")
    print(json.dumps({k: v for k, v in stats.items() if k != "counts"}, indent=2))
    print(json.dumps(stats["counts"], indent=2))


if __name__ == "__main__":
    main()
