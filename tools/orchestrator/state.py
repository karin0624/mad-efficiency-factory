"""Spec state management — reads/writes spec.json, determines resume points."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Phase(str, Enum):
    """Spec lifecycle phases."""

    INITIALIZED = "initialized"
    REQUIREMENTS_GENERATED = "requirements-generated"
    DESIGN_GENERATED = "design-generated"
    TASKS_GENERATED = "tasks-generated"
    IMPL_COMPLETED = "impl-completed"
    VALIDATED = "validated"


class ModifyPhase(str, Enum):
    """Modification sub-phases."""

    ANALYSIS_COMPLETED = "analysis-completed"
    ADR_ACCEPTED = "adr-accepted"
    SPEC_CASCADED = "spec-cascaded"
    DELTA_TASKS_GENERATED = "delta-tasks-generated"
    IMPL_COMPLETED = "impl-completed"
    VALIDATED = "validated"
    TESTS_PASSED = "tests-passed"
    COMPLETED = "completed"


class ImplementResumePoint(str, Enum):
    """Where to resume an implement pipeline."""

    A1_WHAT = "a1-what"
    A1_WHAT_PHASE2 = "a1-what-phase2"
    A2_HOW_FULL = "a2-how-full"
    A2_HOW_REVIEW_ONLY = "a2-how-review-only"
    A3_TASKS = "a3-tasks"
    A3_TASKS_APPROVAL = "a3-tasks-approval"
    B_IMPL = "b-impl"
    B2_VALIDATE = "b2-validate"
    T_TESTS = "t-tests"
    C_COMMIT = "c-commit"


class ModifyResumePoint(str, Enum):
    """Where to resume a modify pipeline."""

    ADR_GATE = "adr-gate"
    M2_CASCADE = "m2-cascade"
    M3_DELTA_TASKS = "m3-delta-tasks"
    B_IMPL = "b-impl"
    B2_VALIDATE = "b2-validate"
    T_TESTS = "t-tests"
    C_COMMIT = "c-commit"


@dataclass
class SpecState:
    """In-memory representation of spec.json."""

    raw: dict[str, Any]
    path: Path

    @property
    def feature_name(self) -> str:
        return self.raw["feature_name"]

    @property
    def phase(self) -> Phase:
        return Phase(self.raw["phase"])

    @property
    def approvals(self) -> dict[str, Any]:
        return self.raw.get("approvals", {})

    @property
    def modifications(self) -> list[dict[str, Any]]:
        return self.raw.get("modifications", [])

    @property
    def design_codex_reviewed(self) -> bool:
        return self.approvals.get("design", {}).get("codex_reviewed", False)

    @property
    def tasks_approved(self) -> bool:
        return self.approvals.get("tasks", {}).get("approved", False)

    def save(self) -> None:
        """Write current state back to spec.json."""
        self.path.write_text(json.dumps(self.raw, indent=2, ensure_ascii=False) + "\n")

    def set_phase(self, phase: Phase) -> None:
        self.raw["phase"] = phase.value
        self.save()

    def set_modify_phase(self, modify_phase: ModifyPhase) -> None:
        """Update the last modification entry's modify_phase."""
        mods = self.raw.setdefault("modifications", [])
        if mods:
            mods[-1]["modify_phase"] = modify_phase.value
            self.save()

    def ensure_modifications_field(self) -> None:
        """Ensure spec.json has a modifications array (backward compat)."""
        if "modifications" not in self.raw:
            self.raw["modifications"] = []
            self.save()


def load_spec(spec_json_path: Path) -> SpecState:
    """Load a spec.json file into a SpecState."""
    raw = json.loads(spec_json_path.read_text())
    return SpecState(raw=raw, path=spec_json_path)


def find_spec_in_worktree(worktree_path: Path) -> SpecState | None:
    """Find and load the first spec.json in a worktree's .kiro/specs/."""
    specs_dir = worktree_path / ".kiro" / "specs"
    if not specs_dir.exists():
        return None
    for spec_dir in specs_dir.iterdir():
        spec_json = spec_dir / "spec.json"
        if spec_json.exists():
            return load_spec(spec_json)
    return None


def find_spec_by_name(worktree_path: Path, feature_name: str) -> SpecState | None:
    """Find a spec by feature name in a worktree."""
    spec_json = worktree_path / ".kiro" / "specs" / feature_name / "spec.json"
    if spec_json.exists():
        return load_spec(spec_json)
    return None


def detect_implement_resume(spec: SpecState) -> ImplementResumePoint:
    """Determine where to resume an implement pipeline based on spec.json state.

    Maps spec phase + approval state to the appropriate pipeline entry point.
    """
    phase = spec.phase

    if phase == Phase.VALIDATED:
        return ImplementResumePoint.T_TESTS

    if phase == Phase.IMPL_COMPLETED:
        return ImplementResumePoint.B2_VALIDATE

    if phase == Phase.TASKS_GENERATED:
        if spec.tasks_approved:
            return ImplementResumePoint.B_IMPL
        return ImplementResumePoint.A3_TASKS_APPROVAL

    if phase == Phase.DESIGN_GENERATED:
        if spec.design_codex_reviewed:
            return ImplementResumePoint.A3_TASKS
        return ImplementResumePoint.A2_HOW_REVIEW_ONLY

    if phase == Phase.REQUIREMENTS_GENERATED:
        return ImplementResumePoint.A2_HOW_FULL

    if phase == Phase.INITIALIZED:
        return ImplementResumePoint.A1_WHAT_PHASE2

    return ImplementResumePoint.A1_WHAT


def detect_modify_resume(spec: SpecState) -> ModifyResumePoint | None:
    """Determine where to resume a modify pipeline.

    Returns None if no modification is in progress.
    """
    mods = spec.modifications
    if not mods:
        return None

    last_mod = mods[-1]
    modify_phase_str = last_mod.get("modify_phase")
    if not modify_phase_str:
        return None

    modify_phase = ModifyPhase(modify_phase_str)

    if modify_phase == ModifyPhase.TESTS_PASSED:
        return ModifyResumePoint.C_COMMIT

    if modify_phase == ModifyPhase.VALIDATED:
        return ModifyResumePoint.T_TESTS

    if modify_phase == ModifyPhase.IMPL_COMPLETED:
        return ModifyResumePoint.B2_VALIDATE

    if modify_phase == ModifyPhase.DELTA_TASKS_GENERATED:
        return ModifyResumePoint.B_IMPL

    if modify_phase == ModifyPhase.SPEC_CASCADED:
        return ModifyResumePoint.M3_DELTA_TASKS

    if modify_phase == ModifyPhase.ADR_ACCEPTED:
        return ModifyResumePoint.M2_CASCADE

    if modify_phase == ModifyPhase.ANALYSIS_COMPLETED:
        return ModifyResumePoint.ADR_GATE

    return None
