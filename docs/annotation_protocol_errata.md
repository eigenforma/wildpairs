# Annotation protocol — technical-document correction judgments (blind)

**This is the only document an annotator may see. Do not show annotators any other file in this
repository, any hypothesis, any model output, or any description of what is being tested.**

## Task

You will see 300 items. Each item shows two versions of a short span of text from a technical
document (text_A and text_B), which differ. The presentation order of the two versions is
randomized — neither is marked as "before" or "after."

For each item, answer one question:

> **Do the two versions assert or require different things, within the text shown — that is,
> could a careful reader or implementer legitimately come away with a different understanding
> or act differently depending on which version they read?**

Answer with exactly one of:
- `"different"` — the versions assert or require different things (any difference in fact,
  obligation strength, quantity, condition, scope, polarity, identifier, or reference target
  counts, however small).
- `"same"` — the versions assert and require the same thing; the differences are wording,
  spelling, punctuation, formatting, grammar, or style only.
- `"unjudgeable"` — the span is too incomplete or too technical to judge in isolation.

## Rules

1. Judge ONLY what the two texts say. Do not guess intent, history, or context beyond the words.
2. Word-level similarity is irrelevant. Two nearly identical spans can differ in what they assert;
   two very different spans can assert the same thing. Judge content, not wording.
3. In technical standards, capitalized MUST / SHOULD / MAY (and their negations) are formal
   obligation levels: a change between them IS a requirement change. A change between, e.g.,
   "must" and "MUST" with the same word is a formatting change.
4. A changed number, identifier, field name, or cross-reference target is a content change
   unless it is transparently the same value written differently.
5. Do not consult any tool, model, or search engine beyond your own judgment.
6. Work item by item; do not revise earlier answers based on patterns you notice later.

## Output format

One JSON object: `{"judgments": [{"item": 0, "verdict": "different"}, ...]}` — all 300 items,
verdicts from the three values above, nothing else.
