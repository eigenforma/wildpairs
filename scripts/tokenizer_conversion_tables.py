"""Pre-tag table: per-encoder tokenizer conversion factors and effective windows
(PREREGISTRATION_E2 §2 — the last lexical table before the tag).

For each pinned configuration's tokenizer (harness/configs/e2_pinned.json): the number of
special tokens added to a single-sequence encoding, the effective window (model max length −
specials), and the measured whitespace→subword conversion ratio on three frozen registers
(the 959 anchor payloads; a 200-passage CondaQA sample; a 200-sentence bis sample as the RFC
register proxy). Tokenizers are lexical — no encoder weights load, no text is embedded.

Recompute: python scripts/tokenizer_conversion_tables.py
Frozen:    results/verification/e2_tokenizer_tables.json
"""
import json, random, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from transformers import AutoTokenizer  # noqa: E402

cfgs = json.loads((ROOT / "harness" / "configs" / "e2_pinned.json").read_text(encoding="utf-8"))
anchors = [json.loads(l) for l in (ROOT / "corpus" / "e2_dilution" / "anchors_frozen.jsonl")
           .read_text(encoding="utf-8").splitlines() if l.strip()]
rng = random.Random(20260805)
payloads = [a["payload_orig"] for a in anchors]
passages = rng.sample([a["passage"] for a in anchors], 200)
bis = [json.loads(l)["old_sentence"] for l in
       (ROOT / "corpus" / "e1_errata" / "bis_pairs.jsonl").read_text(encoding="utf-8").splitlines()[:4000]
       if l.strip()]
bis = rng.sample(bis, 200)

def ratios(tk, texts, prefix=""):
    r = []
    for t in texts:
        ws = len(t.split())
        if not ws:
            continue
        sub = len(tk(prefix + t, add_special_tokens=False)["input_ids"])
        r.append(sub / ws)
    return {"median": round(statistics.median(r), 3),
            "p90": round(sorted(r)[int(0.9 * len(r))], 3)}

out = {"computed": "2026-08-11, pre-tag (tokenizers only — no weights, no embeddings)",
       "construction_factor": 1.3, "configs": {}}
worst_p90 = 0.0
_tk_cache = {}
for c in cfgs["configs"] if isinstance(cfgs, dict) and "configs" in cfgs else cfgs:
    name, ckpt = c["name"], c["model_id"]
    prefix = c.get("prefix") or ""
    try:
        if ckpt not in _tk_cache:
            _tk_cache[ckpt] = AutoTokenizer.from_pretrained(
                ckpt, trust_remote_code=bool(c.get("trust_remote_code")))
        tk = _tk_cache[ckpt]
    except Exception as e:  # noqa: BLE001
        out["configs"][name] = {"error": str(e)[:160]}
        continue
    specials = len(tk("x")["input_ids"]) - len(tk("x", add_special_tokens=False)["input_ids"])
    model_max = tk.model_max_length if tk.model_max_length < 10**9 else None
    row = {"checkpoint": ckpt, "specials_single_sequence": specials,
           "model_max_length": model_max,
           "effective_window": (model_max - specials) if model_max else None,
           "ws_to_subword": {"payloads": ratios(tk, payloads, prefix),
                             "condaqa_passages": ratios(tk, passages, prefix),
                             "rfc_bis_sentences": ratios(tk, bis, prefix)}}
    out["configs"][name] = row
    for reg in row["ws_to_subword"].values():
        worst_p90 = max(worst_p90, reg["p90"])
out["worst_p90_ratio"] = round(worst_p90, 3)
out["factor_verdict"] = ("1.3 construction factor COVERS the worst measured p90 ratio"
                         if worst_p90 <= 1.3 else
                         f"1.3 construction factor is EXCEEDED by worst p90 {worst_p90} — "
                         "realized tokens can overrun nominal bins for that register/config; "
                         "disclosed, truncation flags carry it")
(ROOT / "results" / "verification" / "e2_tokenizer_tables.json").write_text(
    json.dumps(out, indent=1) + "\n", encoding="utf-8")
print(json.dumps({k: v for k, v in out.items() if k != "configs"}, indent=1))
for n, r in out["configs"].items():
    print(n, "->", json.dumps(r.get("ws_to_subword", r), default=str)[:150],
          "| specials", r.get("specials_single_sequence"), "| window", r.get("effective_window"))
