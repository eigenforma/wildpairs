# PREREGISTRATION — E4: The Floor Lemma survey (the deaf-gate bound)

> **STATUS: FROZEN at tag `prereg-e4`** (2026-08-11). B1–B3 numbers ratified by operator ruling
> 2026-08-11 ("freeze as drafted"); registers and per-config devices pinned in §2; the embedding
> pass is legal only after this tag, per the E3 precedent. Proposal provenance:
> `docs/proposals/floor_lemma_2026-08-06.md` (approved 2026-08-06 as partner science).
> Amendments below the tag line hereafter.

## 1. The lemma (the claim being surveyed, not tested — the algebra is checkable today)

Let an encoder embed a register's texts as unit vectors with unit mean direction μ̂, and suppose
every embedding lies within angle θ of μ̂ (⟨u, μ̂⟩ ≥ cos θ for all u), **with θ ≤ π/2** (the
scope condition; for wider cones the bound as stated does not hold — on anisotropic text
registers the condition is satisfied trivially, and B3 checks it empirically). Then for any pair:
**cos(u, v) ≥ cos 2θ.** Proof as in the proposal (decomposition + Cauchy–Schwarz on residuals;
exact; tight at antipodal residuals).

Consequence surveyed: measured cone width converts to a **hard floor under every pairwise
cosine** on that register — any operating point below the floor can never fire, for any pair,
regardless of meaning. Not miscalibrated: *deaf by geometry*.

## 2. Design

- **Registers** (all frozen): errata g2 texts (`corpus/e1_errata/pairs_g1g2.jsonl`), CondaQA
  passages (`corpus/e2_dilution/`), E3 brand-name sentences (frozen sample sha `ceb30784…`).
- **Configurations:** the nine pinned polaritycheck configurations.
- **Numerics regime, declared (review F16):** the **E3 fresh-fp32 pins** (fp32, one pinned
  device per config, the E3-P2 assignments) — floors are geometry claims about the embedding
  cloud, not score-parity claims against the Paper A pinned path; stating the regime here is
  what makes that scoping legitimate. No cross-regime comparison is made.
- **Embedding pass, vectors retained** (the prior sweeps cached only cosines): ~10–20k short
  texts per config; GPU-minutes, fleet-trivial.
- **Per (config, register):** μ̂ (normalized mean of unit vectors); the angle distribution
  θᵤ = arccos⟨u, μ̂⟩; **hard floor** = cos 2θ_max; **practical floor** = cos 2θ_p99 (covers
  ≥ 98% of pairs by union bound). Vacuity table: floors vs the operating points
  {0.30, 0.40, 0.60, 0.80, 0.85, 0.95} (Paper A §5's five shipped + the audited 0.60).
- **Machine check** (§9/X-HYP style): (a) synthetic — vectors sampled in spherical caps at
  several θ, bound verified and tightness demonstrated; (b) empirical — observed minimum
  pairwise cosine ≥ derived hard floor in every (config, register) cell.

## 3. Bars (proposal values; finalized at the freeze)

- **B1:** the practical floor exceeds operating point **0.40** for ≥ 7 of 9 configs on the
  errata register — both surveyed memory-gate cuts (0.30, 0.40) vacuous where they would deploy.
- **B2:** the practical floor exceeds the audited drift cut (**0.60**) for ≥ 5 of 9 configs.
- **B3:** observed minimum pairwise cosine respects the hard floor in **100%** of
  (config, register) cells — the lemma's empirical validity check; a single violation kills the
  empirical claim (the algebra stands regardless; a violation would indicate an instrument
  error — non-unit vectors, wrong μ̂ — and is investigated as such, disclosed either way).
- **Falsifier honesty:** a config with wide angular spread has a low floor and escapes the
  vacuity claim; the bars pre-commit where the bite is predicted, and a miss is a reported miss.

## 4. Analysis and outputs

Frozen JSON (`results/e4_floor_survey.json`): per-cell μ̂ norm, θ distribution summary
(max, p99, p90, median), both floors, vacuity verdicts per operating point, observed min pairwise
cosine, machine-check verdicts, B1–B3 scorecard. One command, offline, vectors retained under
`results/e4_vectors/` (small; enables any reviewer recomputation). Paper slot: a short
independent section or §9-style note — one theorem, one measured table, one machine check.

## 5. Freeze protocol

One commit that (a) finalizes B1–B3 numbers by operator ruling, (b) pins the register file list
and per-config devices, (c) is tagged `prereg-e4`. Amendments below the tag line thereafter.
The embedding pass runs only after the tag exists.

---

**AMENDMENT A1 (2026-08-11, device failure re-pin — E3 A1 precedent):** the two Agora cells
(gte-base, nomic-clustering) OOM'd twice beside the resident 20B (4.5 GB free vs ~1.1 GB
attention allocations; eviction requires an operator password and the operator is in
low-wattage mode). Re-pinned to **Forge** (slice complete, CUDA, fp32 unchanged, batch 8,
expandable segments); per-cell meta records the executed device as always. CPU-on-Agora is
the recorded fallback if Forge's 3.5 GB beside the 120B also refuses.

**AMENDMENT A2 (2026-08-11, B3 investigation closed):** the six flagged cells are all
scope-condition breaches (θ_max > π/2) on the MiniLM/mpnet configurations, cross-device
verified (Forge CUDA reproduces Lear MPS θ_max = 99.796° to 1e-3). Not an instrument error:
the lemma is inapplicable to non-cone clouds, which the flag correctly detected. Full reading:
`docs/findings_e4_2026-08-11.md`. B1/B2 stand as honest substantive misses per the
falsifier-honesty clause.

**AMENDMENT A3 (2026-08-12, correcting A2's provenance — append-only, A2 stands as written above).**
A2 asserted "cross-device verified (Forge CUDA reproduces Lear MPS θ_max = 99.796° to 1e-3)". The
2026-08-12 number-fidelity audit correctly flagged that claim **unsourced**: the probe that
justified it was written to `/tmp` on Forge and never frozen, and every committed vector cell
records `lear/mps`. Two corrections, neither of which changes A2's conclusion:
1. **The claim is now sourced.** Re-run 2026-08-12 and frozen at
   `results/verification/e4_cross_arch_theta.json`: Forge CUDA fp32 reproduces the Lear MPS θ_max on
   **all six breaching cells with maximum deviation 0.000°**.
2. **The figure A2 quotes is the wrong one.** 99.796° is MiniLM on the CondaQA register alone. The
   maximum over breaching cells is **106.321°** (mpnet on the E3 register), and the breach spans
   **six cells** (two configurations × three registers), not one number.
B3's frozen verdict string remains `FAIL (instrument-error investigation per prereg §3)`; the
investigation's *conclusion* is a scope finding, and both are now reported that way rather than the
verdict being softened to its interpretation. Full ledger: `docs/CORRECTIONS_2026-08-12.md`.
