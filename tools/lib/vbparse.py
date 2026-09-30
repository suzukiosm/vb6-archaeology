"""Shared VB6 lexing helpers (encoding-agnostic; operates on decoded text).

Design constraints for this kit:
- Physical line numbers are canonical output. Folding ``_`` continuations must
  never shift reported line numbers, so logical lines carry their physical span.
- Colon-split statements inherit that same physical span (three statements on
  one physical line all report the same phys_start).
- Facts only. No call-graph guessing. No reachability.

Lexical rules follow [MS-VBAL] (the VBA language spec VB6 shares):
- ``comment-body`` may contain line continuations, so a comment ending in
  `` _`` also comments out the next physical line. ``find_comment_continuations``
  reports the absorbed lines so a reader can see what VB6 ignores.
- A line may start with a numeric line label (``10 x = 1`` / ``10:``).
- Identifiers may contain non-ASCII letters (Japanese VB6 allows them).
- ``Else:`` and similar keywords are statements, not line labels.

Known limitations (not implemented):
- Conditional compilation is not evaluated: ``#If`` regions are reported
  (``conditional_regions``) and both branches stay in the statement stream.
- Rare DATA-style statements whose payload contains ``:``
"""

from __future__ import annotations

import re
from typing import Literal, NamedTuple

IDENT = r"[^\W\d]\w*"

_REM_HEAD_RE = re.compile(r"^Rem\b", re.IGNORECASE)
_LABEL_IDENT_RE = re.compile(rf"^(?:{IDENT}|\d+)$")
_LINE_NUMBER_RE = re.compile(r"^(\d+)\s+(\S.*)$")
_DATE_LITERAL_RE = re.compile(r"#[0-9][0-9\s/:.\-]*(?:AM|PM)?\s*#", re.IGNORECASE)
# Keywords that form a statement on their own; ``Else:`` is Else, not a label.
_NOT_LABELS = frozenset({
    "else", "end", "do", "loop", "next", "wend", "return", "resume", "stop", "then", "case",
})
_DIRECTIVE_RE = re.compile(
    r"^#\s*(If|ElseIf|Else|End\s*If|Const)\b\s*(.*?)\s*$", re.IGNORECASE
)
_DIRECTIVE_THEN_RE = re.compile(r"\s+Then$", re.IGNORECASE)


def _scan_line(text: str) -> tuple[str, int | None]:
    """Mask literals/comments on one line; also return where a comment starts."""
    out = list(text)
    i = 0
    while i < len(text):
        start = i
        if text[i] == "'" or (
            text[i:i + 3].casefold() == 'rem'
            and re.match(r'Rem\b', text[i:], re.IGNORECASE)
            and re.search(r'(?:^|:|\bThen|\bElse)\s*$', ''.join(out[:i]), re.IGNORECASE)
        ):
            out[i:] = ' ' * (len(text) - i)
            return ''.join(out), i
        if text[i] == '"':
            i += 1
            while i < len(text):
                if text[i] == '"':
                    i += 1
                    if i < len(text) and text[i] == '"':
                        i += 1
                        continue
                    break
                i += 1
            out[start:i] = ' ' * (i - start)
            continue
        date = _DATE_LITERAL_RE.match(text, i) if text[i] == '#' else None
        if date:
            i = date.end()
            out[start:i] = ' ' * (i - start)
            continue
        i += 1
    return ''.join(out), None


def code_mask(text: str) -> str:
    """Blank literals/comments without shifting offsets; keep code tokens.

    Operates on one physical/logical line. File channels (#1) and type suffixes
    are not date literals. This is lexical filtering, not name resolution.
    """
    return _scan_line(text)[0]

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
    ``Foo:`` or numeric line label). Callers that classify verbs (Kill, Open, …)
    must skip ``label`` so a lone ``Kill:`` is not treated as a Kill statement.

    phys_start / phys_end stay the physical span of the logical line. Splitting
    ``a = 1: b = 2: c = 3`` yields three items with the same phys_start.
    """

    phys_start: int
    phys_end: int
    text: str
    kind: StatementKind


def _is_continuation(stripped: str) -> bool:
    # Whitespace then '_' at line end. A string cannot span lines, so the '_'
    # is either code or inside a comment, and MS-VBAL continues both.
    return len(stripped) >= 2 and stripped[-1] == "_" and stripped[-2] in " \t"


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
        if start is None:
            start = idx
        if _is_continuation(stripped):
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


def find_comment_continuations(lines: list[str]) -> list[dict]:
    """Physical lines VB6 treats as comment text because a comment ended in `` _``.

    Each item: ``line`` (where the comment starts) and ``absorbed`` (the
    following physical lines that belong to it).
    """
    found: list[dict] = []
    comment_line: int | None = None
    absorbed: list[int] = []
    for idx, raw in enumerate(lines, start=1):
        stripped = raw.rstrip()
        if comment_line is not None:
            absorbed.append(idx)
        elif _is_continuation(stripped) and _scan_line(stripped)[1] is not None:
            comment_line = idx
        if comment_line is not None and not _is_continuation(stripped):
            if absorbed:
                found.append({"line": comment_line, "absorbed": absorbed})
            comment_line, absorbed = None, []
    if comment_line is not None and absorbed:
        found.append({"line": comment_line, "absorbed": absorbed})
    return found


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
    mask = code_mask(text)
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
        if ch == ":" and mask[i] == ':' and not text.startswith(':=', i):
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
        if not out and (leading_label or part.isdigit()) and _LABEL_IDENT_RE.match(part) \
                and part.casefold() not in _NOT_LABELS:
            out.append(("label", part))
            continue
        number = _LINE_NUMBER_RE.match(part) if not out else None
        if number:
            out.append(("label", number.group(1)))
            part = number.group(2)
            if _REM_HEAD_RE.match(part):
                break
        out.append(("stmt", part))
    return out


def split_colon_statements(logical_text: str) -> list[str]:
    """Split one already-folded logical line into statement texts.

    Line comments (``'``) and ``Rem`` (rest of the logical line) are dropped.
    A leading line label (``Foo:`` / ``10:`` / ``10 x = 1``) is omitted here; use
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


def conditional_regions(statements: list[Statement]) -> list[dict]:
    """``#If`` / ``#ElseIf`` / ``#Else`` branches as physical line spans.

    Each region: ``line`` (directive), ``directive`` (``#If`` …), ``expr``
    (condition text; empty for ``#Else``), ``depth`` (1 = outermost) and
    ``end`` (line of the next sibling directive or ``#End If``). Conditions are
    not evaluated; an unterminated region ends after the last statement.
    ``#Const`` lines are returned with ``directive`` ``#Const`` and depth 0.
    """
    regions: list[dict] = []
    stack: list[dict] = []
    past_end = (statements[-1].phys_end + 1) if statements else 1
    for stmt in statements:
        if stmt.kind != "stmt":
            continue
        m = _DIRECTIVE_RE.match(stmt.text)
        if not m:
            continue
        word = re.sub(r"\s+", "", m.group(1)).casefold()
        expr = _DIRECTIVE_THEN_RE.sub("", m.group(2)).strip()
        if word == "const":
            regions.append({"line": stmt.phys_start, "directive": "#Const",
                            "expr": expr, "depth": 0, "end": stmt.phys_start})
            continue
        if word in ("elseif", "else", "endif") and stack:
            stack.pop()["end"] = stmt.phys_start
        if word in ("if", "elseif", "else"):
            label = {"if": "#If", "elseif": "#ElseIf", "else": "#Else"}[word]
            region = {"line": stmt.phys_start, "directive": label, "expr": expr,
                      "depth": len(stack) + 1, "end": past_end}
            regions.append(region)
            stack.append(region)
    return regions


def innermost_region(regions: list[dict], line: int) -> dict | None:
    """The deepest ``#If`` branch strictly between its directive and ``end``."""
    best: dict | None = None
    for region in regions:
        if region["directive"] == "#Const":
            continue
        if region["line"] < line < region["end"] and (
            best is None or region["depth"] > best["depth"]
        ):
            best = region
    return best
