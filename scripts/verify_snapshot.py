"""E1-P0 snapshot verification: recompute every load-bearing count from the frozen errata
snapshot and report deltas against the independent second source (the 2026-08-05 workflow
feasibility verifier's parse). Encoder-blind: lexical statistics only.

Modes:
  python scripts/verify_snapshot.py             full verification -> results/verification/
  python scripts/verify_snapshot.py --manifest  checksum-verify every file in corpus/MANIFEST.json

No caps: the full file is parsed; every rate names its denominator; exclusions are counted,
never silently dropped.
"""
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "corpus" / "e1_errata" / "errata.json"
MANIFEST = ROOT / "corpus" / "MANIFEST.json"
OUT = ROOT / "results" / "verification" / "e1_snapshot_verification.json"

# Independent second source: workflow wf_61ec9d1f-b34 feasibility verifier, direct parse
# of a 2026-08-05 download (recorded in docs/experiments.md). Live-database drift between
# that download and our frozen snapshot is expected to be small and is reported, not hidden.
SECOND_SOURCE = {
    "total_entries": 7991,
    "status_Verified": 3710,
    "status_Held for Document Update": 2412,
    "status_Rejected": 1151,
    "status_Reported": 718,
    "verified_both_texts_Technical": 1895,
    "verified_both_texts_Editorial": 1683,
    "kw2119_multiset_changes_technical": 122,
    "number_multiset_changes_technical": 782,
    "jaccard_median_Technical": 0.889,
    "jaccard_median_Editorial": 0.912,
}

KW_PATTERN = re.compile(
    r"\b(MUST NOT|SHALL NOT|SHOULD NOT|NOT RECOMMENDED|MUST|REQUIRED|SHALL|SHOULD|RECOMMENDED|MAY|OPTIONAL)\b"
)
NUM_PATTERN = re.compile(r"\d+(?:\.\d+)?")
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
PERM_SEED = 20260805
PERM_N = 20000


def tokens(text: str) -> set:
    return set(TOKEN_PATTERN.findall(text.lower()))


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta and not tb:
        return 1.0
    return len(ta & tb) / len(ta | tb)


def median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def cliffs_delta(xs, ys):
    """delta = P(x>y) - P(x<y), computed exactly via merge-counting O((n+m)log(n+m))."""
    xs_s, n, m = sorted(xs), len(xs), len(ys)
    import bisect

    gt = lt = 0
    for y in ys:
        lo = bisect.bisect_left(xs_s, y)
        hi = bisect.bisect_right(xs_s, y)
        lt += lo            # x < y
        gt += n - hi        # x > y
    return (gt - lt) / (n * m)


def permutation_p(xs, ys, n_perm=PERM_N, seed=PERM_SEED):
    """Two-sided permutation test, statistic = mean(xs) - mean(ys)."""
    rng = random.Random(seed)
    pooled = list(xs) + list(ys)
    n = len(xs)
    obs = sum(xs) / len(xs) - sum(ys) / len(ys)
    total = sum(pooled)
    count = len(pooled)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(pooled)
        mx = sum(pooled[:n]) / n
        my = (total - mx * n) / (count - n)
        if abs(mx - my) >= abs(obs):
            hits += 1
    return obs, (hits + 1) / (n_perm + 1)


def verify_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text())
    bad = 0
    for f in manifest["files"]:
        if f.get("external"):
            # Corpus lives on a lab host (f["host"], under f["mount"]). Verify locally when
            # that mount is present (i.e. we ARE that host), over ssh with --external from Wu,
            # and otherwise skip without failing -- nodes cannot all reach each other.
            full = f["mount"].rstrip("/") + "/" + f["path"]  # POSIX path on the lab host, never os-local
            if Path(full).exists():
                sha = hashlib.sha256(Path(full).read_bytes()).hexdigest()
                ok = sha == f["sha256"]
                bad += 0 if ok else 1
                print(f"{'OK     ' if ok else 'CORRUPT'} {f['host']}:{full} (local mount)")
            elif "--external" in sys.argv:
                import subprocess

                r = subprocess.run(
                    ["ssh", "-o", "BatchMode=yes", f["host"], f"sha256sum '{full}'"],
                    capture_output=True, text=True, timeout=1800,
                )
                sha = r.stdout.split()[0] if r.returncode == 0 and r.stdout else ""
                ok = sha == f["sha256"]
                bad += 0 if ok else 1
                print(f"{'OK     ' if ok else 'CORRUPT'} {f['host']}:{full} (ssh)")
            else:
                print(f"EXTERN  {f['host']}:{full} (skipped; use --external to verify over ssh)")
            continue
        p = ROOT / f["path"]
        if not p.exists():
            print(f"MISSING {f['path']}")
            bad += 1
            continue
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        ok = sha == f["sha256"]
        bad += 0 if ok else 1
        print(f"{'OK     ' if ok else 'CORRUPT'} {f['path']}")
    print("ALL OK" if bad == 0 else f"FAILED: {bad} file(s)")
    sys.exit(0 if bad == 0 else 1)


def main() -> None:
    if "--manifest" in sys.argv:
        verify_manifest()

    raw = SNAPSHOT.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    data = json.loads(raw)
    assert isinstance(data, list), "schema drift: expected a top-level list"
    required = {"errata_status_code", "errata_type_code", "orig_text", "correct_text", "doc-id"}
    missing = required - set(data[0].keys())
    assert not missing, f"schema drift: first record lacks {missing}"

    result = {"snapshot_sha256": sha, "snapshot_bytes": len(raw)}
    result["total_entries"] = len(data)
    status = Counter(e.get("errata_status_code") for e in data)
    for k, v in status.items():
        result[f"status_{k}"] = v

    def has_both(e):
        return bool((e.get("orig_text") or "").strip()) and bool((e.get("correct_text") or "").strip())

    verified = [e for e in data if e.get("errata_status_code") == "Verified"]
    vt = [e for e in verified if e.get("errata_type_code") == "Technical" and has_both(e)]
    ve = [e for e in verified if e.get("errata_type_code") == "Editorial" and has_both(e)]
    result["verified_both_texts_Technical"] = len(vt)
    result["verified_both_texts_Editorial"] = len(ve)
    result["verified_missing_text_excluded"] = len(verified) - len(vt) - len(ve) - sum(
        1 for e in verified if e.get("errata_type_code") not in ("Technical", "Editorial")
    )

    kw_changed = sum(
        1 for e in vt if Counter(KW_PATTERN.findall(e["orig_text"])) != Counter(KW_PATTERN.findall(e["correct_text"]))
    )
    num_changed = sum(
        1 for e in vt if Counter(NUM_PATTERN.findall(e["orig_text"])) != Counter(NUM_PATTERN.findall(e["correct_text"]))
    )
    result["kw2119_multiset_changes_technical"] = kw_changed
    result["number_multiset_changes_technical"] = num_changed

    jt = [jaccard(e["orig_text"], e["correct_text"]) for e in vt]
    je = [jaccard(e["orig_text"], e["correct_text"]) for e in ve]
    result["jaccard_median_Technical"] = round(median(jt), 4)
    result["jaccard_median_Editorial"] = round(median(je), 4)
    result["jaccard_mean_Technical"] = round(sum(jt) / len(jt), 4)
    result["jaccard_mean_Editorial"] = round(sum(je) / len(je), 4)
    result["cliffs_delta_T_vs_E"] = round(cliffs_delta(jt, je), 4)
    obs, p = permutation_p(jt, je)
    result["perm_mean_diff_T_minus_E"] = round(obs, 4)
    result["perm_p_two_sided"] = round(p, 6)
    result["perm_spec"] = f"mean-diff statistic, {PERM_N} permutations, seed {PERM_SEED}"

    deltas = {}
    for k, ref in SECOND_SOURCE.items():
        ours = result.get(k)
        if isinstance(ref, float):
            deltas[k] = {"ours": ours, "second_source": ref, "delta": round(ours - ref, 4)}
        else:
            deltas[k] = {"ours": ours, "second_source": ref, "delta": ours - ref}
    result["two_source_check"] = deltas

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
