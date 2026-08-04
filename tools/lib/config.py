"""Load archaeology.config.json from the kit / consumer repo root."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parent
CONFIG_NAME = "archaeology.config.json"

DEFAULTS: dict = {
    "protected_source_dirs": ["source"],
    "protected_path_markers": [],
    "default_source_dir": "source",
    "extracts_dir": "working/extracts",
    "reports_dir": "working/reports",
    "skeletons_dir": "working/skeletons",
    "encoding": "cp932",
    "encoding_fallbacks": ["utf-8-sig", "utf-8"],
    "reports_http_port": 8765,
    "geometry_hints": {},
    "deep_read_name_map": {},
    "layout_sub_scores": {
        "form_load": 80,
        "mdiform_load": 80,
    },
    "picture1_height_by_sub": {},
    "verify_report_allow_files": [],
}


@lru_cache(maxsize=1)
def load_config(repo_root: Path | None = None) -> dict:
    root = (repo_root or REPO_ROOT).resolve()
    path = root / CONFIG_NAME
    data = dict(DEFAULTS)
    if path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            data.update({k: v for k, v in raw.items() if not str(k).startswith("$")})
    data["_repo_root"] = root
    data["_config_path"] = path
    return data


def protected_dir_names(repo_root: Path | None = None) -> list[str]:
    """In-repo directory names that must stay read-only.

    An empty list is a valid answer: consumers whose VB6 originals live outside
    the repo protect them with protected_path_markers instead.
    """
    cfg = load_config(repo_root)
    names = cfg.get("protected_source_dirs")
    if names is None:
        names = DEFAULTS["protected_source_dirs"]
    return [str(n) for n in names]


def protected_path_markers(repo_root: Path | None = None) -> list[str]:
    """Path segments that are read-only wherever they appear, in or out of repo."""
    cfg = load_config(repo_root)
    markers = cfg.get("protected_path_markers")
    if markers is None:
        markers = DEFAULTS["protected_path_markers"]
    return [str(m) for m in markers]


def path_hits_protected_marker(path, repo_root: Path | None = None) -> str | None:
    """Return the marker a path contains as a segment, or None."""
    parts = [p for p in str(path).replace("\\", "/").split("/") if p]
    for marker in protected_path_markers(repo_root):
        if marker in parts:
            return marker
    return None


def default_source_root(
    repo_root: Path | None = None, fallback: Path | None = None
) -> Path:
    cfg = load_config(repo_root)
    root = Path(cfg["_repo_root"])
    name = cfg.get("default_source_dir") or ""
    if name:
        candidate = root / name
        if candidate.is_dir():
            return candidate
    for alt in protected_dir_names(root):
        p = root / alt
        if p.is_dir():
            return p
    if fallback is not None:
        return fallback.resolve()
    raise SystemExit(
        f"No protected source directory found under {root}. "
        f"Create '{name or 'source'}/' and set default_source_dir in {CONFIG_NAME}, "
        "or — when the originals live outside the repo — list their path segment "
        "in protected_path_markers and pass --source-root."
    )


def extracts_root(repo_root: Path | None = None) -> Path:
    cfg = load_config(repo_root)
    return Path(cfg["_repo_root"]) / cfg["extracts_dir"]


def reports_root(repo_root: Path | None = None) -> Path:
    cfg = load_config(repo_root)
    return Path(cfg["_repo_root"]) / cfg["reports_dir"]


def skeletons_root(repo_root: Path | None = None) -> Path:
    cfg = load_config(repo_root)
    return Path(cfg["_repo_root"]) / cfg["skeletons_dir"]


def decode_vb6_bytes(raw: bytes, repo_root: Path | None = None) -> str:
    cfg = load_config(repo_root)
    primary = cfg.get("encoding") or "cp932"
    fallbacks = list(cfg.get("encoding_fallbacks") or [])
    for enc in [primary, *fallbacks]:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode(primary, errors="replace")
