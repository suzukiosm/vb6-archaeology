#!/usr/bin/env python3
"""全 .frm/.bas の実行時 Left/Top/Width/Height/Visible 代入をカタログ化する。

設計時座標（Begin..End）とは別。Show / Form_Load 前後で書き換える実行時 Move /
Visible を証拠つきで抽出し、再実装受け渡し用 JSON も出す。

Usage:
  python tools/runtime_layout.py
  python tools/runtime_layout.py --extract working/extracts/<stem>
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from lib.config import (  # noqa: E402
    decode_vb6_bytes,
    extracts_root,
    load_config,
    reports_root,
    skeletons_root,
)

DEFAULT_EXTRACT = None  # require --extract unless a single extract exists
REPORTS = reports_root()
WEB_LIB = skeletons_root()
_EXTRACT_LABEL = ""


def _geometry_hint_replacements() -> list[tuple[str, str]]:
    """Build regex replacements from archaeology.config.json geometry_hints.

    Example config:
      "geometry_hints": {
        "MDIForm1": {"left": 0, "top": 0, "height": 13550, "width": 0},
        "ParentForm": {"width": 14715}
      }
    """
    hints = load_config().get("geometry_hints") or {}
    repl: list[tuple[str, str]] = []
    for form, props in hints.items():
        if not isinstance(props, dict):
            continue
        for prop, val in props.items():
            key = str(prop).lower()
            if key not in ("left", "top", "width", "height"):
                continue
            prop_name = "Top" if key == "top" else key.capitalize()
            if key == "top":
                repl.append((rf"\b{re.escape(str(form))}\.TOP\b", str(val)))
            repl.append((rf"\b{re.escape(str(form))}\.{prop_name}\b", str(val)))
    return repl


PROP = r"(Left|Top|Width|Height|Visible)"
# Target.Prop = expr  /  Me.Prop = expr  /  With X: .Prop =
ASSIGN_RE = re.compile(
    rf"^(?P<object>(?:Me|(?:[A-Za-z_]\w*(?:\([^)]*\))?(?:\.[A-Za-z_]\w*(?:\([^)]*\))?)*)))"
    rf"\.(?P<prop>{PROP})\s*=\s*(?P<expr>.+?)\s*$",
    re.IGNORECASE,
)
DOT_ASSIGN_RE = re.compile(
    rf"^\.(?P<prop>{PROP})\s*=\s*(?P<expr>.+?)\s*$",
    re.IGNORECASE,
)
# If cond Then Ctrl.Visible = True  （行頭以外の代入）
THEN_ASSIGN_RE = re.compile(
    rf"\bThen\s+"
    rf"(?P<object>(?:Me|(?:[A-Za-z_]\w*(?:\([^)]*\))?(?:\.[A-Za-z_]\w*(?:\([^)]*\))?)*)))"
    rf"\.(?P<prop>{PROP})\s*=\s*(?P<expr>.+?)(?=\s+Else\b|\s*:|\s*$)",
    re.IGNORECASE,
)
ELSE_ASSIGN_RE = re.compile(
    rf"\bElse\s+"
    rf"(?P<object>(?:Me|(?:[A-Za-z_]\w*(?:\([^)]*\))?(?:\.[A-Za-z_]\w*(?:\([^)]*\))?)*)))"
    rf"\.(?P<prop>{PROP})\s*=\s*(?P<expr>.+?)(?=\s*:|\s*$)",
    re.IGNORECASE,
)
VISIBLE_BOOL_RE = re.compile(r"^(True|False|-1|0)\b", re.IGNORECASE)
WITH_RE = re.compile(r"^With\s+(?P<object>\S+)", re.IGNORECASE)
END_WITH_RE = re.compile(r"^End\s+With\b", re.IGNORECASE)
SUB_RE = re.compile(
    r"^(?:Private\s+|Public\s+|Friend\s+)?(?:Sub|Function)\s+(?P<name>\w+)\s*\(",
    re.IGNORECASE,
)
END_SUB_RE = re.compile(r"^End\s+(?:Sub|Function)\b", re.IGNORECASE)
SHOW_RE = re.compile(r"\b(?P<form>[A-Za-z_]\w*)\.Show\b", re.IGNORECASE)
VB_NAME_RE = re.compile(r'Attribute\s+VB_Name\s*=\s*"([^"]+)"')
FORM_BEGIN_RE = re.compile(r"^Begin\s+VB\.(?:MDI)?Form\s+(\S+)")

# known form VB_Name set filled at runtime
KNOWN_FORMS: set[str] = set()

OFFSCREEN_THRESHOLD = -10000

# キット既定の経路スコア（アプリ固有 Sub は載せない）。
# 消費者は archaeology.config.json の layout_sub_scores で上書き・追加する。
BUILTIN_LAYOUT_SUB_SCORES: dict[str, int] = {
    "form_load": 80,
    "mdiform_load": 80,
}
# 未登録の *_click に与える名前非依存加点（form_show 経路）
GENERIC_CLICK_BONUS = 10
# codeControlMoves で未登録 *_click の下限
CODE_MOVE_CLICK_FLOOR = 40


def effective_layout_sub_scores(
    override: dict[str, int] | None = None,
) -> dict[str, int]:
    """Builtin scores merged with config (or explicit override). Keys are lowercased."""
    scores = dict(BUILTIN_LAYOUT_SUB_SCORES)
    if override is None:
        raw = load_config().get("layout_sub_scores") or {}
    else:
        raw = override
    if isinstance(raw, dict):
        for key, val in raw.items():
            try:
                scores[str(key).lower()] = int(val)
            except (TypeError, ValueError):
                continue
    return scores


def sub_path_score(
    sub: str | None,
    scores: dict[str, int],
    *,
    click_bonus: int = GENERIC_CLICK_BONUS,
) -> int:
    """Score a Sub name for open-path preference."""
    key = (sub or "").lower()
    points = scores.get(key, 0)
    if key.endswith("_click") and key not in scores:
        points += click_bonus
    return points


def read_cp932(path: pathlib.Path) -> str:
    return decode_vb6_bytes(path.read_bytes())


def strip_comment(line: str) -> str:
    # VB ' comment (not inside strings — good enough for geometry lines)
    in_str = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_str = not in_str
        elif ch == "'" and not in_str:
            return line[:i].rstrip()
    return line.rstrip()


def clean_assign_expr(expr: str) -> str:
    """同一行の `:` 連結や `Else` 以降を落とす。"""
    e = expr.strip()
    e = re.split(r"\s*:\s*", e, maxsplit=1)[0]
    e = re.split(r"\s+Else\b", e, maxsplit=1, flags=re.IGNORECASE)[0]
    return e.strip()


def parse_visible(expr: str) -> bool | None:
    """VB6 Visible 代入値。True/-1 → True · False/0 → False。"""
    m = VISIBLE_BOOL_RE.match(clean_assign_expr(expr))
    if not m:
        return None
    token = m.group(1).lower()
    if token in ("true", "-1"):
        return True
    if token in ("false", "0"):
        return False
    return None


def parse_number(expr: str) -> int | float | None:
    """数値リテラル・単純式・親フォーム相対式を twips 数値へ。

    親フォーム寸法は archaeology.config.json の geometry_hints で供給する。
    未設定なら親相対トークンは置換されず、評価不能として None になり得る。
    """
    e = expr.strip()
    for pat, val in _geometry_hint_replacements():
        e = re.sub(pat, val, e, flags=re.IGNORECASE)
    e = e.strip()
    # 数字と + - * / ( ) 空白のみなら評価
    if re.fullmatch(r"[\d\s+\-*/().]+", e):
        try:
            v = eval(e, {"__builtins__": {}}, {})  # noqa: S307 — 制限済み式
            if isinstance(v, (int, float)):
                return int(v) if float(v) == int(v) else float(v)
        except Exception:
            return None
    m = re.fullmatch(r"-?\d+(?:\.\d+)?", e)
    if m:
        return float(e) if "." in e else int(e)
    return None


def classify(
    obj: str,
    prop: str,
    expr: str,
    value: int | float | bool | None,
    file_vb: str,
) -> str:
    if prop.lower() == "visible":
        # Me / 素の Form 名のみ form_visible。Form.Ctrl は control_visible。
        if obj.lower() == "me":
            return "form_visible"
        parts = obj.split(".")
        if len(parts) == 1 and parts[0] in KNOWN_FORMS:
            return "form_visible"
        return "control_visible"
    o = obj if obj.lower() != "me" else file_vb
    if (
        isinstance(value, (int, float))
        and prop.lower() == "left"
        and value <= OFFSCREEN_THRESHOLD
    ):
        return "offscreen_hide"
    if "Screen." in expr:
        return "screen_adapt"
    if o in KNOWN_FORMS or obj.lower() == "me" and file_vb in KNOWN_FORMS:
        return "form_place"
    if o in ("MDIForm1",) or obj.upper().startswith("MDIFORM"):
        if "Picture1" in obj or obj == "MDIForm1":
            return "mdi_chrome"
    if "Picture1" in obj:
        return "mdi_chrome"
    if re.search(r"[+\-*/]|Index|Cell|SCALE|Ratio|Width|Height|Left|Top", expr):
        if value is None:
            return "control_expr"
    return "control_move"


def discover_forms(extract: pathlib.Path) -> dict[str, str]:
    """vbName -> filename"""
    out: dict[str, str] = {}
    for path in sorted(extract.glob("*.frm")):
        text = read_cp932(path)
        vb = None
        m = VB_NAME_RE.search(text)
        if m:
            vb = m.group(1)
        if not vb:
            for line in text.splitlines():
                bm = FORM_BEGIN_RE.match(line.strip())
                if bm:
                    vb = bm.group(1)
                    break
        if vb:
            out[vb] = path.name
    return out


def extract_file(path: pathlib.Path, file_vb: str) -> list[dict]:
    """コード部のみ走査（設計時 Begin..End プロパティは除外）。

    VB6 .frm は通常: Begin VB.Form … End → Attribute VB_Name → Sub/Function。
    Attribute VB_Name 以降だけを対象にする（プロパティダンプの Left= を拾わない）。
    """
    lines = read_cp932(path).splitlines()
    rows: list[dict] = []
    current_sub: str | None = None
    with_stack: list[str] = []
    # track recent .Show forms for proximity tag
    recent_shows: list[tuple[int, str]] = []

    # コード開始行（1-based）。見つからなければ先頭から（.bas 等）
    code_start = 1
    for i, raw in enumerate(lines, 1):
        if VB_NAME_RE.match(raw.strip()):
            code_start = i
            break
    else:
        for i, raw in enumerate(lines, 1):
            if SUB_RE.match(strip_comment(raw).strip()):
                code_start = i
                break

    for i, raw in enumerate(lines, 1):
        if i < code_start:
            continue
        s = strip_comment(raw).strip()
        if not s:
            continue
        if raw.lstrip().startswith("'"):
            continue

        sm = SUB_RE.match(s)
        if sm:
            current_sub = sm.group("name")
            # Show の文脈は Sub をまたがせない（またぐと隣 Sub の Form へ誤帰属する）
            recent_shows = []
            continue
        if END_SUB_RE.match(s):
            current_sub = None
            recent_shows = []
            continue

        wm = WITH_RE.match(s)
        if wm:
            with_stack.append(wm.group("object"))
            continue
        if END_WITH_RE.match(s):
            if with_stack:
                with_stack.pop()
            continue

        for smatch in SHOW_RE.finditer(s):
            recent_shows.append((i, smatch.group("form")))
            recent_shows = [(ln, f) for ln, f in recent_shows if i - ln <= 40]

        matches: list[tuple[str, str, str]] = []
        am = ASSIGN_RE.match(s)
        if am:
            matches.append(
                (am.group("object"), am.group("prop"), am.group("expr"))
            )
        else:
            dm = DOT_ASSIGN_RE.match(s)
            if dm and with_stack:
                obj0 = with_stack[-1]
                obj0 = re.sub(r"\(.*\)$", "", obj0)
                matches.append((obj0, dm.group("prop"), dm.group("expr")))
            else:
                tm = THEN_ASSIGN_RE.search(s)
                if tm:
                    matches.append(
                        (tm.group("object"), tm.group("prop"), tm.group("expr"))
                    )
                em = ELSE_ASSIGN_RE.search(s)
                if em:
                    matches.append(
                        (em.group("object"), em.group("prop"), em.group("expr"))
                    )

        if not matches:
            continue

        # If Ctrl.Visible = False Then … の比較は代入ではない
        if (
            any(p.lower() == "visible" for _, p, _ in matches)
            and re.match(r"^If\b", s, re.IGNORECASE)
            and not THEN_ASSIGN_RE.search(s)
            and not ELSE_ASSIGN_RE.search(s)
        ):
            continue

        near_show = [f for ln, f in recent_shows if abs(i - ln) <= 25]
        for j in range(i, min(i + 25, len(lines))):
            ahead = strip_comment(lines[j - 1]).strip()
            # 前方も同じ Sub 内まで
            if j > i and (END_SUB_RE.match(ahead) or SUB_RE.match(ahead)):
                break
            for smatch in SHOW_RE.finditer(ahead):
                near_show.append(smatch.group("form"))
        near_show = sorted(set(near_show))

        for obj, prop, expr in matches:
            # skip Printer / ScaleMode-ish non-geometry containers lightly
            if obj.lower() in {
                "printer",
                "commonDialog1",
                "udtprinterinfo5",
                "udtdevmode",
            }:
                continue

            # MDI フォーム内の素の Picture1 → MDIForm1.Picture1
            if file_vb == "MDIForm1" and "." not in obj:
                if obj.lower() == "picture1":
                    obj = f"MDIForm1.{obj}"

            expr_clean = clean_assign_expr(expr)
            if prop.lower() == "visible":
                value = parse_visible(expr_clean)
            else:
                value = parse_number(expr_clean)

            target = file_vb if obj.lower() == "me" else obj
            if "." in obj and obj.lower() != "me":
                target = obj

            kind = classify(obj, prop, expr_clean, value, file_vb)
            prop_norm = prop[0].upper() + prop[1:].lower() if prop else prop
            rows.append(
                {
                    "file": path.name,
                    "file_vb": file_vb,
                    "line": i,
                    "sub": current_sub,
                    "object": obj,
                    "target": target,
                    "prop": prop_norm,
                    "expr": expr_clean,
                    "value": value,
                    "kind": kind,
                    "near_show": near_show,
                    "source": raw.rstrip()[:160],
                }
            )
    return rows


def build_form_show_layout(
    assignments: list[dict],
    forms: dict[str, str],
    sub_scores: dict[str, int] | None = None,
) -> dict:
    """Per form: best-effort show-time Left/Top/Width/Height + mdi Picture1.Height hints."""
    scores = effective_layout_sub_scores(sub_scores)
    by_form: dict[str, dict] = {}

    def ensure(name: str) -> dict:
        if name not in by_form:
            by_form[name] = {
                "vbName": name,
                "file": forms.get(name),
                "left": None,
                "top": None,
                "width": None,
                "height": None,
                "picture1Height": None,
                "evidence": [],
                "all_assignments": [],
            }
        return by_form[name]

    for name in forms:
        ensure(name)

    def score(row: dict, prop: str, form: str) -> int:
        s = sub_path_score(row.get("sub"), scores)
        if form in row.get("near_show", []):
            s += 15
        if row["kind"] == "offscreen_hide":
            s -= 200
        if row["kind"] == "form_place":
            s += 10
        if row["value"] is not None:
            s += 5
        return s

    candidates: dict[tuple[str, str], list[tuple[int, dict]]] = {}
    for row in assignments:
        if row["value"] is None:
            continue
        prop = row["prop"]
        if prop not in ("Left", "Top", "Width", "Height"):
            continue

        # form target?
        target = row["target"]
        form = None
        if target in forms:
            form = target
        elif row["object"].lower() == "me" and row["file_vb"] in forms:
            form = row["file_vb"]
        elif target.startswith("MDIForm1.") or target == "MDIForm1":
            # chrome — attach via near_show, else MDIForm1
            if "Picture1" in target and prop == "Height":
                ctx_forms = list(row.get("near_show") or [])
                if not ctx_forms:
                    ctx_forms = ["MDIForm1"]
                for f in ctx_forms:
                    slot = ensure(f)
                    # MDI 本体は大きい方、子コンテキストは小さい方を採用
                    prev = slot.get("picture1Height")
                    val = int(row["value"])
                    if prev is None:
                        slot["picture1Height"] = val
                    elif f == "MDIForm1" and val > prev:
                        slot["picture1Height"] = val
                    elif f != "MDIForm1" and val < prev:
                        slot["picture1Height"] = val
                    slot["evidence"].append(
                        {
                            "prop": "Picture1.Height",
                            "value": val,
                            "file": row["file"],
                            "line": row["line"],
                            "sub": row["sub"],
                        }
                    )
            continue

        if not form:
            continue
        if row["kind"] not in ("form_place", "offscreen_hide", "screen_adapt"):
            # still allow Me.Height on forms
            if row["object"].lower() != "me":
                continue

        key = (form, prop)
        candidates.setdefault(key, []).append((score(row, prop, form), row))

    for (form, prop), items in candidates.items():
        items.sort(key=lambda x: -x[0])
        # pick best non-offscreen if possible
        chosen = None
        for sc, row in items:
            if row["kind"] != "offscreen_hide":
                chosen = row
                break
        # offscreen-only → no default show coordinate
        if chosen is None:
            continue
        slot = ensure(form)
        prop_l = prop.lower()
        val = chosen["value"]
        if isinstance(val, float) and val == int(val):
            val = int(val)
        slot[prop_l] = val
        slot["evidence"].append(
            {
                "prop": prop,
                "value": val,
                "file": chosen["file"],
                "line": chosen["line"],
                "sub": chosen["sub"],
                "score": score(chosen, prop, form),
            }
        )

    # attach all form_place rows for reference
    for row in assignments:
        if row["kind"] not in ("form_place", "offscreen_hide", "mdi_chrome"):
            continue
        t = row["target"]
        form = t if t in forms else (row["file_vb"] if row["object"].lower() == "me" else None)
        if form and form in by_form:
            by_form[form]["all_assignments"].append(
                {
                    "line": row["line"],
                    "sub": row["sub"],
                    "object": row["object"],
                    "prop": row["prop"],
                    "expr": row["expr"],
                    "value": row["value"],
                    "kind": row["kind"],
                    "file": row["file"],
                }
            )

    return by_form


def build_contextual_form_layout(
    assignments: list[dict],
    forms: dict[str, str],
) -> list[dict]:
    """呼出元 Form/Sub ごとの表示時 Form 配置を組み立てる。

    対象 Form 自身の Form_Load を基底とし、各呼出 Sub 内の数値代入を
    ソース順で上書きする。画面外退避は表示配置として採用しない。
    """
    canonical_forms = {name.lower(): name for name in forms}
    grouped: dict[tuple[str, str, str], list[dict]] = {}

    for row in assignments:
        if row.get("kind") != "form_place" or row.get("value") is None:
            continue
        prop = row.get("prop")
        if prop not in ("Left", "Top", "Width", "Height"):
            continue

        obj = str(row.get("object") or "")
        file_vb = str(row.get("file_vb") or "")
        target = file_vb if obj.lower() == "me" else str(row.get("target") or "")
        form = canonical_forms.get(target.lower())
        if form is None:
            continue
        if obj.lower() not in {"me", form.lower()}:
            continue

        key = (form, file_vb, str(row.get("sub") or ""))
        grouped.setdefault(key, []).append(row)

    def selected_properties(rows: list[dict]) -> dict[str, dict]:
        selected: dict[str, dict] = {}
        for row in sorted(rows, key=lambda item: item["line"]):
            selected[row["prop"].lower()] = row
        return selected

    form_loads: dict[str, dict[str, dict]] = {}
    for (form, from_form, via), rows in grouped.items():
        if from_form.lower() == form.lower() and via.lower() == "form_load":
            form_loads[form] = selected_properties(rows)

    placements: list[dict] = []
    for (form, from_form, via), rows in sorted(
        grouped.items(),
        key=lambda item: tuple(part.lower() for part in item[0]),
    ):
        selected = dict(form_loads.get(form, {}))
        selected.update(selected_properties(rows))
        if not selected:
            continue

        placement = {
            "form": form,
            "from": from_form,
            "via": via,
            "left": None,
            "top": None,
            "width": None,
            "height": None,
            "evidence": [],
        }
        for prop in ("left", "top", "width", "height"):
            row = selected.get(prop)
            if row is None:
                continue
            value = row["value"]
            if isinstance(value, float) and value == int(value):
                value = int(value)
            placement[prop] = value
            placement["evidence"].append(
                {
                    "prop": row["prop"],
                    "value": value,
                    "expr": row["expr"],
                    "file": row["file"],
                    "line": row["line"],
                    "sub": row["sub"],
                }
            )
        placements.append(placement)

    return placements


def build_code_control_moves(
    assignments: list[dict],
    forms: dict[str, str],
    sub_scores: dict[str, int] | None = None,
) -> dict:
    """Form コード内のコントロール座標代入（設計時 Begin ではない）。

    キー: vbName → controlName → { left/top/width/height, evidence[] }
    同一 prop は layout_sub_scores 優先 Sub の最終値を採用。
    """
    scores = effective_layout_sub_scores(sub_scores)
    out: dict[str, dict] = {}

    def ensure_form(vb: str) -> dict:
        if vb not in out:
            out[vb] = {}
        return out[vb]

    def control_base(obj: str) -> str:
        # List1(0) → List1 · MDIForm1.Picture1 → Picture1（フォーム内のみ）
        o = obj
        if "." in o and not o.lower().startswith("me"):
            # 他フォーム参照はスキップ（Qualified.Ctrl は別枠）
            head = o.split(".", 1)[0]
            if head in forms and head != o:
                return ""
            o = o.rsplit(".", 1)[-1]
        o = re.sub(r"\(.*\)$", "", o)
        return o

    scored: dict[tuple[str, str, str], list[tuple[int, dict]]] = {}
    for row in assignments:
        if row["kind"] not in ("control_move", "control_expr"):
            continue
        if row["value"] is None and row["kind"] == "control_expr":
            # 式のみは証拠カタログへ（数値なし）
            pass
        vb = row["file_vb"]
        if vb not in forms:
            continue
        ctrl = control_base(row["object"])
        if not ctrl or ctrl.lower() in {"me", "printer"}:
            continue
        # フォーム自身の Me.Left 等は form_show 側
        if row["object"].lower() == "me":
            continue
        prop = row["prop"]
        sub = (row.get("sub") or "").lower()
        sc = scores.get(sub, 0)
        if sub.endswith("_click"):
            sc = max(sc, CODE_MOVE_CLICK_FLOOR)
        if row["value"] is not None:
            sc += 10
        scored.setdefault((vb, ctrl, prop), []).append((sc, row))

    for (vb, ctrl, prop), items in scored.items():
        items.sort(key=lambda x: (-x[0], x[1]["line"]))
        slot_form = ensure_form(vb)
        slot = slot_form.setdefault(
            ctrl,
            {"left": None, "top": None, "width": None, "height": None, "evidence": []},
        )
        # 最良の数値代入を prop に
        for sc, row in items:
            if row["value"] is None:
                continue
            pl = prop.lower()
            if slot.get(pl) is None:
                val = row["value"]
                if isinstance(val, float) and val == int(val):
                    val = int(val)
                slot[pl] = val
            slot["evidence"].append(
                {
                    "prop": prop,
                    "value": row["value"],
                    "expr": row["expr"],
                    "file": row["file"],
                    "line": row["line"],
                    "sub": row["sub"],
                    "score": sc,
                }
            )
            break
        # 残り証拠（最大 6）
        for sc, row in items[:6]:
            ev = {
                "prop": prop,
                "value": row["value"],
                "expr": row["expr"],
                "file": row["file"],
                "line": row["line"],
                "sub": row["sub"],
                "score": sc,
            }
            if ev not in slot["evidence"]:
                slot["evidence"].append(ev)
        slot["evidence"] = slot["evidence"][:8]

    return out


def write_reports(
    assignments: list[dict],
    form_layout: dict,
    forms: dict[str, str],
    code_moves: dict | None = None,
    form_placements: list[dict] | None = None,
    extract_dir: pathlib.Path | None = None,
    sub_scores: dict[str, int] | None = None,
) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    WEB_LIB.mkdir(parents=True, exist_ok=True)

    code_moves = code_moves or {}
    form_placements = form_placements or []
    used_scores = effective_layout_sub_scores(sub_scores)
    if extract_dir is not None:
        try:
            extract_label = str(extract_dir.resolve().relative_to(REPO)).replace("\\", "/")
        except ValueError:
            extract_label = str(extract_dir).replace("\\", "/")
    else:
        extract_label = _EXTRACT_LABEL or "working/extracts/<stem>"
    try:
        skeletons_label = str(WEB_LIB.resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        skeletons_label = str(WEB_LIB).replace("\\", "/")

    summary = {
        "generated_by": "tools/runtime_layout.py",
        "extract_dir": extract_label,
        "form_count": len(forms),
        "assignment_count": len(assignments),
        "by_kind": {},
        "layout_sub_scores": used_scores,
        "forms": forms,
        "form_show_layout": form_layout,
        "formPlacements": form_placements,
        "code_control_moves": code_moves,
        "assignments": assignments,
        "note": (
            "assignments は Attribute VB_Name 以降のコード部のみ。"
            "設計時 Begin Left/Top は含まない。"
            "layout_sub_scores は builtin + archaeology.config.json。"
        ),
    }
    for row in assignments:
        summary["by_kind"][row["kind"]] = summary["by_kind"].get(row["kind"], 0) + 1

    (REPORTS / "runtime_layout.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # slim JSON for reimplementation consumers
    slim = {
        "generated_by": "tools/runtime_layout.py",
        "twipsNote": "VB6 ScaleMode=1 twips; consumers often map /15 → px",
        "note": "forms=窓位置 · codeControlMoves=Formコード内の Ctrl 座標（Begin プロパティではない）",
        "forms": {
            name: {
                "file": slot["file"],
                "left": slot["left"],
                "top": slot["top"],
                "width": slot["width"],
                "height": slot["height"],
                "picture1Height": slot["picture1Height"],
                "evidence": slot["evidence"][:12],
            }
            for name, slot in sorted(form_layout.items())
        },
        "formPlacements": form_placements,
        "codeControlMoves": {
            vb: {
                ctrl: {
                    "left": slot["left"],
                    "top": slot["top"],
                    "width": slot["width"],
                    "height": slot["height"],
                    "evidence": slot["evidence"][:6],
                }
                for ctrl, slot in sorted(ctrls.items())
                if any(slot.get(k) is not None for k in ("left", "top", "width", "height"))
            }
            for vb, ctrls in sorted(code_moves.items())
        },
        "geometry_hints": load_config().get("geometry_hints") or {},
        "layout_sub_scores": used_scores,
    }
    (WEB_LIB / "runtime-layout.json").write_text(
        json.dumps(slim, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Markdown
    md: list[str] = []
    md.append("# 実行時座標カタログ（全フォーム）\n\n")
    md.append("ツール: `tools/runtime_layout.py`\n")
    md.append(f"抽出: `{extract_label}/*.frm`（+ 参照用 .bas）\n")
    md.append(
        "設計時座標（skeleton / Begin プロパティ）とは別。"
        "**Form コード部**（`Attribute VB_Name` 以降）の "
        "`Left/Top/Width/Height/Visible` 代入。\n\n"
    )
    md.append("## layout_sub_scores（使用値）\n\n")
    md.append("builtin + `archaeology.config.json` のマージ結果。\n\n")
    md.append("| Sub（小文字） | score |\n|---|---:|\n")
    for name, sc in sorted(used_scores.items(), key=lambda x: (-x[1], x[0])):
        md.append(f"| `{name}` | {sc} |\n")
    md.append(
        f"\n名前非依存: 未登録 `*_click` は form_show +{GENERIC_CLICK_BONUS} / "
        f"codeMoves 下限 {CODE_MOVE_CLICK_FLOOR}。\n\n"
    )
    visible_n = sum(
        1 for r in assignments if r["kind"] in ("control_visible", "form_visible")
    )
    md.append("## 総合\n\n")
    md.append(f"| 項目 | 値 |\n|---|---|\n")
    md.append(f"| Forms | {len(forms)} |\n")
    md.append(f"| 代入件数（コード部） | {len(assignments)} |\n")
    md.append(f"| うち Visible | {visible_n} |\n")
    md.append(f"| 経路別 Form 配置 | {len(form_placements)} |\n")
    md.append(f"| codeControlMoves コントロール | "
              f"{sum(len(v) for v in code_moves.values())} |\n")
    for k, v in sorted(summary["by_kind"].items()):
        md.append(f"| kind `{k}` | {v} |\n")
    md.append("\n## 経路別 Form 表示レイアウト\n\n")
    md.append("| Form | From | Via | Left | Top | Width | Height | 証拠 |\n"
              "|---|---|---|---:|---:|---:|---:|---|\n")
    for placement in form_placements:
        ev = "; ".join(
            f"{e.get('sub') or '?'} {e['file']}:L{e['line']} "
            f"{e['prop']}={e['value']}"
            for e in placement["evidence"]
        )
        md.append(
            f"| {placement['form']} | {placement['from']} | {placement['via']} | "
            f"{placement['left']} | {placement['top']} | {placement['width']} | "
            f"{placement['height']} | {ev} |\n"
        )
    md.append("\n## コード内コントロール Move（Begin ではない）\n\n")
    md.append("| Form | Ctrl | Left | Top | Width | Height | 証拠 |\n"
              "|---|---|---:|---:|---:|---:|---|\n")
    for vb, ctrls in sorted(code_moves.items()):
        for ctrl, slot in sorted(ctrls.items()):
            if not any(slot.get(k) is not None for k in ("left", "top", "width", "height")):
                continue
            ev = "; ".join(
                f"{e.get('sub') or '?'} {e['file']}:L{e['line']} "
                f"{e['prop']}={e.get('value', e.get('expr'))}"
                for e in slot["evidence"][:2]
            )
            md.append(
                f"| {vb} | {ctrl} | {slot['left']} | {slot['top']} | "
                f"{slot['width']} | {slot['height']} | {ev} |\n"
            )
    md.append("\n## Form 表示時レイアウト（抽出ベスト）\n\n")
    md.append("| vbName | Left | Top | Width | Height | Picture1.H | 証拠 |\n|---|---:|---:|---:|---:|---:|---|\n")
    for name, slot in sorted(form_layout.items()):
        if not any(
            slot[k] is not None
            for k in ("left", "top", "width", "height", "picture1Height")
        ) and not slot["evidence"]:
            continue
        ev = "; ".join(
            f"{e.get('sub','?')} {e['file']}:L{e['line']} {e['prop']}={e['value']}"
            for e in slot["evidence"][:3]
        )
        md.append(
            f"| {name} | {slot['left']} | {slot['top']} | {slot['width']} | "
            f"{slot['height']} | {slot['picture1Height']} | {ev} |\n"
        )

    md.append("\n## ファイル別（全代入）\n\n")
    by_file: dict[str, list] = {}
    for row in assignments:
        by_file.setdefault(row["file"], []).append(row)
    for fname in sorted(by_file):
        rows = by_file[fname]
        md.append(f"### `{fname}`（{rows[0]['file_vb']}）· {len(rows)} 件\n\n")
        md.append("| L | Sub | kind | 代入 | value | near Show |\n|---|---|---|---|---:|---|\n")
        for row in rows:
            md.append(
                f"| {row['line']} | `{row['sub'] or ''}` | {row['kind']} | "
                f"`{row['object']}.{row['prop']} = {row['expr']}` | "
                f"{row['value'] if row['value'] is not None else '—'} | "
                f"{', '.join(row['near_show'])} |\n"
            )
        md.append("\n")

    md.append("## 再実装への受け渡し\n\n")
    md.append(
        f"- JSON: `{skeletons_label}/runtime-layout.json`"
        "（`forms` + `formPlacements` + `codeControlMoves`）\n"
    )
    md.append(
        "- 親相対式の数値化は `archaeology.config.json` の `geometry_hints` を参照する"
        "（未設定なら親トークンは未解決のまま）\n"
    )
    md.append(
        "- 開経路の優先 Sub スコアは同 config の `layout_sub_scores`"
        "（アプリ固有名は消費者 config に書く。キット既定は form_load / mdiform_load のみ）\n"
    )
    md.append("- セル相対など動的式（`CellLeft` 等）はカタログのみ\n")
    md.append(
        "- Visible はイベント連動が多いため JSON 自動適用せず、"
        "Form 単位で `runtimeLayout.visible` / 専用コンポーネントへ配線"
        "（棚卸し: `form_layout_gap.md`）\n"
    )

    (REPORTS / "runtime_layout.md").write_text("".join(md), encoding="utf-8")
    write_form_layout_gap(assignments, forms, code_moves)


def write_form_layout_gap(
    assignments: list[dict],
    forms: dict[str, str],
    code_moves: dict,
) -> None:
    """Form 別のコード部 L/T/W/H/Visible 件数と着手メモ。"""
    by_vb: dict[str, list[dict]] = {name: [] for name in forms}
    for row in assignments:
        vb = row.get("file_vb")
        if vb in by_vb:
            by_vb[vb].append(row)

    lines: list[str] = []
    lines.append("# Form 別レイアウト・Visible ギャップ（コード部）\n\n")
    lines.append("生成: `tools/runtime_layout.py` → `write_form_layout_gap`\n")
    lines.append(
        "設計時 Begin は skeleton。ここに載るのは **コード部代入のみ**。"
        "消費者リポで Form 単位に適用し、行の「着手」を更新する。\n\n"
    )
    lines.append(
        "| Form | file | geom | Visible | codeMoves | 主な対象 | 着手 |\n"
        "|---|---|---:|---:|---:|---|---|\n"
    )
    for vb, fname in sorted(forms.items(), key=lambda x: x[1].lower()):
        rows = by_vb.get(vb, [])
        geom = sum(
            1
            for r in rows
            if r["kind"]
            in ("control_move", "control_expr", "form_place", "mdi_chrome", "offscreen_hide")
        )
        vis = sum(
            1 for r in rows if r["kind"] in ("control_visible", "form_visible")
        )
        moves = len(code_moves.get(vb, {}))
        ctrls: list[str] = []
        for r in rows:
            if r["kind"] in ("control_move", "control_visible"):
                base = re.sub(r"\(.*\)$", "", r["object"].rsplit(".", 1)[-1])
                if base and base.lower() != "me" and base not in ctrls:
                    ctrls.append(base)
            if len(ctrls) >= 6:
                break
        status = "未精査（消費者リポで到達可否を証拠つき記載）"
        lines.append(
            f"| {vb} | `{fname}` | {geom} | {vis} | {moves} | "
            f"{', '.join(ctrls) or '—'} | {status} |\n"
        )
    lines.append(
        "\n## 順次着手ルール\n\n"
        "1. Startup フォームと Show される子を優先（inventory / deep-read の証拠に従う）\n"
        "2. 各 Form: skeleton（Begin）と本表のコード代入を突き合わせる\n"
        "3. 到達不能は除外または明示（証拠必須）\n"
        "4. 見た目微調整のみは別棚卸しへ\n"
    )
    (REPORTS / "form_layout_gap.md").write_text("".join(lines), encoding="utf-8")


def _resolve_extract(arg: pathlib.Path | None) -> pathlib.Path:
    if arg is not None:
        extract = arg if arg.is_absolute() else REPO / arg
        return extract.resolve()
    root = extracts_root()
    if not root.is_dir():
        raise SystemExit(f"extracts dir missing: {root} (pass --extract)")
    candidates = sorted(p for p in root.iterdir() if p.is_dir())
    if len(candidates) == 1:
        return candidates[0].resolve()
    if not candidates:
        raise SystemExit(f"no extracts under {root}; run extract_vbp.py first")
    names = ", ".join(p.name for p in candidates)
    raise SystemExit(f"multiple extracts ({names}); pass --extract working/extracts/<stem>")


def main() -> int:
    global REPORTS, WEB_LIB
    ap = argparse.ArgumentParser(
        description="Catalog runtime Left/Top/Width/Height/Visible assignments"
    )
    ap.add_argument(
        "--extract",
        type=pathlib.Path,
        default=None,
        help="Extracted project dir (default: sole folder under working/extracts/)",
    )
    args = ap.parse_args()
    extract = _resolve_extract(args.extract)
    REPORTS = reports_root()
    WEB_LIB = skeletons_root()
    REPORTS.mkdir(parents=True, exist_ok=True)
    WEB_LIB.mkdir(parents=True, exist_ok=True)
    if not extract.is_dir():
        print(f"extract not found: {extract}", file=sys.stderr)
        return 1

    forms = discover_forms(extract)
    global KNOWN_FORMS
    KNOWN_FORMS = set(forms)

    assignments: list[dict] = []
    for vb, fname in sorted(forms.items(), key=lambda x: x[1]):
        path = extract / fname
        assignments.extend(extract_file(path, vb))

    # also scan .bas for form geometry (rare)
    for path in sorted(extract.glob("*.bas")):
        assignments.extend(extract_file(path, path.stem))

    global _EXTRACT_LABEL
    try:
        _EXTRACT_LABEL = str(extract.resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        _EXTRACT_LABEL = str(extract).replace("\\", "/")

    sub_scores = effective_layout_sub_scores()
    form_layout = build_form_show_layout(assignments, forms, sub_scores)
    form_placements = build_contextual_form_layout(assignments, forms)
    code_moves = build_code_control_moves(assignments, forms, sub_scores)
    write_reports(
        assignments,
        form_layout,
        forms,
        code_moves,
        form_placements,
        extract_dir=extract,
        sub_scores=sub_scores,
    )

    print(f"forms={len(forms)} assignments={len(assignments)}")
    print(f"formPlacements={len(form_placements)} routes")
    print(f"codeControlMoves={sum(len(v) for v in code_moves.values())} controls")
    print(f"layout_sub_scores={sub_scores}")
    print(f"→ {REPORTS / 'runtime_layout.md'}")
    print(f"→ {WEB_LIB / 'runtime-layout.json'}")
    kinds = {}
    for r in assignments:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    for k, v in sorted(kinds.items()):
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
