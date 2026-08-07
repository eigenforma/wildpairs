# PREREGISTRATION — E3: The Composed Factorial (brand-name flank guard)

> **Binds at tag `prereg-e3`. No encoder has scored any composed pair at this freeze.** The
> per-source coupling orientations (§4) were measured encoder-blind by `harness/e3/build_composed.py`
> and are disclosed observations, not predictions.

## 1. Corpus and sampling

Pools: `pairs_pool.jsonl` (83k pairs; frozen sources per `corpus/MANIFEST.json`). Sweep sample:
per source (paws, qqp, snli, mnli), **2,000 "break" + 2,000 "preserve"** drawn uniformly with seed
20260805 (16,000 pairs total), fixed by `harness/e3/sample_sweep.py` and committed before scoring.

## 2. Numerics and device pins (fixed before the sweep)

fp32 everywhere (ST_FP32=1 on CUDA; MPS default fp32 on Metal). One pinned device per config —
**Forge (3090)**: mxbai, bge, e5 (both) · **Agora (16 GB)**: nomic-clustering, gte · **Lear
(MPS)**: MiniLM, mpnet · **Wu (CPU, pinned Paper A path)**: production router. Both llama-servers
evicted for the sortie and restored after (evict-before-load). No cross-device substitution after
this pin; a device failure re-pins by amendment, dated.

## 3. Hypotheses and bars

- **HE3-1 (artifact share, the headline):** on each aligned source (qqp, snli, mnli), naive AUROC
  minus caliper-matched AUROC ≥ **0.10** for ≥ 7 of 9 configs — the confounder's contribution to
  brand-name separability is large and measurable.
- **HE3-2 (the field's illusion, quantified):** naive AUROC on QQP ≥ **0.80** for ≥ 5 of 9 configs —
  cosine *looks* excellent exactly where the coupling carries it.
- **HE3-3 (PAWS as truth serum):** on PAWS (matched by design, δ = +0.006), every config's AUROC ∈
  [**0.50, 0.75**] and the production path ≤ **0.62** — residual decision content is modest even for
  the strongest encoders when wording can't help.
- **HE3-4 (shipped ceilings):** balanced accuracy at operating points {0.80, 0.85, 0.95} ≤ **0.70**
  in every (config, source) cell — Paper A's ceiling reproduced on the field's own benchmarks.
- **HE3-5 (coupling spectrum prediction):** rank order of per-config naive AUROC across sources
  follows coupling magnitude (qqp > snli ≥ mnli > paws) for ≥ 7 of 9 configs — separability tracks
  the confounder, not the encoder.

## 4. Disclosed encoder-blind measurements (the brand-name coupling rows)

From `results/e3_coupling_stats.json`: paws δ = +0.006 (matched, adversarial); qqp δ = −0.443,
snli δ = −0.372, mnli δ = −0.336 (all aligned — meaning-breaking pairs are lexically farther).
Class medians and counts therein. These motivated HE3-2/HE3-5's directions; no cosine informed
anything in this document.

## 5. Analysis (pre-committed)

Per (config, source): naive AUROC; overlap-decile stratified AUROC; caliper-matched AUROC
(|ΔJaccard| ≤ 0.05 matched subsampling, seed 20260805); balanced accuracy at the six operating
points; bootstrap CIs (10,000, seed 20260805). Artifact share = naive − caliper, reported per cell
with CIs. All results frozen JSON; prose cites, never sources.

## 6. Freeze protocol

Tag `prereg-e3` on the commit containing this file and the sampler. Amendments below the tag line,
dated; post-hoc analyses labeled as such.

---
**AMENDMENT A1 (2026-08-07, before any scoring):** §2's blanket eviction is relaxed to
**evict-only-on-OOM**: measured post-boot headroom (Forge 8.8 GB free beside the resident 120B;
Agora 4.5 GB free beside the 20b) exceeds every E3 wing's footprint, and VRAM co-residency does
not affect pinned numerics. Any OOM during the sortie triggers eviction per the original clause.
Frozen sample: sha256 ceb307849323b1dd27e89a2b21ace89d84266ab8f37e30abd9c04047f5abc497 (16,000
pairs, 2,000×2×4, seed 20260805), committed as corpus/e3_composed_sweep_sample.jsonl.
