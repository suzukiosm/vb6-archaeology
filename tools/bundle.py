#!/usr/bin/env python3
"""Print a token-budgeted context bundle for one procedure from the AI index.

Reads ``<index_dir>/<stem>/`` written by ``python -m tools index``. Sections in
priority order; the procedure code is always included, the rest is added while
the estimate stays within ``--budget`` and anything left out is listed:

1. the procedure chunk (header + code with physical line numbers)
2. VB6 notes (On Error Resume Next, implicit ByRef, Option Explicit …)
3. effects in the procedure (file / DB / SQL literal / COM / UI …)
4. outbound references resolved to one symbol (one summary line each)
5. inbound reference candidates (where this procedure's name is used)
6. the module declarations chunk, and the designer chunk for event handlers
7. code of referenced procedures

References are scope-rule candidates from the index, not a call graph.

    python -m tools bundle Command1_Click@Form1.frm
    python -m tools bundle Value@Widget.cls --kind "Property Get" --budget 2000 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from index_build import estimate_tokens, format_stale, snapshot_problems  # noqa: E402
from lib.config import index_root  # noqa: E402
from lib.console import enable_utf8_stdio  # noqa: E402

PROCEDURE_KINDS = frozenset({"Sub", "Function", "Property Get", "Property Let", "Property Set"})


def load_index(index_dir: Path) -> dict:
    def jsonl(name: str) -> list[dict]:
        path = index_dir / f"{name}.jsonl"
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    return {
        "manifest": json.loads((index_dir / "manifest.json").read_text(encoding="utf-8")),
        "symbols": jsonl("symbols"),
        "occurrences": jsonl("occurrences"),
        "effects": jsonl("effects"),
        "chunks": jsonl("chunks"),
    }


def find_target(symbols: list[dict], name: str, file_hint: str | None, kind: str | None) -> dict:
    matches = [
        s for s in symbols
        if s["kind"] in PROCEDURE_KINDS and s["name"].casefold() == name.casefold()
        and (file_hint is None or Path(s["file"]).name.casefold() == Path(file_hint).name.casefold()
             or Path(s["file"]).stem.casefold() == Path(file_hint).stem.casefold())
        and (kind is None or s["kind"].casefold() == kind.casefold())
    ]
    if not matches:
        raise SystemExit(f"'{name}' is not a procedure in the index; run `python -m tools index` after inventory")
    if len(matches) > 1:
        ids = ", ".join(s["id"] for s in matches)
        raise SystemExit(f"'{name}' matches several procedures ({ids}); use NAME@FILE and/or --kind")
    return matches[0]


def _owner_context(index: dict, target: dict, by_id: dict[str, dict]) -> str:
    """Module and project facts the procedure body does not repeat."""
    file_sym = by_id.get(target["file"]) or {}
    lines: list[str] = []
    implements = file_sym.get("implements") or []
    if implements:
        lines.append("Implements: " + ", ".join(
            item["name"] if isinstance(item, dict) else str(item) for item in implements
        ))
    for key, label in (
        ("vb_predeclared_id", "VB_PredeclaredId"),
        ("vb_global_name_space", "VB_GlobalNameSpace"),
        ("default_member", "default member"),
        ("instancing", "Instancing"),
    ):
        value = file_sym.get(key)
        if value not in (None, "", [], {}):
            lines.append(f"{label}: {value}")
    for ref in file_sym.get("resource_refs") or []:
        if not ref.get("exists"):
            lines.append(f"欠落資源 L{ref.get('line')} {ref.get('file')}（中身は未解析）")
    project = index.get("manifest", {}).get("references") or []
    if project:
        lines.append("References: " + "; ".join(
            " ".join(str(item.get(key)) for key in ("kind", "guid", "lcid", "description") if item.get(key))
            for item in project
        ))
    return "\n".join(lines)


def summary_line(sym: dict) -> str:
    kind = sym["kind"]
    where = f"{sym['file']}:{sym.get('line') or (sym.get('span') or ['?'])[0]}"
    if kind in PROCEDURE_KINDS:
        params = ", ".join(
            p.get("raw") or f"{p['passing']}{'' if p.get('passing_explicit') else '(省略)'} {p['name']} As {p['type']}"
            for p in sym.get("params") or []
        )
        ret = f" As {sym['return_type']}" if sym.get("return_type") else ""
        return f"{sym.get('visibility') or ''} {kind} {sym['name']}({params}){ret} — {where}".strip()
    if kind == "Variable":
        return f"{sym.get('visibility')} {sym['name']} As {sym.get('type')} ({sym.get('type_source')}) — {where}"
    if kind in ("Const", "EnumMember"):
        value = f" = {sym['value']}" if "value" in sym else ""
        return f"{kind} {sym['name']}{value} — {where}"
    if kind == "Declare":
        alias = f" Alias \"{sym['alias']}\"" if sym.get("alias") else ""
        return f"Declare {sym['name']} Lib \"{sym.get('lib')}\"{alias} — {where}"
    if kind == "Control":
        return f"Control {sym['name']} ({sym.get('class')}) — {where}"
    if kind == "File":
        return f"{sym.get('form_kind') or sym.get('type')} {sym['name']} — {sym['file']}"
    return f"{kind} {sym['name']} — {where}"


def _overlaps(span: list[int], wanted: tuple[int, int]) -> bool:
    start, end = span
    lo, hi = wanted
    return not (end < lo or start > hi)


def _part_rows(index: dict, parent_id: str) -> list[dict]:
    rows = [chunk for chunk in index["chunks"] if chunk.get("parent") == parent_id]
    return sorted(rows, key=lambda chunk: chunk.get("stmt") or 0)


def build_bundle(index: dict, target: dict, budget: int,
                 span: tuple[int, int] | None = None) -> dict:
    by_id = {s["id"]: s for s in index["symbols"]}
    chunks = {c["id"]: c for c in index["chunks"]}
    main = chunks[f"chunk:{target['id']}"]
    sections: list[dict] = []
    omitted: list[str] = []
    used = 0

    def add(title: str, body: str, required: bool = False) -> bool:
        nonlocal used
        cost = estimate_tokens(title + body)
        if not required and used + cost > budget:
            omitted.append(title)
            return False
        sections.append({"title": title, "body": body, "tokens_est": cost})
        used += cost
        return True

    procedure_title = f"Procedure {target['id']}"
    procedure_body = f"{main['header']}\n```vb\n{main['code']}\n```"
    procedure_tokens = estimate_tokens(procedure_title + procedure_body)
    children = _part_rows(index, main["id"])
    if span is not None:
        children = [child for child in children if _overlaps(child["span"], span)]
    part_list = [
        {"id": child["id"], "span": child["span"], "stmt": child.get("stmt"),
         "tokens_est": child["tokens_est"]}
        for child in _part_rows(index, main["id"])
    ]
    context = _owner_context(index, target, by_id)
    notes_body = "\n".join(f"- {n}" for n in main["notes"]) if main["notes"] else ""
    full_fits = span is None and procedure_tokens <= budget
    if full_fits:
        add(procedure_title, procedure_body, required=True)
        if context:
            add("Owner context", context, required=True)
        if notes_body:
            add("VB6 notes", notes_body)
        for row in part_list:
            row["included"] = False
    else:
        add(f"Procedure head {target['id']}", main["header"], required=True)
        if context:
            add("Owner context", context, required=True)
        if notes_body:
            add("VB6 notes", notes_body, required=True)
        included_stmts: set[int] = set()
        for child in children:
            title = f"Part {child['stmt']} L{child['span'][0]}-{child['span'][1]}"
            if add(title, child["code"]):
                included_stmts.add(child["stmt"])
        for row in part_list:
            row["included"] = row.get("stmt") in included_stmts
    minimum_tokens = used
    effects = [e for e in index["effects"] if e.get("in") == target["id"]]
    if effects:
        add("Effects (facts)", "\n".join(
            f"- L{e['line']} {e['kind']}: {e['text']}" for e in effects))
    outbound = [by_id[r] for r in main["refs"] if r in by_id]
    if outbound:
        add("Outbound references (resolved candidates)", "\n".join(f"- {summary_line(s)}" for s in outbound))
    inbound = [o for o in index["occurrences"] if target["id"] in o["candidates"] and o.get("in") != target["id"]]
    if inbound:
        add("Inbound reference candidates", "\n".join(
            f"- {o['file']}:{o['line']} in {o.get('in') or '(module level)'} "
            f"({o['context']}, {o['basis']}, {o['resolution']})" for o in inbound))
    decl = chunks.get(f"chunk:{target['file']}#declarations")
    if decl:
        add(f"Module declarations {target['file']}", f"```vb\n{decl['code']}\n```")
    designer = chunks.get(f"chunk:{target['file']}#designer")
    if designer and target.get("event"):
        add(f"Designer {target['file']}", designer["code"])
    for sym in outbound:
        chunk = chunks.get(f"chunk:{sym['id']}")
        if chunk:
            body = f"{chunk['header']}\n```vb\n{chunk['code']}\n```"
            owner = _owner_context(index, sym, by_id)
            if owner:
                body = owner + "\n" + body
            add(f"Referenced procedure {sym['id']}", body)
    gaps = list(main.get("ref_gaps") or [])
    if gaps:
        add("Unresolved or ambiguous references", "\n".join(
            f"- L{g['line']} {g['name']} ({g.get('resolution')}, {g.get('basis')}): {g.get('reason')}"
            for g in gaps
        ))
    return {"target": target["id"], "budget": budget, "tokens_est": used,
            "sections": sections, "omitted": omitted, "unresolved": gaps,
            "budget_exceeded": used > budget or (span is None and not full_fits),
            "procedure_exceeds_budget": procedure_tokens > budget,
            "minimum_tokens": minimum_tokens,
            "parts": part_list,
            "span": list(span) if span else None,
            "note": "references are scope-rule candidates from the index, not a call graph. "
                    "token counts are an estimate."}


def render_markdown(bundle: dict) -> str:
    parts = [f"# Context bundle: {bundle['target']}",
             f"tokens_est {bundle['tokens_est']} / budget {bundle['budget']} · {bundle['note']}"]
    for section in bundle["sections"]:
        parts.append(f"## {section['title']}\n{section['body']}")
    if bundle["omitted"]:
        parts.append("## Omitted (budget)\n" + "\n".join(f"- {t}" for t in bundle["omitted"]))
    titles = {section["title"] for section in bundle["sections"]}
    if bundle.get("unresolved") and "Unresolved or ambiguous references" not in titles:
        parts.append("## Unresolved or ambiguous references\n" + "\n".join(
            f"- L{item['line']} {item['name']}: {item.get('reason')}" for item in bundle["unresolved"]
        ))
    if bundle.get("budget_exceeded"):
        parts.append("budget_exceeded")
    return "\n\n".join(parts) + "\n"


def _parse_span(text: str) -> tuple[int, int]:
    try:
        start_text, end_text = text.split("-", 1)
        start, end = int(start_text), int(end_text)
    except ValueError:
        raise SystemExit("--span is START-END") from None
    if start < 1 or end < start:
        raise SystemExit("--span is START-END")
    return start, end


def resolve_index_dir(arg: Path | None) -> Path:
    if arg is not None:
        path = arg if arg.is_absolute() else REPO / arg
    else:
        root = index_root()
        cands = sorted(p for p in root.iterdir() if (p / "manifest.json").is_file()) if root.is_dir() else []
        if len(cands) != 1:
            raise SystemExit(f"pass --index (found {len(cands)} indexes under {root}); run `python -m tools index`")
        path = cands[0]
    if not (path / "manifest.json").is_file():
        raise SystemExit(f"no manifest.json under {path}; run `python -m tools index`")
    return path


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    ap = argparse.ArgumentParser(description="Token-budgeted context bundle for one procedure (from the AI index)")
    ap.add_argument("target", metavar="PROC[@FILE]")
    ap.add_argument("--kind", choices=sorted(PROCEDURE_KINDS), default=None)
    ap.add_argument("--budget", type=int, default=3000, help="Token estimate budget (default 3000)")
    ap.add_argument("--index", type=Path, default=None, help="Index dir (default: sole one under index_dir)")
    ap.add_argument("--span", default=None, metavar="START-END",
                    help="Physical lines to take instead of the whole procedure")
    ap.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    args = ap.parse_args(argv)
    span = _parse_span(args.span) if args.span else None

    index = load_index(resolve_index_dir(args.index))
    manifest = index["manifest"]
    extract = manifest.get("extract_dir")
    if not extract:
        print(format_stale(["index に抽出先が無い"]), file=sys.stderr)
        return 1
    problems = snapshot_problems(manifest, Path(extract))
    if problems:
        print(format_stale(problems), file=sys.stderr)
        return 1
    name, _, file_hint = args.target.partition("@")
    target = find_target(index["symbols"], name, file_hint or None, args.kind)
    bundle = build_bundle(index, target, args.budget, span=span)
    if span and not any(part.get("included") for part in bundle["parts"]):
        print(f"no statement in lines {span[0]}-{span[1]}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(bundle), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
