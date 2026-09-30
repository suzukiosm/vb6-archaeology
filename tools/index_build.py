#!/usr/bin/env python3
"""Build the AI index of one extract: manifest + symbols / occurrences / effects / chunks.

Input is the facts inventory (``python -m tools inventory``) and the extract it
names. Output goes to ``<index_dir>/<stem>/`` (default ``working/index``):

- ``manifest.json``   schema version, provenance, per-file SHA-256, counts
- ``symbols.jsonl``   one record per file / procedure / Declare / Const / Enum
                      (+ members) / Type / Event / module variable / control
- ``occurrences.jsonl`` lexical uses of known names with *candidate* symbols
                      picked by VB6 scope rules (``basis``); not a call graph
- ``effects.jsonl``   file / registry / COM / DB / SQL literal / process / API /
                      UI statements (facts only; no business meaning)
- ``chunks.jsonl``    per procedure (plus declarations and designer) code with
                      physical line numbers, a context header, VB6 notes,
                      effects, resolved references and a token estimate

A parameter, or a ``Dim`` / ``Static`` / ``Const`` inside the procedure, hides an
outer name: that use is ``resolution=local`` and is not a unique binding to the
outer symbol. ``index`` refuses to run when the extract no longer matches the
hashes ``inventory`` stored (``input_hashes``).

    python -m tools index
    python -m tools index --inventory working/reports/mini_vbp_inventory.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from bisect import bisect_right
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from lib.config import VB6DecodeError, decode_vb6_report, index_root, load_config, reports_root  # noqa: E402
from lib.console import enable_utf8_stdio  # noqa: E402
from lib.declarators import parse_var_declarators, split_top_level  # noqa: E402
from lib.designer import parse_designer  # noqa: E402
from lib.effects import statement_effects  # noqa: E402
from lib.vbparse import IDENT, code_mask, iter_statements, source_span  # noqa: E402

SCHEMA_VERSION = 1
SCHEMA_ID = "vb6-archaeology/index"
STUB_TYPES = frozenset({"relateddoc", "resfile32"})
MODULE_TYPES = frozenset({"module"})
_TOKEN_RE = re.compile(IDENT)
_VB_NAME_RE = re.compile(r'^Attribute\s+VB_Name\b', re.IGNORECASE)
_DEFINITION_RE = re.compile(
    r"^(?:(?:Public|Private|Friend|Global|Static)\s+)*(?:Declare|Sub|Function|Property|Event|Enum|Type)\b",
    re.IGNORECASE,
)
_PROC_LOCAL_RE = re.compile(
    r"^(Dim|Static|Const)\s+(?!Sub\b|Function\b|Property\b)(.+)$",
    re.IGNORECASE,
)
_PROC_HEADER_RE = re.compile(
    r"^(?:(?:Public|Private|Friend|Global|Static)\s+)*(?:Sub|Function|Property)\b",
    re.IGNORECASE,
)
_WITH_RE = re.compile(r"^With\s+(.+)$", re.IGNORECASE)
_END_WITH_RE = re.compile(r"^End\s+With\b", re.IGNORECASE)
_FILE_SURFACE_KEYS = (
    "implements", "with_events", "instancing", "vb_creatable", "vb_exposed",
    "vb_global_name_space", "vb_predeclared_id", "vb_user_mem_id", "class_header",
    "default_member", "enumerator_member",
)
_CONST_NAME_RE = re.compile(rf"^({IDENT})\b")


class StaleInventory(Exception):
    """The extract (or config) no longer matches the hashes stored by inventory."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


def format_stale(problems: list[str]) -> str:
    lines = [
        "inventory の入力と今のファイルが一致しない。"
        "inventory を作り直してから index を作り直す。",
        *(f"- {item}" for item in problems),
    ]
    return "\n".join(lines)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _extract_child(root: Path, rel: str) -> Path | None:
    if not rel or rel.startswith(("/", "\\")) or ".." in Path(rel).parts:
        return None
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


def snapshot_problems(record: dict, extract_dir: Path) -> list[str]:
    """Differences between stored input hashes and the files on disk.

    ``record`` is an inventory or an index manifest (both carry ``input_hashes``
    and ``vbp``). An empty result means the snapshot still matches.
    """
    recorded = record.get("input_hashes")
    if not isinstance(recorded, dict) or "files" not in recorded:
        return ["入力ファイルのハッシュが無い"]
    root = extract_dir.resolve()
    problems: list[str] = []
    vbp_rel = str(recorded.get("vbp_rel") or record.get("vbp") or "")
    vbp_hash = recorded.get("vbp_sha256")
    if vbp_rel and vbp_hash:
        vbp_path = _extract_child(root, vbp_rel)
        if vbp_path is None:
            problems.append(f"vbp のパスが抽出先の外: {vbp_rel}")
        elif not vbp_path.is_file():
            problems.append(f"vbp が無い: {vbp_rel}")
        elif _sha256_file(vbp_path) != vbp_hash:
            problems.append(f"vbp が inventory 作成後に変わった: {vbp_rel}")
    for item in recorded["files"]:
        rel = str(item.get("file") or "")
        digest = str(item.get("sha256") or "")
        path = _extract_child(root, rel)
        if path is None:
            problems.append(f"パスが抽出先の外: {rel}")
            continue
        if not path.is_file():
            problems.append(f"ファイルが無い: {rel}")
            continue
        if _sha256_file(path) != digest:
            problems.append(f"ソースが inventory 作成後に変わった: {rel}")
    cfg_hash = recorded.get("config_sha256")
    if cfg_hash:
        cfg_path = Path(load_config()["_config_path"])
        if cfg_path.is_file() and _sha256_file(cfg_path) != cfg_hash:
            problems.append("設定ファイルが inventory 作成後に変わった")
    return problems


def estimate_tokens(text: str) -> int:
    """Heuristic: ~4 ASCII characters per token, one token per other character."""
    ascii_chars = sum(1 for ch in text if ord(ch) < 128)
    return math.ceil(ascii_chars / 4) + (len(text) - ascii_chars)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def kind_key(kind: str) -> str:
    return kind.replace(" ", "")


class SymbolTable:
    """Symbols with stable ids and the lookups scope resolution needs."""

    def __init__(self) -> None:
        self.records: list[dict] = []
        self.ids: set[str] = set()
        self.by_name: dict[str, list[dict]] = {}
        self.by_file_name: dict[tuple[str, str], list[dict]] = {}
        self.file_by_vb_name: dict[str, str] = {}

    def add(self, record: dict, *, global_scope: bool) -> dict:
        base = record["id"]
        if base in self.ids:
            record["id"] = f"{base}@L{record.get('line') or (record.get('span') or [0])[0]}"
        self.ids.add(record["id"])
        record["_global"] = global_scope
        self.records.append(record)
        key = record["name"].casefold()
        self.by_name.setdefault(key, []).append(record)
        self.by_file_name.setdefault((record["file"].casefold(), key), []).append(record)
        return record

    def public_in_file(self, file: str, name: str) -> list[dict]:
        return [
            r for r in self.by_file_name.get((file.casefold(), name.casefold()), [])
            if r["kind"] == "Control" or str(r.get("visibility") or "Public") in ("Public", "Friend")
        ]


def _is_global(entry: dict, visibility: str, kind: str) -> bool:
    if kind in ("Enum", "EnumMember", "Type"):
        return visibility == "Public"
    return str(entry.get("type") or "") in MODULE_TYPES and visibility in ("Public", "Global")


def build_symbols(inventory: dict) -> SymbolTable:
    table = SymbolTable()
    for entry in inventory.get("files") or []:
        if str(entry.get("type") or "") in STUB_TYPES:
            continue
        file = entry["file"]
        vb_name = entry.get("vb_name") or Path(file).stem
        file_record = {"id": file, "kind": "File", "name": vb_name, "file": file,
                       "type": entry.get("type"), "lines": entry.get("total_lines")}
        if entry.get("form_kind"):
            file_record["form_kind"] = entry["form_kind"]
        if entry.get("options"):
            file_record["options"] = {k: v for k, v in entry["options"].items() if k != "deftypes"}
        surface = entry.get("surface") or {}
        for key in _FILE_SURFACE_KEYS:
            value = surface.get(key)
            if value not in (None, [], {}):
                file_record[key] = value
        if entry.get("resource_refs"):
            file_record["resource_refs"] = entry["resource_refs"]
        table.add(file_record, global_scope=True)
        table.file_by_vb_name[vb_name.casefold()] = file

        for proc in entry.get("procedures") or []:
            rec = {"id": f"{file}#{kind_key(proc['kind'])}:{proc['name']}", "kind": proc["kind"],
                   "name": proc["name"], "file": file, "visibility": proc.get("visibility"),
                   "span": [proc["line_start"], proc["line_end"]],
                   "params": proc.get("params_detail") or []}
            for key in ("return_type", "return_type_source", "attributes", "error_handling",
                        "conditional", "type_suffix"):
                if proc.get(key) is not None:
                    rec[key] = proc[key]
            if proc.get("static"):
                rec["static"] = True
            if proc.get("labels"):
                rec["labels"] = [lb["name"] for lb in proc["labels"]]
            if proc.get("role") == "event":
                rec["event"] = {"owner": proc.get("event_owner"), "event": proc.get("event_name"),
                                "binding": proc.get("event_binding")}
            table.add(rec, global_scope=_is_global(entry, str(proc.get("visibility")), proc["kind"]))
        for decl in entry.get("declares") or []:
            rec = {"id": f"{file}#Declare:{decl['name']}", "kind": "Declare", "name": decl["name"],
                   "file": file, "visibility": decl.get("visibility"), "line": decl["line"],
                   "lib": decl.get("lib"), "alias": decl.get("alias"),
                   "params": decl.get("params_detail") or []}
            if decl.get("return_type"):
                rec["return_type"] = decl["return_type"]
            table.add(rec, global_scope=_is_global(entry, str(decl.get("visibility")), "Declare"))
        for const in entry.get("consts") or []:
            table.add({"id": f"{file}#Const:{const['name']}", "kind": "Const", "name": const["name"],
                       "file": file, "visibility": const.get("visibility"), "line": const["line"],
                       "value": const.get("value")},
                      global_scope=_is_global(entry, str(const.get("visibility")), "Const"))
        for enum in entry.get("enums") or []:
            enum_id = f"{file}#Enum:{enum['name']}"
            vis = str(enum.get("visibility"))
            table.add({"id": enum_id, "kind": "Enum", "name": enum["name"], "file": file,
                       "visibility": vis, "line": enum["line"],
                       "members": [m["name"] for m in enum.get("members") or []]},
                      global_scope=_is_global(entry, vis, "Enum"))
            for member in enum.get("members") or []:
                rec = {"id": f"{enum_id}.{member['name']}", "kind": "EnumMember",
                       "name": member["name"], "file": file, "visibility": vis,
                       "line": member["line"], "enum": enum_id}
                if "value" in member:
                    rec["value"] = member["value"]
                table.add(rec, global_scope=_is_global(entry, vis, "EnumMember"))
        for typ in entry.get("types") or []:
            vis = str(typ.get("visibility"))
            table.add({"id": f"{file}#Type:{typ['name']}", "kind": "Type", "name": typ["name"],
                       "file": file, "visibility": vis, "line": typ["line"],
                       "fields": [{"name": f["name"], "as": f["as"]} for f in typ.get("fields") or []]},
                      global_scope=_is_global(entry, vis, "Type"))
        for event in entry.get("events") or []:
            table.add({"id": f"{file}#Event:{event['name']}", "kind": "Event", "name": event["name"],
                       "file": file, "visibility": event.get("visibility"), "line": event["line"],
                       "args": event.get("args")}, global_scope=False)
        for var in entry.get("variables") or []:
            rec = {"id": f"{file}#Variable:{var['name']}", "kind": "Variable", "name": var["name"],
                   "file": file, "visibility": var.get("visibility"), "line": var["line"],
                   "type": var.get("type"), "type_source": var.get("type_source")}
            for key in ("with_events", "new", "is_array"):
                if var.get(key):
                    rec[key] = True
            if var.get("type_candidates"):
                rec["type_candidates"] = var["type_candidates"]
            table.add(rec, global_scope=_is_global(entry, str(var.get("visibility")), "Variable"))
        bindings = {b["control"].casefold(): b for b in entry.get("data_bindings") or []}
        for ctrl in entry.get("controls") or []:
            suffix = f"({ctrl['index']})" if ctrl.get("index") is not None else ""
            rec = {"id": f"{file}#Control:{ctrl['name']}{suffix}", "kind": "Control",
                   "name": ctrl["name"], "file": file, "class": ctrl.get("class"),
                   "line": ctrl.get("line"), "parent": ctrl.get("parent")}
            if ctrl.get("index") is not None:
                rec["index"] = ctrl["index"]
            binding = bindings.get(ctrl["name"].casefold())
            if binding:
                rec["data_binding"] = {k: v for k, v in binding.items()
                                       if k not in ("control", "class", "line")}
            table.add(rec, global_scope=False)
    return table


def _definition_lines(table: SymbolTable) -> set[tuple[str, str, int]]:
    out: set[tuple[str, str, int]] = set()
    for rec in table.records:
        line = rec.get("line") or (rec.get("span") or [None])[0]
        if line:
            out.add((rec["file"].casefold(), rec["name"].casefold(), line))
    return out


def resolve(table: SymbolTable, file: str, name: str, qualifier: str | None,
            variable_types: dict[str, str]) -> tuple[list[dict], str]:
    """Candidates for one use of ``name`` and the rule that picked them."""
    key = name.casefold()
    if qualifier is not None:
        q = qualifier.casefold()
        if q == "me":
            return table.by_file_name.get((file.casefold(), key), []), "me"
        target = table.file_by_vb_name.get(q)
        if target is not None:
            return table.public_in_file(target, name), "qualified"
        typed = variable_types.get(q)
        target = table.file_by_vb_name.get(typed.casefold()) if typed else None
        if target is not None:
            return table.public_in_file(target, name), "typed_variable"
        return [], "unknown_qualifier"
    same = table.by_file_name.get((file.casefold(), key), [])
    if same:
        return same, "same_file"
    return [r for r in table.by_name.get(key, []) if r["_global"]], "global"


def _context(tokens: list[re.Match], idx: int, masked: str) -> tuple[str, str | None]:
    """(context, qualifier) for token ``idx`` of one statement."""
    tok = tokens[idx]
    before = masked[:tok.start()].rstrip()
    if before.endswith("."):
        head = before[:-1].rstrip()
        qual = re.search(rf"({IDENT})\s*(?:\([^()]*\))?$", head)
        return "member", (qual.group(1) if qual else "")
    after = masked[tok.end():].lstrip()
    first = idx == 0 or (idx == 1 and tokens[0].group(0).lower() in ("set", "let", "call"))
    if first and tokens[0].group(0).lower() == "call" and idx == 1:
        return "call", None
    if first and after.startswith("=") and not after.startswith("=="):
        return "assign", None
    if idx == 0:
        return "head", None
    return "expr", None


def _const_names(rest: str) -> list[str]:
    names: list[str] = []
    for part in split_top_level(rest):
        match = _CONST_NAME_RE.match(part)
        if match:
            names.append(match.group(1))
    return names


def _outer_symbols(table: SymbolTable, file: str, key: str) -> list[dict]:
    return [
        rec for rec in table.by_name.get(key, [])
        if rec["file"] == file or rec.get("_global")
    ]


def _remember_local(
    names: dict[str, dict[str, tuple[str, int]]],
    shadows: dict[str, list[str]],
    proc: dict,
    table: SymbolTable,
    spelling: str,
    line: int,
) -> None:
    key = spelling.casefold()
    bucket = names[proc["id"]]
    if key in bucket:
        return
    bucket[key] = (spelling, line)
    if _outer_symbols(table, proc["file"], key):
        shadows[proc["id"]].append(spelling)


def _procedure_locals(
    procs: list[dict], lines: list[str], table: SymbolTable,
) -> tuple[dict[str, dict[str, tuple[str, int]]], dict[str, list[str]]]:
    """Per procedure: casefold name → (spelling, declaration line), and names that hide an outer symbol."""
    names: dict[str, dict[str, tuple[str, int]]] = {}
    shadows: dict[str, list[str]] = {}
    for proc in procs:
        names[proc["id"]] = {}
        shadows[proc["id"]] = []
        for param in proc.get("params") or []:
            spelling = param.get("name")
            if spelling:
                _remember_local(names, shadows, proc, table, spelling, proc["span"][0])
    if procs:
        starts = [p["span"][0] for p in procs]

        def enclosing(line: int) -> dict | None:
            i = bisect_right(starts, line) - 1
            return procs[i] if i >= 0 and line <= procs[i]["span"][1] else None

        for stmt in iter_statements(lines):
            if stmt.kind != "stmt":
                continue
            match = _PROC_LOCAL_RE.match(code_mask(stmt.text).strip())
            if not match:
                continue
            owner = enclosing(stmt.phys_start)
            if owner is None:
                continue
            kind, rest = match.group(1), match.group(2)
            found = _const_names(rest) if kind.lower() == "const" else [
                item["name"] for item in parse_var_declarators(rest)
            ]
            for spelling in found:
                _remember_local(names, shadows, owner, table, spelling, stmt.phys_start)
    return names, shadows


def _is_local_declaration(masked: str) -> bool:
    return _PROC_LOCAL_RE.match(masked) is not None or _PROC_HEADER_RE.match(masked) is not None


def _visible_declares(table: SymbolTable, file: str) -> dict[str, dict]:
    """Declares this file can call: same-file first, else Public/Global elsewhere."""
    chosen: dict[str, dict] = {}
    for rec in table.records:
        if rec["kind"] != "Declare":
            continue
        same = rec["file"] == file
        if not same and str(rec.get("visibility") or "Public") not in ("Public", "Global"):
            continue
        key = rec["name"].casefold()
        prev = chosen.get(key)
        if prev is None or (same and prev["file"] != file):
            chosen[key] = rec
    return chosen


def _receiver_name(expr: str) -> str | None:
    match = re.match(rf"({IDENT})\b", expr.strip())
    return match.group(1) if match else None


def _narrow_properties(candidates: list[dict], context: str, masked: str) -> list[dict]:
    """Prefer Get for a read and Let/Set for an assignment when both exist."""
    prop = [item for item in candidates if str(item["kind"]).startswith("Property")]
    if len({item["kind"] for item in prop}) < 2:
        return candidates
    head = masked.strip().split(None, 1)[0].lower() if masked.strip() else ""
    if context == "assign":
        preferred = "Property Set" if head == "set" else "Property Let"
        fallback = "Property Set" if preferred == "Property Let" else "Property Let"
        picked = [item for item in prop if item["kind"] == preferred] \
            or [item for item in prop if item["kind"] == fallback]
    else:
        picked = [item for item in prop if item["kind"] == "Property Get"]
    other = [item for item in candidates if not str(item["kind"]).startswith("Property")]
    return other + picked if picked else candidates


def _remember(occurrences: list[dict], file_occ: list[dict], file_sha: str, record: dict) -> None:
    span = source_span(
        file=record["file"], sha256=file_sha, line=record["line"], end_line=record["end_line"],
        stmt=record["stmt"], col=record["col"], end_col=record["end_col"],
    )
    record = {**record, "source_span": span}
    occurrences.append(record)
    file_occ.append(record)


def _gap_reason(occ: dict) -> str:
    if occ.get("reason"):
        return occ["reason"]
    if occ.get("resolution") == "ambiguous":
        return "候補が複数あり、一つに決めない"
    if occ.get("resolution") == "local":
        return "引数またはローカルであり、外側の名前ではない"
    return str(occ.get("resolution") or "unresolved")


def build_index(inventory: dict, extract_dir: Path, *, strict_decode: bool = False) -> dict:
    problems = snapshot_problems(inventory, extract_dir)
    if problems:
        raise StaleInventory(problems)
    table = build_symbols(inventory)
    definitions = _definition_lines(table)
    occurrences: list[dict] = []
    effects: list[dict] = []
    chunks: list[dict] = []
    manifest_files: list[dict] = []

    for entry in inventory.get("files") or []:
        if str(entry.get("type") or "") in STUB_TYPES:
            continue
        file = entry["file"]
        raw = (extract_dir / file).read_bytes()
        file_sha = hashlib.sha256(raw).hexdigest()
        text, decoding = decode_vb6_report(raw, strict=strict_decode)
        lines = text.splitlines()
        manifest_files.append({"file": file, "vb_name": entry.get("vb_name"), "type": entry.get("type"),
                               "sha256": file_sha, "lines": len(lines),
                               "decode": decoding})
        declares = _visible_declares(table, file)
        procs = sorted(
            (r for r in table.records if r["file"] == file and "span" in r),
            key=lambda r: r["span"][0],
        )
        starts = [p["span"][0] for p in procs]
        variable_types = {
            r["name"].casefold(): str(r.get("type") or "")
            for r in table.records if r["file"] == file and r["kind"] == "Variable"
        }
        locals_by_proc, shadows = _procedure_locals(procs, lines, table)

        def enclosing(line: int) -> dict | None:
            i = bisect_right(starts, line) - 1
            return procs[i] if i >= 0 and line <= procs[i]["span"][1] else None

        in_code = not lines or not lines[0].startswith("VERSION")
        with_stack: list[str] = []
        current_owner: str | None = None
        stmt_no = 0
        file_occ: list[dict] = []
        file_effects: list[dict] = []
        for stmt in iter_statements(lines):
            if not in_code:
                in_code = bool(_VB_NAME_RE.match(stmt.text))
                continue
            if stmt.kind != "stmt" or stmt.text.lower().startswith("attribute "):
                continue
            owner = enclosing(stmt.phys_start)
            owner_id = owner["id"] if owner else None
            owner_locals = locals_by_proc.get(owner_id, {}) if owner_id else {}
            if owner_id != current_owner:
                with_stack = []
                current_owner = owner_id
            stmt_no += 1
            masked = code_mask(stmt.text)
            stripped_mask = masked.strip()
            with_head = _WITH_RE.match(stripped_mask)
            if with_head:
                with_stack.append(with_head.group(1).strip())
            elif _END_WITH_RE.match(stripped_mask) and with_stack:
                with_stack.pop()
            if not _DEFINITION_RE.match(masked):
                shown = stmt.text if len(stmt.text) <= 160 else stmt.text[:160]
                for effect in statement_effects(stmt.text, declares):
                    if effect.get("kind") == "api.call" and owner_locals \
                            and str(effect.get("declare") or "").casefold() in owner_locals:
                        continue
                    record = {**effect, "file": file, "line": stmt.phys_start,
                              "end_line": stmt.phys_end, "in": owner_id, "text": shown,
                              "stmt": stmt_no, "col": 1, "end_col": max(len(stmt.text), 1)}
                    record["source_span"] = source_span(
                        file=file, sha256=file_sha, line=stmt.phys_start, end_line=stmt.phys_end,
                        stmt=stmt_no, col=1, end_col=record["end_col"],
                    )
                    if len(stmt.text) > 160:
                        record["text_truncated"] = True
                        record["text_sha256"] = sha256_text(stmt.text)
                    effects.append(record)
                    file_effects.append(record)
            tokens = list(_TOKEN_RE.finditer(masked))
            for idx, tok in enumerate(tokens):
                name = tok.group(0)
                key = name.casefold()
                if key not in table.by_name:
                    continue
                if (file.casefold(), key, stmt.phys_start) in definitions:
                    continue
                context, qualifier = _context(tokens, idx, masked)
                member_assign = context == "member" and masked[tok.end():].lstrip().startswith("=") \
                    and not masked[tok.end():].lstrip().startswith("==")
                from_with = False
                if context == "member" and not qualifier:
                    if not with_stack:
                        hit = table.by_name.get(key) or []
                        if hit:
                            _remember(occurrences, file_occ, file_sha, {
                                "name": name, "file": file, "line": stmt.phys_start,
                                "end_line": stmt.phys_end, "col": tok.start() + 1, "end_col": tok.end(), "stmt": stmt_no,
                                "in": owner_id, "context": context,
                                "candidates": [item["id"] for item in hit],
                                "basis": "with", "resolution": "unresolved",
                                "reason": "ドットの前が空で、With の受け手が無い",
                            })
                        continue
                    qualifier = _receiver_name(with_stack[-1])
                    from_with = True
                    if not qualifier:
                        _remember(occurrences, file_occ, file_sha, {
                            "name": name, "file": file, "line": stmt.phys_start,
                            "end_line": stmt.phys_end, "col": tok.start() + 1, "end_col": tok.end(), "stmt": stmt_no,
                            "in": owner_id, "context": context,
                            "candidates": [f"{owner_id or file}#with:{name}"],
                            "basis": "with", "resolution": "unresolved",
                            "reason": "With の受け手を名前にできない",
                        })
                        continue
                if owner_locals and context == "member" and qualifier \
                        and qualifier.casefold() in owner_locals:
                    _remember(occurrences, file_occ, file_sha, {
                        "name": name, "file": file, "line": stmt.phys_start,
                        "end_line": stmt.phys_end, "col": tok.start() + 1, "end_col": tok.end(), "stmt": stmt_no,
                        "in": owner_id, "context": context, "candidates": [f"{owner_id}#local:{qualifier}"],
                        "basis": "local_qualifier", "resolution": "unresolved",
                        "qualifier": qualifier,
                        "reason": "修飾子は引数またはローカルなので、外側の型には結び付けない",
                    })
                    continue
                if owner_locals and key in owner_locals and context != "member":
                    _spelling, def_line = owner_locals[key]
                    if stmt.phys_start == def_line and _is_local_declaration(masked.strip()):
                        continue
                    _remember(occurrences, file_occ, file_sha, {
                        "name": name, "file": file, "line": stmt.phys_start,
                        "end_line": stmt.phys_end, "col": tok.start() + 1, "end_col": tok.end(), "stmt": stmt_no,
                        "in": owner_id, "context": context, "candidates": [f"{owner_id}#local:{name}"],
                        "basis": "local", "resolution": "local",
                        "reason": "引数またはローカルが同名の外側の名前を隠している",
                    })
                    continue
                was_member = context == "member"
                if member_assign:
                    context = "assign"
                candidates, basis = resolve(
                    table, file, name, qualifier if was_member else None, variable_types
                )
                if not candidates:
                    if from_with:
                        _remember(occurrences, file_occ, file_sha, {
                            "name": name, "file": file, "line": stmt.phys_start,
                            "end_line": stmt.phys_end, "col": tok.start() + 1, "end_col": tok.end(), "stmt": stmt_no,
                            "in": owner_id, "context": context,
                            "candidates": [f"{owner_id or file}#with:{name}"],
                            "basis": "with", "resolution": "unresolved", "qualifier": qualifier,
                            "reason": "With の受け手からメンバーを決められない",
                        })
                    continue
                if from_with:
                    basis = "with"
                if owner and context == "assign" and owner["name"].casefold() == key \
                        and owner["kind"] in ("Function", "Property Get"):
                    context = "function_result"
                    own = [item for item in candidates if item["id"] == owner["id"]]
                    if own:
                        candidates = own
                else:
                    candidates = _narrow_properties(candidates, context, masked)
                occ = {"name": name, "file": file, "line": stmt.phys_start,
                       "end_line": stmt.phys_end, "col": tok.start() + 1, "end_col": tok.end(), "stmt": stmt_no,
                       "in": owner_id, "context": context, "candidates": [c["id"] for c in candidates],
                       "basis": basis, "resolution": "unique" if len(candidates) == 1 else "ambiguous"}
                if qualifier:
                    occ["qualifier"] = qualifier
                if occ["resolution"] != "unique":
                    occ["reason"] = _gap_reason(occ)
                _remember(occurrences, file_occ, file_sha, occ)

        chunks.extend(_file_chunks(entry, lines, procs, file_effects, file_occ, shadows))

    manifest = {
        "schema": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "stem": inventory.get("stem"),
        "vbp": inventory.get("vbp"),
        "startup": (inventory.get("meta") or {}).get("Startup"),
        "project_type": (inventory.get("meta") or {}).get("Type"),
        "inventory_provenance": inventory.get("provenance"),
        "references": [
            {k: r[k] for k in ("kind", "description", "path", "version", "guid", "lcid", "raw") if r.get(k) is not None}
            for r in inventory.get("references") or []
        ],
        "objects": [{k: o.get(k) for k in ("file", "guid", "version")} for o in inventory.get("objects") or []],
        "files": manifest_files,
        "extract_dir": str(extract_dir.resolve()),
        "input_hashes": inventory.get("input_hashes"),
        "counts": {},
        "token_estimate": "ceil(ascii_chars / 4) + non_ascii_chars (heuristic)",
        "notes": [
            "occurrences.candidates are scope-rule candidates, not a call graph",
            "a parameter or Dim/Static/Const local hides an outer name (resolution=local, not a unique outer binding)",
            "ambiguous and unresolved references stay on chunk ref_gaps; they are not omitted",
            "index matches inventory input_hashes; rebuild inventory when sources change",
            "#If branches are not evaluated; both stay in symbols and chunks",
        ],
    }
    symbols = [{k: v for k, v in r.items() if not k.startswith("_")} for r in table.records]
    manifest["counts"] = {"symbols": len(symbols), "occurrences": len(occurrences),
                          "effects": len(effects), "chunks": len(chunks)}
    return {"manifest": manifest, "symbols": symbols, "occurrences": occurrences,
            "effects": effects, "chunks": chunks}


def _notes(entry: dict, proc: dict, shadows: list[str] | None = None) -> list[str]:
    notes: list[str] = []
    if shadows:
        notes.append(
            "引数またはローカルが同名の外側の名前を隠す: "
            + ", ".join(shadows)
            + "。外側の変数や手続きへの一意の参照にはしない"
        )
    opts = entry.get("options") or {}
    if opts and not opts.get("explicit"):
        if opts.get("deftypes"):
            notes.append(
                "Option Explicit なし。DefType があるので、未宣言の型は DefType と分岐の両方があり得る"
                "（#If は評価しない）"
            )
        else:
            notes.append("Option Explicit なし: 未宣言の名前は暗黙に Variant として作られる")
    for item in proc.get("error_handling") or []:
        if item["kind"] == "on_error_resume_next":
            notes.append(
                f"L{item['line']} に On Error Resume Next がある。"
                "この手続きの中で、次の On Error までの失敗を無視する書き方。"
                "呼び出し先には引き継がない。実行経路は解析していない"
            )
    implicit = [p["name"] for p in proc.get("params") or [] if p.get("name") and not p.get("passing_explicit")
                and not p.get("param_array")]
    if implicit:
        notes.append("ByRef（省略時）の引数: " + ", ".join(implicit) + "（呼び出し元の変数を書き換え得る）")
    if (proc.get("attributes") or {}).get("VB_UserMemId") == 0:
        notes.append("既定メンバー（VB_UserMemId=0）: オブジェクト名だけの参照がこのメンバーを指す")
    if proc.get("static"):
        notes.append("Static 手続き: ローカル変数が呼び出し間で値を保持する")
    if proc.get("conditional"):
        cond = proc["conditional"]
        notes.append(f"#If 分岐内（L{cond['line']} {cond['directive']} {cond['expr']}）: 評価していない")
    for p in proc.get("params") or []:
        if p.get("type_source") == "default" and p.get("name"):
            notes.append(f"引数 {p['name']} は型宣言なし（Variant）")
    return notes


def _header(entry: dict, proc: dict | None, title: str) -> str:
    kind = entry.get("form_kind") or entry.get("type") or ""
    bits = [f"{entry['file']} ({entry.get('vb_name') or '?'}, {kind})"]
    opts = entry.get("options")
    if opts:
        bits.append("Option Explicit" if opts.get("explicit") else "Option Explicit なし")
    bits.append(title)
    if proc and proc.get("event"):
        ev = proc["event"]
        bits.append(f"event {ev['owner']}.{ev['event']} [{ev['binding']}]")
    return " · ".join(bits)


def _signature(proc: dict) -> str:
    params = ", ".join(
        p.get("raw") or (
            ("Optional " if p.get("optional") else "")
            + ("ParamArray " if p.get("param_array") else "")
            + f"{p['passing']}{'' if p.get('passing_explicit') else '(省略)'} {p['name']}"
            + ("()" if p.get("is_array") else "")
            + f" As {p['type']}"
            + (f" = {p['default']}" if p.get("default") is not None else "")
        )
        for p in proc.get("params") or []
    )
    ret = f" As {proc['return_type']}" if proc.get("return_type") else ""
    return f"{proc.get('visibility') or ''} {proc['kind']} {proc['name']}({params}){ret}".strip()


def _child_statements(file: str, proc: dict, lines: list[str]) -> list[dict]:
    """One chunk per statement so a long procedure can be fetched in pieces."""
    start, end = proc["span"]
    parts: list[dict] = []
    number = 0
    for stmt in iter_statements(lines):
        if stmt.kind != "stmt" or not (start <= stmt.phys_start <= end):
            continue
        number += 1
        code = f"{stmt.phys_start}| {stmt.text}"
        header = f"{proc['id']} statement {number}"
        parts.append({
            "id": f"chunk:{proc['id']}#stmt:{number}",
            "symbol": proc["id"],
            "parent": f"chunk:{proc['id']}",
            "file": file,
            "span": [stmt.phys_start, stmt.phys_end],
            "stmt": number,
            "header": header,
            "code": code,
            "sha256": sha256_text(code),
            "tokens_est": estimate_tokens(header + code),
            "notes": [],
            "effects": [],
            "refs": [],
        })
    return parts


def _numbered(lines: list[str], start: int, end: int) -> str:
    return "\n".join(f"{n}| {lines[n - 1]}" for n in range(start, min(end, len(lines)) + 1))


def _file_chunks(entry: dict, lines: list[str], procs: list[dict], effects: list[dict],
                 occurrences: list[dict], shadows: dict[str, list[str]] | None = None) -> list[dict]:
    shadows = shadows or {}
    file = entry["file"]
    out: list[dict] = []
    code_start = next((i + 1 for i, ln in enumerate(lines) if _VB_NAME_RE.match(ln.strip())), 1)
    by_owner: dict[str | None, list[dict]] = {}
    for occ in occurrences:
        by_owner.setdefault(occ.get("in"), []).append(occ)
    effects_by_owner: dict[str | None, list[dict]] = {}
    for effect in effects:
        effects_by_owner.setdefault(effect.get("in"), []).append(effect)
    if entry.get("form_kind"):
        rows = []
        for node in parse_designer(lines)[1:]:
            props = node["props"]
            caption = props.get("Caption")
            bits = [f"L{node['line']} {node['name']} ({node['kind']})"]
            if isinstance(caption, str) and caption:
                bits.append(f"Caption={caption}")
            for key in ("Index", "Visible", "Enabled", "DataSource", "DataField", "RecordSource"):
                if key in props:
                    bits.append(f"{key}={props[key]}")
            rows.append(" ".join(bits))
        if rows:
            text = "\n".join(rows)
            header = _header(entry, None, "designer controls")
            notes = [
                f"L{ref.get('line')} {ref.get('prop')} → {ref.get('file')}（"
                + ("ファイルあり。中身は未解析" if ref.get("exists") else "ファイルが無い")
                + "）"
                for ref in entry.get("resource_refs") or []
            ]
            out.append({"id": f"chunk:{file}#designer", "symbol": file, "file": file,
                        "span": [1, code_start - 1], "header": header, "code": text,
                        "sha256": sha256_text(text), "tokens_est": estimate_tokens(header + text),
                        "notes": notes, "effects": [], "refs": []})
    first_proc = procs[0]["span"][0] if procs else len(lines) + 1
    decl_lines = [n for n in range(code_start, first_proc) if lines[n - 1].strip()]
    if decl_lines:
        text = _numbered(lines, decl_lines[0], decl_lines[-1])
        header = _header(entry, None, "module declarations")
        out.append({"id": f"chunk:{file}#declarations", "symbol": file, "file": file,
                    "span": [decl_lines[0], decl_lines[-1]], "header": header, "code": text,
                    "sha256": sha256_text(text), "tokens_est": estimate_tokens(header + text),
                    "notes": [], "effects": [], "refs": []})
    for proc in procs:
        start, end = proc["span"]
        text = _numbered(lines, start, end)
        header = _header(entry, proc, _signature(proc))
        owned = by_owner.get(proc["id"], [])
        refs = sorted({
            occ["candidates"][0] for occ in owned
            if occ["resolution"] == "unique" and occ["candidates"] and occ["candidates"][0] != proc["id"]
        })
        gaps = [
            {
                "name": occ["name"], "line": occ["line"], "resolution": occ["resolution"],
                "basis": occ.get("basis"), "candidates": occ.get("candidates") or [],
                "reason": _gap_reason(occ),
            }
            for occ in owned if occ["resolution"] != "unique"
        ]
        children = _child_statements(file, proc, lines)
        out.append({
            "id": f"chunk:{proc['id']}", "symbol": proc["id"], "file": file, "span": [start, end],
            "header": header, "code": text, "sha256": sha256_text(text),
            "tokens_est": estimate_tokens(header + text),
            "notes": _notes(entry, proc, shadows.get(proc["id"])),
            "effects": [{"kind": e["kind"], "line": e["line"]} for e in effects_by_owner.get(proc["id"], [])],
            "refs": refs,
            "ref_gaps": gaps,
            "parts": [part["id"] for part in children],
        })
        out.extend(children)
    return out


def write_index(data: dict, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"manifest": out_dir / "manifest.json"}
    paths["manifest"].write_text(json.dumps(data["manifest"], ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    for name in ("symbols", "occurrences", "effects", "chunks"):
        path = out_dir / f"{name}.jsonl"
        with path.open("w", encoding="utf-8", newline="\n") as fh:
            for record in data[name]:
                fh.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        paths[name] = path
    return paths


def resolve_inventory(arg: Path | None) -> Path:
    if arg is not None:
        path = arg if arg.is_absolute() else REPO / arg
        if not path.is_file():
            raise SystemExit(f"inventory not found: {path}")
        return path.resolve()
    cands = sorted(reports_root().glob("*_inventory.json"))
    if len(cands) != 1:
        raise SystemExit(f"pass --inventory (found {len(cands)} *_inventory.json under {reports_root()})")
    return cands[0].resolve()


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    ap = argparse.ArgumentParser(
        description="Build the AI index (symbols / occurrences / effects / chunks JSONL) for one extract"
    )
    ap.add_argument("--inventory", type=Path, default=None,
                    help="<stem>_inventory.json (default: sole inventory under reports/)")
    ap.add_argument("--out", type=Path, default=None, help="Output dir (default: <index_dir>/<stem>)")
    ap.add_argument("--strict-decode", action="store_true",
                    help="Fail when a source file cannot be decoded without replacing characters")
    args = ap.parse_args(argv)

    inv_path = resolve_inventory(args.inventory)
    inventory = json.loads(inv_path.read_text(encoding="utf-8"))
    extract_dir = Path(str(inventory.get("extract_dir") or ""))
    if not extract_dir.is_dir():
        print(f"extract not found: {extract_dir} (re-run inventory)", file=sys.stderr)
        return 1
    try:
        data = build_index(inventory, extract_dir, strict_decode=args.strict_decode)
    except StaleInventory as exc:
        print(format_stale(exc.problems), file=sys.stderr)
        return 1
    except VB6DecodeError as exc:
        where = ", ".join(str(n) for n in exc.replacements[:8])
        print(
            f"decode replaced characters ({exc.encoding}); positions: {where}",
            file=sys.stderr,
        )
        return 1
    data["manifest"]["inventory"] = inv_path.name
    data["manifest"]["inventory_sha256"] = hashlib.sha256(inv_path.read_bytes()).hexdigest()
    stem = str(inventory.get("stem") or inv_path.name.replace("_inventory.json", ""))
    out_dir = args.out or (index_root() / stem)
    if not out_dir.is_absolute():
        out_dir = REPO / out_dir
    paths = write_index(data, out_dir)
    print(json.dumps({"out": str(out_dir), **data["manifest"]["counts"],
                      "files": {k: str(v) for k, v in paths.items()}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
