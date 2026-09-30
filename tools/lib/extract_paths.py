"""Resolve VBP references to local analysis copies, never to external originals."""
import json
from pathlib import Path, PureWindowsPath


def reference_key(value: str) -> str:
    return PureWindowsPath(value).as_posix().casefold()


def load_source_map(root: Path) -> dict[str, str] | None:
    report = root / '_extract_report.json'
    if not report.is_file():
        return None
    data = json.loads(report.read_text(encoding='utf-8'))
    if 'source_map' not in data:  # legacy extract: only safe local paths work
        return None
    result = {}
    for entry in data['source_map']:
        key = reference_key(entry['reference'])
        target = entry['copy']
        if key in result and result[key] != target:
            raise ValueError(f'ambiguous extract mapping: {key}')
        result[key] = target
    return result


def resolve_source(root: Path, reference: str, mapping: dict[str, str] | None) -> Path | None:
    value = reference if mapping is None else mapping.get(reference_key(reference))
    if value is None:
        return None
    win = PureWindowsPath(value)
    if win.drive or win.root or '..' in win.parts:
        return None
    path = root.joinpath(*win.parts).resolve()
    if not path.is_relative_to(root.resolve()):
        return None
    return path if path.is_file() else None
