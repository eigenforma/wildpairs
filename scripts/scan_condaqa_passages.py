#!/usr/bin/env python3
"""
scan_condaqa_passages.py -- PREREGISTRATION_E2 SS2 tag-time scan (wildpairs campaign).

Single streaming pass over the frozen local dump
  /mnt/coldstore/wildpairs/enwiki/enwiki-20210701-pages-articles-multistream.xml.bz2
producing, in the working directory (/mnt/coldstore/wildpairs/enwiki_scan/):

  scan_results.jsonl   one line per CondaQA passage (all 1289):
                       {passage_id, tier, title, probes_hit}
                       tier: "full" (all three probes found in one article),
                             "partial" (>=1 probe found), "none".
                       title = best-matching article (most probes hit; first seen wins ties).
  articles_index.tsv   title \t ws_tokens \t byte_offset  for EVERY ns-0 non-redirect
                       article (host-pool candidates byproduct). ws_tokens is the
                       whitespace-token count of the stripped article text.
                       byte_offset is the offset of the "<page>" line in the
                       DECOMPRESSED xml stream (not a multistream/compressed offset).
  summary.json         machine-readable copy of the final summary block.

Matching: article wikitext is minimally stripped (XML/HTML entities unescaped,
<!--comments-->, <ref>...</ref>, {{templates}} (innermost-first, iterated),
[[a|b]]->b / [[a]]->a, '''/'' quoting, leftover <tags>, whitespace collapsed),
then normalized (lowercase). Each passage gets three probes computed from its
identically-normalized text: first 250 chars, last 250 chars, middle sentence.
A token-anchor prefilter (rarest interior token per probe) keeps the per-article
cost near zero; full substring tests run only on prefilter candidates.

Memory discipline: exactly one article held at a time; the 1289 passages and
their probes stay resident (small).

Progress: startup line immediately, an early checkpoint at 10k pages, then a
line every 100k ns-0 articles with elapsed time and compressed-file progress.
"""

import bz2
import html
import io
import json
import os
import re
import time

DUMP = "/mnt/coldstore/wildpairs/enwiki/enwiki-20210701-pages-articles-multistream.xml.bz2"
WORKDIR = "/mnt/coldstore/wildpairs/enwiki_scan"
PASSAGES = os.path.join(WORKDIR, "condaqa_passages.jsonl")
OUT_RESULTS = os.path.join(WORKDIR, "scan_results.jsonl")
OUT_INDEX = os.path.join(WORKDIR, "articles_index.tsv")
OUT_SUMMARY = os.path.join(WORKDIR, "summary.json")

PROBE_CHARS = 250
PROBE_NAMES = ("first250", "mid_sentence", "last250")

# ---------------------------------------------------------------- stripping --

RE_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
RE_REF_SELF = re.compile(r"<ref[^<>]*/>", re.IGNORECASE)
RE_REF_PAIR = re.compile(r"<ref[^<>]*>.*?</ref>", re.IGNORECASE | re.DOTALL)
RE_TEMPLATE_INNER = re.compile(r"\{\{[^{}]*\}\}", re.DOTALL)
RE_LINK = re.compile(r"\[\[([^\[\]]*)\]\]")
RE_TAG = re.compile(r"<[^<>]{0,200}>")


def _link_repl(m):
    inner = m.group(1)
    # [[a|b]] -> b ; [[a]] -> a ; [[File:x|...|caption]] -> caption
    return inner.rsplit("|", 1)[-1]


def strip_wikitext(text):
    """Minimal wikitext strip, per spec. Input is the raw <text> element content
    (XML-escaped); output is plain prose with single-space-collapsed whitespace."""
    if "&" in text:
        text = html.unescape(text)          # &amp;/&lt;/&gt;/&quot;/&nbsp;/... in one pass
        text = text.replace("\xa0", " ")     # &nbsp; -> plain space
    text = RE_COMMENT.sub(" ", text)
    text = RE_REF_SELF.sub(" ", text)
    text = RE_REF_PAIR.sub(" ", text)
    for _ in range(10):                       # innermost-first template removal
        text, n = RE_TEMPLATE_INNER.subn(" ", text)
        if not n:
            break
    for _ in range(2):                        # second pass catches simply-nested links
        text, n = RE_LINK.subn(_link_repl, text)
        if not n:
            break
    text = text.replace("'''", "").replace("''", "")
    text = RE_TAG.sub(" ", text)
    return " ".join(text.split())


def normalize(text):
    """Normalization used for all substring tests: strip + lowercase + collapsed ws."""
    return strip_wikitext(text).lower()


# ------------------------------------------------------------------- probes --

RE_SENT = re.compile(r"(?<=[.!?]) ")


def make_probes(norm_passage):
    """(first 250 normalized chars, middle sentence, last 250 normalized chars)."""
    first = norm_passage[:PROBE_CHARS]
    last = norm_passage[-PROBE_CHARS:]
    sents = [s for s in RE_SENT.split(norm_passage) if s]
    mid = sents[len(sents) // 2] if sents else norm_passage
    return (first, mid, last)


def anchor_token(probe):
    """Rarest-ish complete token inside the probe: longest interior token
    (edge tokens may be truncated by the 250-char cut, so drop them)."""
    toks = probe.split()
    interior = toks[1:-1] if len(toks) > 2 else toks
    return max(interior, key=len) if interior else None


# --------------------------------------------------------------------- main --

def main():
    t0 = time.time()
    passages = []                      # [(pid, norm_text, (p_first, p_mid, p_last))]
    anchors = {}                       # token -> set of passage list-indices
    with open(PASSAGES, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            norm = normalize(row["text"])
            probes = make_probes(norm)
            idx = len(passages)
            passages.append((row["passage_id"], norm, probes))
            for p in probes:
                tok = anchor_token(p)
                if tok:
                    anchors.setdefault(tok, set()).add(idx)
    n_pass = len(passages)
    anchor_keys = set(anchors)
    # best[i] = [n_probes_hit, title, (hit_first, hit_mid, hit_last)]
    best = [[0, None, (False, False, False)] for _ in range(n_pass)]

    dump_size = os.path.getsize(DUMP)
    print(f"[start] {n_pass} passages loaded, {len(anchor_keys)} anchor tokens; "
          f"dump={dump_size/1e9:.2f} GB; scanning...", flush=True)

    raw = open(DUMP, "rb")
    bzf = bz2.BZ2File(raw)
    # C-speed line iteration: BufferedReader.__next__ is C; it pulls from the
    # (Python-level) BZ2File.readinto only once per megabyte, not once per line.
    lines = io.BufferedReader(bzf, 1 << 20)

    idx_out = open(OUT_INDEX, "w", encoding="utf-8", buffering=1 << 20)

    offset = 0            # decompressed-stream byte offset
    page_offset = -1
    in_page = False
    in_text = False
    skip_page = False
    title = None
    ns = 0
    text_parts = []

    pages = 0
    articles = 0
    redirects = 0
    non_ns0 = 0
    next_early = 10_000

    def finish_article():
        nonlocal articles
        raw_text = b"".join(text_parts).decode("utf-8", errors="replace")
        norm_art = normalize(raw_text)
        toks = norm_art.split()
        idx_out.write(f"{title}\t{len(toks)}\t{page_offset}\n")
        articles += 1
        hits = anchor_keys.intersection(toks)
        if hits:
            cand = set()
            for tok in hits:
                cand |= anchors[tok]
            for i in cand:
                flags = tuple(p in norm_art for p in passages[i][2])
                n = sum(flags)
                if n > best[i][0]:
                    best[i] = [n, title, flags]
        if articles % 100_000 == 0:
            el = time.time() - t0
            pct = raw.tell() / dump_size * 100
            print(f"[progress] articles={articles:,} pages={pages:,} "
                  f"elapsed={el/60:.1f}m compressed~{pct:.1f}% "
                  f"matched_any={sum(1 for b in best if b[0] > 0)}", flush=True)

    for line in lines:
        llen = len(line)
        if in_text:
            end = line.find(b"</text>")
            if end == -1:
                text_parts.append(line)
            else:
                text_parts.append(line[:end])
                in_text = False
            offset += llen
            continue
        s = line.strip()
        if not in_page:
            if s == b"<page>":
                in_page = True
                page_offset = offset
                skip_page = False
                title = None
                ns = 0
                text_parts = []
        elif s == b"</page>":
            pages += 1
            if not skip_page and title is not None:
                finish_article()
            in_page = False
            if pages == next_early:
                next_early = 0
                print(f"[early] pages={pages:,} articles={articles:,} "
                      f"elapsed={time.time()-t0:.0f}s", flush=True)
        elif skip_page:
            pass
        elif s.startswith(b"<title>"):
            title = html.unescape(
                s[7:s.find(b"</title>")].decode("utf-8", errors="replace"))
        elif s.startswith(b"<ns>"):
            ns = s[4:s.find(b"</ns>")]
            if ns != b"0":
                skip_page = True
                non_ns0 += 1
        elif s.startswith(b"<redirect"):
            skip_page = True
            redirects += 1
        elif s.startswith(b"<text"):
            gt = line.find(b">", line.find(b"<text"))
            if line[gt - 1:gt] == b"/":          # <text ... />  (empty)
                text_parts = []
            else:
                rest = line[gt + 1:]
                end = rest.find(b"</text>")
                if end == -1:
                    text_parts = [rest]
                    in_text = True
                else:
                    text_parts = [rest[:end]]
        offset += llen

    lines.close()
    raw.close()
    idx_out.close()

    # ------------------------------------------------------------- results --
    tiers = {"full": 0, "partial": 0, "none": 0}
    with open(OUT_RESULTS, "w", encoding="utf-8") as f:
        for (pid, _norm, _probes), (n, btitle, flags) in zip(passages, best):
            tier = "full" if n == 3 else ("partial" if n else "none")
            tiers[tier] += 1
            f.write(json.dumps({
                "passage_id": pid,
                "tier": tier,
                "title": btitle,
                "probes_hit": [nm for nm, hit in zip(PROBE_NAMES, flags) if hit],
            }, ensure_ascii=False) + "\n")

    el = time.time() - t0
    matched = tiers["full"] + tiers["partial"]
    summary = {
        "dump": DUMP,
        "pages_seen": pages,
        "articles_ns0": articles,
        "redirects_skipped": redirects,
        "non_ns0_skipped": non_ns0,
        "passages": n_pass,
        "tier_full": tiers["full"],
        "tier_partial": tiers["partial"],
        "tier_none": tiers["none"],
        "match_rate_any": round(matched / n_pass, 4),
        "match_rate_full": round(tiers["full"] / n_pass, 4),
        "elapsed_sec": round(el),
    }
    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("=" * 64)
    print("[summary] NATIVE-arm substring-match scan, enwiki-20210701")
    print(f"  pages seen        : {pages:,}")
    print(f"  ns-0 articles     : {articles:,} (redirects skipped: {redirects:,}, "
          f"non-ns0 skipped: {non_ns0:,})")
    print(f"  passages          : {n_pass}")
    print(f"  tier full         : {tiers['full']}  ({tiers['full']/n_pass:.1%})")
    print(f"  tier partial      : {tiers['partial']}  ({tiers['partial']/n_pass:.1%})")
    print(f"  tier none         : {tiers['none']}  ({tiers['none']/n_pass:.1%})")
    print(f"  match rate (any)  : {matched/n_pass:.1%}")
    print(f"  elapsed           : {el/3600:.2f} h")
    print("=" * 64, flush=True)


if __name__ == "__main__":
    main()
