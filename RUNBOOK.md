# RUNBOOK — operator command triggers for the wildpairs program

## R0 census — COMPLETE 2026-08-05 (from Wu; Project_Intern/scripts + live probes)

Topology locked (`Project_Intern/scripts/start_lab.ps1`, fleet on 10.1.20.0/24, Tailscale alternates exist): **Wu** = this Windows box, the authoring workstation. **macbeth** (10.1.20.2) / **othello** (10.1.20.101) = Proxmox hosts. **forge** (10.1.20.223) / **agora** (10.1.20.207) = their VMs. **lear** (10.1.20.201) = Mac workstation. **puck** (10.1.20.20) = sentinel.

Live state, verified: **Forge** — rebooted by operator 2026-08-05, RTX 3090 24 GB, `gpt-oss-120b-mxfp4` resident (20.6/24.6 GB), 36 °C idle, `llama-forge` systemd active, `/mnt/weight_vault` 1.4 TB free (E2 host corpora fit here). **Agora** — up 13 d, llama-server (`gpt-oss-20b-Q4_K_M`, ctx 32768) + Project Intern Ops API (`/runs/start|pause`, `/power/*`, `/forge/status`) both healthy as systemd services. **Lear** — ollama :11434 healthy, ten models: mistral-small:24b, qwq:32b, qwen2.5-coder:32b, advisor, gemma2:27b, qwen3.5, qwen3:30b-a3b, themis, qwen3:14b, gemma4.

Control: **SSH from Wu is passwordless to forge and agora** (`ssh scott@10.1.20.223`, `ssh scott@10.1.20.207`) — verified. **Automation rule (learned 2026-08-06):** scripts and background jobs must target **LAN IPs, never bare hostnames** — bare names resolve via Tailscale MagicDNS and Tailscale SSH periodically demands an interactive re-auth click, which kills unattended jobs (observed: exit 255, "failed to fetch next SSH action"). Bare names are fine for interactive human sessions only. Fleet convention (`sync_node.sh`): nodes are pull-consumers, never push; Wu orchestrates via `deploy_secrets.ps1`. Known nit: `/forge/status` GPU telemetry fields are null while `nvidia-smi` works over SSH. Project_Intern is a **parked** effort (operator ruling 2026-08-05) — we reuse its machinery but do not develop it; wildpairs will carry its own thermal watch (`scripts/fleet_watch.py`, a ~20-line ssh+nvidia-smi loop) before any overnight run.

**TRIGGER 1 — RESOLVED 2026-08-05.** Lear's automation identity is `aiuser` (by design: `aiuser_scopedown.sh`); Wu's ssh config already maps `lear`→aiuser+id_intern. Operator authorized Tailscale SSH; the `id_intern` key was then installed into aiuser's `authorized_keys`, so **both paths now answer in BatchMode**: `ssh lear` (Tailscale MagicDNS) and `ssh aiuser@10.1.20.201` (LAN fallback, what the lifeboat scripts use).

**TRIGGER 2 — RESOLVED 2026-08-05.** Nodes hold no GitHub credentials (`git ls-remote` fails on forge and agora) and Wu's Git Bash has no rsync — transport is a **tar-pipe from Wu**, credential-free, matching the fleet's pull-consumer/Wu-orchestrates convention. The R1 deploy line below is the canonical sync; re-run it after any Wu-side commit. (A GitHub deploy key per node remains an option if we later want node-side `git pull`.)

**Scheduler ruling (operator asked; answered from `ops_api/routes/runs.py` + `controller.py`):** `/runs/start` launches the AutomationController — Project Intern *agent-cycle* machinery (`mode`/`scope` are display-only; `include_distiller/agora/forge` gates thread into `_execute_run()`), and `/runs/start-planned` drives triad-planned directives. **Not a batch-job scheduler; wildpairs does not use it.** wildpairs jobs run via `ssh + nohup` from Wu; the Ops API serves power (`/power/*`), readiness (`/health/ready`), and GPU telemetry (`/test/gpu-status`).

**Model placement policy (operator ruling, 2026-08-05, verbatim intent):** any model in the grid can host anywhere; **evict the last model before the next one loads**; system-RAM offload is welcome — set long timeouts and spend time as a resource. Cascade default remains Forge=120B arbitration, Agora=20B + mining, Lear fleet=bulk labeling, with per-stage swaps freely allowed under evict-before-load.

**Model format policy (settled 2026-08-05).** Format follows workload: **encoders = safetensors** via sentence-transformers (the pinned polaritycheck checkpoints — already the paved road at 33M–435M params); **LLM labeling tier = GGUF** via llama.cpp/ollama (the only runtime honoring RAM-offload-with-long-timeouts); **EXL2** only for dense models that fully fit VRAM and need speed (it cannot RAM-spill); **AWQ** only if a vLLM batch-labeling bench wins on throughput; **ONNX** has real upside for the ~1–2M-call embedding sweeps (CPU sharding on Agora beside Forge's GPU) but is a *different configuration* by the audit's own validity discipline — it may substitute a pinned encoder **only after a parity gate** (cosine delta ≤ 1e-5 on a frozen probe set), else it enters as its own named configuration arm.

---

Exact lines to run on the lab systems, in trigger order. Placeholders are marked `⟨LIKE THIS⟩` and exist only until R0 output locks them. Rules of the road: every job writes only under `~/wildpairs-work/results/<hostname>/`; nothing overwrites a frozen file; every result file is followed by a `sha256sum` line appended to `results/<hostname>/CHECKSUMS`; jobs that die get re-run, never hand-patched.

## R0 — connectivity census (run once, paste full output back; unblocks everything below)

From any shell that reaches the LAN (adjust hostnames if mDNS differs — try `macbeth`/`othello` or IPs):

```sh
# reachability + inference endpoints
for H in forge macbeth agora othello; do echo "== $H =="; ping -c 1 -W 2 $H 2>&1 | tail -1; done
curl -s --max-time 5 http://⟨FORGE⟩:8080/health && echo " <- forge llama-server"
curl -s --max-time 5 http://⟨AGORA⟩:8080/health && echo " <- agora llama-server"
curl -s --max-time 5 http://⟨AGORA⟩:8000/docs -o /dev/null -w "%{http_code} <- agora ops api\n"
curl -s --max-time 5 http://⟨LEAR⟩:11434/api/tags | head -c 400; echo " <- lear ollama models"

# loaded/available models on the llama-servers
curl -s http://⟨FORGE⟩:8080/v1/models | head -c 600; echo
curl -s http://⟨AGORA⟩:8080/v1/models | head -c 600; echo

# per-box inventory (run ON each box, or via ssh if this box can reach them)
hostname; uname -a; python3 --version; git --version
nvidia-smi --query-gpu=name,memory.total --format=csv 2>/dev/null || system_profiler SPDisplaysDataType 2>/dev/null | head -5
df -h ~ | tail -1
ls ⟨ENCODER_CHECKPOINT_DIR⟩ 2>/dev/null   # where the pinned polaritycheck encoders live, if present
```

Also answer in prose: (1) can this Windows box ssh into each system (`ssh ⟨user⟩@⟨host⟩ hostname`)? (2) preferred repo transport — git pull from the private GitHub remote, or rsync/scp from this box? (3) does the Agora Ops API already schedule jobs, and what does a job submission look like?

## R1 — repo onto each box — **DONE fleet-wide 2026-08-05** (re-run after any Wu commit)

```sh
# canonical sync, from Wu (Git Bash), per node (forge | agora | lear):
cd /c/Users/poeti && tar -cf - --exclude=.git --exclude=__pycache__ wildpairs | \
  ssh $NODE "rm -rf ~/wildpairs-work && mkdir -p ~/wildpairs-work && \
             tar -xf - -C ~/wildpairs-work --strip-components=1 && \
             cd ~/wildpairs-work && python3 scripts/verify_snapshot.py --manifest"
# must end ALL OK — 2026-08-05: ALL OK on forge, agora, and lear (frozen corpus bit-identical on all three)
# venv + pip: deferred until the encoder harness lands (requirements are stdlib-only at E1-P0)
```

## R2 — E1-P3 labeling cascade (Lear bulk pass, then 120B arbitration)

Trigger: after `prereg-e1` tag exists and E1-P2 granularities are frozen.

```sh
# Lear — small-model bulk pass over Verified-Technical pairs (edit-class pre-labels):
python3 harness/e1/label_cascade.py --stage bulk --endpoint http://localhost:11434 \
  --model ⟨SMALL_MODEL_TAG⟩ --out results/lear/e1_class_bulk.jsonl
# Forge/Agora — 120B arbitration ONLY on rows where bulk pass disagrees or abstains:
python3 harness/e1/label_cascade.py --stage arbitrate --endpoint http://localhost:8080 \
  --in results/lear/e1_class_bulk.jsonl --out results/⟨HOST⟩/e1_class_final.jsonl
```

Isolation rule: the cascade prompt files contain no hypothesis text — labelers never see H1–H5 or any cosine. `label_cascade.py` refuses to run if `PREREGISTRATION_E1.md` is in its context path.

## R3 — E1-P4 encoder sweep (Forge, <1 GPU-hour)

```sh
python3 harness/e1/encoder_sweep.py --pairs corpus/e1_errata/frozen_pairs.jsonl \
  --configs harness/configs/nine_pinned.json --granularities g1,g2,g3 \
  --out results/forge/e1_scores.json
python3 scripts/freeze_results.py results/forge/e1_scores.json   # sha256 + append-only
```

## R4 — E1-P6 bis mining (Agora, CPU + small models, overnight-safe)

```sh
nohup python3 harness/e1/bis_mine.py --index corpus/e1_errata/rfc-index.xml \
  --rfc-dir /data/rfc-text/ --out results/agora/bis_candidates.jsonl > logs/bis_mine.log 2>&1 &
tail -f logs/bis_mine.log   # progress; safe to disconnect, job survives logout via nohup
```

## R5 — E2-P1 host corpus acquisition — **STARTED 2026-08-05** (Agora `/mnt/coldstore`, operator-provisioned 1 TB volume)

Layout: `/mnt/coldstore/wildpairs/{enwiki,pmc,rfc-text,results}` (created, writable as scott). Status: **rfc-text COMPLETE (550 MB via rsync)**; **enwiki-20210701-pages-articles-multistream.xml.bz2 downloading** (`wget -c`, nohup, survives disconnects — resume by re-running the same line); PMC deferred until `prereg-e2` fixes the slice.

```sh
# already run (repeat = resume, both idempotent):
ssh agora
cd /mnt/coldstore/wildpairs/rfc-text  && rsync -az rsync.rfc-editor.org::rfcs-text-only .
cd /mnt/coldstore/wildpairs/enwiki    && wget -c https://archive.org/download/enwiki-20210701/enwiki-20210701-pages-articles-multistream.xml.bz2
# PMC OA CC-BY slice via AWS mirror (FTP retires 2026-08) — after prereg-e2 defines ⟨SLICE⟩:
aws s3 sync s3://pmc-oa-opendata/oa_comm/txt/ /mnt/coldstore/wildpairs/pmc/ --no-sign-request --exclude "*" --include "⟨SLICE⟩"
# freeze when a transfer completes (external-corpus manifest entry, recorded on Wu):
sha256sum /mnt/coldstore/wildpairs/enwiki/* /mnt/coldstore/wildpairs/rfc-text/rfc-index.xml
```

DAC option (operator-confirmed): at sweep time Forge mounts coldstore read-only over the 40GbE link (`setup_dac_nfs.sh` precedent) so the 3090 streams hosts at NVMe-class speed; fallback is pre-sharded tar-pipe.

### Storage tiering (settled 2026-08-05, operator + census)

Agora's virtual disk grown +1 TB at the Proxmox layer (sda now 1.3 T; underlying NVMe 1.88 T). Policy: **NVMe = hot** (active models incl. the 120b arbitration weapon, frozen sweep inputs, results in flight); **coldstore spinner = cold** (raw dumps, corpus archives, model backups — sequential one-pass reads only; never stream sweep inputs from it). The `bench_staging` copy to `/mnt/coldstore/models/` (125 GB, running) is a **backup, not an eviction** — nothing gets deleted from NVMe now that the disk is grown. enwiki-20210701 verified byte-exact vs archive.org content-length (19,773,796,684); sha256 running, manifest entry on completion.

**TRIGGER — RESOLVED 2026-08-05, operator-executed.** growpart → pvresize → lvextend → resize2fs completed; root now **1.3 T, 23% used, 983 G free**, verified layer-by-layer from Wu with llama-server and the Ops API healthy throughout. (Incident note for the record: the growpart step ran ~9 minutes and looked stalled; diagnosis from Wu showed no stuck process, no lock, no half-write — it committed cleanly and exited. Slow ≠ stuck; check the journal before touching anything.) enwiki sha256 `cf5ab6b3…` recorded as the manifest's first external-corpus entry; rfc-text deterministic digest running.

## R6 — E2-P4 embedding sweep, sharded over the 40GbE DAC

Trigger: after `prereg-e2` tag. Shard by anchor id, odd→Forge even→Agora; identical script, identical config hashes.

```sh
# each box:
nohup python3 harness/e2/titration_sweep.py --shard ⟨odd|even⟩ \
  --hosts /data/enwiki/ --payloads corpus/e2_dilution/anchors_frozen.jsonl \
  --out results/⟨HOST⟩/e2_shard.json > logs/e2_sweep.log 2>&1 &
# integrity handshake when both shards finish (over the DAC):
python3 scripts/merge_shards.py results/forge/e2_shard.json results/agora/e2_shard.json \
  --verify-config-hash --out results/e2_scores_merged.json
```

## Block protocol

When anything blocks: capture the exact command + last 30 log lines, note the box and timestamp, and send it. You get back either a corrected exact line for you to run, or a script change committed to the repo which you `git pull` and re-trigger. Never improvise a fix on-box; the improvisation becomes an unrecorded fork of the harness.
