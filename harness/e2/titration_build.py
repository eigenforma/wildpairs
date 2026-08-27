"""E2-P2: construct the titrated stimulus set, encoder-blind (PREREGISTRATION_E2 section 2).

Committed BEFORE the prereg-e2 tag as the executable construction rules; no encoder is
loaded here and no text is embedded - everything below is whitespace/lexical assembly.
Both members of every pair share a byte-identical host frame with the payload at the
identical sentence slot; the pinned drop rule is applied at the anchor level with the
operative cuts REUSED from the frozen table (never re-derived), cross-checked against
the formula max(ws of orig/para/affirm) > W(L)/2, W(L) = ceil(L/1.3).

Recompute: python harness/e2/titration_build.py --host-domain enwiki \
    --hosts <hostpool.jsonl> --draw results/verification/e2_host_draw.json \
    --seed 20260805 [--native <extended.jsonl>]
Inputs : corpus/e2_dilution/anchors_frozen.jsonl (frozen),
         results/verification/e2_attrition_tables.json (frozen drop-rule arithmetic),
         results/verification/e2_host_draw.json (the FROZEN host assignment: one host
         per (anchor x domain), seed 20260805, reused across all (L, position) cells -
         the tag-time section-2 pin; this build takes the first draw candidate passing
         the contamination exclusion and records every substitution),
         SPLICE host pool jsonl rows {host_id, text} (scripts/e2_pack_hostpools.py),
         NATIVE extended-passages jsonl rows {passage_id, extended_text}
         (passage_id == anchor_id; same pack script, from the native-scan join).
Output : corpus/e2_dilution/stimuli/stimuli_<domain>_<arm>.jsonl, one row per pair
         member: {stim_id, anchor_id, arm, host_domain, host_id, L, position, pair,
         member, text, payload_ws}; plus a .manifest.json beside each file (counts,
         drops, cross-checks, seed, pins). Exits nonzero on any frozen-table mismatch
         or any unfillable SPLICE cell - no silent caps.
"""
import argparse
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ANCHORS = ROOT / "corpus" / "e2_dilution" / "anchors_frozen.jsonl"
ATTRITION = ROOT / "results" / "verification" / "e2_attrition_tables.json"
OUT_DIR = ROOT / "corpus" / "e2_dilution" / "stimuli"

BINS = [64, 96, 128, 256, 512, 1024, 2048, 4096]
POSITIONS = ["early", "middle", "late"]
# PIN: positions early/middle/late = first/middle/last decile of host sentence slots
# (prereg section 2). Realized here as the decile MIDPOINT fraction of the m+1
# insertion slots: slot = floor(q * (m+1)) clamped to m, q in {0.05, 0.50, 0.95}.
POS_Q = {"early": 0.05, "middle": 0.50, "late": 0.95}
DOMAINS = ["enwiki", "pmc", "rfc"]

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")   # verbatim harness/e2/build_anchors.py


def sentences(text: str):
    return [s.strip() for s in SENT_SPLIT.split(text.strip()) if s.strip()]


def ws(s: str) -> int:
    return len(s.split())


def norm(s: str) -> str:
    """Whitespace-collapsed, casefolded - the contamination-check normal form (pin)."""
    return " ".join(s.split()).casefold()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cuts(attrition_path: Path):
    """Operative per-bin budgets/cuts from the FROZEN attrition table (reuse, not
    re-derive); each value is asserted against the pinned formula before use."""
    frozen = json.loads(attrition_path.read_text(encoding="utf-8"))
    cuts = {}
    for L in BINS:
        b = frozen["per_bin"][str(L)]
        W = math.ceil(L / 1.3)
        if b["ws_budget_W"] != W or b["cut_max_member_gt"] != W / 2:
            sys.exit(f"frozen attrition table disagrees with the pinned formula at L={L}: "
                     f"{b['ws_budget_W']}/{b['cut_max_member_gt']} vs {W}/{W / 2}")
        cuts[L] = {"W": b["ws_budget_W"], "cut": b["cut_max_member_gt"],
                   "frozen_eligible": b["eligible"], "frozen_scope_eligible": b["scope_eligible"]}
    return cuts


def max_member_ws(a) -> int:
    return max(ws(a["payload_orig"]), ws(a["payload_para"]), ws(a["payload_affirm"]))


def scope_fits(a, cut) -> bool:
    """The frozen table's scope arithmetic verbatim (scripts/e2_attrition_tables.py):
    max(ws(orig), ws(scope)) <= cut, over scope-present anchors."""
    return "payload_scope" in a and max(ws(a["payload_orig"]), ws(a["payload_scope"])) <= cut


def crosscheck_attrition(anchors, cuts):
    """Recompute per-bin eligibility on the frozen anchors and demand exact agreement
    with results/verification/e2_attrition_tables.json. Hard-fails on any mismatch."""
    diffs, table = [], {}
    for L in BINS:
        cut = cuts[L]["cut"]
        elig = sum(1 for a in anchors if max_member_ws(a) <= cut)
        scope = sum(1 for a in anchors if scope_fits(a, cut))
        table[str(L)] = {"eligible": elig, "scope_fit": scope,
                         "frozen_eligible": cuts[L]["frozen_eligible"],
                         "frozen_scope_eligible": cuts[L]["frozen_scope_eligible"]}
        if elig != cuts[L]["frozen_eligible"]:
            diffs.append(f"L={L}: eligible {elig} != frozen {cuts[L]['frozen_eligible']}")
        if scope != cuts[L]["frozen_scope_eligible"]:
            diffs.append(f"L={L}: scope_fit {scope} != frozen {cuts[L]['frozen_scope_eligible']}")
    if diffs:
        sys.exit("attrition cross-check FAILED (frozen table is the authority):\n  "
                 + "\n  ".join(diffs))
    return table


def build_frame(host_text: str, budget: int):
    """Host frame = the first `budget` whitespace tokens of the host document as a list
    of sentence strings; the final sentence is word-truncated so the frame lands on
    exactly `budget` tokens (PIN: exact-budget construction - prereg says 'assembled
    once to W(L) whitespace tokens'). Returns None when the host runs short."""
    frame, used = [], 0
    for s in sentences(host_text):
        n = ws(s)
        if used + n <= budget:
            frame.append(s)
            used += n
        else:
            frame.append(" ".join(s.split()[: budget - used]))
            used = budget
        if used == budget:
            return frame
    return None


def slot_index(m: int, position: str) -> int:
    """m host sentences -> m+1 insertion slots (0..m); slot = floor(q*(m+1)), clamped."""
    return min(m, int(POS_Q[position] * (m + 1)))


def splice(frame, slot: int, payload: str) -> str:
    return " ".join(frame[:slot] + [payload] + frame[slot:])


def pairs_for(anchor, cut):
    """Pair classes per prereg section 1: flip = orig->affirm, faithful = orig->para,
    scope (secondary) = orig->scope. Scope emitted only when the anchor is bin-eligible
    AND the scope member fits the frozen table's scope cut (intersection - a titrated
    passage cannot be built for an ineligible anchor)."""
    out = [("flip", anchor["payload_affirm"]), ("faithful", anchor["payload_para"])]
    if scope_fits(anchor, cut):
        out.append(("scope", anchor["payload_scope"]))
    return out


# =============================================================================
# HOST ASSIGNMENT -- PINNED (PREREGISTRATION_E2 section 2, frozen at tag prereg-e2):
# ONE host document per (anchor x domain), drawn once with seed 20260805 by
# scripts/e2_host_draw.py, REUSED across all (L, position) cells - dilution is
# titrated within a fixed host, so cross-L comparisons never confound host identity;
# each (L, position) frame is carved deterministically from that document (prefix
# frame of the budget, slot per position). The frozen draw carries seeded backup
# candidates; the build takes the FIRST candidate passing the pinned contamination
# exclusion (a host must not contain the payload sentence, any member, or the
# anchor's source passage - whitespace-collapsed casefolded substring test) and
# records every substitution. The pool length rule (>= W(4096) ws tokens) guarantees
# every bin's frame budget by construction; a short host is an invariant violation.
# =============================================================================
def select_host(candidates, pool, needles):
    """(host_id, text, candidate_index) for the first candidate present in the pool and
    not contaminated for this anchor; (None, None, None) when the list is exhausted."""
    for i, hid in enumerate(candidates):
        text = pool.get(hid)
        if text is None:
            continue
        hnorm = norm(text)
        if any(n in hnorm for n in needles):
            continue
        return hid, text, i
    return None, None, None


def build_splice(anchors, cuts, pool, draw_map, bins, positions, writer, counts):
    unfilled, collisions, substitutions = [], {}, {}
    for a in anchors:
        aid = a["anchor_id"]
        candidates = draw_map.get(aid)
        if not candidates:
            sys.exit(f"frozen draw carries no candidates for anchor {aid} - draw file "
                     f"damaged or wrong domain")
        needles = [norm(a["passage"]), norm(a["payload_orig"]), norm(a["payload_para"]),
                   norm(a["payload_affirm"])]
        if "payload_scope" in a:
            needles.append(norm(a["payload_scope"]))
        host_id, host_text, ci = select_host(candidates, pool, needles)
        if host_id is None:
            for L in bins:
                if max_member_ws(a) <= cuts[L]["cut"]:
                    unfilled.extend({"anchor_id": aid, "L": L, "position": p}
                                    for p in positions)
            continue
        if ci > 0:
            substitutions[aid] = {"candidate_index_used": ci, "host_id": host_id}
        for L in bins:
            W, cut = cuts[L]["W"], cuts[L]["cut"]
            if max_member_ws(a) > cut:
                continue
            budget = W - ws(a["payload_orig"])   # PIN: orig member realizes exactly W(L)
            frame = build_frame(host_text, budget)
            if frame is None:
                sys.exit(f"invariant violated: host {host_id} shorter than budget "
                         f"{budget} at L={L} despite the >= W(4096) pool rule")
            slots_seen = set()
            for position in positions:
                slot = slot_index(len(frame), position)
                slots_seen.add(slot)
                a_text = splice(frame, slot, a["payload_orig"])
                for pair, payload_b in pairs_for(a, cut):
                    writer(aid, "splice", host_id, L, position, pair,
                           "a", a_text, ws(a["payload_orig"]))
                    writer(aid, "splice", host_id, L, position, pair,
                           "b", splice(frame, slot, payload_b), ws(payload_b))
                    counts["splice"][str(L)][pair] += 1
            if len(positions) > 1 and len(slots_seen) < len(positions):
                # short frames can map distinct position labels onto one slot; counted,
                # never smoothed (inherent at small L, disclosed via the manifest)
                collisions[str(L)] = collisions.get(str(L), 0) + 1
    return unfilled, collisions, substitutions


# =============================================================================
# NATIVE arm (prereg section 2, measured match rate 94.8%, dump 20210701 disclosed
# as the NATIVE host source). Join key passage_id == anchor_id, realized by
# scripts/e2_host_draw.py's native join (scan passage ids -> anchor passages by
# exact text equality). Position is realized as a whitespace-token allocation:
# round(q * host_budget) tokens before the payload, the rest after (decile-midpoint
# q as in the SPLICE arm), deficits shifted to the other side. Locating is done on
# whitespace-collapsed text, case-insensitive with a length-preservation guard (the
# scan matched under lowercase normalization); residual failures drop from NATIVE
# ONLY, per reason, disclosed in the manifest.
# =============================================================================
def _find_ci(hay: str, needle: str) -> int:
    """Case-insensitive find with a length-preservation guard (exact-find fallback
    when lowercasing changes string length, which would corrupt offsets)."""
    hl, nl = hay.lower(), needle.lower()
    if len(hl) == len(hay) and len(nl) == len(needle):
        return hl.find(nl)
    return hay.find(needle)


def native_members(extended: str, anchor, budget: int, position: str):
    ext = " ".join(extended.split())
    pas = " ".join(anchor["passage"].split())
    pay = " ".join(anchor["payload_orig"].split())
    g = _find_ci(ext, pas)
    if g < 0:
        return None, "passage_not_found"
    off = _find_ci(pas, pay)
    if off < 0:
        return None, "payload_not_in_passage"
    start = g + off
    before_all = ext[:start].split()
    after_all = ext[start + len(pay):].split()
    nb = min(int(round(POS_Q[position] * budget)), len(before_all))
    na = min(budget - nb, len(after_all))
    short = budget - nb - na
    if short > 0:
        extra = min(short, len(before_all) - nb)
        nb += extra
        short -= extra
    if short > 0:
        return None, "insufficient_context"
    return (before_all[len(before_all) - nb:], after_all[:na]), None


def build_native(anchors, cuts, native_rows, bins, positions, writer, counts):
    by_id = {r["passage_id"]: r["extended_text"] for r in native_rows}
    drops = {}
    matched = set()
    for L in bins:
        W, cut = cuts[L]["W"], cuts[L]["cut"]
        for a in anchors:
            if max_member_ws(a) > cut:
                continue
            ext = by_id.get(a["anchor_id"])
            if ext is None:
                drops["no_native_row"] = drops.get("no_native_row", 0) + 1
                continue
            budget = W - ws(a["payload_orig"])
            for position in positions:
                got, why = native_members(ext, a, budget, position)
                if got is None:
                    drops[why] = drops.get(why, 0) + 1
                    continue
                before, after = got
                matched.add(a["anchor_id"])
                pay = " ".join(a["payload_orig"].split())
                a_text = " ".join(before + [pay] + after)
                for pair, payload_b in pairs_for(a, cut):
                    pb = " ".join(payload_b.split())
                    writer(a["anchor_id"], "native", a["anchor_id"], L, position, pair,
                           "a", a_text, ws(pay))
                    writer(a["anchor_id"], "native", a["anchor_id"], L, position, pair,
                           "b", " ".join(before + [pb] + after), ws(pb))
                    counts["native"][str(L)][pair] += 1
    return drops, matched


def main(argv=None):
    ap = argparse.ArgumentParser(description="E2 titration build (encoder-blind)")
    ap.add_argument("--anchors", default=str(ANCHORS))
    ap.add_argument("--attrition", default=str(ATTRITION))
    ap.add_argument("--host-domain", required=True, choices=DOMAINS)
    ap.add_argument("--hosts", default=None, help="SPLICE host pool jsonl {host_id, text}")
    ap.add_argument("--draw", default=None,
                    help="frozen host draw json (required with --hosts): "
                         "results/verification/e2_host_draw.json")
    ap.add_argument("--seed", type=int, default=None,
                    help="required with --hosts; must equal the frozen draw's seed")
    ap.add_argument("--native", default=None,
                    help="NATIVE extended-passages jsonl {passage_id, extended_text}")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--bins", default=",".join(str(b) for b in BINS))
    ap.add_argument("--positions", default=",".join(POSITIONS))
    args = ap.parse_args(argv)

    if not args.hosts and not args.native:
        sys.exit("nothing to build: pass --hosts (SPLICE) and/or --native (NATIVE)")
    if args.hosts and (args.seed is None or not args.draw):
        sys.exit("--hosts requires --draw (the frozen assignment) and --seed "
                 "(cross-checked against the draw's recorded seed)")
    bins = [int(b) for b in args.bins.split(",") if b.strip()]
    if any(b not in BINS for b in bins):
        sys.exit(f"--bins must be a subset of the registered grid {BINS}")
    positions = [p.strip() for p in args.positions.split(",") if p.strip()]
    if any(p not in POSITIONS for p in positions):
        sys.exit(f"--positions must be a subset of {POSITIONS}")

    anchors_path, attrition_path = Path(args.anchors), Path(args.attrition)
    anchors = [json.loads(l) for l in anchors_path.read_text(encoding="utf-8").splitlines()
               if l.strip()]
    cuts = load_cuts(attrition_path)
    attr_table = crosscheck_attrition(anchors, cuts)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    dom = args.host_domain

    inputs = {"anchors": {"path": str(anchors_path), "sha256": sha256_file(anchors_path)},
              "attrition": {"path": str(attrition_path),
                            "sha256": sha256_file(attrition_path)}}
    counts = {"splice": {str(L): {"flip": 0, "faithful": 0, "scope": 0} for L in bins},
              "native": {str(L): {"flip": 0, "faithful": 0, "scope": 0} for L in bins}}
    manifest = {
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host_domain": dom, "seed": args.seed, "bins": bins, "positions": positions,
        "inputs": inputs, "attrition_crosscheck": {"pass": True, "per_bin": attr_table},
        "pins": [
            "drop rule: anchor drops from bin L when max ws-tokens over (orig, para, affirm) "
            "> W(L)/2, W(L)=ceil(L/1.3); operative cuts loaded from the frozen table",
            "host frame budget = W(L) - ws(payload_orig): the orig member realizes exactly "
            "W(L) ws tokens; the b member differs only by the payload length delta "
            "(host byte-identical either side, payload at the identical slot)",
            "frame = first budget ws tokens of the host document, sentences joined by a "
            "single space, final sentence word-truncated to land exactly on budget",
            "insertion slot = floor(q*(m+1)) over the m+1 host sentence slots, "
            "q = decile midpoints {early: 0.05, middle: 0.50, late: 0.95}, clamped to m",
            "sentence splitter = build_anchors.py's (?<=[.!?])\\s+ verbatim",
            "contamination normal form: whitespace-collapsed casefolded substring test; "
            "needles = source passage + every payload member",
            "scope pair emitted when anchor-eligible AND max(ws(orig), ws(scope)) <= cut "
            "(the frozen table's scope arithmetic)",
            "NATIVE position realized as ws-token allocation around the payload at the "
            "decile-midpoint fractions, deficits shifted; locate on ws-collapsed text, "
            "case-insensitive with length-preservation guard",
            "host assignment (frozen at tag): ONE host per (anchor x domain) from "
            "results/verification/e2_host_draw.json (seed 20260805), reused across all "
            "(L, position) cells; first candidate passing contamination is the operative "
            "host, substitutions recorded below",
        ],
        "tbd_at_tag": [
            "none - the pre-tag TBDs (host assignment, native join key, dump version) "
            "are discharged by the tag-time section-2 pins; see 'pins'",
        ],
    }

    def make_writer(fh):
        def writer(anchor_id, arm_, host_id, L, position, pair, member, text, payload_ws):
            fh.write(json.dumps({
                "stim_id": f"{arm_}:{dom}:{anchor_id}:L{L}:{position}:{pair}:{member}",
                "anchor_id": anchor_id, "arm": arm_, "host_domain": dom, "host_id": host_id,
                "L": L, "position": position, "pair": pair, "member": member,
                "text": text, "payload_ws": payload_ws}, ensure_ascii=False) + "\n")
            writer.rows += 1
        writer.rows = 0
        return writer

    failures = []

    if args.hosts:
        hosts_path, draw_path = Path(args.hosts), Path(args.draw)
        pool = {}
        for l in hosts_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                if r["host_id"] in pool:
                    sys.exit(f"duplicate host_id {r['host_id']!r} in {hosts_path}")
                pool[r["host_id"]] = r["text"]
        if not pool:
            sys.exit(f"empty host pool: {hosts_path}")
        draw_doc = json.loads(draw_path.read_text(encoding="utf-8"))
        if draw_doc["meta"]["seed"] != args.seed:
            sys.exit(f"--seed {args.seed} != frozen draw seed {draw_doc['meta']['seed']}")
        draw_map = {d["anchor_id"]: d["candidates"] for d in draw_doc["draws"]
                    if d["domain"] == dom}
        inputs["hosts"] = {"path": str(hosts_path), "sha256": sha256_file(hosts_path),
                           "n_hosts": len(pool)}
        inputs["draw"] = {"path": str(draw_path), "sha256": sha256_file(draw_path),
                          "n_draws_this_domain": len(draw_map)}
        out_path = out_dir / f"stimuli_{dom}_splice.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            w = make_writer(fh)
            unfilled, collisions, subs = build_splice(anchors, cuts, pool, draw_map,
                                                      bins, positions, w, counts)
        manifest["splice"] = {
            "output": {"path": str(out_path), "sha256": sha256_file(out_path),
                       "rows": w.rows},
            "per_bin_pairs": counts["splice"], "unfilled_cells": unfilled,
            "position_slot_collision_anchors_per_bin": collisions,
            "host_substitutions": {"n": len(subs), "detail": subs},
        }
        if unfilled:
            failures.append(f"{len(unfilled)} SPLICE cells unfillable from this host pool "
                            "(first: %r)" % unfilled[0])

    if args.native:
        native_path = Path(args.native)
        native_rows = [json.loads(l) for l in
                       native_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        inputs["native"] = {"path": str(native_path), "sha256": sha256_file(native_path),
                            "n_rows": len(native_rows)}
        out_path = out_dir / f"stimuli_{dom}_native.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            w = make_writer(fh)
            drops, matched = build_native(anchors, cuts, native_rows, bins, positions,
                                          w, counts)
        manifest["native"] = {
            "output": {"path": str(out_path), "sha256": sha256_file(out_path),
                       "rows": w.rows},
            "per_bin_pairs": counts["native"], "drops": drops,
            "matched_anchors": len(matched),
            "substring_match_rate_of_anchor_population":
                round(len(matched) / len(anchors), 4) if anchors else None,
        }

    man_path = out_dir / f"stimuli_{dom}.manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"manifest: {man_path}")
    for arm in ("splice", "native"):
        if arm in manifest:
            print(f"{arm}: {manifest[arm]['output']['rows']} rows -> "
                  f"{manifest[arm]['output']['path']}")
    if failures:
        sys.exit("BUILD INCOMPLETE (manifest still written):\n  " + "\n  ".join(failures))


if __name__ == "__main__":
    main()
