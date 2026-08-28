"""Shared VB6 lexing helpers (encoding-agnostic; operates on decoded text).

Design constraints for this kit:
- Physical line numbers are canonical output. Folding ``_`` continuations must
  never shift reported line numbers, so logical lines carry their physical span.
- Colon-split statements inherit that same physical span (three statements on
  one physical line all report the same phys_start).
- Facts only. No call-graph guessing. No reachability.

Known limitations (not implemented):
- Conditional compilation ``#If`` / ``#Else`` / ``#End If`` outside strings
- Old numeric line numbers (``10 Print``)
- Rare DATA-style statements whose payload contains ``:``
"""

from __future__ import annotations

import re
from typing import Literal, NamedTuple

_REM_HEAD_RE = re.compile(r"^Rem\b", re.IGNORECASE)
_LABEL_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

StatementKind = Literal["stmt", "label"]


class LogicalLine(NamedTuple):
    """One VB6 statement after joining ``_`` line continuations.

    phys_start / phys_end are 1-based physical line numbers (inclusive). For a
    single-line statement, phys_start == phys_end. ``text`` is the joined,
    left/right-stripped statement with continuation markers removed.
    """

    phys_start: int
    phys_end: int
    text: str


class Statement(NamedTuple):
    """One colon-split unit after ``_`` folding.

    ``kind`` is ``stmt`` (executable / declarative text) or ``label`` (a leading
    ``Foo:`` line label). Callers that classify verbs (Kill, Open, …) must skip
    ``label`` so a lone ``Kill:`` is not treated as a Kill statement.

    phys_start / phys_end stay the physical span of the logical line. Splitting
    ``a = 1: b = 2: c = 3`` yields three items with the same phys_start.
    """

    phys_start: int
    phys_end: int
    text: str
    kind: StatementKind


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


def _strip_line_comment(text: str) -> str:
    """Drop ``'`` comments outside strings. ``\"\"`` is an escaped quote."""
    in_str = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            if in_str and i + 1 < n and text[i + 1] == '"':
                i += 2
                continue
            in_str = not in_str
            i += 1
            continue
        if ch == "'" and not in_str:
            return text[:i].rstrip()
        i += 1
    return text.rstrip()


def _split_on_unquoted_colons(text: str) -> list[str]:
    """Split on ``:`` that are not inside double-quoted strings (VB ``\"\"``)."""
    parts: list[str] = []
    buf: list[str] = []
    in_str = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == '"':
            buf.append(ch)
            if in_str and i + 1 < n and text[i + 1] == '"':
                buf.append('"')
                i += 2
                continue
            in_str = not in_str
            i += 1
            continue
        if ch == ":" and not in_str:
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf).strip())
    return parts


def _parts_with_kind(logical_text: str) -> list[tuple[StatementKind, str]]:
    """Comment-strip, drop Rem, split colons, mark a leading line label."""
    code = _strip_line_comment(logical_text).strip()
    if not code:
        return []
    if _REM_HEAD_RE.match(code):
        return []
    parts = _split_on_unquoted_colons(code)
    # ``Foo:`` → ["Foo", ""]; bare ``Foo`` (Sub call) → ["Foo"] and is a stmt.
    leading_label = len(parts) > 1
    out: list[tuple[StatementKind, str]] = []
    for part in parts:
        if not part:
            continue
        if _REM_HEAD_RE.match(part):
            break
        if leading_label and not out and _LABEL_IDENT_RE.match(part):
            out.append(("label", part))
            continue
        out.append(("stmt", part))
    return out


def split_colon_statements(logical_text: str) -> list[str]:
    """Split one already-folded logical line into statement texts.

    Line comments (``'``) and ``Rem`` (rest of the logical line) are dropped.
    A leading line label (``Foo:`` or ``Foo: x = 1``) is omitted here; use
    ``iter_statements`` when callers must distinguish ``kind="label"``.
    ``:`` inside double-quoted strings (including VB ``\"\"`` escapes) does
    not split.
    """
    return [text for kind, text in _parts_with_kind(logical_text) if kind == "stmt"]


def iter_statements(lines: list[str]) -> list[Statement]:
    """Fold ``_`` continuations, then colon-split each logical line.

    Each item is one statement or one line label. Physical span is that of the
    logical line (not a new line number per colon piece).
    """
    out: list[Statement] = []
    for logical in iter_logical_lines(lines):
        for kind, text in _parts_with_kind(logical.text):
            out.append(Statement(logical.phys_start, logical.phys_end, text, kind))
    return out
