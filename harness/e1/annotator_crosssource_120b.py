"""Annotator B for the CROSS-SOURCE construct packet (refutation test for the
labelling-convention objection to the sign-flip law): the local gpt-oss-120b
(different model family, never exposed to any hypothesis) judges the 300 blind items under
docs/annotation_protocol_errata.md, one item per call, temperature 0.

  python3 harness/e1/annotator_errata_120b.py http://localhost:8080 <out.json>

Same firewall and mechanics as the bis-audit seat (harness/e1/annotator_b_120b.py), including
the harmony-template workaround: the Output-format section is stripped and the verdict is one
bare word. Resumable.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PROTOCOL = (ROOT / "docs" / "annotation_protocol_errata.md").read_text(encoding="utf-8")
PACKET = json.loads((ROOT / "results" / "verification" / "crosssource_blind_packet.json").read_text(encoding="utf-8"))

PROTOCOL_PROMPT = PROTOCOL.split("## Output format")[0]
SYSTEM = (
    "You are an independent blind annotator. Follow the protocol below exactly. Judge only from "
    "the two texts given. Answer with exactly one lowercase word: different, same, or unjudgeable. "
    "No other text.\n\n--- PROTOCOL ---\n" + PROTOCOL_PROMPT
)


def ask(base, a, b):
    body = {
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"text_A:\n{a}\n\ntext_B:\n{b}\n\nYour one-word verdict:"},
        ],
        "temperature": 0.0,
        "max_tokens": 2048,
    }
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            content = json.load(r)["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        print("SERVER ERROR BODY:", e.read().decode(errors="replace")[:500], flush=True)
        raise
    low = content.strip().lower()
    if low in ("different", "same", "unjudgeable"):
        return low
    for v in ("unjudgeable", "different", "same"):
        if v in low:
            return v
    return "unparseable"


def main():
    base, out_path = sys.argv[1].rstrip("/"), Path(sys.argv[2])
    done = {}
    if out_path.exists():
        done = {j["item"]: j["verdict"] for j in json.loads(out_path.read_text())["judgments"]}
    for it in PACKET:
        i = it["item"]
        if i in done:
            continue
        t0 = time.time()
        v = ask(base, it["text_A"], it["text_B"])
        done[i] = v
        out_path.write_text(json.dumps(
            {"annotator": "B", "context": "gpt-oss-120b local, blind protocol, temp 0",
             "judgments": [{"item": k, "verdict": done[k]} for k in sorted(done)]}, indent=1))
        print(f"[{time.strftime('%H:%M:%S')}] item {i}: {v} ({time.time()-t0:.0f}s) [{len(done)}/380]", flush=True)


if __name__ == "__main__":
    main()
