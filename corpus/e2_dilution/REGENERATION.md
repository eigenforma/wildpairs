# Regenerating the E2 derived corpora (3.32 GB, deliberately untracked)

These artifacts are **deterministic functions of frozen inputs plus committed code**, so the
repository carries their sha256 manifest (`REGENERABLE_MANIFEST.json`) and the commands to
rebuild them bit-identically, not the bytes. Three reasons, in order of force:

1. **License.** `stimuli_rfc_splice.jsonl` is spliced RFC text. PREREGISTRATION_E2 §2 commits
   this program to "spliced RFC derivatives are never redistributed — regeneration script +
   checksums only" (Paper A §9's read-but-not-redistributed precedent). Shipping the bytes would
   break the policy the program set for itself. enwiki hosts are CC BY-SA and PMC hosts are
   CC-BY-class; both are redistributable *with* their terms, but the same regeneration route
   serves them and keeps one rule for all three domains.
2. **Durability.** Seven of these files exceed GitHub's 100 MB hard per-file limit; tracking them
   makes the repository unpushable, i.e. **the tracked bytes were the thing preventing off-site
   backup of everything else.**
3. **They are outputs, not evidence.** Every claim in the papers recomputes from
   `results/**` + the frozen source corpora; the stimuli are an intermediate.

The frozen *inputs* (errata.json, CondaQA, the host draw, anchors) and all *results* stay
tracked. The enwiki/PMC/RFC source corpora live on the fleet with `corpus/MANIFEST.json`
checksums, plus the PMC two-site freeze.

## Rebuild, in order

```bash
# 1. host draw (already tracked as results/verification/e2_host_draw.json - verify, don't redraw)
python scripts/e2_host_draw.py --seed 20260805 --out results/verification/e2_host_draw.json

# 2. host text extraction (needs the fleet's frozen dumps; ranged multistream decompression)
python scripts/e2_extract_articles.py            # enwiki hosts + native extended passages
python scripts/e2_pack_hostpools.py              # packs hosts_{enwiki,pmc,rfc}.jsonl + manifest

# 3. stimuli construction (pure function of hostpools + anchors_frozen + the pinned rules)
python harness/e2/titration_build.py --seed 20260805 \
    --draw results/verification/e2_host_draw.json

# 4. verify bit-identity against the manifest
python -c "import json,hashlib,os; m=json.load(open('corpus/e2_dilution/REGENERABLE_MANIFEST.json')); \
[print(('OK  ' if hashlib.sha256(open(p,'rb').read()).hexdigest()==v['sha256'] else 'DIFF'), p) \
 for p,v in m.items()]"
```

A `DIFF` means the build is not reproducing the frozen instrument — treat it as an instrument
defect and investigate before analyzing anything, exactly as E3 amendment A2 handled its caliper
bug.

## What the manifest covers

13 artifacts, 3.32 GB: the four stimuli files (three SPLICE domains + NATIVE), the four host
pools, the enwiki host-pool index, the native extended passages, and the two `needed_*` source
bundles. Sizes and sha256 for each are in `REGENERABLE_MANIFEST.json`.

---

## E2 score files (added 2026-08-12)

Same rule, applied to the sweep outputs. **Tracked:** the four per-node shards as `.json.gz`
(~20 MB total, 96% compression; these are the irreplaceable GPU output) plus
`results/E2_SCORES_MANIFEST.json` with the sha256 of every uncompressed file.
**Untracked:** `results/{odd,even}/e2_shard.json` and `results/e2_scores_merged.json` (1.07 GB),
which are deterministic functions of the shards produced by committed scripts in about a minute:

```bash
gunzip -k results/forge/e2_shard_*.json.gz results/agora/e2_shard_*.json.gz
python scripts/e2_concat_node_shards.py results/forge/e2_shard_odd.json  results/agora/e2_shard_odd.json  --out results/odd/e2_shard.json
python scripts/e2_concat_node_shards.py results/forge/e2_shard_even.json results/agora/e2_shard_even.json --out results/even/e2_shard.json
python scripts/merge_shards.py results/odd/e2_shard.json results/even/e2_shard.json --verify-config-hash --out results/e2_scores_merged.json
python harness/e2/e2_analysis.py --scores results/e2_scores_merged.json \
    --stimuli corpus/e2_dilution/stimuli/stimuli_enwiki_splice.jsonl --out results/e2_analysis.json
```

`results/e2_analysis.json` (2.4 MB) — the file the paper actually reads — stays tracked, as does
every other frozen result. Verify any rebuild against `E2_SCORES_MANIFEST.json`.
