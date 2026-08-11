"""E2-P2: construct the titrated stimulus set, encoder-blind (PREREGISTRATION_E2 section 2).

Committed BEFORE the prereg-e2 tag as the executable construction rules; no encoder is
loaded here and no text is embedded - everything below is whitespace/lexical assembly.
Both members of every pair share a byte-identical host frame with the payload at the
identical sentence slot; the pinned drop rule is applied at the anchor level with the
operative cuts REUSED from the frozen table (never re-derived), cross-checked against
the formula max(ws of orig/para/affirm) > W(L)/2, W(L) = ceil(L/1.3).

Recompute: python harness/e2/titration_build.py --host-domain enwiki \
    --hosts <hostpool.jsonl> --seed <int> [--native <extended.jsonl>]
Inputs : corpus/e2_dilution/anchors_frozen.jsonl (frozen),
         results/verification/e2_attrition_tables.json (frozen drop-rule arithmetic),
         SPLICE host pool jsonl rows {host_id, text},
         NATIVE extended-passages jsonl rows {passage_id, extended_text} (the enwiki
         scan output feeds it - TBD until that scan lands, see NATIVE block below).
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
import random
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


def cell_seed(seed: int, anchor_id: str, L: int, position: str) -> int:
    """Deterministic per-cell RNG key: stable across sessions/platforms (sha256, not
    Python's salted hash), so the drawn hosts are byte-identical on every rebuild."""
    h = hashlib.sha256(f"{seed}|{anchor_id}|{L}|{position}".encode("utf-8")).hexdigest()
    return int(h, 16)


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
# TBD AT TAG TIME -- PREREGISTRATION_E2 section 2, "Host assignment (pinned before
# tag)": which enwiki articles QUALIFY as hosts, HOW MANY DRAWS per (anchor, L,
# position), and the operative RNG SEED are specified in section 6 at tag time.
# Until that pin lands, the draw below is a PROVISIONAL placeholder: one uniform
# draw per (anchor, L, position) from the supplied --hosts pool, deterministic in
# (--seed, anchor_id, L, position), host text consumed from document start.
# The CONTAMINATION EXCLUSION is already the pinned rule and IS implemented here:
# a host must not contain the payload sentence (any member) or the anchor's source
# passage (substring test on whitespace-collapsed, casefolded text).
# =============================================================================
def draw_host(pool, host_norms, host_ws, needles, budget: int, rng: random.Random):
    """Uniform order without replacement until a qualifying host is found. Qualifying =
    long enough for the frame budget AND not contaminated for this anchor. Returns
    (host_id, frame) or (None, None) when the pool is exhausted."""
    order = list(range(len(pool)))
    rng.shuffle(order)
    for i in order:
        if host_ws[i] < budget:
            continue
        if any(n in host_norms[i] for n in needles):
            continue
        frame = build_frame(pool[i]["text"], budget)
        if frame is not None:
            return pool[i]["host_id"], frame
    return None, None


def build_splice(anchors, cuts, pool, bins, positions, seed, writer, counts):
    host_norms = [norm(h["text"]) for h in pool]
    host_ws = [ws(h["text"]) for h in pool]
    unfilled, collisions = [], {}
    for L in bins:
        W, cut = cuts[L]["W"], cuts[L]["cut"]
        for a in anchors:
            if max_member_ws(a) > cut:
                continue
            needles = [norm(a["passage"]), norm(a["payload_orig"]), norm(a["payload_para"]),
                       norm(a["payload_affirm"])]
            if "payload_scope" in a:
                needles.append(norm(a["payload_scope"]))
            budget = W - ws(a["payload_orig"])   # PIN: orig member realizes exactly W(L)
            slots_seen, cells_ok = set(), 0
            for position in positions:
                rng = random.Random(cell_seed(seed, a["anchor_id"], L, position))
                host_id, frame = draw_host(pool, host_norms, host_ws, needles, budget, rng)
                if frame is None:
                    unfilled.append({"anchor_id": a["anchor_id"], "L": L, "position": position})
                    continue
                slot = slot_index(len(frame), position)
                slots_seen.add(slot)
                cells_ok += 1
                a_text = splice(frame, slot, a["payload_orig"])
                for pair, payload_b in pairs_for(a, cut):
                    writer(a["anchor_id"], "splice", host_id, L, position, pair,
                           "a", a_text, ws(a["payload_orig"]))
                    writer(a["anchor_id"], "splice", host_id, L, position, pair,
                           "b", splice(frame, slot, payload_b), ws(payload_b))
                    counts["splice"][str(L)][pair] += 1
            if cells_ok > 1 and len(slots_seen) < cells_ok:
                # short frames can map distinct position labels onto one slot; counted,
                # never smoothed (inherent at small L, disclosed via the manifest)
                collisions[str(L)] = collisions.get(str(L), 0) + 1
    return unfilled, collisions


# =============================================================================
# TBD AT TAG TIME -- NATIVE arm (prereg section 2, "NATIVE arm (supporting,
# ecological)"): the extended-passages file is the enwiki scan output (in flight,
# prereg section 6 "NATIVE-arm substring-match rate"); until it lands, the join key
# (passage_id == anchor_id), the dump version (20210701 vs 20210720 test), and the
# sentence-slot reconciliation of position are PROVISIONAL. Position is realized
# here as a whitespace-token allocation: floor/round(q * host_budget) tokens before
# the payload, the rest after (decile-midpoint q as in the SPLICE arm), deficits
# shifted to the other side; anchors whose passage is not an exact substring of
# extended_text drop from NATIVE ONLY (recorded, per the prereg's 70-90% expected
# match rate).
# =============================================================================
def native_members(extended: str, anchor, budget: int, position: str):
    g = extended.find(anchor["passage"])
    if g < 0:
        return None, "passage_not_found"
    off = anchor["passage"].find(anchor["payload_orig"])
    if off < 0:
        return None, "payload_not_in_passage"
    start = g + off
    before_all = extended[:start].split()
    after_all = extended[start + len(anchor["payload_orig"]):].split()
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
                a_text = " ".join(before + [a["payload_orig"]] + after)
                for pair, payload_b in pairs_for(a, cut):
                    writer(a["anchor_id"], "native", a["anchor_id"], L, position, pair,
                           "a", a_text, ws(a["payload_orig"]))
                    writer(a["anchor_id"], "native", a["anchor_id"], L, position, pair,
                           "b", " ".join(before + [payload_b] + after), ws(payload_b))
                    counts["native"][str(L)][pair] += 1
    return drops, matched


def main(argv=None):
    ap = argparse.ArgumentParser(description="E2 titration build (encoder-blind)")
    ap.add_argument("--anchors", default=str(ANCHORS))
    ap.add_argument("--attrition", default=str(ATTRITION))
    ap.add_argument("--host-domain", required=True, choices=DOMAINS)
    ap.add_argument("--hosts", default=None, help="SPLICE host pool jsonl {host_id, text}")
    ap.add_argument("--seed", type=int, default=None, help="required with --hosts")
    ap.add_argument("--native", default=None,
                    help="NATIVE extended-passages jsonl {passage_id, extended_text}")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--bins", default=",".join(str(b) for b in BINS))
    ap.add_argument("--positions", default=",".join(POSITIONS))
    args = ap.parse_args(argv)

    if not args.hosts and not args.native:
        sys.exit("nothing to build: pass --hosts (SPLICE) and/or --native (NATIVE)")
    if args.hosts and args.seed is None:
        sys.exit("--seed is required with --hosts (deterministic host draw)")
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
            "decile-midpoint fractions, deficits shifted",
        ],
        "tbd_at_tag": [
            "PREREGISTRATION_E2 section 2 'Host assignment': host qualification, draws per "
            "(anchor, L, position), operative seed - pinned in section 6 at tag time",
            "NATIVE join key passage_id == anchor_id (provisional until the enwiki scan "
            "output lands) and the winning July-2021 dump version",
            "NATIVE sentence-slot reconciliation of position",
            "unfillable-SPLICE-cell policy (currently: hard fail)",
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
        hosts_path = Path(args.hosts)
        pool = [json.loads(l) for l in hosts_path.read_text(encoding="utf-8").splitlines()
                if l.strip()]
        if not pool:
            sys.exit(f"empty host pool: {hosts_path}")
        inputs["hosts"] = {"path": str(hosts_path), "sha256": sha256_file(hosts_path),
                           "n_hosts": len(pool)}
        out_path = out_dir / f"stimuli_{dom}_splice.jsonl"
        with out_path.open("w", encoding="utf-8") as fh:
            w = make_writer(fh)
            unfilled, collisions = build_splice(anchors, cuts, pool, bins, positions,
                                                args.seed, w, counts)
        manifest["splice"] = {
            "output": {"path": str(out_path), "sha256": sha256_file(out_path),
                       "rows": w.rows},
            "per_bin_pairs": counts["splice"], "unfilled_cells": unfilled,
            "position_slot_collision_anchors_per_bin": collisions,
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
