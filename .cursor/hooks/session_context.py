#!/usr/bin/env python3
"""sessionStart: remind agent to load kit canon."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

try:
    from tools.status import build_status, format_status_lines  # noqa: E402
except Exception:  # hook must not fail sessionStart
    build_status = None  # type: ignore[assignment]
    format_status_lines = None  # type: ignore[assignment]

CONTEXT = (
    "[vb6-archaeology] Before work: Read AGENTS.md then docs/ai-onboarding.md. "
    "Canon: docs/flow/_master.md. Cycle: verify → understand (tools/) → optional implement. "
    "Protected dirs (default source/, see archaeology.config.json) are read-only "
    "(exception: python -m tools fixture). "
    "Commands: /vb6-extract /vb6-inventory /frm-deep-read /runtime-layout "
    "/vb6-comprehend /vb6-report /vb6-verify-reports /serve-reports /kit-smoke. "
    "Reimpl excerpt: python -m tools excerpt or serve /excerpt. "
    "Pipeline status: python -m tools status. "
    "config-check: python -m tools config-check."
)


def _status_block() -> str:
    fallback = (
        "stem=- extract=no inventory=no\n"
        "deep-read=0/0 ticks=0/0 excerpt=no\n"
        "verify=not persisted layout=no"
    )
    if build_status is None or format_status_lines is None:
        return fallback
    try:
        return format_status_lines(build_status(REPO))
    except Exception:
        return fallback


def main() -> int:
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        _ = json.loads(sys.stdin.read() or "{}")
    except Exception:
        pass

    extra = CONTEXT + "\n" + _status_block()
    print(
        json.dumps(
            {
                "env": {
                    "VB6_ARCHAEOLOGY": "1",
                    "VB6_AI_ONBOARDING": "docs/ai-onboarding.md",
                },
                "additional_context": extra,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
