"""Side-effect evidence per statement (facts only, no business meaning).

Each rule names what a statement touches outside the procedure: files, the
registry, COM objects, a database API, a process, the UI. SQL is reported as
the literal text of string constants that start with a SQL verb; nothing is
parsed or executed. ``db.method`` is a method-name candidate (``.Execute``,
``OpenRecordset`` …), not proof that the receiver is a database object.
"""

from __future__ import annotations

import re

from .declarators import split_top_level
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
_CREATE_CALL_RE = re.compile(r"\b(CreateObject|GetObject)\s*\(", re.IGNORECASE)
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


def _call_arguments(text: str, open_paren: int) -> list[str]:
    """Arguments inside the parentheses that start at ``open_paren``."""
    if open_paren >= len(text) or text[open_paren] != "(":
        return []
    depth = 0
    in_str = False
    i = open_paren + 1
    start = i
    while i < len(text):
        ch = text[i]
        if ch == '"':
            if in_str and i + 1 < len(text) and text[i + 1] == '"':
                i += 2
                continue
            in_str = not in_str
        elif not in_str and ch == "(":
            depth += 1
        elif not in_str and ch == ")":
            if depth == 0:
                return [part for part in split_top_level(text[start:i]) if part]
            depth -= 1
        i += 1
    return [part for part in split_top_level(text[start:]) if part]


def _vb_string(arg: str) -> str | None:
    text = arg.strip()
    if len(text) < 2 or not text.startswith('"'):
        return None
    body: list[str] = []
    i = 1
    while i < len(text):
        if text[i] == '"':
            if i + 1 < len(text) and text[i + 1] == '"':
                body.append('"')
                i += 2
                continue
            return "".join(body)
        body.append(text[i])
        i += 1
    return None


def _object_calls(text: str, masked: str) -> list[dict]:
    """``CreateObject`` / ``GetObject`` calls in code, not inside strings.

    ``GetObject``'s first argument is a pathname and the second is a class.
    ``CreateObject``'s first argument is a ProgID.
    """
    out: list[dict] = []
    for match in _CREATE_CALL_RE.finditer(masked):
        args = _call_arguments(text, match.end() - 1)
        call = match.group(1)
        if call.lower() == "getobject":
            out.append({
                "kind": "com.get",
                "call": call,
                "pathname": _vb_string(args[0]) if args else None,
                "class": _vb_string(args[1]) if len(args) > 1 else None,
            })
        else:
            out.append({
                "kind": "com.create",
                "call": call,
                "progid": _vb_string(args[0]) if args else None,
            })
    return out


def statement_effects(text: str, declares: dict[str, dict] | None = None) -> list[dict]:
    """Effects of one colon-split statement. ``declares``: lower name → Declare."""
    masked = code_mask(text)
    out: list[dict] = []
    fkind = _file_kind(masked)
    if fkind:
        out.append({"kind": f"file.{fkind}"})
    for m in _REGISTRY_RE.finditer(masked):
        out.append({"kind": "registry", "call": m.group(1)})
    out.extend(_object_calls(text, masked))
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
                effect = {"kind": "api.call", "declare": decl["name"], "lib": decl.get("lib"),
                          "alias": decl.get("alias")}
                if decl.get("id"):
                    effect["symbol"] = decl["id"]
                out.append(effect)
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
