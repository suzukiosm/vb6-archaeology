"""VB6 declarators: variables, parameters and implicit types (facts only).

The type of an undeclared name is decided mechanically by VB6, so it is a fact
the kit can record with its reason (``type_source``):
``as`` (``As T``), ``suffix`` (``Name$``), ``deftype`` (``DefInt A-Z``) or
``default`` (Variant). ``Dim a, b As Long`` makes ``a`` a Variant; each
declarator is resolved on its own. Parameters are ``ByRef`` unless ``ByVal``
is written (``passing_explicit`` says which).
"""

from __future__ import annotations

import re

from .vbparse import IDENT

TYPE_SUFFIXES: dict[str, str] = {
    "%": "Integer", "&": "Long", "!": "Single", "#": "Double", "@": "Currency", "$": "String",
}
DEFTYPE_NAMES: dict[str, str] = {
    "bool": "Boolean", "byte": "Byte", "int": "Integer", "lng": "Long", "cur": "Currency",
    "sng": "Single", "dbl": "Double", "dec": "Decimal", "date": "Date", "str": "String",
    "obj": "Object", "var": "Variant",
}
_SUFFIX_CLASS = "[%&!#@$]"
DEFTYPE_RE = re.compile(r"^Def(Bool|Byte|Int|Lng|Cur|Sng|Dbl|Dec|Date|Str|Obj|Var)\s+(.+)$",
                        re.IGNORECASE)
_RANGE_RE = re.compile(r"^([A-Za-z])(?:\s*-\s*([A-Za-z]))?$")
_VAR_DECL_RE = re.compile(
    rf"^({IDENT})({_SUFFIX_CLASS})?\s*(?:\(([^)]*)\))?\s*(?:As\s+(New\s+)?(.+?))?\s*$",
    re.IGNORECASE,
)
_PASSING = {"byval": "ByVal", "byref": "ByRef"}
_PARAM_KEYWORDS = frozenset({"byval", "byref", "optional", "paramarray"})
_PARAM_RE = re.compile(
    r"^(?:(Optional)\s+)?(?:(ByVal|ByRef)\s+)?(?:(ParamArray)\s+)?"
    rf"({IDENT})({_SUFFIX_CLASS})?\s*(\(\s*\))?\s*(?:As\s+(.+?))?\s*(?:=\s*(.+))?$",
    re.IGNORECASE,
)


def split_top_level(text: str, sep: str = ",") -> list[str]:
    """Split on ``sep`` outside double-quoted strings and parentheses."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    in_str = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '"':
            if in_str and i + 1 < len(text) and text[i + 1] == '"':
                buf.append('""')
                i += 2
                continue
            in_str = not in_str
        elif not in_str and ch == "(":
            depth += 1
        elif not in_str and ch == ")":
            depth = max(0, depth - 1)
        elif not in_str and depth == 0 and ch == sep:
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail or parts:
        parts.append(tail)
    return parts


def parse_deftype(stmt: str, line: int) -> dict | None:
    """``DefInt A-Z, I`` → ``{type, ranges, line}``; None if not a Deftype statement."""
    m = DEFTYPE_RE.match(stmt)
    if not m:
        return None
    ranges = [r.replace(" ", "") for r in split_top_level(m.group(2)) if r]
    return {"type": DEFTYPE_NAMES[m.group(1).lower()], "ranges": ranges, "line": line}


def deftype_letters(deftypes: list[dict]) -> dict[str, str]:
    """Upper-case first letter → type. Later statements override earlier ones."""
    letters: dict[str, str] = {}
    for item in deftypes:
        for rng in item["ranges"]:
            m = _RANGE_RE.match(rng)
            if not m:
                continue
            lo, hi = m.group(1).upper(), (m.group(2) or m.group(1)).upper()
            for code in range(ord(min(lo, hi)), ord(max(lo, hi)) + 1):
                letters[chr(code)] = item["type"]
    return letters


def resolve_type(name: str, suffix: str | None, declared: str | None,
                 letters: dict[str, str]) -> tuple[str, str]:
    """(type, type_source) by VB6's precedence: As > suffix > Deftype > Variant."""
    if declared:
        return declared, "as"
    if suffix:
        return TYPE_SUFFIXES[suffix], "suffix"
    first = name[:1].upper()
    if first in letters:
        return letters[first], "deftype"
    return "Variant", "default"


def parse_var_declarators(rest: str, letters: dict[str, str] | None = None) -> list[dict]:
    """``a, b(1 To 3) As Long, c$`` → one record per declarator."""
    out: list[dict] = []
    for part in split_top_level(rest):
        m = _VAR_DECL_RE.match(part)
        if not m:
            continue
        name, suffix, dims, new, declared = m.groups()
        declared = declared.strip() if declared else None
        typ, source = resolve_type(name, suffix, declared, letters or {})
        out.append({
            "name": name,
            "type": typ,
            "type_source": source,
            "type_suffix": suffix,
            "new": bool(new),
            "is_array": dims is not None,
            "dims": dims.strip() if dims is not None else None,
        })
    return out


def parse_params(params: str, letters: dict[str, str] | None = None) -> list[dict]:
    """Structured parameters. Unparsed pieces keep their raw text under ``raw``."""
    out: list[dict] = []
    for part in split_top_level(params or ""):
        if not part:
            continue
        m = _PARAM_RE.match(part)
        if not m or m.group(4).casefold() in _PARAM_KEYWORDS:
            out.append({"raw": part})
            continue
        optional, passing, param_array, name, suffix, array, declared, default = m.groups()
        declared = declared.strip() if declared else None
        typ, source = resolve_type(name, suffix, declared, letters or {})
        out.append({
            "name": name,
            "passing": _PASSING[passing.lower()] if passing else "ByRef",
            "passing_explicit": passing is not None,
            "optional": optional is not None,
            "param_array": param_array is not None,
            "is_array": array is not None,
            "type": typ,
            "type_source": source,
            "default": default.strip() if default is not None else None,
        })
    return out
