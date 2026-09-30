"""Accessor-qualified tick targets, with conservative legacy compatibility."""


def target_name(proc: dict) -> str:
    name = str(proc.get('name') or '')
    kind = str(proc.get('kind') or '')
    return f'{name}|{kind}' if kind.lower().startswith('property ') else name


def normalize_ticks(ticked: set[tuple[str, str]]) -> set[tuple[str, str]]:
    return {(f.replace('\\', '/').casefold(), n.casefold()) for f, n in ticked}


def is_ticked(file_name: str, proc: dict, ticked: set[tuple[str, str]]) -> bool:
    """Match against normalize_ticks output in O(1) per procedure."""
    key = (file_name.replace('\\', '/').casefold(), target_name(proc).casefold())
    # A legacy unqualified Property tick cannot prove which accessor was read.
    return key in ticked
