"""E2 host slice: freeze the PMC-OA CC-BY-class txt slice from the deprecated S3 path.

DEADLINE-DRIVEN: s3://pmc-oa-opendata/deprecated/ is deleted on or after 2026-08-24
(NCBI announcement 2026-02-12). This script freezes, per PREREGISTRATION_E2 §2:
  1. The FULL key listing of deprecated/oa_comm/txt/all/  -> listing snapshot (the
     pinned enumeration source, entered into corpus/MANIFEST.json on Wu afterwards).
  2. Any filelist/metadata CSVs under deprecated/oa_comm/  -> license record.
  3. The slice: walking PMC IDs in NUMERIC ascending order, fetch each txt and keep
     it if its whitespace-token count >= 6000, until 2000 articles are kept.
  4. CHECKSUMS: sha256 per kept file + listing + filelists.

Stdlib only. Resumable: re-running skips work already done (listing file, selection
log, existing article files). Designed for `nohup python3 pmc_freeze.py` on agora in
/mnt/coldstore/wildpairs/pmc/. All network I/O is anonymous HTTPS GETs.
"""
import csv, hashlib, os, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BUCKET = "https://pmc-oa-opendata.s3.amazonaws.com"
PREFIX = "deprecated/oa_comm/txt/all/"
ROOT = Path(".")
LISTING = ROOT / "listing_deprecated_oa_comm_txt_all.txt"
LISTING_DONE = ROOT / "listing.COMPLETE"
SEL_LOG = ROOT / "selection_log.csv"
SLICE = ROOT / "slice"
FILELISTS = ROOT / "filelists"
TARGET_KEEP = 2000
MIN_WS_TOKENS = 6000
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


def get(url, timeout=90, tries=4):
    last = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - log and retry, overnight job
            last = e
            time.sleep(2 ** k)
    raise RuntimeError(f"GET failed after {tries}: {url}: {last}")


def list_prefix(prefix, out_path, label):
    """Full paginated ListObjectsV2 under prefix; one key per line; resumable only
    as all-or-nothing (marker file). Returns key count."""
    done_marker = Path(str(out_path) + ".COMPLETE")
    if done_marker.exists():
        n = sum(1 for _ in open(out_path, encoding="utf-8"))
        print(f"[listing] {label}: already complete, {n} keys", flush=True)
        return n
    token, n, t0 = None, 0, time.time()
    with open(out_path, "w", encoding="utf-8") as f:
        while True:
            q = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
            if token:
                q["continuation-token"] = token
            xml = get(BUCKET + "/?" + urllib.parse.urlencode(q))
            root = ET.fromstring(xml)
            for c in root.findall("s3:Contents", NS):
                key = c.find("s3:Key", NS).text
                size = c.find("s3:Size", NS).text
                f.write(f"{key}\t{size}\n")
                n += 1
            trunc = root.find("s3:IsTruncated", NS)
            if trunc is not None and trunc.text == "true":
                token = root.find("s3:NextContinuationToken", NS).text
                if n % 50000 == 0:
                    print(f"[listing] {label}: {n} keys, {time.time()-t0:.0f}s", flush=True)
            else:
                break
    done_marker.write_text("complete\n")
    print(f"[listing] {label}: COMPLETE, {n} keys, {time.time()-t0:.0f}s", flush=True)
    return n


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    SLICE.mkdir(exist_ok=True)
    FILELISTS.mkdir(exist_ok=True)

    # 1. full listing of the article prefix (the pinned enumeration source)
    list_prefix(PREFIX, LISTING, "oa_comm/txt/all")

    # 2. filelist/metadata CSVs under deprecated/oa_comm/ (license record)
    fl_listing = FILELISTS / "listing_oa_comm_nonarticle.txt"
    if not Path(str(fl_listing) + ".COMPLETE").exists():
        token, keys = None, []
        while True:
            q = {"list-type": "2", "prefix": "deprecated/oa_comm/", "max-keys": "1000"}
            if token:
                q["continuation-token"] = token
            root = ET.fromstring(get(BUCKET + "/?" + urllib.parse.urlencode(q)))
            stop = False
            for c in root.findall("s3:Contents", NS):
                key = c.find("s3:Key", NS).text
                if key.startswith(PREFIX):
                    stop = True   # reached the huge article range; CSVs sort before 'txt/all'
                    break
                keys.append(key)
            trunc = root.find("s3:IsTruncated", NS)
            if stop or trunc is None or trunc.text != "true":
                break
            token = root.find("s3:NextContinuationToken", NS).text
        with open(fl_listing, "w", encoding="utf-8") as f:
            f.write("\n".join(keys) + "\n")
        for key in keys:
            if key.endswith((".csv", ".txt")) and "filelist" in key.lower():
                dest = FILELISTS / key.rsplit("/", 1)[1]
                if not dest.exists():
                    dest.write_bytes(get(BUCKET + "/" + urllib.parse.quote(key)))
                    print(f"[filelist] fetched {key}", flush=True)
        Path(str(fl_listing) + ".COMPLETE").write_text("complete\n")

    # 3. numeric-ascending walk until TARGET_KEEP articles of >= MIN_WS_TOKENS
    ids = []
    with open(LISTING, encoding="utf-8") as f:
        for line in f:
            key = line.split("\t")[0]
            m = re.search(r"PMC(\d+)\.txt$", key)
            if m:
                ids.append((int(m.group(1)), key))
    ids.sort()
    print(f"[walk] {len(ids)} article keys, walking ascending", flush=True)

    seen, kept = set(), 0
    if SEL_LOG.exists():
        with open(SEL_LOG, encoding="utf-8", newline="") as f:
            for row in csv.reader(f):
                if row and row[0] != "pmcid":
                    seen.add(int(row[0]))
                    kept += row[3] == "1"
        print(f"[resume] {len(seen)} processed, {kept} kept", flush=True)

    log = open(SEL_LOG, "a", encoding="utf-8", newline="")
    w = csv.writer(log)
    if not seen:
        w.writerow(["pmcid", "bytes", "ws_tokens", "kept"])
    t0 = time.time()
    for pmcid, key in ids:
        if kept >= TARGET_KEEP:
            break
        if pmcid in seen:
            continue
        try:
            data = get(BUCKET + "/" + urllib.parse.quote(key))
        except RuntimeError as e:
            print(f"[warn] {e}", flush=True)
            w.writerow([pmcid, -1, -1, 0]); log.flush()
            continue
        text = data.decode("utf-8", errors="replace")
        ws = len(text.split())
        keep = int(ws >= MIN_WS_TOKENS)
        if keep:
            (SLICE / f"PMC{pmcid}.txt").write_bytes(data)
            kept += 1
        w.writerow([pmcid, len(data), ws, keep]); log.flush()
        if (len(seen) + 1) % 200 == 0 or keep and kept % 100 == 0:
            print(f"[walk] processed~{len(seen)+1} last=PMC{pmcid} kept={kept} "
                  f"({time.time()-t0:.0f}s)", flush=True)
        seen.add(pmcid)
    log.close()
    print(f"[walk] DONE: kept={kept}", flush=True)

    # 4. checksums
    with open(ROOT / "CHECKSUMS", "w", encoding="utf-8") as f:
        f.write(f"{sha256_file(LISTING)}  {LISTING.name}\n")
        for p in sorted(FILELISTS.iterdir()):
            f.write(f"{sha256_file(p)}  filelists/{p.name}\n")
        for p in sorted(SLICE.iterdir()):
            f.write(f"{sha256_file(p)}  slice/{p.name}\n")
    print("[done] CHECKSUMS written; slice frozen", flush=True)


if __name__ == "__main__":
    main()
