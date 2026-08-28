#!/usr/bin/env python3
"""Deep-read a VB6 .frm (Form) or .bas/.cls (surface; no designer live/dead).

検証→理解→実装サイクルの「理解」段で再利用する。足りない抽出・誤検知が出たら
ワンショットを増やさず、本ファイルを改定してから再実行すること。

Outputs:
  - skeleton JSON (live controls only) -> working/skeletons/<out_key>-skeleton.json
  - deep read report -> working/reports/<out_key>_deep_read.md

  out_key = deep_read_name_map[VB_Name] or lowercase VB_Name
  (fallback: file stem when VB_Name is missing)

Usage:
  python tools/frm_deep_read.py <frm_filename> --extract working/extracts/<stem>
  python tools/frm_deep_read.py Form1.frm --extract working/extracts/mini_vbp
"""

import argparse
import json
import pathlib
import re
import sys
from datetime import date

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from lib.config import (  # noqa: E402
    decode_vb6_bytes,
    extracts_root,
    load_config,
    optional_assign_markers,
    preferred_extract,
    reports_root,
    skeletons_root,
)
from lib.console import enable_utf8_stdio  # noqa: E402
from lib.show_style import (  # noqa: E402
    parse_lifetime_calls_in_line,
    parse_show_calls_in_line,
    self_show_style,
)
from lib.vbparse import iter_statements  # noqa: E402
from vb6_inventory import parse_surface  # noqa: E402

MODULE_SUFFIXES = {".bas", ".cls"}
FORM_SUFFIXES = {".frm"}

EXTRACT = extracts_root()  # overridden in main() via --extract
SKELETONS = skeletons_root()
REPORTS = reports_root()

EVENT_SUFFIXES = re.compile(
    r"^(\w+)_(Click|DblClick|Change|KeyDown|KeyPress|KeyUp|MouseDown|MouseMove|"
    r"MouseUp|Load|Unload|Activate|Deactivate|Resize|Paint|GotFocus|LostFocus|"
    r"Scroll|Timer|ItemClick|RowColChange|Validate|DropDown|OLEDragDrop|"
    r"OLEDragOver|OLEStartDrag|dblclick|keydown|mousedown|change|click|unload)$",
    re.IGNORECASE,
)

# Designer-leak font face names. These are not controls.
# Only faces seen in Japanese field .frm files; do not guess more.
FONT_FACE_BLACKLIST = frozenset({
    "ＭＳ Ｐゴシック",
    "ＭＳ ゴシック",
    "MS PGothic",
    "MS Gothic",
})

# show_map stays live-Sub only. unobserved is the old "dead" exclusion
# (do not widen the map when renaming no-caller Subs).
SHOW_MAP_EXCLUDED_STATUS = frozenset({"dead", "unobserved"})


def read_cp932(path: pathlib.Path) -> str:
    return decode_vb6_bytes(path.read_bytes())


def load_bas_text() -> str:
    parts = []
    for bas in sorted(EXTRACT.glob("*.bas")):
        parts.append(read_cp932(bas))
    return "\n".join(parts)


def load_project_code_text() -> str:
    """All .frm code sections + .bas (for cross-form ``Form.Control`` refs)."""
    parts = []
    for frm in sorted(EXTRACT.glob("*.frm")):
        text = read_cp932(frm)
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("Attribute VB_Name"):
                parts.append("\n".join(lines[i:]))
                break
    parts.append(load_bas_text())
    return "\n".join(parts)


# ── Controls ──────────────────────────────────────────────

def extract_controls(lines: list[str]):
    """Parse Begin..End control tree.

    Important: match ActiveX too (e.g. MSFlexGridLib.MSFlexGrid). Skipping those
    causes their End to pop the parent and corrupt Form Width/Height / depth.
    BeginProperty/EndProperty are ignored (not Begin <kind> <name>).
    Nested Left/Top are parent-relative; abs_left/abs_top are form-client absolute.
    Form size prefers ClientWidth/ClientHeight over outer Width/Height.
    Form-level ``MDIChild`` is copied into ``form_info`` for show_style heuristics.
    """
    form_info = {
        "name": "", "caption": "",
        "width": None, "height": None,
        "clientWidth": None, "clientHeight": None,
        "kind": "",
        "mdi_child": None,
    }
    controls = []
    stack: list[dict] = []

    for i, line in enumerate(lines):
        s = line.strip()

        # Begin VB.CommandButton Foo  /  Begin MSFlexGridLib.MSFlexGrid MS1
        m = re.match(r"Begin\s+(\S+)\s+(\S+)\s*$", s)
        if m and not s.startswith("BeginProperty"):
            parent = stack[-1] if stack else None
            stack.append({
                "kind": m.group(1), "name": m.group(2), "line": i + 1,
                "caption": "", "left": None, "top": None,
                "width": None, "height": None,
                "clientWidth": None, "clientHeight": None,
                "depth": len(stack),
                "parent": parent["name"] if parent else None,
                "abs_left": 0, "abs_top": 0,
                "index": None, "visible": True, "enabled": True,
                "mdi_child": None,
            })
            continue

        if s == "End" and stack:
            ctrl = stack.pop()
            # Nested Left/Top are parent-relative. Parents already have Left/Top
            # (VB6 writes them before nested Begin). Form/MDIForm origin = 0,0.
            al = ctrl["left"] or 0
            at = ctrl["top"] or 0
            for p in stack:
                if p["kind"] in ("VB.Form", "VB.MDIForm"):
                    continue
                al += p["left"] or 0
                at += p["top"] or 0
            ctrl["abs_left"] = al
            ctrl["abs_top"] = at

            if ctrl["kind"] in ("VB.Form", "VB.MDIForm"):
                cw = ctrl.get("clientWidth")
                ch = ctrl.get("clientHeight")
                form_info = {
                    "name": ctrl["name"],
                    "caption": ctrl["caption"],
                    "width": cw if cw is not None else ctrl["width"],
                    "height": ch if ch is not None else ctrl["height"],
                    "clientWidth": cw,
                    "clientHeight": ch,
                    "kind": ctrl["kind"],
                    "mdi_child": ctrl.get("mdi_child"),
                }
            else:
                controls.append(ctrl)
            continue

        if stack:
            cur = stack[-1]
            cm = re.match(r'Caption\s*=\s*"([^"]*)"', s)
            if cm:
                cur["caption"] = cm.group(1)
            for prop in ("Left", "Top", "Width", "Height"):
                pm = re.match(rf"{prop}\s*=\s*(-?\d+)", s)
                if pm:
                    cur[prop.lower()] = int(pm.group(1))
            for prop, key in (
                ("ClientWidth", "clientWidth"),
                ("ClientHeight", "clientHeight"),
            ):
                pm = re.match(rf"{prop}\s*=\s*(-?\d+)", s)
                if pm:
                    cur[key] = int(pm.group(1))
            im = re.match(r"Index\s*=\s*(\d+)", s)
            if im:
                cur["index"] = int(im.group(1))
            # VB6: Visible/Enabled = 0 'False
            vm = re.match(r"Visible\s*=\s*(-?\d+)", s)
            if vm:
                cur["visible"] = vm.group(1) != "0"
            em = re.match(r"Enabled\s*=\s*(-?\d+)", s)
            if em:
                cur["enabled"] = em.group(1) != "0"
            # Form / control MDIChild (typically on the Form root)
            mm = re.match(r"MDIChild\s*=\s*(-?\d+)", s, re.IGNORECASE)
            if mm:
                cur["mdi_child"] = mm.group(1) != "0"

    return form_info, controls


# ── Events ────────────────────────────────────────────────

def _assign_value_re(markers: list[str]) -> re.Pattern[str] | None:
    if not markers:
        return None
    alts = "|".join(re.escape(m) for m in markers)
    return re.compile(rf'(?:{alts})\s*=\s*"([^"]+)"')


def extract_events(lines: list[str], assign_markers: list[str] | None = None):
    events = []
    in_code = False
    current = None
    if assign_markers is None:
        assign_markers = optional_assign_markers()
    marker_re = _assign_value_re(assign_markers)

    for i, line in enumerate(lines):
        s = line.strip()
        if not in_code:
            if s.startswith("Attribute VB_Name"):
                in_code = True
            continue

        # VB6: Private Static Sub Foo( も拾う（processCalender Label2_Click 等）
        sub_m = re.match(
            r"(Private\s+|Public\s+)?(Static\s+)?(Sub|Function|Property\s+\w+)\s+(\w+)\s*\(",
            s,
        )
        if sub_m:
            if current:
                current["end_line"] = i
                current["size"] = current["end_line"] - current["start_line"] + 1
                events.append(current)
            scope = ((sub_m.group(1) or "") + (sub_m.group(2) or "")).strip()
            current = {
                "name": sub_m.group(4),
                "kind": sub_m.group(3),
                "scope": scope,
                "start_line": i + 1, "end_line": None, "size": 0,
                "comment_lines": 0,
            }
            continue

        end_m = re.match(r"End\s+(Sub|Function|Property)", s)
        if end_m and current:
            current["end_line"] = i + 1
            current["size"] = current["end_line"] - current["start_line"] + 1
            events.append(current)
            current = None
            continue

        if current and s.startswith("'"):
            current["comment_lines"] += 1
            continue

        if current and s and not s.startswith("'"):
            if marker_re:
                pm = marker_re.search(s)
                if pm:
                    current.setdefault("para_sets", []).append(pm.group(1))

    if current:
        current["end_line"] = len(lines)
        current["size"] = current["end_line"] - current["start_line"] + 1
        events.append(current)

    for ev in events:
        ev.setdefault("shows", [])
        ev.setdefault("para_sets", [])
        ev.setdefault("show_calls", [])
        ev.setdefault("lifetime_calls", [])

    _attach_show_and_lifetime(events, lines)

    for ev in events:
        # dedupe preserving order
        ev["shows"] = list(dict.fromkeys(ev["shows"]))
        ev["para_sets"] = list(dict.fromkeys(ev["para_sets"]))

    return events


def _attach_show_and_lifetime(events: list[dict], lines: list[str]) -> None:
    """Attach Show / Load / Unload surface to the Sub that contains the line.

    One colon-split statement at a time. Does not resolve targets or graph.
    """
    if not events:
        return
    for stmt in iter_statements(lines):
        if stmt.kind != "stmt":
            continue
        owner = None
        for ev in events:
            start = ev.get("start_line") or 0
            end = ev.get("end_line") or 0
            if start <= stmt.phys_start <= end:
                owner = ev
                break
        if owner is None:
            continue
        for call in parse_show_calls_in_line(stmt.text, stmt.phys_start):
            owner["shows"].append(call["target"])
            owner["show_calls"].append(call)
        for hit in parse_lifetime_calls_in_line(stmt.text, stmt.phys_start):
            owner["lifetime_calls"].append(hit)


def analyze_menus(controls: list[dict], events: list[dict]):
    """Flag menus that are invisible/disabled or lack *_Click (Caption-only traps).

    VB6 identifiers are case-insensitive: menu ``SAG`` ↔ handler ``sag_Click``.
    """
    event_names = {e["name"].lower() for e in events}
    findings = []
    for c in controls:
        if c["kind"] != "VB.Menu":
            continue
        click = f"{c['name']}_Click".lower()
        has_click = click in event_names
        dead_ui = (not c.get("visible", True)) or (not c.get("enabled", True))
        if dead_ui or not has_click:
            findings.append({
                "name": c["name"],
                "caption": c.get("caption", ""),
                "line": c["line"],
                "visible": c.get("visible", True),
                "enabled": c.get("enabled", True),
                "has_click": has_click,
                "warn": (
                    "メニューを遷移に使わないこと"
                    if dead_ui or not has_click
                    else ""
                ),
            })
    return findings


def _menu_has_click(name: str, event_names: set[str]) -> bool:
    return f"{name}_Click".lower() in event_names


def _count_menu_nodes(tree: list[dict]) -> int:
    return sum(1 + _count_menu_nodes(n.get("children") or []) for n in tree)


def flatten_menu_tree(tree: list[dict], depth: int = 0) -> list[dict]:
    """Depth-first rows for reports. Does not mutate the tree."""
    rows: list[dict] = []
    for node in tree:
        rows.append({
            "name": node.get("name") or "",
            "caption": node.get("caption") or "",
            "line": node.get("line"),
            "visible": node.get("visible", True),
            "enabled": node.get("enabled", True),
            "has_click": bool(node.get("has_click")),
            "parent": node.get("parent") or "",
            "depth": depth,
            "index": node.get("index"),
        })
        rows.extend(flatten_menu_tree(node.get("children") or [], depth + 1))
    return rows


def build_menu_tree(controls: list[dict], events: list[dict] | None = None) -> list[dict]:
    """Designer menu tree: parent/child, Caption, Visible/Enabled.

    Designer values only. Runtime ``Enabled =`` / ``Visible =`` belong in
    layout and are not mixed in. Every ``VB.Menu`` is included (not just
    warnings). ``has_click`` is a fact (``Name_Click`` exists), not a warn.
    """
    menus = [c for c in controls if c.get("kind") == "VB.Menu"]
    if not menus:
        return []
    event_names = {e["name"].lower() for e in (events or []) if e.get("name")}
    nodes: list[dict] = []
    for c in menus:
        node = {
            "name": c.get("name") or "",
            "caption": c.get("caption") or "",
            "line": c.get("line"),
            "visible": c.get("visible", True),
            "enabled": c.get("enabled", True),
            "has_click": _menu_has_click(str(c.get("name") or ""), event_names),
            "parent": c.get("parent") or "",
            "children": [],
        }
        if c.get("index") is not None:
            node["index"] = c["index"]
        nodes.append(node)

    by_name: dict[str, list[dict]] = {}
    for node in nodes:
        by_name.setdefault(str(node["name"]).lower(), []).append(node)

    roots: list[dict] = []
    for node in nodes:
        pname = str(node.get("parent") or "").lower()
        candidates = [
            p for p in by_name.get(pname, [])
            if (p.get("line") or 0) < (node.get("line") or 0)
        ]
        if candidates:
            parent = max(candidates, key=lambda p: p.get("line") or 0)
            parent["children"].append(node)
        else:
            roots.append(node)
    return roots


def extract_show_map(events: list[dict]):
    """Live-Sub Show / marker rows. ``unobserved`` is excluded like old ``dead``."""
    rows = []
    for e in events:
        if e.get("status") in SHOW_MAP_EXCLUDED_STATUS:
            continue
        if not e.get("shows") and not e.get("para_sets") and not e.get("show_calls"):
            continue
        rows.append({
            "sub": e["name"],
            "line": e["start_line"],
            "shows": e.get("shows", []),
            "para_sets": e.get("para_sets", []),
            "calls": e.get("show_calls", []),
        })
    return rows


def form_show_style_block(form_info: dict) -> dict:
    """Attach self show_style candidate to the form being deep-read."""
    block = self_show_style(
        mdi_child=form_info.get("mdi_child"),
        form_kind=form_info.get("kind") or "",
    )
    block["form"] = form_info.get("name") or ""
    return block


# ── Dead code ─────────────────────────────────────────────

def classify_events(
    events: list[dict], code_text: str, bas_text: str,
    controls: list[dict] | None = None, form_name: str = "",
):
    """Classify Subs as live / unobserved / dead (orphan).

    Event-named Subs are live when the owning control exists in the designer
    (case-insensitive). Orphan handlers stay live only when called as a
    normal Sub. A general Sub with no regex-observed caller is ``unobserved``
    (not unreachable). ``dead`` is reserved for orphan handlers with no
    observed call.
    """
    search_text = code_text + "\n" + bas_text
    control_names = {c["name"].lower() for c in (controls or [])}
    self_owners = {"form", "mdiform"}
    if form_name:
        self_owners.add(form_name.lower())

    def has_real_calls(name: str) -> bool:
        pattern = re.compile(
            rf"(?:Call\s+)?(?<!\bSub\s)(?<!\bFunction\s){re.escape(name)}\s*[\(\s\n]",
            re.IGNORECASE,
        )
        for m in pattern.finditer(search_text):
            ctx = search_text[max(0, m.start() - 30):m.start()]
            if "Sub " not in ctx and "Function " not in ctx:
                return True
        return False

    for ev in events:
        m = EVENT_SUFFIXES.match(ev["name"])
        ev["is_event"] = bool(m)
        if m:
            owner = m.group(1).lower()
            if owner in control_names or owner in self_owners:
                ev["status"] = "live"
            elif has_real_calls(ev["name"]):
                ev["status"] = "live"
                ev["dead_reason"] = ""
                ev["note"] = "orphan handler, called as sub"
            else:
                ev["status"] = "dead"
                ev["dead_reason"] = "orphan (control not in designer)"
            continue

        ev["status"] = "live" if has_real_calls(ev["name"]) else "unobserved"
        if ev["status"] == "unobserved":
            ev["dead_reason"] = "no_caller_observed"

    return events


def classify_controls(controls, code_text, project_text, events=None, form_name=""):
    """Mark control live if referenced in code OR it owns a live event handler.

    Matching rules (avoid false positives from other forms' same-named controls):
      1. Event owner (e.g. Command1_Click → Command1)
      2. Unqualified ``ControlName`` in **this** form's code only
      3. Qualified ``FormName.ControlName`` anywhere in project (.frm code + .bas)

    Note: ``\\bCommand1\\b`` does NOT match ``Command1_Click`` (underscore is a
    word char). Event owners must be treated as live explicitly.
    """
    event_owners: set[str] = set()
    for ev in events or []:
        if ev.get("status") in SHOW_MAP_EXCLUDED_STATUS:
            continue
        m = EVENT_SUFFIXES.match(ev["name"])
        if m:
            event_owners.add(m.group(1))

    owners_lower = {o.lower() for o in event_owners}
    for ctrl in controls:
        name = ctrl["name"]
        if name in FONT_FACE_BLACKLIST:
            ctrl["live"] = False
            continue
        # VB6 identifiers are case-insensitive (designer label3 ↔ code Label3)
        if name.lower() in owners_lower:
            ctrl["live"] = True
            continue
        own_hit = bool(
            re.search(rf"\b{re.escape(name)}\b", code_text, re.IGNORECASE)
        )
        qualified_hit = False
        if form_name:
            qualified_hit = bool(
                re.search(
                    rf"\b{re.escape(form_name)}\.{re.escape(name)}\b",
                    project_text,
                    re.IGNORECASE,
                )
            )
        ctrl["live"] = own_hit or qualified_hit
    return controls


# ── Data paths ────────────────────────────────────────────

def extract_declared_apis(*texts: str) -> set[str]:
    """Names of ``Declare Function/Sub`` Win32 APIs (frm + bas)."""
    names: set[str] = set()
    for text in texts:
        for m in re.finditer(
            r"Declare\s+(?:Function|Sub)\s+(\w+)", text, re.IGNORECASE
        ):
            names.add(m.group(1))
    return names


def extract_data_paths(lines: list[str], api_names: set[str] | None = None):
    """I/O surface of the form.

    - open: ``Open ... As #1`` and ``Open ... As #fileNum`` (variable channel)
    - api: call sites of Declare'd APIs (ShellExecute, SetWindowPos, ...)
    - fileops: Kill / Name..As statements (file delete/rename)
    - other: non-dat file literals (.csv/.txt/.tbl/.ter/.nmb/.hou/.ch)
    """
    api_names = api_names or set()
    paths = {
        "dat": [], "mdb": [], "shell": [], "open": [],
        "api": [], "fileops": [], "other": [],
    }
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("'"):
            continue
        ln = i + 1
        if re.search(r"\.dat", s, re.IGNORECASE):
            paths["dat"].append({"line": ln, "text": s[:200]})
        if re.search(r"\.mdb", s, re.IGNORECASE):
            paths["mdb"].append({"line": ln, "text": s[:200]})
        if re.search(r"\bShell\b", s):
            paths["shell"].append({"line": ln, "text": s[:200]})
        if re.match(r".*\bOpen\b.*\bAs\s*#\s*\w+", s, re.IGNORECASE):
            paths["open"].append({"line": ln, "text": s[:200]})
        if api_names and not re.match(r"(Private\s+|Public\s+)?Declare\b", s, re.IGNORECASE):
            for name in api_names:
                if re.search(rf"\b{re.escape(name)}\b", s):
                    paths["api"].append({"line": ln, "text": s[:200], "api": name})
                    break
        if re.match(r"(Call\s+)?Kill\b", s, re.IGNORECASE) or re.match(
            r"Name\s+[^=(].*\sAs\s", s, re.IGNORECASE
        ):
            paths["fileops"].append({"line": ln, "text": s[:200]})
        if re.search(r"\.(csv|txt|tbl|ter|nmb|hou|ch)\b", s, re.IGNORECASE):
            paths["other"].append({"line": ln, "text": s[:200]})
    return paths


def extract_para(lines: list[str], markers: list[str] | None = None):
    """Optional assignment-marker scan. Kit default markers are empty."""
    if markers is None:
        markers = optional_assign_markers()
    hits = []
    if not markers:
        return hits
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("'"):
            continue
        for marker in markers:
            if marker in s:
                hits.append({"line": i + 1, "text": s[:200], "marker": marker})
                break
    return hits


# VB6 line labels that collide with block syntax (not GoTo targets we care about).
_GOTO_RESERVED_LABELS = frozenset({"else", "case"})
_OPEN_AS_RE = re.compile(r".*\bOpen\b.*\bAs\s*#\s*\w+", re.IGNORECASE)
_LABEL_RE = re.compile(r"^(\w+)\s*:\s*('.*)?$", re.IGNORECASE)
# Bare / trailing-comment GoTo (not On Error GoTo, not Then/Else GoTo).
_UNCOND_GOTO_RE = re.compile(r"^GoTo\s+(\w+)\s*('.*)?$", re.IGNORECASE)
_COND_GOTO_RE = re.compile(
    r"\b(?:Then|Else)\s+GoTo\s+(\w+)\b", re.IGNORECASE
)
_ON_ERROR_GOTO_RE = re.compile(r"\bOn\s+Error\s+GoTo\b", re.IGNORECASE)
_ON_ERROR_GOTO_TARGET_RE = re.compile(
    r"^On\s+Error\s+GoTo\s+(\w+)\s*('.*)?$", re.IGNORECASE
)
_GOSUB_RE = re.compile(r"^GoSub\s+(\w+)\s*('.*)?$", re.IGNORECASE)
_COND_GOSUB_RE = re.compile(
    r"\b(?:Then|Else)\s+GoSub\s+(\w+)\b", re.IGNORECASE
)
# Only these kinds open a skip span. on_error / gosub stay on the label map.
SKIP_SPAN_GOTO_KINDS = frozenset({"unconditional", "conditional"})

# Statements worth flagging when skipped by a forward GoTo (I/O · Call · Load).
# Assignments / Dim are omitted to avoid flooding; tick still reads the span.
_SKIP_STMT_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("open", _OPEN_AS_RE),
    ("line_input", re.compile(r"\bLine\s+Input\s+#", re.IGNORECASE)),
    ("input_file", re.compile(r"\bInput\s+#", re.IGNORECASE)),
    ("print_file", re.compile(r"\bPrint\s+#", re.IGNORECASE)),
    ("write_file", re.compile(r"\bWrite\s+#", re.IGNORECASE)),
    ("get_file", re.compile(r"\bGet\s+#", re.IGNORECASE)),
    ("put_file", re.compile(r"\bPut\s+#", re.IGNORECASE)),
    ("close", re.compile(r"\bClose\s+#", re.IGNORECASE)),
    ("kill", re.compile(r"\bKill\b", re.IGNORECASE)),
    ("shell", re.compile(r"\bShell\b", re.IGNORECASE)),
    ("call", re.compile(r"^(?:Call\s+)\w+", re.IGNORECASE)),
    ("unload", re.compile(r"\bUnload\b", re.IGNORECASE)),
    ("load", re.compile(r"^Load\s+\w+", re.IGNORECASE)),
    ("msgbox", re.compile(r"\bMsgBox\b", re.IGNORECASE)),
    ("gosub", _GOSUB_RE),
]


def classify_goto_skip_stmt(text: str) -> str | None:
    """Return stmt_kind if the line is interesting when GoTo-skipped, else None."""
    s = text.strip()
    if not s or s.startswith("'"):
        return None
    code = s.split("'")[0].strip()
    if not code:
        return None
    if _UNCOND_GOTO_RE.match(code) or _ON_ERROR_GOTO_RE.search(code):
        return None
    if _LABEL_RE.match(code):
        return None
    for kind, pattern in _SKIP_STMT_RULES:
        if pattern.search(code):
            return kind
    return None


def _open_path_fragment(text: str) -> str:
    """Best-effort path snippet from an Open statement (quoted literals preferred)."""
    quotes = re.findall(r'"([^"]*)"', text)
    if quotes:
        # Prefer the fragment that looks like a file/path.
        for q in reversed(quotes):
            if re.search(r"\.\w{1,8}\b|\\|/", q):
                return q[:120]
        return quotes[-1][:120]
    return text[:120]


def _scan_sub_gotos_and_labels(
    lines: list[str], start: int, end: int,
) -> tuple[dict[str, int], list[tuple[int, str, str]]]:
    """Return (labels lower→line, gotos) for body lines after Sub header."""
    body = lines[start:end]
    labels: dict[str, int] = {}
    gotos: list[tuple[int, str, str]] = []
    for offset, raw in enumerate(body):
        ln = start + 1 + offset
        s = raw.strip()
        if not s or s.startswith("'"):
            continue
        lm = _LABEL_RE.match(s)
        if lm:
            name = lm.group(1)
            if name.lower() not in _GOTO_RESERVED_LABELS:
                labels.setdefault(name.lower(), ln)
            continue
        oem = _ON_ERROR_GOTO_TARGET_RE.match(s)
        if oem:
            gotos.append((ln, oem.group(1), "on_error"))
            continue
        gsm = _GOSUB_RE.match(s)
        if gsm:
            gotos.append((ln, gsm.group(1), "gosub"))
            continue
        um = _UNCOND_GOTO_RE.match(s)
        if um:
            gotos.append((ln, um.group(1), "unconditional"))
            continue
        code_only = s.split("'")[0]
        if _ON_ERROR_GOTO_RE.search(code_only):
            continue
        cm = _COND_GOTO_RE.search(code_only)
        if cm:
            gotos.append((ln, cm.group(1), "conditional"))
            continue
        cgs = _COND_GOSUB_RE.search(code_only)
        if cgs:
            gotos.append((ln, cgs.group(1), "gosub_conditional"))
    return labels, gotos


def collect_goto_label_maps(
    lines: list[str], events: list[dict] | None = None,
) -> list[dict]:
    """Per-Sub GoTo / label inventory (facts only; no reachability proof)."""
    if events is None:
        events = extract_events(lines)
    maps: list[dict] = []
    for ev in events:
        start, end = ev.get("start_line"), ev.get("end_line")
        if not start or not end or end < start:
            continue
        labels, gotos = _scan_sub_gotos_and_labels(lines, start, end)
        if not labels and not gotos:
            continue
        maps.append({
            "sub": ev["name"],
            "status": ev.get("status") or "",
            "labels": [
                {"name": name, "line": ln}
                for name, ln in sorted(labels.items(), key=lambda x: x[1])
            ],
            "gotos": [
                {"line": ln, "target": tgt, "kind": kind}
                for ln, tgt, kind in gotos
            ],
        })
    return maps


def find_goto_skipped_stmts(
    lines: list[str], events: list[dict] | None = None,
) -> list[dict]:
    """Mark interesting stmts skipped by a forward GoTo in the same Sub.

    Static approx → **到達不能候補** only (never asserted dead):

    - unconditional ``GoTo L`` — fall-through never reaches the stmt
    - ``If … Then GoTo L`` / ``Else GoTo L`` — skipped on that branch

    Interesting kinds: file I/O (Open/Close/Kill/Print#/…), Call, Shell,
    Load/Unload, MsgBox. Dim/assignments are omitted.

    ``On Error GoTo`` and ``GoSub`` are recorded on the label map but do
    not open a skip span (the Open still runs; Return comes back).

    Not modeled: jump *into* the span, Resume, multi-label graphs,
    backward GoTo.
    """
    if events is None:
        events = extract_events(lines)

    findings: list[dict] = []
    seen: set[tuple[str, int, int, int]] = set()

    for ev in events:
        start = ev.get("start_line")
        end = ev.get("end_line")
        if not start or not end or end < start:
            continue
        body = lines[start:end]
        labels, gotos = _scan_sub_gotos_and_labels(lines, start, end)

        for goto_line, label_name, kind in gotos:
            if kind not in SKIP_SPAN_GOTO_KINDS:
                continue
            label_line = labels.get(label_name.lower())
            if label_line is None or label_line <= goto_line:
                continue

            for offset, raw in enumerate(body):
                ln = start + 1 + offset
                if not (goto_line < ln < label_line):
                    continue
                s = raw.strip()
                stmt_kind = classify_goto_skip_stmt(s)
                if not stmt_kind:
                    continue
                key = (ev["name"], goto_line, label_line, ln)
                if key in seen:
                    continue
                seen.add(key)
                entry = {
                    "sub": ev["name"],
                    "goto_line": goto_line,
                    "label": label_name,
                    "label_line": label_line,
                    "stmt_line": ln,
                    "stmt_text": s[:200],
                    "stmt_kind": stmt_kind,
                    "goto_kind": kind,
                    "path_fragment": (
                        _open_path_fragment(s) if stmt_kind == "open" else ""
                    ),
                    # Compat aliases used by older report/tests
                    "open_line": ln,
                    "open_text": s[:200],
                }
                findings.append(entry)

    findings.sort(key=lambda f: (f["stmt_line"], f["goto_line"]))
    return findings


def find_goto_skipped_opens(
    lines: list[str], events: list[dict] | None = None,
) -> list[dict]:
    """Open-only subset of :func:`find_goto_skipped_stmts` (compat wrapper)."""
    return [
        f for f in find_goto_skipped_stmts(lines, events)
        if f.get("stmt_kind") == "open"
    ]


def annotate_offscreen(form_info: dict, controls: list[dict]):
    """Flag controls placed outside the form client area (design-time).

    VB6 forms in this VBP hide working controls off-screen (form9 calendar
    grid, PrSet Check1, Form15 Text1). They are unreachable by mouse at
    runtime even though Visible=True. Annotation only — live/dead judgment
    is unchanged (code may still read/write them).
    """
    cw = form_info.get("width")
    ch = form_info.get("height")
    for c in controls:
        if c["kind"] in ("VB.Menu", "VB.Timer") or cw is None or ch is None:
            c["offscreen"] = False
            continue
        w = c.get("width") or 0
        h = c.get("height") or 0
        c["offscreen"] = (
            c["abs_left"] >= cw or c["abs_top"] >= ch
            or c["abs_left"] + w <= 0 or c["abs_top"] + h <= 0
        )
    return controls


CONTAINER_KINDS = ("VB.Frame", "VB.PictureBox")


def _find_parent(controls: list[dict], child: dict):
    """Resolve a child's design-time parent control (arrays disambiguated by center)."""
    pname = (child.get("parent") or "").lower()
    if not pname:
        return None
    hits = [c for c in controls if c["name"].lower() == pname and c is not child]
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0]
    cx = child["abs_left"] + (child.get("width") or 0) / 2
    cy = child["abs_top"] + (child.get("height") or 0) / 2
    for h in hits:
        if (
            h["abs_left"] <= cx <= h["abs_left"] + (h.get("width") or 0)
            and h["abs_top"] <= cy <= h["abs_top"] + (h.get("height") or 0)
        ):
            return h
    return hits[0]


def annotate_hidden_ancestor(controls: list[dict]):
    """Flag children of a permanently invisible container.

    Only dead containers count: a code-referenced Frame/PictureBox can be
    switched to Visible=True at runtime, so its children must stay in the
    skeleton as normally visible. A container with Visible=0 and zero code
    references can never appear, so its children are unreachable at runtime
    (``ancestor_hidden`` / ``ancestor_hidden_by``).
    """
    for c in controls:
        if c["kind"] in ("VB.Menu", "VB.Timer"):
            continue
        guard = 0
        node = c
        while guard < 16:
            guard += 1
            parent = _find_parent(controls, node)
            if parent is None:
                break
            if (
                parent["kind"] in CONTAINER_KINDS
                and parent.get("visible", True) is False
                and not parent.get("live", False)
            ):
                c["ancestor_hidden"] = True
                c["ancestor_hidden_by"] = parent["name"]
                break
            node = parent
    return controls


# ── Skeleton output ───────────────────────────────────────

CAT_MAP = {
    "VB.Menu": "menus", "VB.CommandButton": "buttons", "VB.Frame": "frames",
    "VB.Label": "labels", "VB.TextBox": "textboxes", "VB.CheckBox": "checkboxes",
    "VB.ComboBox": "combos", "VB.ListBox": "listboxes", "VB.OptionButton": "options",
    "VB.PictureBox": "pictures", "VB.FileListBox": "files", "VB.DirListBox": "files",
    "VB.Timer": "timers",
    "MSFlexGridLib.MSFlexGrid": "grids",
}


def build_skeleton(form_info, controls):
    """Skeleton = code-live controls + visible on-screen statics.

    Static labels/frames with no code reference are still real design-time UI
    (Form14 has 13 controls and zero code). Excluding them broke UI fidelity
    (form9 Label12(1) regression). ``code_ref: false`` marks display-only.
    """
    skel = {"form": form_info}
    for ctrl in controls:
        code_live = bool(ctrl.get("live", True))
        display_only = (
            not code_live
            and ctrl.get("visible", True)
            and not ctrl.get("offscreen", False)
            and ctrl["kind"] not in ("VB.Menu", "VB.Timer")
        )
        if not code_live and not display_only:
            continue
        entry = {k: v for k, v in ctrl.items() if k != "live"}
        entry["code_ref"] = code_live
        cat = CAT_MAP.get(ctrl["kind"], "others")
        skel.setdefault(cat, []).append(entry)
    return {k: v for k, v in skel.items() if v or k == "form"}


# ── Report output ─────────────────────────────────────────

def write_report(
    report_path, frm_filename, form_info, controls, events, data_paths, para_hits,
    total_lines, menu_findings, show_map, source_label=None,
    goto_skipped_opens=None,
    show_style=None,
    goto_skipped_stmts=None,
    goto_label_maps=None,
    menu_tree=None,
    assign_markers=None,
):
    live = [c for c in controls if c.get("live")]
    dead = [c for c in controls if not c.get("live")]
    live_events = [e for e in events if e["status"] == "live"]
    unobserved_events = [e for e in events if e["status"] == "unobserved"]
    dead_events = [e for e in events if e["status"] == "dead"]
    events_sorted = sorted(live_events, key=lambda e: e["size"], reverse=True)
    markers = list(assign_markers or [])
    show_marker_col = bool(markers) or any(
        r.get("para_sets") for r in (show_map or [])
    )
    src = source_label or frm_filename
    style = show_style or form_show_style_block(form_info)
    skipped = list(goto_skipped_stmts or goto_skipped_opens or [])
    goto_maps = list(goto_label_maps or [])

    md = []
    md.append(f"# {form_info['name']}（{frm_filename}）深読みレポート\n\n")
    md.append(f"日付: {date.today().isoformat()}（デッドコード除外済み）\n")
    md.append(f"ソース: `{src}`（CP932, {total_lines}行）\n")
    md.append(f"Form Caption: `{form_info['caption']}`\n\n")
    md.append(f"> コントロール: {len(controls)} 全体 → **{len(live)} ライブ** / {len(dead)} デッド（コード未参照）\n")
    md.append(
        f"> イベント: {len(events)} 全体 → **{len(live_events)} ライブ**"
        f" / {len(unobserved_events)} 未観測"
        f" / {len(dead_events)} デッド（orphan）\n\n"
    )
    # 本ツールは .frm 単体解析。他 .frm/.bas からの参照は見えないため、
    # イベント 0 や unobserved を「孤立・到達不能」と即断させない注記を必ず出す。
    md.append(
        "> **範囲**: 本レポートはこの .frm 単体の解析。他 .frm/.bas からの参照"
        "（`Show` の呼び元・外部 Sub によるコントロール操作）は対象外。"
        "イベント数 0 や `unobserved` を孤立・到達不能と即断しない"
        f"{'（イベント 0 でも外部から Load / 操作される場合がある）。' if not live_events else '。'}\n\n"
    )

    md.append("## show_style（候補・ヒューリスティック）\n\n")
    md.append(
        "> 再実装の見せ方候補。断定しない。規約: "
        "`docs/reimplementation-handoff.md`。"
        " `vbModal`→`modal_overlay` / `MDIChild`→`mdi_child` / それ以外は `unknown`。\n\n"
    )
    md.append(
        f"- **この Form 自身**: `{style.get('show_style', 'unknown')}`"
        f" （confidence={style.get('confidence', 'none')}）"
    )
    if style.get("evidence"):
        md.append(f" — 証拠: `{style['evidence']}`")
    if style.get("note"):
        md.append(f" — {style['note']}")
    md.append("\n")
    if form_info.get("mdi_child") is not None:
        md.append(
            f"- デザイナ `MDIChild`: "
            f"{'True' if form_info.get('mdi_child') else 'False'}\n"
        )
    if form_info.get("kind"):
        md.append(f"- `Begin` kind: `{form_info['kind']}`\n")
    md.append("\n")

    tree = list(menu_tree or [])
    if tree:
        md.append("## メニュー木（デザイナ値）\n\n")
        md.append(
            "> 親子・Caption・Visible/Enabled は Begin ブロックの値。"
            "実行時の `Enabled =` / `Visible =` は layout を見る（混ぜない）。\n\n"
        )
        md.append(
            "| name | parent | Caption | Vis | En | Click | L |\n"
            "|---|---|---|---|---|---|---|\n"
        )
        for row in flatten_menu_tree(tree):
            indent = "—" * row["depth"]
            name = f"{indent}`{row['name']}`" if indent else f"`{row['name']}`"
            parent = f"`{row['parent']}`" if row["parent"] else "—"
            md.append(
                f"| {name} | {parent} | {row['caption'] or '（空）'} | "
                f"{'Y' if row['visible'] else 'N'} | "
                f"{'Y' if row['enabled'] else 'N'} | "
                f"{'Y' if row['has_click'] else 'N'} | {row['line']} |\n"
            )
        md.append("\n")

    if menu_findings:
        md.append("## メニュー警告（Invisible / Disabled / Click 無し）\n\n")
        md.append("> Caption だけ見て遷移を付けないこと（Caption-only navigation trap）。\n\n")
        md.append("| name | Caption | Vis | En | Click | L |\n|---|---|---|---|---|---|\n")
        for f in menu_findings:
            md.append(
                f"| `{f['name']}` | {f['caption'] or '（空）'} | "
                f"{'Y' if f['visible'] else 'N'} | {'Y' if f['enabled'] else 'N'} | "
                f"{'Y' if f['has_click'] else '**N**'} | {f['line']} |\n"
            )

    if show_map:
        if show_marker_col:
            md.append("\n## Form.Show / 代入マーカー マップ（ライブ Sub）\n\n")
            md.append(
                "| Sub | L | target | arg | show_style | 代入 |\n"
                "|---|---|---|---|---|---|\n"
            )
        else:
            md.append("\n## Form.Show マップ（ライブ Sub）\n\n")
            md.append("| Sub | L | target | arg | show_style |\n|---|---|---|---|---|\n")
        for r in show_map[:40]:
            paras = ", ".join(f'`"{p}"`' for p in r["para_sets"]) or "—"
            marker_cell = f" | {paras}" if show_marker_col else ""
            calls = r.get("calls") or []
            if calls:
                for c in calls:
                    md.append(
                        f"| `{r['sub']}` | {c.get('line', r['line'])} | "
                        f"`{c['target']}` | {c.get('arg') or '—'} | "
                        f"`{c.get('show_style', 'unknown')}`{marker_cell} |\n"
                    )
            elif r.get("shows"):
                shows = ", ".join(f"`{s}`" for s in r["shows"])
                md.append(
                    f"| `{r['sub']}` | {r['line']} | {shows} | — | "
                    f"`unknown`{marker_cell} |\n"
                )
            else:
                md.append(
                    f"| `{r['sub']}` | {r['line']} | — | — | —{marker_cell} |\n"
                )
        if len(show_map) > 40:
            md.append(f"\n他 {len(show_map) - 40} 件省略\n")

    lifetime_rows = []
    for ev in events:
        for hit in ev.get("lifetime_calls") or []:
            lifetime_rows.append({**hit, "sub": ev.get("name")})
    if lifetime_rows:
        md.append("\n## Load/Unload 文面\n\n")
        md.append(
            "> 文面の列挙。ターゲットは解決しない。GoTo 飛び越え候補とは別"
            "（こちらは全文。飛び越え規則は既存のまま）。\n\n"
        )
        md.append("| Sub | L | kind | target |\n|---|---|---|---|\n")
        for hit in lifetime_rows[:40]:
            md.append(
                f"| `{hit.get('sub')}` | {hit.get('line')} | "
                f"`{hit.get('kind')}` | `{hit.get('target')}` |\n"
            )
        if len(lifetime_rows) > 40:
            md.append(f"\n他 {len(lifetime_rows) - 40} 件省略\n")

    md.append("\n## ライブイベントプロシージャ\n\n")
    md.append("| Sub | 行範囲 | 行数 | scope |\n|---|---|---|---|\n")
    for e in events_sorted[:25]:
        md.append(f"| `{e['name']}` | L{e['start_line']}-{e['end_line']} | {e['size']} | {e['scope']} |\n")
    if len(events_sorted) > 25:
        md.append(f"\n他 {len(events_sorted) - 25} 件省略\n")

    if unobserved_events:
        md.append(f"\n## 未観測プロシージャ（{len(unobserved_events)}件）\n\n")
        md.append(
            "> この .frm と .bas の正規表現では呼び出し未観測。到達不能ではない。\n\n"
        )
        for e in unobserved_events:
            reason = e.get("dead_reason", "")
            suffix = f" — {reason}" if reason else ""
            md.append(
                f"- `{e['name']}` L{e['start_line']}-{e['end_line']} "
                f"({e['size']}行){suffix}\n"
            )

    if dead_events:
        md.append(f"\n## デッドプロシージャ（orphan）（{len(dead_events)}件）\n\n")
        for e in dead_events:
            reason = e.get("dead_reason", "")
            suffix = f" — {reason}" if reason else ""
            md.append(f"- `{e['name']}` L{e['start_line']}-{e['end_line']} ({e['size']}行){suffix}\n")

    offscreen_live = [c for c in live if c.get("offscreen")]
    if offscreen_live:
        md.append(f"\n## 画面外配置のライブコントロール（{len(offscreen_live)}件）\n\n")
        md.append("> Visible でもフォームクライアント領域外＝実行時にマウス到達不能。コードからの読み書きのみ。\n\n")
        for c in offscreen_live[:20]:
            idx = f"({c['index']})" if c.get("index") is not None else ""
            kind = c["kind"].split(".")[-1]
            md.append(
                f"- `{c['name']}`{idx} ({kind}) "
                f"abs=({c['abs_left']},{c['abs_top']}) L{c['line']}\n"
            )
        if len(offscreen_live) > 20:
            md.append(f"\n他 {len(offscreen_live) - 20} 件省略\n")

    hidden_ancestor = [c for c in controls if c.get("ancestor_hidden")]
    if hidden_ancestor:
        md.append(f"\n## 親コンテナ非表示で到達不能（{len(hidden_ancestor)}件）\n\n")
        md.append(
            "> 親 Frame/PictureBox が `Visible=0` かつコード未参照＝実行時に表示され得ない。"
            "skeleton には `ancestor_hidden: true` で含まれる。\n\n"
        )
        for c in hidden_ancestor[:20]:
            idx = f"({c['index']})" if c.get("index") is not None else ""
            kind = c["kind"].split(".")[-1]
            md.append(
                f"- `{c['name']}`{idx} ({kind}) Caption=`{c.get('caption', '')}` "
                f"L{c['line']} — 親 `{c.get('ancestor_hidden_by', '')}`\n"
            )
        if len(hidden_ancestor) > 20:
            md.append(f"\n他 {len(hidden_ancestor) - 20} 件省略\n")

    onscreen_dead = [
        c for c in dead
        if c.get("visible", True) and not c.get("offscreen")
        and not c.get("ancestor_hidden")
        and c["kind"] not in ("VB.Menu", "VB.Timer")
    ]
    if onscreen_dead:
        md.append(f"\n## 画面内・可視だがコード未参照（{len(onscreen_dead)}件）\n\n")
        md.append("> 表示専用（静的ラベル等）。skeleton には `code_ref: false` で含まれる。\n\n")
        for c in onscreen_dead[:20]:
            idx = f"({c['index']})" if c.get("index") is not None else ""
            kind = c["kind"].split(".")[-1]
            md.append(
                f"- `{c['name']}`{idx} ({kind}) "
                f"Caption=`{c.get('caption', '')}` L{c['line']}\n"
            )
        if len(onscreen_dead) > 20:
            md.append(f"\n他 {len(onscreen_dead) - 20} 件省略\n")

    md.append("\n## データパス\n")
    for cat, items in data_paths.items():
        if items:
            md.append(f"\n### {cat}（{len(items)}箇所）\n\n")
            for item in items[:10]:
                md.append(f"- L{item['line']}: `{item['text'][:150]}`\n")
            if len(items) > 10:
                md.append(f"\n他 {len(items) - 10} 件省略\n")

    if goto_maps:
        with_goto = [g for g in goto_maps if g.get("gotos")]
        md.append(f"\n## GoTo / ラベル地図（{len(with_goto)} Sub）\n\n")
        md.append(
            "> 事実のみ（行と名前）。到達可能性の証明ではない。"
            " `GoTo` / `On Error GoTo` / `GoSub` を kind 付きで載せる。"
            " tick 精読前に「この Sub に飛びはあるか」を確認する入口。\n\n"
        )
        for g in with_goto[:20]:
            labels = ", ".join(
                f"`{x['name']}:` L{x['line']}" for x in (g.get("labels") or [])[:12]
            ) or "—"
            jumps = ", ".join(
                f"L{x['line']}→`{x['target']}` ({x['kind']})"
                for x in (g.get("gotos") or [])[:12]
            ) or "—"
            md.append(
                f"- `{g['sub']}`"
                f"{' · ' + g['status'] if g.get('status') else ''}"
                f" — GoTo: {jumps} — Labels: {labels}\n"
            )
        if len(with_goto) > 20:
            md.append(f"\n他 {len(with_goto) - 20} Sub 省略\n")

    if skipped:
        md.append(f"\n## GoTo で飛び越えられる文（候補）（{len(skipped)}件）\n\n")
        md.append(
            "> **静的近似・候補**。**到達不能と断定しない。**"
            " 同一 Sub 内で前方の `GoTo <Label>` と後方の `Label:` の間にある"
            " 注目文（ファイル I/O · `Call` · `Shell` · `Load`/`Unload` · `MsgBox`）を列挙。"
            " Dim / 代入はノイズ回避のため出さない。**ソース順＝実行順と読まないこと。**\n"
            ">\n"
            "> - **unconditional**: 素の `GoTo` — フォールスルーではその文に届かない候補\n"
            "> - **conditional**: `If … Then GoTo` / `Else GoTo` — その分岐では飛ばす。"
            "別分岐では到達しうるため候補扱い\n"
            "> - **on_error / gosub**: ラベル地図の候補。飛び越えスパンは作らない"
            "（エラー時だけ飛ぶ / `Return` で戻る）。デッド確定しない\n"
            "> - **未対応**: スパン内への別ラベル入口、`Resume`、後方 GoTo、"
            "複数入口の証明\n\n"
        )
        md.append(
            "| Sub | GoTo | 種別 | Label | kind | 文 | 断片 |\n"
            "|---|---|---|---|---|---|---|\n"
        )
        for f in skipped[:40]:
            frag = (f.get("path_fragment") or f.get("stmt_text") or f.get("open_text") or "")
            frag = frag.replace("|", "\\|")[:80]
            stmt_ln = f.get("stmt_line") or f.get("open_line")
            kind = f.get("stmt_kind") or "open"
            md.append(
                f"| `{f['sub']}` | L{f['goto_line']} | {f['goto_kind']} | "
                f"`{f['label']}:` L{f['label_line']} | `{kind}` | L{stmt_ln} | `{frag}` |\n"
            )
        if len(skipped) > 40:
            md.append(f"\n他 {len(skipped) - 40} 件省略\n")

    if para_hits:
        marker_names = ", ".join(f"`{m}`" for m in markers) or "—"
        md.append(
            f"\n## 任意スキャン（消費者固有の識別子）（{len(para_hits)}箇所）\n\n"
        )
        md.append(
            f"> config `optional_assign_markers`（{marker_names}）。"
            "キット必須の業務キーではない。\n\n"
        )
        for h in para_hits[:15]:
            md.append(f"- L{h['line']}: `{h['text'][:150]}`\n")

    report_path.write_text("".join(md), encoding="utf-8")


def _source_kind(path: pathlib.Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".cls":
        return "class"
    if suffix == ".bas":
        return "module"
    return "form"


def analyze_module_file(lines: list[str], path: pathlib.Path, vb_name: str) -> dict:
    """Facts for one .bas/.cls. No designer live/dead and no Form chrome."""
    events = extract_events(lines)
    for ev in events:
        ev["status"] = "listed"
        ev["dead_reason"] = ""
        ev["note"] = "module/class: no designer live/dead"
    show_calls: list[dict] = []
    for ev in events:
        show_calls.extend(ev.get("show_calls") or [])
    return {
        "kind": _source_kind(path),
        "file": path.name,
        "vb_name": vb_name or path.stem,
        "surface": parse_surface(lines),
        "procedures": [
            {
                "name": ev.get("name"),
                "kind": ev.get("kind"),
                "start_line": ev.get("start_line"),
                "end_line": ev.get("end_line"),
                "size": ev.get("size"),
            }
            for ev in events
        ],
        "show_calls": show_calls,
        "goto_skipped_stmts": find_goto_skipped_stmts(lines, events),
        "goto_label_maps": [
            g for g in collect_goto_label_maps(lines, events) if g.get("gotos")
        ],
    }


def write_module_skeleton(path: pathlib.Path, data: dict) -> None:
    payload = {
        "kind": data.get("kind"),
        "file": data.get("file"),
        "vb_name": data.get("vb_name"),
        "surface": data.get("surface") or {},
        "procedures": data.get("procedures") or [],
        "show_calls": data.get("show_calls") or [],
    }
    if data.get("goto_skipped_stmts"):
        payload["goto_skipped_stmts"] = data["goto_skipped_stmts"]
    if data.get("goto_label_maps"):
        payload["goto_label_maps"] = data["goto_label_maps"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_module_report(
    report_path: pathlib.Path,
    data: dict,
    *,
    source_label: str,
    total_lines: int,
) -> None:
    kind = data.get("kind") or "module"
    vb_name = data.get("vb_name") or ""
    file_name = data.get("file") or ""
    surface = data.get("surface") or {}
    impl = ", ".join(i.get("name") or "" for i in surface.get("implements") or []) or "—"
    we = ", ".join(
        f"{w.get('name')} As {w.get('as_type')}"
        for w in surface.get("with_events") or []
    ) or "—"
    inst = surface.get("instancing")
    inst_s = "—" if inst is None else str(inst)
    md = [
        f"# {vb_name}（{file_name}）表面レポート\n\n",
        f"日付: {date.today().isoformat()}\n",
        f"ソース: `{source_label}`（CP932, {total_lines}行）\n",
        f"種別: `{kind}`\n\n",
        "> **範囲**: この `.bas` / `.cls` 単体。Form の deep-read ではない"
        "（メニュー・Ctrl・`MDIChild`・ライブ/デッド分類なし）。"
        "呼び出しグラフは作らない。\n\n",
        "## 表面（Implements / WithEvents / Instancing）\n\n",
        f"- Implements: {impl}\n",
        f"- WithEvents: {we}\n",
        f"- Instancing: {inst_s}\n",
        f"- VB_Creatable: {surface.get('vb_creatable')}\n",
        f"- VB_Exposed: {surface.get('vb_exposed')}\n\n",
        f"## プロシージャ（{len(data.get('procedures') or [])}）\n\n",
    ]
    md.append("| name | kind | lines |\n|---|---|---|\n")
    for proc in data.get("procedures") or []:
        md.append(
            f"| `{proc.get('name')}` | {proc.get('kind') or ''} | "
            f"L{proc.get('start_line')}–{proc.get('end_line')} |\n"
        )
    calls = data.get("show_calls") or []
    if calls:
        md.append(f"\n## Show 文（事実）（{len(calls)}）\n\n")
        md.append("> `Foo.Show [arg]` の文面だけ。呼び出しグラフではない。\n\n")
        for call in calls:
            arg = call.get("arg") or "—"
            md.append(
                f"- L{call.get('line')}: `{call.get('target')}.Show {arg}` "
                f"`{call.get('show_style', 'unknown')}`\n"
            )
    maps = data.get("goto_label_maps") or []
    if maps:
        md.append(f"\n## GoTo / ラベル地図（{len(maps)} Sub）\n\n")
        md.append("> 事実のみ。飛び越えスパンは前方 GoTo のみ。デッド確定しない。\n\n")
        for row in maps:
            jumps = ", ".join(
                f"L{x['line']}→`{x['target']}` ({x['kind']})"
                for x in (row.get("gotos") or [])
            ) or "—"
            md.append(f"- `{row.get('sub')}` — {jumps}\n")
    skipped = data.get("goto_skipped_stmts") or []
    if skipped:
        md.append(f"\n## GoTo で飛び越えられる文（候補）（{len(skipped)}件）\n\n")
        md.append("> 静的近似・候補。到達不能と断定しない。ソース順＝実行順と読まない。\n\n")
        for hit in skipped:
            md.append(
                f"- `{hit.get('sub')}` GoTo L{hit.get('goto_line')} → "
                f"`{hit.get('label')}` skips [{hit.get('stmt_kind')}] "
                f"L{hit.get('stmt_line')}\n"
            )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("".join(md), encoding="utf-8")


def run_module_deep_read(
    src_path: pathlib.Path,
    *,
    vb_name: str,
    skel_path: pathlib.Path | None,
    report_path: pathlib.Path | None,
    source_label: str,
) -> dict:
    lines = read_cp932(src_path).splitlines()
    data = analyze_module_file(lines, src_path, vb_name)
    print(f"=== {src_path.name} ===")
    print(f"{data['kind']}: {data['vb_name']}")
    print(f"Lines: {len(lines)}")
    print(f"Procedures: {len(data['procedures'])}")
    print(f"Show calls: {len(data['show_calls'])}")
    print(f"GoTo-skipped stmt candidates: {len(data['goto_skipped_stmts'])}")
    if skel_path is not None:
        write_module_skeleton(skel_path, data)
        print(f"\nSkeleton -> {skel_path}")
    if report_path is not None:
        write_module_report(
            report_path, data, source_label=source_label, total_lines=len(lines)
        )
        print(f"Report  -> {report_path}")
    return data


# ── main ──────────────────────────────────────────────────

def resolve_deep_read_out_key(
    vb_name: str,
    frm_path: pathlib.Path,
    mapping: dict | None = None,
) -> str:
    """Output basename key: deep_read_name_map[VB_Name] or lowercase VB_Name."""
    if mapping is None:
        raw = load_config().get("deep_read_name_map") or {}
        mapping = raw if isinstance(raw, dict) else {}
    if vb_name and mapping:
        for k, v in mapping.items():
            if str(k).lower() == vb_name.lower():
                return str(v)
    if vb_name:
        return vb_name.lower()
    return frm_path.stem.lower().replace("　", "").replace(" ", "")


def _resolve_extract(arg: pathlib.Path | None) -> pathlib.Path:
    if arg is not None:
        extract = arg if arg.is_absolute() else REPO / arg
        return extract.resolve()
    preferred = preferred_extract()
    if preferred is not None:
        return preferred
    root = extracts_root()
    if not root.is_dir():
        raise SystemExit(f"extracts dir missing: {root} (pass --extract)")
    candidates = sorted(p for p in root.iterdir() if p.is_dir())
    if len(candidates) == 1:
        return candidates[0].resolve()
    if not candidates:
        raise SystemExit(f"no extracts under {root}; run extract first")
    names = ", ".join(p.name for p in candidates)
    raise SystemExit(
        f"multiple extracts ({names}); pass --extract working/extracts/<stem> "
        "or set default_extract in archaeology.config.json"
    )


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    global EXTRACT, REPORTS, SKELETONS
    parser = argparse.ArgumentParser(
        description="Deep-read a VB6 .frm, or a .bas/.cls surface report"
    )
    parser.add_argument(
        "frm",
        help=".frm / .bas / .cls filename (or path) inside --extract directory",
    )
    parser.add_argument(
        "--extract",
        type=pathlib.Path,
        default=None,
        help="Extracted project dir (default: sole folder under working/extracts/)",
    )
    parser.add_argument(
        "--skeleton",
        help="Skeleton JSON path or filename (default: working/skeletons/<out_key>-skeleton.json)",
    )
    parser.add_argument(
        "--report",
        help="Report MD path or filename (default: working/reports/<out_key>_deep_read.md)",
    )
    parser.add_argument("--no-skeleton", action="store_true", help="Skip skeleton output")
    parser.add_argument("--no-report", action="store_true", help="Skip report output")
    args = parser.parse_args(argv)

    EXTRACT = _resolve_extract(args.extract)
    REPORTS = reports_root()
    SKELETONS = skeletons_root()
    REPORTS.mkdir(parents=True, exist_ok=True)
    SKELETONS.mkdir(parents=True, exist_ok=True)

    frm_arg = pathlib.Path(args.frm)
    frm_path = frm_arg if frm_arg.is_file() else EXTRACT / frm_arg.name
    if not frm_path.exists():
        print(f"ERROR: {frm_path} not found", file=sys.stderr)
        return 1

    suffix = frm_path.suffix.lower()
    if suffix not in FORM_SUFFIXES | MODULE_SUFFIXES:
        print(
            f"ERROR: deep-read accepts .frm / .bas / .cls (got {frm_path.name})",
            file=sys.stderr,
        )
        return 2

    text = read_cp932(frm_path)
    lines = text.splitlines()
    bas_text = load_bas_text()
    project_text = load_project_code_text()

    code_start = 0
    vb_name = ""
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("Attribute VB_Name"):
            code_start = i
            m = re.search(r'Attribute\s+VB_Name\s*=\s*"([^"]+)"', s, re.IGNORECASE)
            if m:
                vb_name = m.group(1)
            break
    code_text = "\n".join(lines[code_start:])

    # 出力キー: VB_Name + deep_read_name_map（frm_deep_read_all と同契約）
    out_key = resolve_deep_read_out_key(vb_name, frm_path)
    skel_name = args.skeleton or f"{out_key}-skeleton.json"
    report_name = args.report or f"{out_key}_deep_read.md"

    def _out_path(name: str, default_dir: pathlib.Path) -> pathlib.Path:
        path = pathlib.Path(name)
        if not path.is_absolute() and path.parent == pathlib.Path("."):
            return default_dir / path.name
        if not path.is_absolute():
            return REPO / path
        return path

    if suffix in MODULE_SUFFIXES:
        try:
            source_label = str(frm_path.resolve().relative_to(REPO)).replace("\\", "/")
        except ValueError:
            source_label = str(frm_path).replace("\\", "/")
        run_module_deep_read(
            frm_path,
            vb_name=vb_name,
            skel_path=None if args.no_skeleton else _out_path(skel_name, SKELETONS),
            report_path=None if args.no_report else _out_path(report_name, REPORTS),
            source_label=source_label,
        )
        return 0

    assign_markers = optional_assign_markers()
    form_info, controls = extract_controls(lines)
    events = extract_events(lines, assign_markers=assign_markers)
    api_names = extract_declared_apis(code_text, bas_text)
    data_paths = extract_data_paths(lines, api_names)
    para_hits = extract_para(lines, markers=assign_markers)

    events = classify_events(
        events, code_text, bas_text, controls, form_name=form_info.get("name") or "",
    )
    controls = classify_controls(
        controls, code_text, project_text, events, form_name=form_info.get("name") or "",
    )
    controls = annotate_offscreen(form_info, controls)
    controls = annotate_hidden_ancestor(controls)
    menu_findings = analyze_menus(controls, events)
    menu_tree = build_menu_tree(controls, events)
    show_map = extract_show_map(events)
    goto_skipped_stmts = find_goto_skipped_stmts(lines, events)
    goto_label_maps = collect_goto_label_maps(lines, events)

    live_ctrls = [c for c in controls if c.get("live")]
    dead_ctrls = [c for c in controls if not c.get("live")]
    live_events = [e for e in events if e["status"] == "live"]
    unobserved_events = [e for e in events if e["status"] == "unobserved"]
    dead_events = [e for e in events if e["status"] == "dead"]
    hidden_n = sum(1 for c in controls if c.get("ancestor_hidden"))

    print(f"=== {args.frm} ===")
    print(f"Form: {form_info['name']} / Caption: {form_info['caption']}")
    print(f"Lines: {len(lines)}")
    print(f"Controls: {len(controls)} total -> {len(live_ctrls)} live, {len(dead_ctrls)} dead")
    print(
        f"Events: {len(events)} total -> {len(live_events)} live, "
        f"{len(unobserved_events)} unobserved, {len(dead_events)} dead"
    )
    print(
        f"Menu tree: {_count_menu_nodes(menu_tree)} "
        f"(roots={len(menu_tree)}) / warnings: {len(menu_findings)} "
        f"/ Show map rows: {len(show_map)}"
    )
    if hidden_n:
        print(f"Ancestor-hidden controls: {hidden_n}")

    for cat, items in data_paths.items():
        if items:
            print(f"Data {cat}: {len(items)} hits")
    if para_hits:
        print(f"assign-marker hits: {len(para_hits)}")
    if goto_skipped_stmts:
        print(f"GoTo-skipped stmt candidates: {len(goto_skipped_stmts)}")
        for f in goto_skipped_stmts[:8]:
            print(
                f"  {f['sub']}  GoTo L{f['goto_line']} ({f['goto_kind']}) -> "
                f"{f['label']}: L{f['label_line']}  skips [{f.get('stmt_kind')}] "
                f"L{f.get('stmt_line')}  "
                f"{(f.get('path_fragment') or f.get('stmt_text') or '')[:60]}"
            )

    if menu_findings:
        print("Menu warnings:")
        for f in menu_findings[:12]:
            flags = []
            if not f["visible"]:
                flags.append("Invisible")
            if not f["enabled"]:
                flags.append("Disabled")
            if not f["has_click"]:
                flags.append("NoClick")
            print(f"  {f['name']} \"{f['caption']}\" [{','.join(flags)}]")

    if unobserved_events:
        print("Unobserved procedures (not unreachable):")
        for e in unobserved_events:
            reason = e.get("dead_reason", "")
            print(f"  {e['name']}  L{e['start_line']}-{e['end_line']}  ({e['size']} lines)  {reason}")
    if dead_events:
        print("Dead procedures (orphan handlers):")
        for e in dead_events:
            reason = e.get("dead_reason", "")
            print(f"  {e['name']}  L{e['start_line']}-{e['end_line']}  ({e['size']} lines)  {reason}")
    offscreen_live = [c for c in live_ctrls if c.get("offscreen")]
    if offscreen_live:
        print(f"Offscreen live controls: {len(offscreen_live)}")

    if not args.no_skeleton:
        skel = build_skeleton(form_info, controls)
        style_block = form_show_style_block(form_info)
        skel["show_style"] = style_block
        if menu_tree:
            skel["menu_tree"] = menu_tree
        if menu_findings:
            skel["menu_warnings"] = menu_findings
        if show_map:
            skel["show_map"] = show_map
        if goto_skipped_stmts:
            skel["goto_skipped_stmts"] = goto_skipped_stmts
        if goto_label_maps:
            skel["goto_label_maps"] = [
                g for g in goto_label_maps if g.get("gotos")
            ]
        skel_path = pathlib.Path(skel_name)
        if not skel_path.is_absolute() and skel_path.parent == pathlib.Path("."):
            skel_path = SKELETONS / skel_path.name
        elif not skel_path.is_absolute():
            skel_path = REPO / skel_path
        skel_path.parent.mkdir(parents=True, exist_ok=True)
        skel_path.write_text(json.dumps(skel, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSkeleton -> {skel_path}")

    if not args.no_report:
        report_path = pathlib.Path(report_name)
        if not report_path.is_absolute() and report_path.parent == pathlib.Path("."):
            report_path = REPORTS / report_path.name
        elif not report_path.is_absolute():
            report_path = REPO / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            source_label = str(frm_path.resolve().relative_to(REPO)).replace("\\", "/")
        except ValueError:
            source_label = str(frm_path).replace("\\", "/")
        write_report(
            report_path, frm_path.name, form_info, controls, events, data_paths, para_hits,
            len(lines), menu_findings, show_map, source_label=source_label,
            goto_skipped_stmts=goto_skipped_stmts,
            goto_label_maps=goto_label_maps,
            show_style=form_show_style_block(form_info),
            menu_tree=menu_tree,
            assign_markers=assign_markers,
        )
        print(f"Report  -> {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
