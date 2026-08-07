# Annotation protocol — technical-sentence revision judgments (blind)

**This is the only document an annotator may see. Do not show annotators any other file in this
repository, any hypothesis, any model output, or any description of what is being tested.**

## Task

You will see 200 items. Each item shows two versions of a sentence from a technical document
(text_A and text_B), which differ. The presentation order of the two versions is randomized —
neither is marked as "before" or "after."

For each item, answer one question:

> **Do the two versions place different requirements or state different facts — that is, could a
> careful implementer or reader legitimately act differently depending on which version they read?**

Answer with exactly one of:
- `"different"` — the versions require or assert different things (any difference in obligation
  strength, quantity, condition, scope, polarity, or asserted fact counts, however small).
- `"same"` — the versions require and assert the same thing; the differences are wording,
  formatting, grammar, or style only.
- `"unjudgeable"` — the fragment is too incomplete or too technical to judge in isolation.

## Rules

1. Judge ONLY what the two texts say. Do not guess intent, history, or context beyond the words.
2. Word-level similarity is irrelevant. Two nearly identical sentences can differ in requirement;
   two very different sentences can require the same thing. Judge requirements, not wording.
3. In technical standards, capitalized MUST / SHOULD / MAY (and their negations) are formal
   obligation levels: a change between them IS a requirement change. A change between, e.g.,
   "must" and "MUST" with the same word is a formatting change.
4. Do not consult any tool, model, or search engine. Your judgment only.
5. Work item by item; do not revise earlier answers based on patterns you notice later.

## Output format

One JSON object: `{"judgments": [{"item": 0, "verdict": "different"}, ...]}` — all 200 items,
verdicts from the three values above, nothing else.
