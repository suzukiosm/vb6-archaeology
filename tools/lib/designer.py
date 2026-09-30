"""VB6 designer blocks: ``Begin <class> <name>`` … ``End`` with raw properties.

Shared by inventory and deep-read so both see the same control tree. Rules:
- ``BeginProperty X`` … ``EndProperty`` blocks (Font, Panels, Buttons …) belong
  to the enclosing control but are kept apart in ``property_blocks``; their
  ``Caption`` / ``Width`` never overwrite the control's own values.
- Strings unescape ``""``. ``$"Form1.frx":0000`` (string) and
  ``"Form1.frx":0000`` (binary) are recorded in ``frx_refs``; the ``.frx`` bytes
  are not read.
- Values are raw: an int when the text is an integer, else the text without a
  trailing ``'`` comment. Nothing is translated (``Visible = 0`` stays 0).
"""

from __future__ import annotations

import re

_BEGIN_RE = re.compile(r"^Begin\s+(\S+)\s+(\S+)\s*$")
_BEGIN_PROPERTY_RE = re.compile(r"^BeginProperty\s+(\S+)")
_PROPERTY_RE = re.compile(r"^([A-Za-z_][\w.()]*)\s*=\s*(.*)$")
_FRX_RE = re.compile(r'^(\$?)"([^"]*)":([0-9A-Fa-f]+)')
_ATTRIBUTE_VB_NAME_RE = re.compile(r"^Attribute\s+VB_Name\b", re.IGNORECASE)

DATA_BINDING_KEYS = (
    "DataSource", "DataField", "DataMember", "DatabaseName", "RecordSource",
    "RecordsetType", "Connect", "ConnectionString", "CommandType", "Exclusive", "ReadOnly",
)


def _quoted(text: str) -> tuple[str, str] | None:
    """(unescaped string, rest) for a leading VB string literal."""
    if not text.startswith('"'):
        return None
    out: list[str] = []
    i = 1
    while i < len(text):
        if text[i] == '"':
            if i + 1 < len(text) and text[i + 1] == '"':
                out.append('"')
                i += 2
                continue
            return "".join(out), text[i + 1:]
        out.append(text[i])
        i += 1
    return "".join(out), ""


def parse_property_value(text: str) -> tuple[object, dict | None]:
    """(value, frx reference or None) for the right-hand side of ``Key = …``."""
    text = text.strip()
    frx = _FRX_RE.match(text)
    if frx:
        kind = "string" if frx.group(1) else "binary"
        return None, {"file": frx.group(2), "offset": frx.group(3), "kind": kind}
    quoted = _quoted(text)
    if quoted is not None:
        return quoted[0], None
    raw = text.split("'", 1)[0].strip()
    if re.fullmatch(r"-?\d+", raw):
        return int(raw), None
    return raw, None


def parse_designer(lines: list[str]) -> list[dict]:
    """Designer nodes in document order (root first).

    Each node: ``kind`` · ``name`` · ``line`` · ``end_line`` · ``depth`` ·
    ``parent`` (node index or None) · ``props`` · ``frx_refs`` ·
    ``property_blocks`` (``{"path", "line", "props"}``). Parsing stops at
    ``Attribute VB_Name`` where the code section begins.
    """
    nodes: list[dict] = []
    stack: list[int] = []
    blocks: list[dict] = []  # open BeginProperty blocks of the current control
    for idx, raw in enumerate(lines, start=1):
        s = raw.strip()
        if _ATTRIBUTE_VB_NAME_RE.match(s):
            break
        bp = _BEGIN_PROPERTY_RE.match(s)
        if bp and stack:
            path = "/".join([*(b["name"] for b in blocks), bp.group(1)])
            block = {"name": bp.group(1), "path": path, "line": idx, "props": {}}
            nodes[stack[-1]]["property_blocks"].append(block)
            blocks.append(block)
            continue
        if s == "EndProperty" and blocks:
            blocks.pop()
            continue
        m = _BEGIN_RE.match(s)
        if m and not blocks:
            nodes.append({
                "kind": m.group(1), "name": m.group(2), "line": idx, "end_line": None,
                "depth": len(stack), "parent": stack[-1] if stack else None,
                "props": {}, "frx_refs": [], "property_blocks": [],
            })
            stack.append(len(nodes) - 1)
            continue
        if s == "End" and stack and not blocks:
            nodes[stack.pop()]["end_line"] = idx
            continue
        pm = _PROPERTY_RE.match(s)
        if pm and stack:
            value, frx = parse_property_value(pm.group(2))
            target = blocks[-1]["props"] if blocks else nodes[stack[-1]]["props"]
            target[pm.group(1)] = value
            if frx is not None:
                nodes[stack[-1]]["frx_refs"].append({"prop": pm.group(1), "line": idx, **frx})
    for node in nodes:
        if node["end_line"] is None:
            node["end_line"] = len(lines)
    return nodes


def data_binding(props: dict) -> dict:
    """The data-binding subset of a control's raw properties (may be empty)."""
    lower = {k.lower(): k for k in props}
    return {key: props[lower[key.lower()]] for key in DATA_BINDING_KEYS if key.lower() in lower}
