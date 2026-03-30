"""Template engine for {{ var }} resolution in YAML workflow definitions."""

from __future__ import annotations

import re
from typing import Any

# Matches {{ var_name }}, {{ expr }}, with optional whitespace
_TEMPLATE_RE = re.compile(r"\{\{\s*(.+?)\s*\}\}")


def resolve(template: str, variables: dict[str, Any]) -> str:
    """Resolve all {{ var }} placeholders in a string.

    Supports:
      - Simple variable: {{ foo }} -> variables["foo"]
      - Dotted access: {{ result.bar }} -> variables["result"]["bar"]
      - 'in' expressions: {{ resume_point in RUN_A1 }} -> bool evaluation
      - Truthy check: {{ needs_plan }} -> bool(variables["needs_plan"])
    """
    def _replace(match: re.Match[str]) -> str:
        expr = match.group(1).strip()
        value = _evaluate(expr, variables)
        return str(value)

    return _TEMPLATE_RE.sub(_replace, template)


def evaluate_condition(template: str, variables: dict[str, Any]) -> bool:
    """Evaluate a {{ expr }} template as a boolean condition.

    Empty string or missing 'when' is treated as True (always run).
    """
    if not template or not template.strip():
        return True

    resolved = resolve(template, variables)

    # Handle string booleans
    lower = resolved.strip().lower()
    if lower in ("true", "1", "yes"):
        return True
    if lower in ("false", "0", "no", "none", ""):
        return False

    return bool(resolved)


def resolve_dict(params: dict[str, str], variables: dict[str, Any]) -> dict[str, str]:
    """Resolve all {{ var }} placeholders in a dict's values."""
    return {k: resolve(v, variables) for k, v in params.items()}


def _evaluate(expr: str, variables: dict[str, Any]) -> Any:
    """Evaluate a single expression against variables."""
    # "x in Y" pattern: check membership
    if " in " in expr:
        parts = expr.split(" in ", 1)
        left = _lookup(parts[0].strip(), variables)
        right = _lookup(parts[1].strip(), variables)
        if isinstance(right, (list, tuple, set)):
            return left in right
        if isinstance(right, str):
            return str(left) in right
        return False

    # "not x" pattern
    if expr.startswith("not "):
        inner = expr[4:].strip()
        return not _evaluate(inner, variables)

    # Simple lookup
    return _lookup(expr, variables)


def _lookup(key: str, variables: dict[str, Any]) -> Any:
    """Look up a potentially dotted key in the variables dict.

    Returns the value or the original key string if not found
    (treat as literal).
    """
    # Check direct lookup first
    if key in variables:
        return variables[key]

    # Dotted access: result.bar -> variables["result"]["bar"]
    if "." in key:
        parts = key.split(".")
        current: Any = variables
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return key  # Not found, return as literal
        return current

    # Not found — return as literal string
    return key
