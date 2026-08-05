"""E2-P0 freeze: fetch the three CondaQA splits once from the canonical GitHub repo
(AbhilashaRavichander/CondaQA @ main, Apache-2.0 — license verified via the GitHub API
2026-08-05), store byte-exact, record in the corpus manifest. Same refusal discipline
as freeze_errata.py: frozen files are never overwritten.
"""
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://raw.githubusercontent.com/AbhilashaRavichander/CondaQA/main/data/"
SPLITS = ["condaqa_train.json", "condaqa_dev.json", "condaqa_test.json"]
DEST_DIR = ROOT / "corpus" / "e2_dilution"
MANIFEST = ROOT / "corpus" / "MANIFEST.json"


def main() -> None:
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"files": []}
    for name in SPLITS:
        dest = DEST_DIR / name
        if dest.exists():
            sys.exit(f"REFUSED: {dest} already exists. Frozen files are never overwritten.")
        url = BASE + name
        req = urllib.request.Request(url, headers={"User-Agent": "wildpairs-freeze/1.0 (research; scott@eigenforma.com)"})
        with urllib.request.urlopen(req, timeout=300) as r:
            raw = r.read()
        sha = hashlib.sha256(raw).hexdigest()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        manifest["files"].append(
            {
                "path": str(dest.relative_to(ROOT)).replace("\\", "/"),
                "source_url": url,
                "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "bytes": len(raw),
                "sha256": sha,
                "role": "E2 payload corpus: CondaQA (EMNLP 2022), Apache-2.0, canonical GitHub distribution",
            }
        )
        print(f"FROZEN {name}: {len(raw):,} bytes, sha256={sha[:16]}...")
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
