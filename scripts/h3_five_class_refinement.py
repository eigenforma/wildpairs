"""A9 labeled post-hoc refinement: H3 re-scored on the five-class cascade partition.

H3 (prereg-e1 §3) was scored on the three-class regex partition (kw2119 / number / other);
the deviation is disclosed as amendment A9 and the cascade has now run. This recomputes the
per-class median cosines from the FROZEN sweep under the semantic labels, so the paper can say
whether the verdict is partition-robust with a number instead of an argument.

Post-hoc by construction (labels assigned 2026-08-11/12, after the sweep). The prereg verdict
stands on the registered partition; this is a refinement, reported as such.

Recompute: python scripts/h3_five_class_refinement.py
Frozen:    results/verification/h3_five_class_refinement.json
"""
import json, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "results" / "verification"
BAR = 0.97

rows = [json.loads(l) for l in
        (ROOT / "results" / "wu" / "e1_class_cascade.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()]
cls = {r["pair_id"]: r["final"] for r in rows}
regex_cls = {r["pair_id"]: (r["regex_label"] or "none") for r in rows}
arbitrated = {r["pair_id"] for r in rows if r.get("arbiter")}

def table(labels, subset=None):
    out = {}
    for f in sorted((ROOT / "results" / "e1_sweep").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        g2 = d["granularities"]["g2"]
        per = {}
        for pid, c in labels.items():
            if subset is not None and pid not in subset:
                continue
            if pid in g2:
                per.setdefault(c, []).append(g2[pid])
        stats = {c: {"n": len(v), "median": round(statistics.median(v), 4)}
                 for c, v in sorted(per.items())}
        ranked = sorted(stats.items(), key=lambda kv: -kv[1]["median"])
        top2 = [k for k, _ in ranked[:2]]
        out[d["config"]] = {
            "by_class": stats, "top2": top2,
            "h3_style_hit": set(top2) == {"kw2119", "number"}
                            and all(stats[k]["median"] >= BAR for k in ("kw2119", "number")
                                    if k in stats)}
    return out

five = table(cls)
three = table(regex_cls)
five_arb = table(cls, subset=arbitrated)

hits5 = sum(1 for v in five.values() if v["h3_style_hit"])
hits3 = sum(1 for v in three.values() if v["h3_style_hit"])
res = {
    "note": "post-hoc refinement (A9); the registered H3 verdict on the three-class regex "
            "partition is unchanged and stands as FAILED",
    "bar": BAR, "granularity": "g2",
    "h3_style_hits_five_class": f"{hits5}/9",
    "h3_style_hits_three_class_recomputed": f"{hits3}/9",
    "class_sizes_five": {c: sum(1 for x in cls.values() if x == c) for c in sorted(set(cls.values()))},
    "regex_precision_vs_semantic": {
        "regex_number_n": sum(1 for p, c in regex_cls.items() if c == "number"),
        "regex_number_confirmed": sum(1 for p, c in regex_cls.items()
                                      if c == "number" and cls[p] == "number"),
        "regex_kw2119_n": sum(1 for p, c in regex_cls.items() if c == "kw2119"),
        "regex_kw2119_confirmed": sum(1 for p, c in regex_cls.items()
                                      if c == "kw2119" and cls[p] == "kw2119")},
    "five_class": five, "three_class_recomputed": three,
    "five_class_arbitrated_only": five_arb,
    "arbitrated_n": len(arbitrated),
    "unsampled_kept_bulk": sum(1 for r in rows if r.get("unsampled")),
}
(V / "h3_five_class_refinement.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")

print(f"H3-style hits: five-class {hits5}/9 | three-class {hits3}/9 (bar {BAR}, g2)")
print("class sizes:", res["class_sizes_five"])
p = res["regex_precision_vs_semantic"]
print(f"regex precision: number {p['regex_number_confirmed']}/{p['regex_number_n']}"
      f" = {p['regex_number_confirmed']/p['regex_number_n']:.1%}"
      f" | kw2119 {p['regex_kw2119_confirmed']}/{p['regex_kw2119_n']}"
      f" = {p['regex_kw2119_confirmed']/p['regex_kw2119_n']:.1%}")
print("\nper-config medians (five-class, g2):")
for cfg, v in five.items():
    b = v["by_class"]
    print(f"  {cfg[:44]:44} " + "  ".join(
        f"{c[:4]}={b[c]['median']:.3f}" for c in ("kw2119", "number", "polarity-negation",
                                                  "identifier-constant", "scope-other") if c in b)
          + f"  top2={v['top2']}")
