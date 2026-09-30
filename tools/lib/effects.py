"""Side-effect evidence per statement (facts only, no business meaning).

Each rule names what a statement touches outside the procedure: files, the
registry, COM objects, a database API, a process, the UI. SQL is reported as
the literal text of string constants that start with a SQL verb; nothing is
parsed or executed. ``db.method`` is a method-name candidate (``.Execute``,
``OpenRecordset`` …), not proof that the receiver is a database object.
"""

from __future__ import annotations

import re

from .file_statements import FILE_STATEMENT_PATTERNS, is_file_statement
from .show_style import parse_lifetime_calls_in_line, parse_show_calls_in_line
from .vbparse import code_mask

_HEAD = r"(?:^|\b(?:Then|Else)\s+)"
FILE_KINDS = tuple(FILE_STATEMENT_PATTERNS)
_FILE_EXTRA = (
    ("filecopy", re.compile(_HEAD + r"FileCopy\s", re.IGNORECASE)),
    ("mkdir", re.compile(_HEAD + r"MkDir\s", re.IGNORECASE)),
    ("rmdir", re.compile(_HEAD + r"RmDir\s", re.IGNORECASE)),
    ("chdir", re.compile(_HEAD + r"ChDir\s", re.IGNORECASE)),
    ("chdrive", re.compile(_HEAD + r"ChDrive\s", re.IGNORECASE)),
    ("setattr", re.compile(_HEAD + r"SetAttr\s", re.IGNORECASE)),
    ("lock", re.compile(_HEAD + r"(?:Lock|Unlock)\s", re.IGNORECASE)),
)
_REGISTRY_RE = re.compile(r"\b(SaveSetting|GetSetting|GetAllSettings|DeleteSetting)\b", re.IGNORECASE)
_CREATE_RE = re.compile(r'\b(CreateObject|GetObject)\s*\(\s*"([^"]*)"', re.IGNORECASE)
_CREATE_DYNAMIC_RE = re.compile(r"\b(CreateObject|GetObject)\s*\(", re.IGNORECASE)
_NEW_RE = re.compile(r"\bNew\s+([^\W\d]\w*\.[^\W\d]\w*)", re.IGNORECASE)
_DB_METHOD_RE = re.compile(
    r"\.(Execute|OpenRecordset|OpenDatabase|OpenConnection|BeginTrans|CommitTrans|RollbackTrans)\b",
    re.IGNORECASE,
)
_DB_ENGINE_RE = re.compile(r"\b(DBEngine|Workspaces)\b", re.IGNORECASE)
_SQL_RE = re.compile(
    r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|EXEC|EXECUTE|TRUNCATE|MERGE)\b",
    re.IGNORECASE,
)
_STRING_RE = re.compile(r'"((?:[^"]|"")*)"')
_SHELL_RE = re.compile(r"(?:\bShell\s*\(|" + _HEAD + r"Shell\s)", re.IGNORECASE)
_MSGBOX_RE = re.compile(r"\bMsgBox\b", re.IGNORECASE)
_POPUP_RE = re.compile(r"\bPopupMenu\s+([^\W\d][\w.]*)", re.IGNORECASE)
_END_RE = re.compile(r"^End\s*$", re.IGNORECASE)
_PRINTER_RE = re.compile(r"\bPrinter\.", re.IGNORECASE)
_SENDKEYS_RE = re.compile(r"\bSendKeys\b", re.IGNORECASE)


def _file_kind(masked: str) -> str | None:
    for kind in FILE_KINDS:
        if is_file_statement(masked, kind):
            return kind
    for kind, pattern in _FILE_EXTRA:
        if pattern.search(masked):
            return kind
    return None


def statement_effects(text: str, declares: dict[str, dict] | None = None) -> list[dict]:
    """Effects of one colon-split statement. ``declares``: lower name → Declare."""
    masked = code_mask(text)
    out: list[dict] = []
    fkind = _file_kind(masked)
    if fkind:
        out.append({"kind": f"file.{fkind}"})
    for m in _REGISTRY_RE.finditer(masked):
        out.append({"kind": "registry", "call": m.group(1)})
    literal_creates = list(_CREATE_RE.finditer(text))
    for m in literal_creates:
        out.append({"kind": "com.create", "call": m.group(1), "progid": m.group(2)})
    if not literal_creates:
        for m in _CREATE_DYNAMIC_RE.finditer(masked):
            out.append({"kind": "com.create", "call": m.group(1), "progid": None})
    for m in _NEW_RE.finditer(masked):
        out.append({"kind": "com.new", "class": m.group(1)})
    for m in _DB_METHOD_RE.finditer(masked):
        out.append({"kind": "db.method", "method": m.group(1)})
    if _DB_ENGINE_RE.search(masked):
        out.append({"kind": "db.engine"})
    for m in _STRING_RE.finditer(text):
        literal = m.group(1).replace('""', '"')
        if _SQL_RE.match(literal):
            out.append({"kind": "sql.literal", "sql": literal[:300]})
    if _SHELL_RE.search(masked):
        out.append({"kind": "process.shell"})
    if declares:
        for word in set(re.findall(r"[^\W\d]\w*", masked)):
            decl = declares.get(word.lower())
            if decl is not None:
                out.append({"kind": "api.call", "declare": decl["name"], "lib": decl.get("lib"),
                            "alias": decl.get("alias")})
    for call in parse_show_calls_in_line(text, 0):
        out.append({"kind": "ui.show", "target": call["target"], "arg": call["arg"]})
    for call in parse_lifetime_calls_in_line(text, 0):
        out.append({"kind": f"ui.{call['kind']}", "target": call["target"]})
    if _MSGBOX_RE.search(masked):
        out.append({"kind": "ui.msgbox"})
    for m in _POPUP_RE.finditer(masked):
        out.append({"kind": "ui.popupmenu", "menu": m.group(1)})
    if _PRINTER_RE.search(masked):
        out.append({"kind": "printer"})
    if _SENDKEYS_RE.search(masked):
        out.append({"kind": "sendkeys"})
    if _END_RE.match(masked.strip()):
        out.append({"kind": "app.end"})
    return out
