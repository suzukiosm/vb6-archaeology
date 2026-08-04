#!/usr/bin/env python3
"""Deep-read a VB6 .frm: extract live controls, events, data paths, PARA, dead code.

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
    preferred_extract,
    reports_root,
    skeletons_root,
)
from lib.console import enable_utf8_stdio  # noqa: E402

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
    """
    form_info = {
        "name": "", "caption": "",
        "width": None, "height": None,
        "clientWidth": None, "clientHeight": None,
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

    return form_info, controls


# ── Events ────────────────────────────────────────────────

def extract_events(lines: list[str]):
    events = []
    in_code = False
    current = None

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
            for sm in re.finditer(r"\b([A-Za-z_][\w]*)\.Show\b", s):
                current.setdefault("shows", []).append(sm.group(1))
            pm = re.search(r'PARA\s*=\s*"([^"]+)"', s)
            if pm:
                current.setdefault("para_sets", []).append(pm.group(1))

    if current:
        current["end_line"] = len(lines)
        current["size"] = current["end_line"] - current["start_line"] + 1
        events.append(current)

    for ev in events:
        ev.setdefault("shows", [])
        ev.setdefault("para_sets", [])
        # dedupe preserving order
        ev["shows"] = list(dict.fromkeys(ev["shows"]))
        ev["para_sets"] = list(dict.fromkeys(ev["para_sets"]))

    return events


def analyze_menus(controls: list[dict], events: list[dict]):
    """Flag menus that are invisible/disabled or lack *_Click (kensaku-class traps).

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


def extract_show_map(events: list[dict]):
    rows = []
    for e in events:
        if e.get("status") == "dead":
            continue
        if not e.get("shows") and not e.get("para_sets"):
            continue
        rows.append({
            "sub": e["name"],
            "line": e["start_line"],
            "shows": e.get("shows", []),
            "para_sets": e.get("para_sets", []),
        })
    return rows


# ── Dead code ─────────────────────────────────────────────

def classify_events(
    events: list[dict], code_text: str, bas_text: str,
    controls: list[dict] | None = None, form_name: str = "",
):
    """Classify subs live/dead.

    Event-named subs are live only if the owning control exists in the designer
    (case-insensitive). Orphan handlers (e.g. Form11 ``Text1_OLEDragDrop`` with
    no ``Text1``) never fire; they stay live only when explicitly called as a
    normal sub elsewhere (e.g. Denpyou ``FX_Click`` called from ``faxx_Click``).
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

        ev["status"] = "live" if has_real_calls(ev["name"]) else "dead"
        if ev["status"] == "dead":
            ev["dead_reason"] = "no caller"

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
        if ev.get("status") == "dead":
            continue
        m = EVENT_SUFFIXES.match(ev["name"])
        if m:
            event_owners.add(m.group(1))

    owners_lower = {o.lower() for o in event_owners}
    for ctrl in controls:
        name = ctrl["name"]
        if name in ("ＭＳ Ｐゴシック",):
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


def extract_para(lines: list[str]):
    hits = []
    for i, line in enumerate(lines):
        if "PARA" in line and not line.strip().startswith("'"):
            hits.append({"line": i + 1, "text": line.strip()[:200]})
    return hits


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
):
    live = [c for c in controls if c.get("live")]
    dead = [c for c in controls if not c.get("live")]
    live_events = [e for e in events if e["status"] == "live"]
    dead_events = [e for e in events if e["status"] == "dead"]
    events_sorted = sorted(live_events, key=lambda e: e["size"], reverse=True)
    src = source_label or frm_filename

    md = []
    md.append(f"# {form_info['name']}（{frm_filename}）深読みレポート\n\n")
    md.append(f"日付: {date.today().isoformat()}（デッドコード除外済み）\n")
    md.append(f"ソース: `{src}`（CP932, {total_lines}行）\n")
    md.append(f"Form Caption: `{form_info['caption']}`\n\n")
    md.append(f"> コントロール: {len(controls)} 全体 → **{len(live)} ライブ** / {len(dead)} デッド（コード未参照）\n")
    md.append(f"> イベント: {len(events)} 全体 → **{len(live_events)} ライブ** / {len(dead_events)} デッド\n\n")
    # 本ツールは .frm 単体解析。他 .frm/.bas からの参照は見えないため、
    # イベント 0 を「孤立・到達不能」と即断させない注記を必ず出す。
    md.append(
        "> **範囲**: 本レポートはこの .frm 単体の解析。他 .frm/.bas からの参照"
        "（`Show` の呼び元・外部 Sub によるコントロール操作）は対象外。"
        "イベント数 0 を孤立・到達不能と即断しない"
        f"{'（イベント 0 でも外部から Load / 操作される場合がある）。' if not live_events else '。'}\n\n"
    )

    if menu_findings:
        md.append("## メニュー警告（Invisible / Disabled / Click 無し）\n\n")
        md.append("> Caption だけ見て遷移を付けないこと。`kensaku` 誤配線の再発防止。\n\n")
        md.append("| name | Caption | Vis | En | Click | L |\n|---|---|---|---|---|---|\n")
        for f in menu_findings:
            md.append(
                f"| `{f['name']}` | {f['caption'] or '（空）'} | "
                f"{'Y' if f['visible'] else 'N'} | {'Y' if f['enabled'] else 'N'} | "
                f"{'Y' if f['has_click'] else '**N**'} | {f['line']} |\n"
            )

    if show_map:
        md.append("\n## Form.Show / PARA= マップ（ライブ Sub）\n\n")
        md.append("| Sub | L | .Show | PARA= |\n|---|---|---|---|\n")
        for r in show_map[:40]:
            shows = ", ".join(f"`{s}`" for s in r["shows"]) or "—"
            paras = ", ".join(f'`"{p}"`' for p in r["para_sets"]) or "—"
            md.append(f"| `{r['sub']}` | {r['line']} | {shows} | {paras} |\n")
        if len(show_map) > 40:
            md.append(f"\n他 {len(show_map) - 40} 件省略\n")

    md.append("\n## ライブイベントプロシージャ\n\n")
    md.append("| Sub | 行範囲 | 行数 | scope |\n|---|---|---|---|\n")
    for e in events_sorted[:25]:
        md.append(f"| `{e['name']}` | L{e['start_line']}-{e['end_line']} | {e['size']} | {e['scope']} |\n")
    if len(events_sorted) > 25:
        md.append(f"\n他 {len(events_sorted) - 25} 件省略\n")

    if dead_events:
        md.append(f"\n## デッドプロシージャ（{len(dead_events)}件）\n\n")
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

    if para_hits:
        md.append(f"\n## PARA（{len(para_hits)}箇所）\n\n")
        for h in para_hits[:15]:
            md.append(f"- L{h['line']}: `{h['text'][:150]}`\n")

    report_path.write_text("".join(md), encoding="utf-8")


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
    parser = argparse.ArgumentParser(description="Deep-read a VB6 .frm")
    parser.add_argument(
        "frm",
        help=".frm filename (or path) inside --extract directory",
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

    form_info, controls = extract_controls(lines)
    events = extract_events(lines)
    api_names = extract_declared_apis(code_text, bas_text)
    data_paths = extract_data_paths(lines, api_names)
    para_hits = extract_para(lines)

    events = classify_events(
        events, code_text, bas_text, controls, form_name=form_info.get("name") or "",
    )
    controls = classify_controls(
        controls, code_text, project_text, events, form_name=form_info.get("name") or "",
    )
    controls = annotate_offscreen(form_info, controls)
    controls = annotate_hidden_ancestor(controls)
    menu_findings = analyze_menus(controls, events)
    show_map = extract_show_map(events)

    live_ctrls = [c for c in controls if c.get("live")]
    dead_ctrls = [c for c in controls if not c.get("live")]
    live_events = [e for e in events if e["status"] == "live"]
    dead_events = [e for e in events if e["status"] == "dead"]
    hidden_n = sum(1 for c in controls if c.get("ancestor_hidden"))

    print(f"=== {args.frm} ===")
    print(f"Form: {form_info['name']} / Caption: {form_info['caption']}")
    print(f"Lines: {len(lines)}")
    print(f"Controls: {len(controls)} total -> {len(live_ctrls)} live, {len(dead_ctrls)} dead")
    print(f"Events: {len(events)} total -> {len(live_events)} live, {len(dead_events)} dead")
    print(f"Menu warnings: {len(menu_findings)} / Show+PARA map rows: {len(show_map)}")
    if hidden_n:
        print(f"Ancestor-hidden controls: {hidden_n}")

    for cat, items in data_paths.items():
        if items:
            print(f"Data {cat}: {len(items)} hits")
    if para_hits:
        print(f"PARA: {len(para_hits)} hits")

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

    if dead_events:
        print("Dead procedures:")
        for e in dead_events:
            reason = e.get("dead_reason", "")
            print(f"  {e['name']}  L{e['start_line']}-{e['end_line']}  ({e['size']} lines)  {reason}")
    offscreen_live = [c for c in live_ctrls if c.get("offscreen")]
    if offscreen_live:
        print(f"Offscreen live controls: {len(offscreen_live)}")

    if not args.no_skeleton:
        skel = build_skeleton(form_info, controls)
        if menu_findings:
            skel["menu_warnings"] = menu_findings
        if show_map:
            skel["show_map"] = show_map
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
        )
        print(f"Report  -> {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
