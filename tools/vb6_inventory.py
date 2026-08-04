#!/usr/bin/env python3
"""Deterministic VB6 project inventory: VBP -> files -> procedures.

Reads an extracted VBP (CP932) and lists, per source file, every procedure
definition found at line start. No call-graph guessing; only facts:
  - VBP metadata (Startup, Title, version, Object=, form/module/class in VBP order)
  - per file: VB_Name, form kind, controls (from the .frm header)
  - per procedure: kind, visibility, params, returns, line range, event role

Outputs <stem>_inventory.json / .md / .html into working/reports/.
Read-only on sources.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))
from lib.cache import content_key  # noqa: E402
from lib.cache import load as cache_load  # noqa: E402
from lib.cache import store as cache_store  # noqa: E402
from lib.config import decode_vb6_bytes, reports_root  # noqa: E402
from lib.console import enable_utf8_stdio  # noqa: E402
from lib.vbparse import iter_logical_lines  # noqa: E402

# Bump when parse_* output shape or semantics change (invalidates the cache).
# Suffix is part of the key (see inventory_file): .frm vs .bas parse differently.
PARSER_VERSION = "inv-4"

# VBP project metadata: lowercase match → canonical key for report consumers.
VBP_META_CANON = {
    "startup": "Startup",
    "title": "Title",
    "exename32": "ExeName32",
    "iconform": "IconForm",
    "name": "Name",
    "command32": "Command32",
    "helpfile": "HelpFile",
    "majorver": "MajorVer",
    "minorver": "MinorVer",
    "revisionver": "RevisionVer",
    "versioncomments": "VersionComments",
    "versioncompanyname": "VersionCompanyName",
    "versionfiledescription": "VersionFileDescription",
    "versionlegalcopyright": "VersionLegalCopyright",
    "versionproductname": "VersionProductName",
}
AS_RETURN_RE = re.compile(r"(?i)^As\s+(.+?)\s*$")

PROC_RE = re.compile(
    r"^(?:(Public|Private|Friend)\s+)?(?:Static\s+)?"
    r"(Sub|Function|Property\s+(?:Get|Let|Set))\s+([A-Za-z_]\w*)",
    re.IGNORECASE,
)
DECLARE_RE = re.compile(
    r"^(?:(Public|Private)\s+)?Declare\s+(Sub|Function)\s+(\w+)\s+Lib\s+\"([^\"]+)\"",
    re.IGNORECASE,
)
END_RE = re.compile(r"^End\s+(Sub|Function|Property)\b", re.IGNORECASE)
CONTROL_RE = re.compile(r"^\s*Begin\s+([\w.]+)\s+(\w+)")
VBNAME_RE = re.compile(r'^Attribute\s+VB_Name\s*=\s*"([^"]+)"', re.IGNORECASE)

# Module-level declarations (facts only; locals inside procedures are excluded)
CONST_RE = re.compile(
    r"^(?:(Public|Private|Global)\s+)?Const\s+([A-Za-z_]\w*)\s*=\s*(.+)$",
    re.IGNORECASE,
)
ENUM_RE = re.compile(
    r"^(?:(Public|Private)\s+)?Enum\s+([A-Za-z_]\w*)", re.IGNORECASE
)
TYPE_RE = re.compile(
    r"^(?:(Public|Private)\s+)?Type\s+([A-Za-z_]\w*)\s*$", re.IGNORECASE
)
EVENT_RE = re.compile(
    r"^(?:(Public)\s+)?Event\s+([A-Za-z_]\w*)\s*\((.*)\)\s*$", re.IGNORECASE
)
END_ENUM_RE = re.compile(r"^End\s+Enum\b", re.IGNORECASE)
END_TYPE_RE = re.compile(r"^End\s+Type\b", re.IGNORECASE)
ENUM_MEMBER_RE = re.compile(r"^([A-Za-z_]\w*)\s*(?:=\s*(.+))?$")
TYPE_FIELD_RE = re.compile(r"^([A-Za-z_][\w]*(?:\([^)]*\))?)\s+As\s+(.+)$", re.IGNORECASE)


def decode(raw: bytes) -> str:
    """Config-driven decode (cp932 primary + fallbacks from archaeology.config.json)."""
    return decode_vb6_bytes(raw)


def looks_like_parent_common(path: str) -> bool:
    """True when a VBP path climbs two or more parent dirs (shared-lib style).

    Inspired by vbSpec's optional skip of ``..\\..``-style entries. Default off
    in this kit; enable via ``--skip-parent-common``.
    """
    norm = path.replace("/", "\\")
    return sum(1 for part in norm.split("\\") if part == "..") >= 2


def parse_vbp(vbp_path: Path, *, skip_parent_common: bool = False) -> dict:
    """Parse VBP facts: forms, modules, classes, Object= components, meta.

    ``Class=`` uses the same ``Ident; path`` shape as ``Module=``. Entries
    without a path (no ``; file``) are omitted and recorded in ``warnings``.
    Paths that look like shared parent-tree libs may be omitted when
    ``skip_parent_common`` is set (recorded under ``skipped_parent_common``).
    """
    text = decode(vbp_path.read_bytes())
    forms: list[str] = []
    modules: list[dict] = []
    classes: list[dict] = []
    objects: list[dict] = []
    skipped_parent_common: list[dict] = []
    warnings: list[dict] = []
    meta: dict[str, str] = {}

    def maybe_skip(kind: str, path: str, ident: str = "") -> bool:
        if skip_parent_common and looks_like_parent_common(path):
            skipped_parent_common.append(
                {"kind": kind, "file": path, "ident": ident or None}
            )
            return True
        return False

    def warn_missing_path(kind: str, ident: str, raw: str) -> None:
        # ``Module=Foo`` / ``Class=Bar`` (no ``; path``) would otherwise yield
        # file="" and pollute missing_in_extract with an empty path.
        warnings.append(
            {
                "kind": kind,
                "reason": "missing_path",
                "ident": ident or None,
                "raw": raw,
            }
        )

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("["):
            continue
        if line.startswith("Form="):
            name = line.split("=", 1)[1].strip().strip('"')
            if not name:
                warnings.append(
                    {"kind": "form", "reason": "missing_path", "ident": None, "raw": line}
                )
                continue
            if maybe_skip("form", name):
                continue
            if name not in forms:
                forms.append(name)
        elif line.startswith("Module="):
            ident, _, fname = line.split("=", 1)[1].partition(";")
            ident, fname = ident.strip(), fname.strip().strip('"')
            if not fname:
                warn_missing_path("module", ident, line)
                continue
            if maybe_skip("module", fname, ident):
                continue
            modules.append({"module": ident, "file": fname})
        elif line.startswith("Class="):
            ident, _, fname = line.split("=", 1)[1].partition(";")
            ident, fname = ident.strip(), fname.strip().strip('"')
            if not fname:
                warn_missing_path("class", ident, line)
                continue
            if maybe_skip("class", fname, ident):
                continue
            classes.append({"class": ident, "file": fname})
        elif line.startswith("Object="):
            raw = line.split("=", 1)[1].strip()
            if ";" in raw:
                file_part = raw.split(";")[-1].strip() or None
            else:
                file_part = None  # malformed / GUID-only; keep raw for evidence
            objects.append({"raw": raw, "file": file_part})
        else:
            key, sep, val = line.partition("=")
            canon = VBP_META_CANON.get(key.lower()) if sep else None
            if canon:
                meta[canon] = val.strip().strip('"')
    return {
        "forms": forms,
        "modules": modules,
        "classes": classes,
        "objects": objects,
        "skipped_parent_common": skipped_parent_common,
        "warnings": warnings,
        "meta": meta,
    }


def extract_params_returns(after_name: str) -> tuple[str, str | None]:
    """Parse ``(params) [As return]`` after a procedure name on a folded line."""
    s = after_name.lstrip()
    if not s.startswith("("):
        return "", None
    depth = 0
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                params = s[1:i].strip()
                rest = s[i + 1 :].strip()
                # Strip trailing ' comment (common on hand-written signatures).
                cpos = rest.find("'")
                if cpos >= 0:
                    rest = rest[:cpos].rstrip()
                m = AS_RETURN_RE.match(rest)
                return params, (m.group(1).strip() if m else None)
    return s[1:].strip(), None


def file_kind_label(f: dict) -> str:
    if f.get("form_kind"):
        return f["form_kind"]
    t = f.get("type")
    if t == "class":
        return "Class"
    if t == "module":
        return "Module"
    return "?"


def parse_form_header(lines: list[str]) -> tuple[str | None, list[dict]]:
    """Return (form kind e.g. VB.Form / VB.MDIForm, controls) from a .frm header."""
    form_kind: str | None = None
    controls: list[dict] = []
    for line in lines:
        if VBNAME_RE.match(line):
            break  # header ends where attributes/code begin
        m = CONTROL_RE.match(line)
        if not m:
            continue
        cls, name = m.group(1), m.group(2)
        if form_kind is None:
            form_kind = cls
        else:
            controls.append({"class": cls, "name": name})
    return form_kind, controls


def parse_procedures(lines: list[str]) -> tuple[list[dict], list[dict]]:
    """Return (procedures, declares).

    Line numbers are physical (1-based). ``_`` continuations are folded so that
    multi-line ``Declare`` signatures capture the full Lib target, while the
    reported ``line`` stays the physical line where the statement begins.
    """
    procs: list[dict] = []
    declares: list[dict] = []
    logical = iter_logical_lines(lines)
    in_header = bool(logical) and logical[0].text.startswith("VERSION")
    open_proc: dict | None = None
    for ll in logical:
        stripped = ll.text
        if in_header:
            if VBNAME_RE.match(stripped):
                in_header = False
            continue
        dm = DECLARE_RE.match(stripped)
        if dm and open_proc is None:
            declares.append(
                {
                    "name": dm.group(3),
                    "kind": dm.group(2).capitalize(),
                    "visibility": (dm.group(1) or "Public").capitalize(),
                    "lib": dm.group(4),
                    "line": ll.phys_start,
                }
            )
            continue
        if open_proc is None:
            pm = PROC_RE.match(stripped)
            # a Declare line also matches PROC_RE via "Sub|Function"? no: Declare comes first
            if pm and not stripped.lower().startswith("declare"):
                kind = re.sub(r"\s+", " ", pm.group(2)).title()
                params, returns = extract_params_returns(stripped[pm.end() :])
                open_proc = {
                    "name": pm.group(3),
                    "kind": kind,
                    "visibility": (pm.group(1) or "Public").capitalize(),
                    "params": params,
                    "returns": returns,
                    "line_start": ll.phys_start,
                }
        else:
            if END_RE.match(stripped):
                open_proc["line_end"] = ll.phys_end
                open_proc["lines"] = ll.phys_end - open_proc["line_start"] + 1
                procs.append(open_proc)
                open_proc = None
    if open_proc is not None:  # unterminated (should not happen in valid VB6)
        open_proc["line_end"] = len(lines)
        open_proc["lines"] = len(lines) - open_proc["line_start"] + 1
        open_proc["unterminated"] = True
        procs.append(open_proc)
    return procs, declares


def parse_declarations(lines: list[str]) -> dict:
    """Collect module-level Const / Enum / Type / Event facts.

    Declarations inside a Sub/Function/Property are excluded (locals). Enum and
    Type blocks close on ``End Enum`` / ``End Type`` (neither matches END_RE, so
    the verify_inventory proc/End invariant is unaffected). Line numbers are
    physical. Multi-declaration single lines (``Const A = 1, B = 2``) capture the
    first name only — noted as a known limitation.
    """
    consts: list[dict] = []
    enums: list[dict] = []
    types: list[dict] = []
    events: list[dict] = []
    logical = iter_logical_lines(lines)
    in_header = bool(logical) and logical[0].text.startswith("VERSION")
    in_proc = False
    open_enum: dict | None = None
    open_type: dict | None = None

    for ll in logical:
        s = ll.text
        if in_header:
            if VBNAME_RE.match(s):
                in_header = False
            continue

        if open_enum is not None:
            if END_ENUM_RE.match(s):
                open_enum["line_end"] = ll.phys_end
                enums.append(open_enum)
                open_enum = None
            elif not s.startswith("'") and s:
                mm = ENUM_MEMBER_RE.match(s)
                if mm:
                    open_enum["members"].append({"name": mm.group(1), "line": ll.phys_start})
            continue
        if open_type is not None:
            if END_TYPE_RE.match(s):
                open_type["line_end"] = ll.phys_end
                types.append(open_type)
                open_type = None
            elif not s.startswith("'") and s:
                fm = TYPE_FIELD_RE.match(s)
                if fm:
                    open_type["fields"].append(
                        {"name": fm.group(1), "as": fm.group(2).strip(), "line": ll.phys_start}
                    )
            continue

        # Track procedure context so locals are not counted as module-level.
        if not in_proc:
            pm = PROC_RE.match(s)
            if pm and not s.lower().startswith("declare"):
                in_proc = True
                continue
        else:
            if END_RE.match(s):
                in_proc = False
            continue

        # Module-level declarations only reach here.
        em = ENUM_RE.match(s)
        if em:
            open_enum = {
                "name": em.group(2),
                "visibility": (em.group(1) or "Public").capitalize(),
                "line": ll.phys_start,
                "line_end": ll.phys_start,
                "members": [],
            }
            continue
        tm = TYPE_RE.match(s)
        if tm:
            open_type = {
                "name": tm.group(2),
                "visibility": (tm.group(1) or "Public").capitalize(),
                "line": ll.phys_start,
                "line_end": ll.phys_start,
                "fields": [],
            }
            continue
        vm = EVENT_RE.match(s)
        if vm:
            events.append(
                {
                    "name": vm.group(2),
                    "visibility": (vm.group(1) or "Public").capitalize(),
                    "args": vm.group(3).strip(),
                    "line": ll.phys_start,
                }
            )
            continue
        cm = CONST_RE.match(s)
        if cm:
            consts.append(
                {
                    "name": cm.group(2),
                    "visibility": (cm.group(1) or "Private").capitalize(),
                    "value": cm.group(3).strip(),
                    "line": ll.phys_start,
                }
            )

    if open_enum is not None:  # unterminated
        open_enum["unterminated"] = True
        enums.append(open_enum)
    if open_type is not None:
        open_type["unterminated"] = True
        types.append(open_type)
    return {"consts": consts, "enums": enums, "types": types, "events": events}


def classify_events(procs: list[dict], control_names: set[str], is_form: bool) -> None:
    prefixes = {n.lower() for n in control_names}
    if is_form:
        prefixes |= {"form", "mdiform"}
    for p in procs:
        name = p["name"]
        owner = None
        # longest matching "<owner>_" prefix wins (owners may contain underscores)
        for i in range(len(name) - 1, 0, -1):
            if name[i] == "_" and name[:i].lower() in prefixes:
                owner = name[:i]
                break
        if owner is not None:
            p["role"] = "event"
            p["event_owner"] = owner
            p["event_name"] = name[len(owner) + 1 :]
        else:
            p["role"] = "general"


def inventory_file(path: Path, use_cache: bool = True) -> dict:
    raw = path.read_bytes()
    # Include suffix: identical bytes as .frm vs .bas produce different results.
    key: str | None = None
    if use_cache:
        key = content_key(raw, f"{PARSER_VERSION}|{path.suffix.lower()}")
        hit = cache_load(key)
        if hit is not None:
            hit["file"] = path.name  # same content, possibly different filename
            return hit
    result = _parse_bytes(raw, path)
    if use_cache and key is not None:
        cache_store(key, result)
    return result


def _parse_bytes(raw: bytes, path: Path) -> dict:
    lines = decode(raw).splitlines()
    vb_name = None
    for line in lines:
        m = VBNAME_RE.match(line)
        if m:
            vb_name = m.group(1)
            break
    is_form = path.suffix.lower() == ".frm"
    form_kind, controls = parse_form_header(lines) if is_form else (None, [])
    procs, declares = parse_procedures(lines)
    decls = parse_declarations(lines)
    classify_events(procs, {c["name"] for c in controls}, is_form)
    return {
        "file": path.name,
        "vb_name": vb_name,
        "form_kind": form_kind,
        "total_lines": len(lines),
        "control_count": len(controls),
        "controls": controls,
        "declares": declares,
        "consts": decls["consts"],
        "enums": decls["enums"],
        "types": decls["types"],
        "events": decls["events"],
        "procedures": procs,
    }


def build_report(
    extract_dir: Path,
    vbp_path: Path,
    use_cache: bool = True,
    jobs: int = 1,
    skip_parent_common: bool = False,
) -> dict:
    vbp = parse_vbp(vbp_path, skip_parent_common=skip_parent_common)
    missing: list[str] = []
    # VBP order: Form → Module → Class (same family as extract_vbp FILE_KEYS).
    ordered = (
        [(f, "form") for f in vbp["forms"]]
        + [(m["file"], "module") for m in vbp["modules"]]
        + [(c["file"], "class") for c in vbp["classes"]]
    )
    present: list[tuple[str, str]] = []
    for fname, ftype in ordered:
        # Relative paths may include subdirs; resolve against extract_dir.
        if (extract_dir / fname).is_file():
            present.append((fname, ftype))
        else:
            missing.append(fname)

    def work(item: tuple[str, str]) -> dict:
        fname, ftype = item
        info = inventory_file(extract_dir / fname, use_cache=use_cache)
        info["type"] = ftype
        return info

    # ThreadPoolExecutor.map preserves input order, so VBP order is kept.
    if jobs and jobs > 1 and len(present) > 1:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            files: list[dict] = list(pool.map(work, present))
    else:
        files = [work(item) for item in present]
    listed = {Path(f["file"]).name.lower() for f in files} | {
        Path(m).name.lower() for m in missing
    }
    extras = sorted(
        p.name
        for p in extract_dir.iterdir()
        if p.suffix.lower() in (".frm", ".bas", ".cls") and p.name.lower() not in listed
    )
    return {
        "vbp": vbp_path.name,
        "stem": vbp_path.stem,
        "extract_dir": str(extract_dir.resolve()),
        "meta": vbp["meta"],
        "objects": vbp["objects"],
        "file_count": len(files),
        "proc_total": sum(len(f["procedures"]) for f in files),
        "files": files,
        "missing_in_extract": missing,
        "not_in_vbp": extras,
        "skipped_parent_common": vbp["skipped_parent_common"],
        "warnings": vbp.get("warnings") or [],
    }


def write_markdown(report: dict, out: Path) -> None:
    meta = report["meta"]
    ver = ".".join(
        meta.get(k, "?") for k in ("MajorVer", "MinorVer", "RevisionVer")
    )
    L = [
        f"# {report['vbp']} インベントリ（VBP → ファイル → プロシージャ）",
        "",
        f"- Startup: `{meta.get('Startup', '?')}` / Title: `{meta.get('Title', '?')}` / Exe: `{meta.get('ExeName32', '?')}`",
        f"- Name: `{meta.get('Name', '?')}` / Version: `{ver}` / Command32: `{meta.get('Command32') or '—'}`",
        f"- ファイル: **{report['file_count']}**（VBP 記載順 Form→Module→Class） / プロシージャ合計: **{report['proc_total']}**",
        "- 行頭のプロシージャ定義のみを機械抽出（呼び出し推定なし）。行番号は抽出コピーの実ファイル基準。",
        "",
    ]
    if report.get("objects"):
        objs = ", ".join(
            f"`{o['file']}`" if o.get("file") else f"`{o['raw']}`"
            for o in report["objects"]
        )
        L.append(f"- Object（OCX 等）: {objs}")
    if report["missing_in_extract"]:
        L.append(f"- ⚠ VBP に記載だが抽出フォルダに無い: {', '.join(report['missing_in_extract'])}")
    if report["not_in_vbp"]:
        L.append(f"- ⚠ 抽出フォルダにあるが VBP 未記載: {', '.join(report['not_in_vbp'])}")
    if report.get("skipped_parent_common"):
        sk = ", ".join(
            f"`{s['file']}`" for s in report["skipped_parent_common"]
        )
        L.append(f"- （参考）親共通パスをスキップ: {sk}")
    if report.get("warnings"):
        for w in report["warnings"]:
            L.append(
                f"- ⚠ VBP 警告 ({w.get('kind')}/{w.get('reason')}): `{w.get('raw')}`"
            )
    L.append("")
    L.append("## 目次")
    L.append("")
    L.append("| # | ファイル | 種別 | VB_Name | 行数 | コントロール | プロシージャ |")
    L.append("|---:|---|---|---|---:|---:|---:|")
    for i, f in enumerate(report["files"], 1):
        kind = file_kind_label(f)
        L.append(
            f"| {i} | `{f['file']}` | {kind} | `{f['vb_name'] or '?'}` "
            f"| {f['total_lines']:,} | {f['control_count'] or '-'} | {len(f['procedures'])} |"
        )
    L.append("")
    for f in report["files"]:
        kind = file_kind_label(f)
        L.append(f"## {f['file']} — `{f['vb_name'] or '?'}`（{kind}, {f['total_lines']:,} 行）")
        L.append("")
        events = [p for p in f["procedures"] if p["role"] == "event"]
        general = [p for p in f["procedures"] if p["role"] == "general"]
        if events:
            L.append(f"### イベントハンドラ（{len(events)}）")
            L.append("")
            L.append("| コントロール | イベント | プロシージャ | 引数 | 行 | 規模 |")
            L.append("|---|---|---|---|---|---:|")
            for p in sorted(events, key=lambda x: (x["event_owner"].lower(), x["event_name"].lower())):
                L.append(
                    f"| `{p['event_owner']}` | {p['event_name']} | `{p['name']}` "
                    f"| `{p.get('params') or ''}` "
                    f"| {p['line_start']}–{p['line_end']} | {p['lines']} |"
                )
            L.append("")
        if general:
            L.append(f"### Sub / Function / Property（{len(general)}）")
            L.append("")
            L.append("| 種別 | 名前 | 可視性 | 引数 | 戻り値 | 行 | 規模 |")
            L.append("|---|---|---|---|---|---|---:|")
            for p in general:
                ret = p.get("returns") or "—"
                L.append(
                    f"| {p['kind']} | `{p['name']}` | {p['visibility']} "
                    f"| `{p.get('params') or ''}` | `{ret}` "
                    f"| {p['line_start']}–{p['line_end']} | {p['lines']} |"
                )
            L.append("")
        if f["declares"]:
            L.append(f"### API 宣言（Declare, {len(f['declares'])}）")
            L.append("")
            for d in f["declares"]:
                L.append(f"- `{d['name']}` ({d['kind']}, {d['lib']}) — L{d['line']}")
            L.append("")
        if f.get("consts"):
            L.append(f"### 定数（Const, {len(f['consts'])}）")
            L.append("")
            for c in f["consts"]:
                L.append(f"- `{c['name']}` = `{c['value']}` ({c['visibility']}) — L{c['line']}")
            L.append("")
        if f.get("enums"):
            L.append(f"### 列挙型（Enum, {len(f['enums'])}）")
            L.append("")
            for en in f["enums"]:
                members = ", ".join(m["name"] for m in en["members"]) or "—"
                L.append(f"- `{en['name']}` ({en['visibility']}) L{en['line']}–{en['line_end']}: {members}")
            L.append("")
        if f.get("types"):
            L.append(f"### ユーザー定義型（Type, {len(f['types'])}）")
            L.append("")
            for t in f["types"]:
                fields = ", ".join(fld["name"] for fld in t["fields"]) or "—"
                L.append(f"- `{t['name']}` ({t['visibility']}) L{t['line']}–{t['line_end']}: {fields}")
            L.append("")
        if f.get("events"):
            L.append(f"### イベント宣言（Event, {len(f['events'])}）")
            L.append("")
            for ev in f["events"]:
                L.append(f"- `{ev['name']}({ev['args']})` ({ev['visibility']}) — L{ev['line']}")
            L.append("")
    out.write_text("\n".join(L) + "\n", encoding="utf-8")


def write_html(report: dict, out: Path) -> None:
    meta = report["meta"]
    e = html.escape

    def proc_rows(procs: list[dict], event: bool) -> str:
        rows = []
        for p in procs:
            loc = f"{p['line_start']}–{p['line_end']}"
            params = e(p.get("params") or "")
            if event:
                rows.append(
                    f"<tr><td><code>{e(p['event_owner'])}</code></td>"
                    f"<td>{e(p['event_name'])}</td><td><code>{e(p['name'])}</code></td>"
                    f"<td><code>{params}</code></td>"
                    f"<td>{loc}</td><td class='num'>{p['lines']}</td></tr>"
                )
            else:
                ret = e(p["returns"]) if p.get("returns") else "—"
                rows.append(
                    f"<tr><td>{e(p['kind'])}</td><td><code>{e(p['name'])}</code></td>"
                    f"<td>{e(p['visibility'])}</td><td><code>{params}</code></td>"
                    f"<td><code>{ret}</code></td><td>{loc}</td>"
                    f"<td class='num'>{p['lines']}</td></tr>"
                )
        return "".join(rows)

    toc_rows = []
    sections = []
    for i, f in enumerate(report["files"], 1):
        kind = file_kind_label(f)
        anchor = f"f{i}"
        toc_rows.append(
            f"<tr class='tocrow' data-for='{anchor}'><td class='num'>{i}</td>"
            f"<td><a href='#{anchor}'><code>{e(f['file'])}</code></a></td>"
            f"<td>{e(kind)}</td><td><code>{e(f['vb_name'] or '?')}</code></td>"
            f"<td class='num'>{f['total_lines']:,}</td>"
            f"<td class='num'>{f['control_count'] or '-'}</td>"
            f"<td class='num'>{len(f['procedures'])}</td></tr>"
        )
        events = sorted(
            (p for p in f["procedures"] if p["role"] == "event"),
            key=lambda x: (x["event_owner"].lower(), x["event_name"].lower()),
        )
        general = [p for p in f["procedures"] if p["role"] == "general"]
        blocks = []
        if events:
            blocks.append(
                f"<h4>イベントハンドラ（{len(events)}）</h4>"
                "<table><tr><th>コントロール</th><th>イベント</th><th>プロシージャ</th>"
                "<th>引数</th><th>行</th><th>規模</th></tr>"
                + proc_rows(events, True)
                + "</table>"
            )
        if general:
            blocks.append(
                f"<h4>Sub / Function / Property（{len(general)}）</h4>"
                "<table><tr><th>種別</th><th>名前</th><th>可視性</th><th>引数</th>"
                "<th>戻り値</th><th>行</th><th>規模</th></tr>"
                + proc_rows(general, False)
                + "</table>"
            )
        if f["declares"]:
            items = "".join(
                f"<li><code>{e(d['name'])}</code>（{e(d['kind'])}, {e(d['lib'])}）L{d['line']}</li>"
                for d in f["declares"]
            )
            blocks.append(f"<h4>API 宣言（{len(f['declares'])}）</h4><ul>{items}</ul>")
        if f.get("consts"):
            items = "".join(
                f"<li><code>{e(c['name'])}</code> = <code>{e(c['value'])}</code>"
                f"（{e(c['visibility'])}）L{c['line']}</li>"
                for c in f["consts"]
            )
            blocks.append(f"<h4>定数（Const, {len(f['consts'])}）</h4><ul>{items}</ul>")
        if f.get("enums"):
            items = "".join(
                f"<li><code>{e(en['name'])}</code>（{e(en['visibility'])}）"
                f"L{en['line']}–{en['line_end']}: "
                f"{e(', '.join(m['name'] for m in en['members']) or '—')}</li>"
                for en in f["enums"]
            )
            blocks.append(f"<h4>列挙型（Enum, {len(f['enums'])}）</h4><ul>{items}</ul>")
        if f.get("types"):
            items = "".join(
                f"<li><code>{e(t['name'])}</code>（{e(t['visibility'])}）"
                f"L{t['line']}–{t['line_end']}: "
                f"{e(', '.join(fld['name'] for fld in t['fields']) or '—')}</li>"
                for t in f["types"]
            )
            blocks.append(f"<h4>ユーザー定義型（Type, {len(f['types'])}）</h4><ul>{items}</ul>")
        if f.get("events"):
            items = "".join(
                f"<li><code>{e(ev['name'])}({e(ev['args'])})</code>"
                f"（{e(ev['visibility'])}）L{ev['line']}</li>"
                for ev in f["events"]
            )
            blocks.append(f"<h4>イベント宣言（Event, {len(f['events'])}）</h4><ul>{items}</ul>")
        sections.append(
            f"<details class='filesec' id='{anchor}'><summary><b>{e(f['file'])}</b> — "
            f"<code>{e(f['vb_name'] or '?')}</code>（{e(kind)}, {f['total_lines']:,} 行, "
            f"proc {len(f['procedures'])}）</summary>" + "".join(blocks) + "</details>"
        )

    warns = []
    if report["missing_in_extract"]:
        warns.append("VBP 記載だが抽出に無い: " + ", ".join(map(e, report["missing_in_extract"])))
    if report["not_in_vbp"]:
        warns.append("抽出にあるが VBP 未記載: " + ", ".join(map(e, report["not_in_vbp"])))
    if report.get("skipped_parent_common"):
        warns.append(
            "親共通パスをスキップ: "
            + ", ".join(e(s["file"]) for s in report["skipped_parent_common"])
        )
    for w in report.get("warnings") or []:
        warns.append(
            f"VBP 警告 ({e(w.get('kind'))}/{e(w.get('reason'))}): {e(w.get('raw'))}"
        )
    warn_html = "".join(f"<p class='warn'>⚠ {w}</p>" for w in warns)
    ver = ".".join(meta.get(k, "?") for k in ("MajorVer", "MinorVer", "RevisionVer"))
    obj_html = ""
    if report.get("objects"):
        obj_html = (
            "<br>Object: "
            + ", ".join(
                f"<code>{e(o['file'] or o['raw'])}</code>" for o in report["objects"]
            )
        )

    doc = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<title>{e(report['vbp'])} インベントリ</title>
<style>
body{{font-family:"Segoe UI",Meiryo,sans-serif;margin:2rem auto;max-width:1100px;line-height:1.5;color:#222}}
table{{border-collapse:collapse;margin:.5rem 0 1rem;width:100%}}
th,td{{border:1px solid #ccc;padding:.25rem .5rem;font-size:.85rem;text-align:left}}
th{{background:#f0f2f5}}
td.num{{text-align:right}}
code{{background:#f4f4f4;padding:0 .2rem}}
details{{border:1px solid #ddd;border-radius:6px;margin:.4rem 0;padding:.3rem .8rem}}
summary{{cursor:pointer;padding:.3rem 0}}
.warn{{color:#a00}}
.meta{{color:#555}}
.toolbar{{position:sticky;top:0;background:#fff;padding:.6rem 0;border-bottom:1px solid #eee;z-index:1;display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}}
.toolbar input{{flex:1;min-width:12rem;padding:.35rem .5rem;font-size:.9rem;border:1px solid #bbb;border-radius:4px}}
.toolbar button{{padding:.35rem .7rem;font-size:.85rem;cursor:pointer;border:1px solid #bbb;border-radius:4px;background:#f7f7f7}}
.toolbar .count{{color:#555;font-size:.8rem;white-space:nowrap}}
</style></head><body>
<h1>{e(report['vbp'])} インベントリ（VBP → ファイル → プロシージャ）</h1>
<p class="meta">Startup: <code>{e(meta.get('Startup', '?'))}</code> ／ Title: <code>{e(meta.get('Title', '?'))}</code> ／ Exe: <code>{e(meta.get('ExeName32', '?'))}</code><br>
Name: <code>{e(meta.get('Name', '?'))}</code> ／ Version: <code>{e(ver)}</code> ／ Command32: <code>{e(meta.get('Command32') or '—')}</code>{obj_html}<br>
ファイル {report['file_count']}（VBP 記載順 Form→Module→Class） ／ プロシージャ合計 {report['proc_total']}。
行頭のプロシージャ定義のみを機械抽出（呼び出し推定なし）。行番号は working/extracts の実ファイル基準。</p>
{warn_html}
<div class="toolbar">
  <input id="q" type="search" placeholder="検索: ファイル名 / VB_Name / プロシージャ名 / Const / Enum …" autocomplete="off">
  <button id="expandAll" type="button">全て開く</button>
  <button id="collapseAll" type="button">全て閉じる</button>
  <span class="count" id="count"></span>
</div>
<h2>目次</h2>
<table><tr><th>#</th><th>ファイル</th><th>種別</th><th>VB_Name</th><th>行数</th><th>Ctrl</th><th>Proc</th></tr>
{''.join(toc_rows)}</table>
<h2>ファイル別詳細</h2>
{''.join(sections)}
<script>
(function(){{
  var q=document.getElementById('q');
  var count=document.getElementById('count');
  var secs=Array.prototype.slice.call(document.querySelectorAll('details.filesec'));
  // textContent (not innerText): hidden sections still match on later queries.
  var hay=secs.map(function(s){{return (s.textContent||'').toLowerCase();}});
  // One hit per file: detail text is authoritative; TOC row follows via data-for.
  function apply(){{
    var t=q.value.trim().toLowerCase();
    var shown=0;
    secs.forEach(function(s,i){{
      var hit=!t||hay[i].indexOf(t)>=0;
      s.style.display=hit?'':'none';
      var row=document.querySelector('tr.tocrow[data-for="'+s.id+'"]');
      if(row) row.style.display=hit?'':'none';
      if(hit) shown++;
      if(t&&hit) s.open=true;
    }});
    count.textContent=t?(shown+' / '+secs.length+' 件一致'):(secs.length+' ファイル');
  }}
  q.addEventListener('input',apply);
  document.getElementById('expandAll').onclick=function(){{secs.forEach(function(s){{if(s.style.display!=='none')s.open=true;}});}};
  document.getElementById('collapseAll').onclick=function(){{secs.forEach(function(s){{s.open=false;}});}};
  apply();
}})();
</script>
</body></html>
"""
    out.write_text(doc, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    parser = argparse.ArgumentParser(description="VB6 project inventory (facts only)")
    parser.add_argument("extract_dir", type=Path)
    parser.add_argument("--vbp", type=Path, default=None, help="default: sole *.vbp in extract_dir")
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable the content-hash parse cache (working/.cache/)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Parse files in parallel with N workers (default 1; helps large trees)",
    )
    parser.add_argument(
        "--skip-parent-common",
        action="store_true",
        help="Skip VBP entries whose path climbs two or more parent dirs (..\\..)",
    )
    args = parser.parse_args(argv)

    root = args.extract_dir if args.extract_dir.is_absolute() else REPO_ROOT / args.extract_dir
    root = root.resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")
    vbp = args.vbp
    if vbp is None:
        cands = list(root.glob("*.vbp"))
        if len(cands) != 1:
            raise SystemExit(f"expected exactly one .vbp in {root}, found {len(cands)}")
        vbp = cands[0]

    report = build_report(
        root,
        vbp,
        use_cache=not args.no_cache,
        jobs=args.jobs,
        skip_parent_common=args.skip_parent_common,
    )

    out_dir = args.out_dir or reports_root()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = vbp.stem
    json_path = out_dir / f"{stem}_inventory.json"
    md_path = out_dir / f"{stem}_inventory.md"
    html_path = out_dir / f"{stem}_inventory.html"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_markdown(report, md_path)
    write_html(report, html_path)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "md": str(md_path),
                "html": str(html_path),
                "files": report["file_count"],
                "procs": report["proc_total"],
                "objects": len(report.get("objects") or []),
                "missing_in_extract": report["missing_in_extract"],
                "not_in_vbp": report["not_in_vbp"],
                "skipped_parent_common": report.get("skipped_parent_common") or [],
                "warnings": report.get("warnings") or [],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
