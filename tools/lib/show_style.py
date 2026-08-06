"""Heuristic Show / MDIChild → show_style candidates for reimplementation.

Candidates (see docs/reimplementation-handoff.md):
  mdi_child | modal_overlay | navigate | unknown

Only ``vbModal`` / ``MDIChild=-1`` get a positive style; bare ``.Show`` stays
``unknown`` so agents do not treat every Show as a full-page navigate.
"""

from __future__ import annotations

import re

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
