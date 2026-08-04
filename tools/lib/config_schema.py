#!/usr/bin/env python3
"""Validate archaeology.config.json against the bundled JSON Schema.

Deliberately a small stdlib-only checker rather than a `jsonschema` dependency:
the kit ships with the standard library alone. It covers the subset the schema
in `schema/archaeology.config.schema.json` uses (type, required, properties,
additionalProperties, items, minLength, minItems, minimum, maximum) and reports
every problem with the JSON path that needs fixing.

    python -m tools config-check
    python -m tools config-check --config path/to/archaeology.config.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .console import enable_utf8_stdio

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_NAME = "archaeology.config.json"
SCHEMA_PATH = REPO_ROOT / "schema" / "archaeology.config.schema.json"

TYPE_NAMES: dict[str, type | tuple[type, ...]] = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


def _describe(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _type_matches(value: object, name: str) -> bool:
    expected = TYPE_NAMES.get(name)
    if expected is None:
        return True
    if name in ("integer", "number") and isinstance(value, bool):
        return False  # JSON booleans are Python ints; never accept them as numbers
    return isinstance(value, expected)


def validate(data: object, schema: dict, path: str = "") -> list[str]:
    """Return a list of human-fixable problems; empty means valid."""
    errors: list[str] = []
    where = path or "(root)"

    expected_type = schema.get("type")
    if expected_type and not _type_matches(data, expected_type):
        errors.append(f"{where} must be {expected_type} (got {_describe(data)})")
        return errors

    if isinstance(data, str):
        min_length = schema.get("minLength")
        if min_length is not None and len(data) < min_length:
            errors.append(f"{where} must be at least {min_length} character(s)")

    if isinstance(data, int) and not isinstance(data, bool):
        minimum, maximum = schema.get("minimum"), schema.get("maximum")
        if minimum is not None and data < minimum:
            errors.append(f"{where} must be >= {minimum} (got {data})")
        if maximum is not None and data > maximum:
            errors.append(f"{where} must be <= {maximum} (got {data})")

    if isinstance(data, list):
        min_items = schema.get("minItems")
        if min_items is not None and len(data) < min_items:
            errors.append(f"{where} must have at least {min_items} item(s)")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(data):
                errors.extend(validate(item, item_schema, f"{path}[{index}]"))

    if isinstance(data, dict):
        properties = schema.get("properties") or {}
        for key in schema.get("required") or []:
            if key not in data:
                errors.append(f"{where} is missing required key {key!r}")
        extra_schema = schema.get("additionalProperties")
        for key, value in data.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key in properties:
                errors.extend(validate(value, properties[key], child_path))
            elif isinstance(extra_schema, dict):
                errors.extend(validate(value, extra_schema, child_path))
            elif extra_schema is False:
                errors.append(f"{child_path} is not a known setting")

    return errors


def check_config(config_path: Path, schema_path: Path = SCHEMA_PATH) -> list[str]:
    if not schema_path.is_file():
        return [f"schema missing: {schema_path}"]
    if not config_path.is_file():
        return [f"config missing: {config_path}"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{config_path.name}: invalid JSON at line {exc.lineno}: {exc.msg}"]
    return [f"{config_path.name}: {problem}" for problem in validate(data, schema)]


def main(argv: list[str] | None = None) -> int:
    enable_utf8_stdio()
    ap = argparse.ArgumentParser(description="Validate archaeology.config.json")
    ap.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / CONFIG_NAME,
        help=f"Config to validate (default: {CONFIG_NAME} at the repo root)",
    )
    ap.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    args = ap.parse_args(argv)

    problems = check_config(args.config, args.schema)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        print(f"config-check: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    print(f"config-check: {args.config.name} OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
