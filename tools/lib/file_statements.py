"""VB6 file statements on one ``code_mask``-ed statement (strings/comments blanked).

Shared by io-catalog, deep-read GoTo-skip hints and later catalogs so the
tools cannot disagree about what counts as ``Open`` or ``Get``. VB6 makes the
``#`` before a file number optional in ``Open … As [#]n`` and ``Get/Put [#]n,``,
and ``Close`` takes an optional list; the ``#``-less forms are anchored to the
start of the statement (or after ``Then`` / ``Else``) so ``rs.Open`` /
``rs.Close`` method calls and ``Property Get`` headers do not match.
"""

from __future__ import annotations

import re

_HEAD = r"(?:^|\b(?:Then|Else)\s+)"
# File number without '#': literal, variable, member or array element.
_CHANNEL = r"(?:\d+|[^\W\d][\w.]*(?:\([^)]*\))?)"

FILE_STATEMENT_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "open": (
        re.compile(r"\bOpen\b.*\bAs\s*#\s*\w+", re.IGNORECASE),
        re.compile(
            _HEAD + r"Open\s+.+?\s+As\s+" + _CHANNEL + r"(?:\s+Len\s*=.*)?\s*$",
            re.IGNORECASE,
        ),
    ),
    "line_input": (re.compile(r"\bLine\s+Input\s+#", re.IGNORECASE),),
    "input": (re.compile(r"\bInput\s+#", re.IGNORECASE),),
    "print": (re.compile(r"\bPrint\s+#", re.IGNORECASE),),
    "write": (re.compile(r"\bWrite\s+#", re.IGNORECASE),),
    "get": (
        re.compile(r"\bGet\s+#", re.IGNORECASE),
        re.compile(_HEAD + r"Get\s+" + _CHANNEL + r"\s*,", re.IGNORECASE),
    ),
    "put": (
        re.compile(r"\bPut\s+#", re.IGNORECASE),
        re.compile(_HEAD + r"Put\s+" + _CHANNEL + r"\s*,", re.IGNORECASE),
    ),
    "close": (re.compile(_HEAD + r"Close\b(?!\s*=)", re.IGNORECASE),),
    "kill": (re.compile(r"\bKill\b", re.IGNORECASE),),
    # Name <old> As <new>. Not ``Name =`` (property) or ``Name(``.
    "name": (re.compile(r"\bName\s+[^=(].*\sAs\s", re.IGNORECASE),),
}


def is_file_statement(masked: str, kind: str) -> bool:
    return any(p.search(masked) for p in FILE_STATEMENT_PATTERNS[kind])


def file_statement_kind(masked: str, kinds: tuple[str, ...]) -> str | None:
    """First kind in ``kinds`` whose pattern matches, else None."""
    for kind in kinds:
        if is_file_statement(masked, kind):
            return kind
    return None
