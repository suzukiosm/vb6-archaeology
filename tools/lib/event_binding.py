"""Event-handler owner resolution shared by inventory and deep-read.

VB6 binds a handler by name: ``<owner>_<event>``, where <owner> is a designer
control, the module's own object (``Form_Load``, ``UserControl_Initialize``,
``Class_Terminate`` …) or a module-level ``WithEvents`` variable. This module
matches that naming rule only. It does not check the event name or signature
against a type library, so a match is a binding candidate, not proof.
"""

from __future__ import annotations

from collections.abc import Iterable

# The module's own object prefix per source kind (designer root or class).
SELF_OWNERS_BY_SUFFIX: dict[str, tuple[str, ...]] = {
    ".frm": ("Form", "MDIForm"),
    ".ctl": ("UserControl",),
    ".pag": ("PropertyPage",),
    ".dob": ("UserDocument",),
    ".dsr": ("DataEnvironment", "DataReport"),
    ".cls": ("Class",),
}

BINDING_DESIGNER = "designer"
BINDING_SELF = "self"
BINDING_WITHEVENTS = "withevents"


def self_owners_for(suffix: str) -> tuple[str, ...]:
    return SELF_OWNERS_BY_SUFFIX.get(suffix.lower(), ())


def resolve_event_owner(
    proc_name: str,
    *,
    controls: Iterable[str] = (),
    self_owners: Iterable[str] = (),
    with_events: Iterable[str] = (),
) -> dict | None:
    """Return ``{owner, event, binding}`` for the longest matching owner prefix.

    Owners may themselves contain underscores (``cmd_Save_Click`` with a control
    ``cmd_Save``), so the longest ``<owner>_`` prefix wins. Names compare
    case-insensitively, as VB6 identifiers do.
    """
    owners: dict[str, str] = {}
    for binding, names in (
        (BINDING_DESIGNER, controls),
        (BINDING_WITHEVENTS, with_events),
        (BINDING_SELF, self_owners),
    ):
        for name in names:
            owners.setdefault(str(name).casefold(), binding)
    for i in range(len(proc_name) - 1, 0, -1):
        if proc_name[i] != "_" or i == len(proc_name) - 1:
            continue
        binding = owners.get(proc_name[:i].casefold())
        if binding is not None:
            return {"owner": proc_name[:i], "event": proc_name[i + 1:], "binding": binding}
    return None
