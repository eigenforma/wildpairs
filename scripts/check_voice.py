"""Scan paper-facing prose for the tells the author has flagged.

Why this is a script and not a rule. On 2026-08-12 the author named a list of my verbal habits.
I acknowledged the list and committed a fresh instance of it in the same sentence. He named that
one. I acknowledged again and committed another in that sentence. He named that one too. Three
for three, each time inside prose written to demonstrate awareness of the problem.

The conclusion is not that I should try harder. It is that these are invisible to me at the
moment of writing, so detection has to be external, like `recompute_headline_numbers.py`. Run
this before any draft goes to the author or out of the lab.

Two categories, because they fail differently:
  BANNED   words that assert significance instead of demonstrating it, and metaphors standing in
           for a measurable quantity. Replace with the concrete thing.
  SUSPECT  constructions that are sometimes legitimate. Each hit needs a human decision, and the
           default is to cut. One exception is written into the voice guide: interpolated
           relative clauses, cleft sentences, sparing semicolons and sentence-adverb pivots are
           explicitly in-voice (frias_voice.md rule 7) even though checkers flag them. A "which
           is" that identifies a thing is one of those. A "which is" that explains why a result
           matters is a redemption clause and comes out.

Run: python scripts/check_voice.py [paths...]   (defaults to the paper-facing set)
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Every surface that reaches a reader. Frozen results, pre-registration text above a tag line,
# quoted material and commit history are excluded: those are the record, and editing them to
# read better would corrupt it.
DEFAULT = [
    # TRIMMED 2026-08-27 for the public release: in-repo surfaces only. Internal working
    # documents left the tip (docs/history_attestation.md records the curation), and the
    # private outreach surfaces are scanned from the private side by passing them as args.
    # The 2026-08-13 lesson stands: a linter is only as good as its file list.
    "docs/paper_b_draft_v3.md", "docs/arxiv/paper_b.tex", "README.md",
    "docs/reference_verification.md", "docs/bar_ledger.md",
    "docs/CORRECTIONS_2026-08-12.md", "docs/SCOPE_FREEZE_2026-08-12.md",
    "docs/annotation_protocol_errata.md", "docs/annotation_protocol_bis.md",
    "docs/history_attestation.md",
]

# Deliberately NOT scanned, and the reason has to be a reason rather than an oversight:
#   PREREGISTRATION_*.md               frozen above the tag line; amendments are append-only.
#   results/**                         frozen results. The JSON wins; prose never edits it.
#   Superseded drafts left the public tip on 2026-08-27; they live in the author's archive.
NOT_SCANNED = []

BANNED = [
    # asserting significance instead of demonstrating it
    r"load[- ]bearing", r"doing (a lot of |the )?(quiet |real |heavy )(work|lifting)",
    r"that'?s not nothing", r"and that matters\b", r"earns? its keep",
    r"the thing to hold onto", r"that'?s the (whole|entire) (argument|point)",
    r"would cost (us |me )?precision", r"costs? (us |me )?precision",
    # signalling candour instead of being candid
    r"and honestly", r"\bhonestly\b", r"i (need|want|have) to be honest",
    r"(one|a|the) (honest|real|genuine) (caveat|limitation|question|answer|version|reading|take)",
    r"stated honestly", r"\bgenuinely\b", r"in all honesty", r"most honest thing anyone",
    # metaphor standing in for a measurable quantity
    r"blast radius", r"\bfootgun\b", r"belt[- ]and[- ](suspenders|braces)",
    r"wearing (a|the) costume", r"in a trench ?coat", r"wearing the same hat",
    r"cosplaying as", r"the shape of the problem", r"\bleverag(e|es|ed|ing)\b",
    # operator rulings 2026-08-12: each has a precise replacement, so there is no judgment call
    r"hand[- ]?wav(e|es|ed|ing|y)",        # -> dismiss, dismissed without argument
    r"smoking gun",                         # -> root cause, or decisive finding
    r"cuts both ways",                      # -> bidirectional, or state both directions
    r"\bfull stop\b",                       # -> the period already does this
    r"\bthat tracks\b",                     # -> filler
    r"sanity check",                        # -> test, or review
    r"surface area",                        # overused; name the thing exposed
    # performed deference and self-flagellation
    r"you'?re absolutely right", r"you'?re right to push back", r"and that'?s on me",
    r"\bgood catch\b", r"sharp catch", r"\bfair point\b",
    r"i should have (checked|asked|verified) before",
    # the thread's other consensus tics
    r"sit with (it|this|that)", r"stay with (it|this|that)", r"let'?s pause right here",
    r"say the word", r"now i have the (complete|full) picture",
    r"(get some rest|you'?ve done enough|seriously,? go (to bed|home))",
    r"worth flagging", r"so no one is surprised later", r"\bone wrinkle\b",
    r"pull on (this|that) thread", r"let me ground myself", r"know this cold",
    r"that (pain|challenge|frustration) is real",
]

# FICTIONALISING. The operator's sharpest finding, and epistemic rather than stylistic: I use
# these words for things that have not happened yet, in the same register as measured results.
# A result does not "land"; it is either computed or it is not. An agent is not "in flight"; a
# process is running or it is not. Every hit here is a place where anticipated state was narrated
# as real, which in this lab is the failure the whole method exists to prevent.
FICTIONALISING = [
    r"\bland(s|ed|ing)?\b", r"\bin[- ]flight\b", r"\bquiet(ly)?\b", r"\bsharper?\b",
    r"\bcoming (together|along)\b", r"\bshaping up\b", r"\bon track\b",
]

# Deliberately NOT banned, against the thread's advice, because they are real words or terms of
# art and banning them would cost precision: canonical, defense-in-depth, sanity check, pipeline,
# register, stack, scope, hand-waving, smoking gun, cuts both ways, full stop, that tracks,
# surface area, legible, authorship, contract. Several sit in the author's own lexicon, and
# "legible" is his. A crowd-sourced tell list has its own false-positive rate.
SUSPECT = [
    # operator ruling: real words, rationed. Precise where needed, absent where decorative.
    (r"\bcanonical\b", "expensive spice: only where authority is the point"),
    (r"\bscope\b", "only a registered scope; never decorative"),
    (r"\bdefen[cs]e[- ]in[- ]depth\b", "security only, and only for a genuinely layered system"),
    (r"\bseam\b", "software seams only; otherwise use a thesaurus"),
    (r"\bspine\b", "software or anatomy only; otherwise use a thesaurus"),
    (r"\bhinge\b", "name the concrete thing it turns on"),
    (r"\bshape[sd]?\b", "heavily overused; name what changed"),
    (r"\brobust\b", "only in 'robust to X' with X named"),
    (r"\bpipeline\b|\bregister\b|\bstack\b", "fine for the real thing, vague otherwise"),
    (r"\bpush(ing|ed)? back\b|\bpushback\b", "fine when the disagreement is literal"),
    (r"\blegible\b|\blegibility\b", "the author's word, not mine; leave his usages alone"),
    # structural
    (r"not (just|merely|simply|only) .{0,45}\bbut\b", "reversal reflex; say the second half"),
    (r"\bwhich is (why|the)\b", "editorial connective; often a redemption clause"),
    (r"\bworth (noting|stating|saying)\b", "if it is worth it, say it without the frame"),
    (r"\bis informative\b|\binstructive\b", "redemption clause on a failure"),
    (r"\bexactly (the|what|why|how)\b", "intensifier doing work a number should do"),
    (r"\bthe real \w+ is\b", "asserts significance; state the thing"),
]


# A quoted title is the record, not our prose. Flagging it would push an editor toward
# altering a citation, which is the one edit that corrupts rather than improves.
EXEMPT = [
    re.compile(r"Learning robust negation text", re.I),   # title may wrap a line
    re.compile(r"negation-robust", re.I),   # Truong et al.'s own term of art
]


# A phrase inside `backticks` is being NAMED, not used. Without this, a document that discusses
# the banned list cannot exist: the corrections ledger tripped its own linter three times for
# quoting the very phrases it reports removing, and so would this file's docstring. The rule is
# narrow on purpose — code spans only, never ordinary quotation marks, because "scare quotes" are
# how a tell gets smuggled back in while looking cited.
CODESPAN = re.compile(r"`[^`]+`")


def exempted(line, span):
    if any(m.start() <= span[0] and m.end() >= span[1] for m in CODESPAN.finditer(line)):
        return True
    return any(m.start() <= span[0] and m.end() >= span[1] for pat in EXEMPT
               for m in pat.finditer(line))


def scan(paths):
    banned = fiction = suspect = 0
    for p in paths:
        f = ROOT / p
        if not f.exists():
            print(f"  missing: {p}")
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for pat in FICTIONALISING:
                for m in re.finditer(pat, line, re.I):
                    if exempted(line, m.span()):
                        continue
                    print(f"  FICTION  {p}:{i}  {m.group(0)!r}  "
                          f"(anticipated state narrated as real; say what is computed)")
                    fiction += 1
            for pat in BANNED:
                for m in re.finditer(pat, line, re.I):
                    if exempted(line, m.span()):
                        continue
                    print(f"  BANNED   {p}:{i}  {m.group(0)!r}")
                    banned += 1
            for pat, why in SUSPECT:
                for m in re.finditer(pat, line, re.I):
                    if exempted(line, m.span()):
                        continue
                    print(f"  SUSPECT  {p}:{i}  {m.group(0)!r}  ({why})")
                    suspect += 1
    return banned, fiction, suspect


if __name__ == "__main__":
    paths = [a for a in sys.argv[1:] if not a.startswith("-")] or DEFAULT
    print(f"voice check over {len(paths)} file(s)")
    b, fi, s = scan(paths)
    print()
    print(f"{b} BANNED, {fi} FICTIONALISING, {s} SUSPECT")
    if b or fi:
        print("BANNED and FICTIONALISING come out. Replace each with the concrete thing.")
        sys.exit(1)
    print("clean on banned and fictionalising.")
