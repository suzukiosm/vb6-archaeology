#!/usr/bin/env python3
"""sessionStart: remind agent to load kit canon."""

from __future__ import annotations

import json
import sys

CONTEXT = (
    "[vb6-archaeology] Before work: Read AGENTS.md then docs/ai-onboarding.md. "
    "Canon: docs/flow/_master.md. Cycle: verify → understand (tools/) → optional implement. "
    "Protected dirs (default source/, see archaeology.config.json) are read-only "
    "(exception: python tools/make_fixture.py). "
    "Commands: /vb6-extract /vb6-inventory /frm-deep-read /vb6-comprehend "
    "/vb6-report /vb6-verify-reports /serve-reports /kit-smoke."
)


def main() -> int:
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        _ = json.loads(sys.stdin.read() or "{}")
    except Exception:
        pass

    print(
        json.dumps(
            {
                "env": {
                    "VB6_ARCHAEOLOGY": "1",
                    "VB6_AI_ONBOARDING": "docs/ai-onboarding.md",
                },
                "additional_context": CONTEXT,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
