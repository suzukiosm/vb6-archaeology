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

from index_build import estimate_tokens  # noqa: E402
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


def build_bundle(index: dict, target: dict, budget: int) -> dict:
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

    add(f"Procedure {target['id']}", f"{main['header']}\n```vb\n{main['code']}\n```", required=True)
    if main["notes"]:
        add("VB6 notes", "\n".join(f"- {n}" for n in main["notes"]))
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
            add(f"Referenced procedure {sym['id']}", f"{chunk['header']}\n```vb\n{chunk['code']}\n```")
    return {"target": target["id"], "budget": budget, "tokens_est": used,
            "sections": sections, "omitted": omitted,
            "note": "references are scope-rule candidates from the index, not a call graph"}


def render_markdown(bundle: dict) -> str:
    parts = [f"# Context bundle: {bundle['target']}",
             f"tokens_est {bundle['tokens_est']} / budget {bundle['budget']} · {bundle['note']}"]
    for section in bundle["sections"]:
        parts.append(f"## {section['title']}\n{section['body']}")
    if bundle["omitted"]:
        parts.append("## Omitted (budget)\n" + "\n".join(f"- {t}" for t in bundle["omitted"]))
    return "\n\n".join(parts) + "\n"


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
    ap.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    args = ap.parse_args(argv)

    index = load_index(resolve_index_dir(args.index))
    name, _, file_hint = args.target.partition("@")
    target = find_target(index["symbols"], name, file_hint or None, args.kind)
    bundle = build_bundle(index, target, args.budget)
    if args.json:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(bundle), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
