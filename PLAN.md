# PLAN — wildpairs (Paper B execution program)

**Status: LIVE — updated as executed. Every figure in this file names the script that recomputes it (attractor hygiene, inherited from ruling-theory HANDOFF §7).**

Working repo name `wildpairs`: the property both experiments share — the pairs come from the wild, authored by nobody for this audit. Rename is free while private; operator ruling invited.

**Label collision, on the record:** ruling-theory `HANDOFF.md` §7 item 5 uses "Paper B" for the *methods* paper (corpus-lens debate, beartrap A/B). This program is the *empirical follow-up* to Similarity Gates (Paper A). Two different papers. In cross-repo references, this one is **wildpairs**, that one is **the methods paper**.

---

## 0. The frame

Paper A showed with an 80-pair authored instrument that cosine-threshold gates measure wording where they are deployed to measure meaning. wildpairs measures that failure where it lives: in text nobody authored for the audit, at the passage lengths deployed gates actually compare.

- **E1 — The Institution Flagged It.** 25 years of IETF errata verification supply meaning-change labels produced by an institution: each minimal edit ruled Technical (meaning-changing) or Editorial (meaning-preserving) by RFC-stream verifiers. Can any of the nine pinned encoder configurations, at any shipped operating point, see what the verifiers saw — and does anything fitted on errata survive transfer to bis-revision requirement-strength changes?
- **E2 — The Dilution Law.** CondaQA crowd-authored reversal/paraphrase payloads embedded in byte-identical real host passages (Wikipedia fit; PMC-OA and RFC held out), titrated L = 64→4096 tokens at controlled positions. Headline: the per-encoder critical length L* at which flip-vs-faithful AUROC falls below usable discrimination and below every shipped operating point. The ~1/L cosine-gap decay for mean pooling is pre-registered as *calibration*, not discovery.

They interlock: the RFC corpus is E1's label source and E2's held-out host register (one shared frozen snapshot). E1 observes dilution in the wild across three granularities; E2 titrates it causally.

Full experiment specifications, hypotheses with numeric bars, verified dataset provenance, and the adversarial novelty/feasibility findings: [docs/experiments.md](docs/experiments.md). Design provenance (14-agent design→judge→verify workflow, 2026-08-05): ruling-theory `docs/paper_b_experiments_2026-08-05.md`.

---

## 1. Integrity discipline — "not a single erratum in our data sets"

1. **Freeze-first.** Every external corpus is fetched once, stored byte-exact under `corpus/`, and named in `corpus/MANIFEST.json` with SHA-256, size, source URL, and retrieval time. No analysis touches a live URL. Recompute: `scripts/verify_snapshot.py --manifest`.
2. **Two-source verification for load-bearing counts.** Every count that appears in a claim is recomputed by a script in this repo AND was independently derived once elsewhere (the 2026-08-05 workflow verifier's parse is source #2 for E1; discrepancies are reported, not averaged).
3. **No caps.** Counting scripts process full files and report denominators with any excluded remainder named (ruling-theory `experiments/lib/evidence.py` discipline; ported here as `harness/lib/evidence.py` when the harness lands).
4. **Encoder-blind construction.** No encoder loads until the pre-registration for that experiment is frozen by tagged commit. The E1 freeze tag is `prereg-e1`; E2's is `prereg-e2`.
5. **Contamination boundaries.** The proposer never verifies its own claim. Annotation arms are independent lenses over one frozen corpus with predictions withheld. The second annotator (human or agent context) must not have seen this repo's corpora or predictions.
6. **Results are frozen JSON** under `results/`, written once by the harness, read by the paper. Prose never carries a number the JSONs cannot recompute.

## 2. Phase matrix — E1 (errata)

| phase | what | where | state |
|---|---|---|---|
| E1-P0 | Freeze `errata.json`; snapshot verification: reproduce the workflow verifier's counts (entries, status/type distributions, both-texts counts, keyword/number edit-class counts, Jaccard-by-class + Cliff's δ + permutation p) | this box (`scripts/freeze_errata.py`, `scripts/verify_snapshot.py`) | **executing 2026-08-05** |
| E1-P1 | Pre-registration freeze: exclusion filters, tokenizer, granularity extraction spec, H1–H5 bars, analysis plan; tag `prereg-e1` | this box | drafted — [PREREGISTRATION_E1.md](PREREGISTRATION_E1.md) |
| E1-P2 | Diff-localization → three granularities per pair (changed-sentence / quoted-passage / section-context); section-context needs RFC full text (rsync mirror on Agora NVMe); disclose quote-relocation match rate | this box + Agora | pending P1 |
| E1-P3 | Edit-class machine labeling with the tiered cascade: small-model bulk pass (Lear :11434 + Agora small models) → 120B arbitration on disagreements (Forge/Agora :8080) | swarm | pending P2; RUNBOOK R2 |
| E1-P4 | Encoder sweep: 9 pinned polaritycheck configurations × all pairs × 3 granularities; shipped operating points 0.30/0.40/0.60/0.80/0.85/0.95 | Forge (GPU) | pending P1 freeze; <1 GPU-hour; RUNBOOK R3 |
| E1-P5 | Human annotation: 300-pair label-noise arm + 200-pair bis alignment audit; κ; ~30 annotator-hours budgeted | operator + independent second | pending P3 |
| E1-P6 | Bis corpus mining: ALL obsoletes families from `rfc-index.xml`, aligned through intermediate revisions; artifact taxonomy excluded before labeling; gate: ≥100 human-verified genuine strength transitions | Agora (CPU + small models) | pending; RUNBOOK R4 |
| E1-P7 | Repairs fit on errata (per-encoder threshold; logistic cosine+Jaccard; NLI cross-encoder), frozen evaluation on bis; cluster bootstrap by RFC | Forge | pending P4+P6 |

## 3. Phase matrix — E2 (dilution)

| phase | what | where | state |
|---|---|---|---|
| E2-P0 | Freeze CondaQA snapshot (canonical GitHub distribution, Apache-2.0); measure the single-sentence-edit yield rate (pre-registered fallback target ≥400 anchors); payload length stats | this box | **DONE 2026-08-05** — two-source exact; **anchor yield 960/1,273 = 0.754**, recompute: `scripts/verify_condaqa.py` |
| E2-P1 | Acquire + freeze hosts: enwiki-20210701 (archive.org, ~19 GB), PMC-OA CC-BY slice (AWS mirror), RFC tarball (shared with E1) — **storage: Forge `/mnt/weight_vault` (1.4 TB free; Agora home has only 16 GB — fleet_watch finding), NFS-over-DAC serves it to Agora** | Forge storage, 300 Mbps egress budget | RUNBOOK R5 |
| E2-P2 | Pre-registration freeze (`prereg-e2`): length grid {64,128,256,512,1024,2048,4096}, positions, yield pipeline, α calibration claim, L* definitions, NevIR-anchored intercept prediction | this box | pending |
| E2-P3 | Titration build: SPLICE arm (primary, byte-identical hosts) + NATIVE arm (supporting; substring-match rate disclosed) | Agora | pending |
| E2-P4 | Embedding sweep: ~1–2M calls, 9 configs + long-context nomic; sharded Forge+Agora over the 40GbE DAC; truncation regime (L>512 on 512-window encoders) analyzed separately | Forge + Agora | 1–3 GPU-days; RUNBOOK R6 |
| E2-P5 | Two-annotator standalone-semantics relabel, 200 anchors; ~2 days | operator + independent second | pending |
| E2-P6 | Decay fit Δ(L)=Δ₀·(k/L)^α + monotone spline; L*(0.75), L*(0.55) per encoder; frozen prediction on PMC + RFC hosts | this box or Lear | pending P4 |
| E2-X | Lab-only extension arms: MRL family across truncation dims (does L* shrink with dim?); native-Poincaré encoders (the case Paper A §9 left open) | Forge | after P6, week-budget permitting |

## 4. Swarm job matrix and control triggers

Roles: **Forge/Macbeth** (24 GB VRAM) — all encoder sweeps, 120B arbitration. **Agora/Othello** (16 GB VRAM, Ops API :8000) — storage + mining + second embedding shard + 120B labeling. **Lear** (Mac, ollama :11434) — small-model bulk labeling, advisor, curve fitting. Interconnect: 40GbE DAC Forge↔Agora for shard exchange; USB4 Lear↔Agora backup.

Exact operator command triggers live in [RUNBOOK.md](RUNBOOK.md). **R0 (connectivity census) is the only blocker for everything swarm-side:** it verifies reachability of the three endpoints from this box, confirms repo transport (git pull vs rsync), and inventories the installed model/encoder families against the pinned polaritycheck checkpoints. Operator runs R0 once and pastes output back; the runbook then locks from placeholders to exact lines.

What this box (Windows/Falsifyer-adjacent) does regardless of the swarm: all freezing, all pre-registration, all statistics on frozen JSONs, all paper prose.

## 5. Standing asks of the operator (current, dated 2026-08-05)

1. Run RUNBOOK R0 (connectivity census) from any shell that can reach the LAN; paste output.
2. Ruling on repo name (`wildpairs` vs alternative attractor).
3. Ruling on LICENSE (blocking release, not development — same as Paper A; code and corpora may want different terms; all E1/E2 sources are BCP-78 / CC / Apache-2.0 and redistribution-safe except spliced RFC text, which ships as regeneration scripts, precedent Paper A §9).
4. Identify the independent second annotator (human, or an agent context that has never seen this repo — the boundary is load-bearing).

## 6. Execution log

- **2026-08-05** — Repo created. PLAN, experiments spec, PREREGISTRATION_E1 draft, RUNBOOK R0–R6 written. E1-P0 executed: `errata.json` frozen and verified — see `results/verification/e1_snapshot_verification.json` (all figures recomputed by `scripts/verify_snapshot.py`; two-source check against the 2026-08-05 workflow verifier's independent parse recorded in `docs/experiments.md`). **Every count matched exactly.** First substantive finding: the natural overlap-coupling is negligible-size and benign-direction (Cliff's δ = −0.10, Technical slightly *more* reworded than Editorial; perm p = 1e-4) — nature runs a near-matched design; stratified reporting stays mandatory.
- **2026-08-05, later** — R0 census run from the Windows box (results in RUNBOOK): Agora fully live (llama-server + Ops API), Lear live (ten-model ollama fleet), **Forge asleep** — wake is operator TRIGGER 1. Repo filed private at `eigenforma/wildpairs`.
- **2026-08-05, E2-P0** — CondaQA frozen (3 splits, canonical GitHub, Apache-2.0 verified via API). Verification two-source exact: 14,182 rows, 1,289 passages (474/115/700), zero cross-split PassageID overlap. **The design's riskiest unknown is now measured: 960 anchor sets (75.4%) have BOTH paraphrase and affirmative edits recoverable as single-sentence substitutions — 1.6× the ≥600 design target, 2.4× the ≥400 fallback.** Per-type single-sentence rates: paraphrase 0.909, scope 0.790, affirmative 0.764. Payload median 23 words (p90 = 39): half-bin rule bites only at L=64. Recompute: `scripts/verify_condaqa.py`. `scripts/fleet_watch.py` added (wildpairs-owned thermal/status watch) — first snapshot caught the Agora-disk correction in E2-P1.
- **2026-08-05, evening** — Forge rebooted by operator: RTX 3090, 120B resident, 36 °C, service active. Both R0 triggers resolved (Lear = aiuser by design; Tailscale SSH authorized + LAN key installed — full passwordless fleet control from Wu on both network paths). Scheduler ruled: `/runs/start` is Project Intern agent-cycle machinery, not for wildpairs; jobs go `ssh + nohup` from Wu. Operator model policy recorded: any model anywhere, evict-before-load, RAM-offload with long timeouts. **R1 done fleet-wide:** wildpairs deployed by tar-pipe to forge, agora, lear; frozen-manifest verification `ALL OK` on all three nodes.
