"""YAML workflow loader with Pydantic validation."""

from __future__ import annotations

from pathlib import Path

import yaml

from .schema import Workflow


def load_workflow(path: Path | str) -> Workflow:
    """Load and validate a YAML workflow definition.

    Args:
        path: Path to the .yaml workflow file.

    Returns:
        Validated Workflow model.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the YAML is malformed.
        pydantic.ValidationError: If the schema validation fails.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Workflow file must be a YAML mapping: {path}")

    return Workflow.model_validate(raw)
