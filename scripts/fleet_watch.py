"""One-line-per-host fleet status from Wu: GPU, inference endpoint, disk. wildpairs-owned
(Project_Intern is parked; this replaces reading /forge/status for thermal watch).

  python scripts/fleet_watch.py            one snapshot
  python scripts/fleet_watch.py --watch 60 repeat every 60 s until Ctrl-C
"""
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6"]
# LAN IPs, not bare hostnames: MagicDNS routes ssh through Tailscale SSH, which demands
# interactive re-auth and kills unattended runs (RUNBOOK automation rule, 2026-08-06).
SSH_TARGET = {"forge": "scott@10.1.20.223", "agora": "scott@10.1.20.207", "lear": "aiuser@10.1.20.201"}


def sh(host: str, cmd: str) -> str:
    try:
        return subprocess.run(SSH + [SSH_TARGET.get(host, host), cmd], capture_output=True, text=True, timeout=25).stdout.strip()
    except Exception:
        return ""


def http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def gpu_line(host: str) -> str:
    q = sh(host, "nvidia-smi --query-gpu=memory.used,memory.total,temperature.gpu,utilization.gpu --format=csv,noheader,nounits")
    if not q:
        return "gpu:unreachable"
    parts = [x.strip() for x in q.split(",")]
    if len(parts) != 4:
        return f"gpu:ERROR({q.splitlines()[0][:40]})"
    used, total, temp, util = parts
    return f"gpu:{used}/{total}MiB {temp}C {util}%"


def snapshot() -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    for host in ("forge", "agora"):
        llama = "llama:UP" if http_ok(f"http://{host}:8080/health") else "llama:DOWN"
        vol = "/mnt/weight_vault" if host == "forge" else "/mnt/coldstore"
        disk = sh(host, f"df -h --output=avail {vol} 2>/dev/null | tail -1 || df -h --output=avail ~ | tail -1")
        print(f"[{ts}] {host:6s} {gpu_line(host):28s} {llama}  free:{disk.strip()}")
    try:
        with urllib.request.urlopen("http://lear:11434/api/tags", timeout=5) as r:
            n = len(json.load(r).get("models", []))
        lear = f"ollama:UP models:{n}"
    except Exception:
        lear = "ollama:DOWN"
    load = sh("lear", "sysctl -n vm.loadavg 2>/dev/null || uptime")
    print(f"[{ts}] lear   {lear}  load:{load.strip()[:40]}")


def main() -> None:
    if "--watch" in sys.argv:
        every = int(sys.argv[sys.argv.index("--watch") + 1])
        while True:
            snapshot()
            print("-" * 72)
            time.sleep(every)
    else:
        snapshot()


if __name__ == "__main__":
    main()
