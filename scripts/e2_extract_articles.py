"""Ranged enwiki article extraction (runs on agora beside the coldstore dump). Given a
title list, uses the LOCAL multistream index (offset:pageid:title, bz2) to seek straight
to each title's compressed stream and decompress ONLY that stream (~100 pages) - no full
dump pass. Wikitext -> plain text via scan_condaqa_passages.py's strip pipeline
(strip_wikitext, imported verbatim; NOT lowercased - hosts keep natural case, whitespace
already single-space-collapsed by the strip).

Run (agora):
  cd ~/wildpairs-work && python3 scripts/e2_extract_articles.py \
      --titles /mnt/coldstore/wildpairs/hostbuild/needed_enwiki_titles.txt \
      --out /mnt/coldstore/wildpairs/hostbuild/articles_text.jsonl
Defaults point at the frozen 20210701 dump + its multistream index in enwiki_scan/.
Output rows: {title, ws_tokens, text}. Missing titles are reported LOUDLY and listed in
<out>.missing.txt; the Wu-side pack step (scripts/e2_pack_hostpools.py) enforces
coverage. Recompute: rerun this line (deterministic given dump + index + title list).
"""
import argparse
import bz2
import html
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scan_condaqa_passages import strip_wikitext  # noqa: E402  (pipeline reuse, verbatim)

DUMP = "/mnt/coldstore/wildpairs/enwiki/enwiki-20210701-pages-articles-multistream.xml.bz2"
INDEX = ("/mnt/coldstore/wildpairs/enwiki_scan/"
         "enwiki-20210701-pages-articles-multistream-index.txt.bz2")

RE_PAGE = re.compile(rb"<page>(.*?)</page>", re.DOTALL)
RE_TITLE = re.compile(rb"<title>(.*?)</title>")
RE_NS = re.compile(rb"<ns>(.*?)</ns>")
RE_TEXT = re.compile(rb"<text[^>]*>(.*?)</text>", re.DOTALL)


def read_index(index_path, needed_forms):
    """title form -> compressed stream offset, for needed titles only. Index lines are
    offset:pageid:title; titles may contain ':' so split at most twice."""
    streams = {}
    with bz2.open(index_path, "rt", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split(":", 2)
            if len(parts) != 3:
                continue
            title = parts[2]
            if title in needed_forms:
                streams.setdefault(int(parts[0]), set()).add(needed_forms[title])
    return streams


def decompress_stream(fh, offset):
    fh.seek(offset)
    d = bz2.BZ2Decompressor()
    out = []
    while not d.eof:
        chunk = fh.read(1 << 20)
        if not chunk:
            break
        out.append(d.decompress(chunk))
    return b"".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="ranged multistream article extraction")
    ap.add_argument("--titles", required=True)
    ap.add_argument("--dump", default=DUMP)
    ap.add_argument("--index", default=INDEX)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    t0 = time.time()

    wanted = [l for l in Path(args.titles).read_text(encoding="utf-8").splitlines()
              if l.strip()]
    # The multistream index stores raw titles; the scan emitted html-unescaped ones.
    # Accept both spellings, canonicalize to the requested form.
    needed_forms = {}
    for t in wanted:
        needed_forms[t] = t
        esc = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") \
               .replace('"', "&quot;")
        needed_forms.setdefault(esc, t)
    print(f"[start] {len(wanted)} titles wanted", flush=True)
    streams = read_index(args.index, needed_forms)
    n_hit = sum(len(v) for v in streams.values())
    print(f"[index] {len(streams)} streams cover {n_hit} titles "
          f"({time.time() - t0:.0f}s)", flush=True)

    found = {}
    with open(args.dump, "rb") as fh, open(args.out, "w", encoding="utf-8") as out:
        for k, off in enumerate(sorted(streams)):
            targets = streams[off]
            data = decompress_stream(fh, off)
            for m in RE_PAGE.finditer(data):
                page = m.group(1)
                tm = RE_TITLE.search(page)
                if not tm:
                    continue
                title = html.unescape(tm.group(1).decode("utf-8", errors="replace"))
                if title not in targets or title in found:
                    continue
                nm = RE_NS.search(page)
                if nm and nm.group(1) != b"0":
                    continue
                xm = RE_TEXT.search(page)
                raw = xm.group(1).decode("utf-8", errors="replace") if xm else ""
                text = strip_wikitext(html.unescape(raw))
                found[title] = True
                out.write(json.dumps({"title": title, "ws_tokens": len(text.split()),
                                      "text": text}, ensure_ascii=False) + "\n")
            if (k + 1) % 500 == 0:
                print(f"[progress] streams {k + 1}/{len(streams)} found={len(found)} "
                      f"({time.time() - t0:.0f}s)", flush=True)

    missing = [t for t in wanted if t not in found]
    if missing:
        mp = Path(args.out + ".missing.txt")
        mp.write_text("\n".join(missing) + "\n", encoding="utf-8")
        print(f"MISSING {len(missing)} titles (listed in {mp}) - pack step will "
              f"enforce coverage", flush=True)
    print(f"[done] {len(found)}/{len(wanted)} articles -> {args.out} "
          f"({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
