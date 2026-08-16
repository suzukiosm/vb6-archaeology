"""Heuristic Show / MDIChild → show_style candidates for reimplementation.

Candidates (see docs/reimplementation-handoff.md):
  mdi_child | modal_overlay | navigate | unknown

Only ``vbModal`` / ``MDIChild=-1`` get a positive style; bare ``.Show`` stays
``unknown`` so agents do not treat every Show as a full-page navigate.
"""

from __future__ import annotations

import re
from pathlib import Path

SHOW_CALL_RE = re.compile(
    r"\b([A-Za-z_][\w]*)\.Show(?:\s+(vbModal|vbModeless|\d+))?\b",
    re.IGNORECASE,
)

SHOW_STYLES = frozenset({"mdi_child", "modal_overlay", "navigate", "unknown"})


def classify_show_arg(arg: str | None) -> str:
    """Map a Show argument to a show_style candidate."""
    if arg is None or str(arg).strip() == "":
        return "unknown"
    a = str(arg).strip().lower()
    if a in ("vbmodal", "1"):
        return "modal_overlay"
    # vbModeless / 0: evidence only — do not claim navigate without agreement
    return "unknown"


def self_show_style(*, mdi_child: bool | None, form_kind: str = "") -> dict:
    """Candidate for how *this* form should appear when shown by a parent."""
    kind = (form_kind or "").strip()
    if mdi_child is True:
        return {
            "show_style": "mdi_child",
            "confidence": "heuristic",
            "evidence": "MDIChild <> 0",
        }
    if kind.endswith("MDIForm") or kind == "VB.MDIForm":
        return {
            "show_style": "unknown",
            "confidence": "heuristic",
            "evidence": "VB.MDIForm (shell; not a child)",
            "note": "MDI parent — children use mdi_child",
        }
    if mdi_child is False:
        return {
            "show_style": "unknown",
            "confidence": "heuristic",
            "evidence": "MDIChild = 0",
        }
    return {
        "show_style": "unknown",
        "confidence": "none",
        "evidence": None,
    }


def parse_show_calls_in_line(line: str, line_no: int) -> list[dict]:
    """Extract Show calls from one code line (CP932-decoded unicode)."""
    s = line.strip()
    if not s or s.startswith("'"):
        return []
    out = []
    for sm in SHOW_CALL_RE.finditer(s):
        target = sm.group(1)
        arg = sm.group(2)
        out.append(
            {
                "target": target,
                "arg": arg,
                "show_style": classify_show_arg(arg),
                "line": line_no,
                "text": s[:160],
            }
        )
    return out


def _form_lookup_key(entry: dict) -> str:
    vb = str(entry.get("vb_name") or "").strip()
    if vb:
        return vb.lower()
    return Path(str(entry.get("file") or "")).stem.lower()


def invert_show_calls(files: list[dict]) -> tuple[dict[str, list[dict]], list[dict]]:
    """Transpose existing ``show_calls`` onto their targets.

    Does not scan new source or invent edges. A target string that does not
    uniquely match an inventory Form (``vb_name``, then file stem) is listed
    under unresolved instead of being attached to a form.
    """
    forms = [f for f in files if str(f.get("type") or "").lower() == "form"]
    by_vb: dict[str, list[dict]] = {}
    by_stem: dict[str, list[dict]] = {}
    for form in forms:
        vb = str(form.get("vb_name") or "").strip()
        if vb:
            by_vb.setdefault(vb.lower(), []).append(form)
        stem = Path(str(form.get("file") or "")).stem
        if stem:
            by_stem.setdefault(stem.lower(), []).append(form)

    inbound: dict[str, list[dict]] = {_form_lookup_key(f): [] for f in forms}
    unresolved: list[dict] = []

    for src in files:
        for call in src.get("show_calls") or []:
            target = str(call.get("target") or "").strip()
            rec = {
                "from_file": src.get("file"),
                "from_vb_name": src.get("vb_name"),
                "target": target,
                "arg": call.get("arg"),
                "show_style": call.get("show_style", "unknown"),
                "line": call.get("line"),
                "text": call.get("text"),
            }
            if not target:
                rec["reason"] = "unresolved"
                unresolved.append(rec)
                continue
            hits = by_vb.get(target.lower()) or []
            if not hits:
                hits = by_stem.get(target.lower()) or []
            if len(hits) != 1:
                rec["reason"] = "ambiguous" if len(hits) > 1 else "unresolved"
                unresolved.append(rec)
                continue
            inbound.setdefault(_form_lookup_key(hits[0]), []).append(rec)
    return inbound, unresolved


def attach_show_inbound(report: dict) -> dict:
    """Add ``show_inbound`` on each Form and ``show_unresolved`` on the report."""
    files = report.get("files") or []
    inbound_map, unresolved = invert_show_calls(files)
    for entry in files:
        if str(entry.get("type") or "").lower() != "form":
            continue
        entry["show_inbound"] = list(inbound_map.get(_form_lookup_key(entry), []))
    report["show_unresolved"] = unresolved
    return report
