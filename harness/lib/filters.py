"""Prereg-pinned filters for E1. The code-primary predicate is frozen by the prereg-e1
tag; changing it afterward is an amendment, never an edit (PREREGISTRATION_E1.md section 7).
"""
import re

CODE_LINE = re.compile(r"(::=|=/|^[\s|+\-=_*#0-9a-fA-Fx,.:;()\[\]{}<>/\\'\"]+$)")


def alpha_ratio(text: str) -> float:
    """Alphabetic characters over non-whitespace characters (1.0 for empty)."""
    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return 1.0
    return sum(c.isalpha() for c in non_ws) / len(non_ws)


def code_line_fraction(text: str) -> float:
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return 0.0
    return sum(bool(CODE_LINE.search(l)) for l in lines) / len(lines)


def is_code_primary(orig_text: str, correct_text: str) -> bool:
    """A pair is code-primary if EITHER text has alpha ratio < 0.70 over non-whitespace,
    or >= 50% of its non-empty lines match the ABNF/code indicator set."""
    for t in (orig_text, correct_text):
        if alpha_ratio(t) < 0.70 or code_line_fraction(t) >= 0.50:
            return True
    return False
