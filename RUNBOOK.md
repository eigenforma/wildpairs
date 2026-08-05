# RUNBOOK — operator command triggers for the wildpairs program

## R0 census — COMPLETE 2026-08-05 (from Wu; Project_Intern/scripts + live probes)

Topology locked (`Project_Intern/scripts/start_lab.ps1`, fleet on 10.1.20.0/24, Tailscale alternates exist): **Wu** = this Windows box, the authoring workstation. **macbeth** (10.1.20.2) / **othello** (10.1.20.101) = Proxmox hosts. **forge** (10.1.20.223) / **agora** (10.1.20.207) = their VMs. **lear** (10.1.20.201) = Mac workstation. **puck** (10.1.20.20) = sentinel.

Live state, verified: **Forge** — rebooted by operator 2026-08-05, RTX 3090 24 GB, `gpt-oss-120b-mxfp4` resident (20.6/24.6 GB), 36 °C idle, `llama-forge` systemd active, `/mnt/weight_vault` 1.4 TB free (E2 host corpora fit here). **Agora** — up 13 d, llama-server (`gpt-oss-20b-Q4_K_M`, ctx 32768) + Project Intern Ops API (`/runs/start|pause`, `/power/*`, `/forge/status`) both healthy as systemd services. **Lear** — ollama :11434 healthy, ten models: mistral-small:24b, qwq:32b, qwen2.5-coder:32b, advisor, gemma2:27b, qwen3.5, qwen3:30b-a3b, themis, qwen3:14b, gemma4.

Control: **SSH from Wu is passwordless to forge and agora** (`ssh scott@10.1.20.223`, `ssh scott@10.1.20.207`) — verified. Fleet convention (`sync_node.sh`): nodes are pull-consumers, never push; Wu orchestrates via `deploy_secrets.ps1`. Known nit: `/forge/status` GPU telemetry fields are null while `nvidia-smi` works over SSH — fix in Project_Intern before overnight thermal watches.

**⚡ TRIGGER 1 (open): give Wu a key to Lear** (Wu→Lear and Agora→Lear both currently refused; one password entry, then Wu commands the whole fleet):

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh scott@10.1.20.201 "cat >> ~/.ssh/authorized_keys"
# verify: ssh -o BatchMode=yes scott@10.1.20.201 hostname
```

**TRIGGER 2 (open, one-word answer):** wildpairs transport to nodes — `rsync` from Wu (recommended: no credentials ever land on nodes, matches deploy_secrets pattern) or a GitHub deploy key per node. Model placement needs no ruling: Forge=120B arbitration, Agora=20B + mining, Lear fleet=bulk labeling matches the cascade as designed.

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

## R1 — repo onto each box (after R0 decides transport)

```sh
# git route (needs a token or deploy key on the box):
git clone https://github.com/eigenforma/wildpairs ~/wildpairs-work && cd ~/wildpairs-work
# rsync route (from this Windows box, per system):
# rsync -av --exclude .git /c/Users/poeti/wildpairs/ ⟨user⟩@⟨host⟩:~/wildpairs-work/
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python3 scripts/verify_snapshot.py --manifest    # must print ALL OK before any job runs
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

## R5 — E2-P1 host corpus acquisition (Agora NVMe; egress-budget aware, resumable)

```sh
# RFC full text (shared frozen snapshot with E1), ~175 MB:
rsync -avz rsync.rfc-editor.org::rfcs-text-only /data/rfc-text/
# enwiki-20210701 (CondaQA's source snapshot) from archive.org, ~19 GB — resumable:
wget -c https://archive.org/download/enwiki-20210701/⟨DUMP_FILE⟩ -P /data/enwiki/
# PMC OA CC-BY slice via AWS mirror (FTP retires 2026-08):
aws s3 sync s3://pmc-oa-opendata/oa_comm/txt/ /data/pmc/ --no-sign-request --exclude "*" --include "⟨SLICE⟩"
sha256sum /data/rfc-text/rfc-index.xml /data/enwiki/* >> results/agora/CHECKSUMS
```

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
