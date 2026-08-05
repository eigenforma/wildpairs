"""E1-P0 freeze: fetch errata.json once, store byte-exact, record in the corpus manifest.

Freeze-first discipline: refuses to overwrite an existing frozen file (no --force flag
exists on purpose — a re-freeze is a new file name and a manifest entry, never a mutation).
"""
import hashlib
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://www.rfc-editor.org/errata.json"
DEST = ROOT / "corpus" / "e1_errata" / "errata.json"
MANIFEST = ROOT / "corpus" / "MANIFEST.json"


def main() -> None:
    if DEST.exists():
        sys.exit(f"REFUSED: {DEST} already exists. Frozen files are never overwritten.")
    req = urllib.request.Request(URL, headers={"User-Agent": "wildpairs-freeze/1.0 (research; scott@eigenforma.com)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
    sha = hashlib.sha256(raw).hexdigest()
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_bytes(raw)

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"files": []}
    manifest["files"].append(
        {
            "path": str(DEST.relative_to(ROOT)).replace("\\", "/"),
            "source_url": URL,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "bytes": len(raw),
            "sha256": sha,
            "role": "E1 primary corpus: RFC Editor errata database",
        }
    )
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"FROZEN {DEST.name}: {len(raw):,} bytes, sha256={sha}")


if __name__ == "__main__":
    main()
