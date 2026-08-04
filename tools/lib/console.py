"""Keep tool output printable whatever the console code page is.

VB6 sources are CP932 and their captions end up in tool stdout. On a console
that is not Japanese (an English Windows shell uses cp1252) printing them
raises UnicodeEncodeError and the whole run dies after the analysis already
succeeded. Every CLI entry point forces UTF-8 first.
"""

from __future__ import annotations

import sys


def enable_utf8_stdio() -> None:
    """Switch stdout/stderr to UTF-8. Safe to call more than once."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:  # StringIO in tests, or a closed stream
            continue
        encoding = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
        if encoding in ("utf8", "utf8sig"):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # A stream that refuses reconfiguration is better left as it was.
            continue
