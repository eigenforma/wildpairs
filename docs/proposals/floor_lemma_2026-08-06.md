# Proposal — The Floor Lemma (the deaf-gate bound)

**Status: PROPOSED. Independent of every existing claim and pillar: it touches neither the wording–meaning coupling, nor the audit AUROCs, nor the dilution law, nor the hyperbolic charts. It is a statement about the instrument's reachable range.**

## The lemma

Let an encoder embed a register's texts as unit vectors, and let μ̂ be the unit mean direction of that population. Suppose every embedding lies within angle θ of μ̂ (i.e., ⟨u, μ̂⟩ ≥ cos θ for all u). Then for **any** pair u, v:

**cos(u, v) ≥ cos 2θ.**

*Proof.* Decompose u = cos θᵤ · μ̂ + rᵤ with ⟨rᵤ, μ̂⟩ = 0, ‖rᵤ‖ = sin θᵤ, θᵤ ≤ θ (likewise v). Then cos(u,v) = cos θᵤ cos θᵥ + ⟨rᵤ, rᵥ⟩ ≥ cos θᵤ cos θᵥ − sin θᵤ sin θᵥ = cos(θᵤ + θᵥ) ≥ cos 2θ. ∎ (Elementary, exact, and tight — equality at antipodal residuals.)

## Why it bites

Sentence-embedding spaces are famously anisotropic (Ethayarajh 2019; Gao et al. 2019): in-register embeddings concentrate in a narrow cone. The lemma converts measured cone width into a **hard floor under every pairwise cosine** — and therefore into a vacuity verdict on gate operating points: **any threshold below the floor can never fire on that register, for any pair, regardless of meaning.** The gate is not miscalibrated there; it is *deaf by geometry*.

This would retroactively explain a Paper A §6 observation as an instance of a theorem: the audited guard's threshold was "unreachable by construction" (all 56 mutations scored 0.832–0.9997). And it aims squarely at the shipped low cuts in the prevalence survey (cosine 0.30 and 0.40 memory gates): the prediction is that for modern encoders on natural prose registers, those operating points are not conservative — they are *unreachable*.

## The investigation (E4, "the floor survey")

1. **Embedding pass, vectors retained** (the sweeps cached only cosines): all frozen registers — errata g2 texts, CondaQA passages, E3 brand-name sentences — through the nine pinned configurations. Small: ~10–20k short texts per config; fleet-trivial (GPU-minutes under the E3 device pins).
2. **Per (config, register):** μ̂, the angle distribution θᵤ; report θ_max → **hard floor** cos 2θ_max, and θ_p99 → **practical floor** cos 2θ_p99 (covers ≥ 98% of pairs by union bound).
3. **Vacuity table:** floors vs the six operating points {0.30, 0.40, 0.60, 0.80, 0.85, 0.95}, per config and register — which shipped cuts are geometrically unreachable, where.
4. **Machine check** in the §9/X-HYP style: (a) synthetic — vectors sampled in a spherical cap, bound verified and tightness demonstrated; (b) empirical — observed minimum pairwise cosine ≥ derived hard floor in every cell.
5. **Pre-registered bars, committed before the embedding pass (numbers to be finalized at the freeze, direction fixed now):**
   - B1: the practical floor exceeds operating point **0.40** for ≥ 7 of 9 configs on the errata register (both surveyed memory-gate cuts vacuous).
   - B2: the practical floor exceeds the audited drift cut (cosine **0.60**) for ≥ 5 of 9 configs.
   - B3: observed minimum pairwise cosine respects the hard floor in **100%** of (config, register) cells — the lemma's empirical validity check; a single violation kills the empirical claim (the algebra stands regardless).
6. **Falsifier honesty:** a config with wide angular spread has a low floor and escapes the vacuity claim — the bars pre-commit where we predict it bites, and a miss is reported as a miss.

## Where it slots

A short independent section or a §9-style note: one theorem, one measured table, one machine check. New pillar class: not "the score measures the wrong thing" (coupling), not "the signal dies with length" (dilution), but **"below this line the instrument cannot hear at all — and shipped defaults live below the line."** Cites anisotropy literature as ground, contributes the operating-point vacuity consequence for deployed gates, which that literature never drew.

**Cost:** one prereg amendment-style freeze, GPU-minutes of embedding, an afternoon of analysis. **Risk:** low — the algebra is checkable today; only the empirical bite is at stake, and either outcome is reportable.
