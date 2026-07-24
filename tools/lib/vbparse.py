"""Shared VB6 lexing helpers (encoding-agnostic; operates on decoded text).

Design constraints for this kit:
- Physical line numbers are canonical output. Folding ``_`` continuations must
  never shift reported line numbers, so logical lines carry their physical span.
- Facts only. No call-graph guessing.
"""

from __future__ import annotations

from typing import NamedTuple


class LogicalLine(NamedTuple):
    """One VB6 statement after joining ``_`` line continuations.

    phys_start / phys_end are 1-based physical line numbers (inclusive). For a
    single-line statement, phys_start == phys_end. ``text`` is the joined,
    left/right-stripped statement with continuation markers removed.
    """

    phys_start: int
    phys_end: int
    text: str


def iter_logical_lines(lines: list[str]) -> list[LogicalLine]:
    """Fold trailing ``_`` continuations into logical lines.

    A physical line is a continuation opener when, after right-stripping, it
    ends with a space (or tab) followed by ``_``. VB6 requires whitespace before
    the underscore, which distinguishes it from an identifier ending in ``_``.
    """
    out: list[LogicalLine] = []
    buf: list[str] = []
    start: int | None = None

    for idx, raw in enumerate(lines, start=1):
        stripped = raw.rstrip()
        is_cont = len(stripped) >= 2 and stripped[-1] == "_" and stripped[-2] in " \t"
        if start is None:
            start = idx
        if is_cont:
            buf.append(stripped[:-1].rstrip())
            continue
        buf.append(stripped)
        text = " ".join(part.strip() for part in buf if part.strip() != "") if len(buf) > 1 else buf[0].strip()
        out.append(LogicalLine(start, idx, text))
        buf = []
        start = None

    if buf:  # trailing dangling continuation (malformed source)
        text = " ".join(part.strip() for part in buf if part.strip() != "")
        out.append(LogicalLine(start or len(lines), len(lines), text))
    return out
