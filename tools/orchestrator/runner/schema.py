"""Pydantic models for YAML workflow definitions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class VarDef(BaseModel):
    """Variable definition in the workflow vars block."""

    from_param: str = ""
    type: Literal["string", "path", "bool", "int"] = "string"
    default: Any = None


class OnFeedback(BaseModel):
    """Action to take when user provides feedback at a review gate."""

    rerun: str
    extra_params: dict[str, str] = Field(default_factory=dict)
    then: str = ""


class OnResumeAction(BaseModel):
    """Action to take when resuming from an on_marker pause, based on user input."""

    goto: str = ""               # Step ID to jump to ("_abort" to abort)
    resume_session: bool = False  # Resume saved claude session
    extra_prompt: str = ""        # Additional prompt for session resume


class OnMarkerAction(BaseModel):
    """Action to take when a specific marker is detected."""

    pause: str = ""
    save_session: bool = False
    rerun: str = ""
    goto: str = ""
    question: str = ""
    options: list[str] = Field(default_factory=list)
    on_resume: dict[str, OnResumeAction] = Field(default_factory=dict)


class Step(BaseModel):
    """A single step in a workflow."""

    id: str
    type: Literal["claude", "python", "skill", "review_gate", "parallel"]

    # claude step fields
    prompt: str = ""
    model: str = "sonnet"
    cwd: str = ""
    params: dict[str, str] = Field(default_factory=dict)
    when: str = ""
    markers: list[str] = Field(default_factory=list)
    on_marker: dict[str, OnMarkerAction] = Field(default_factory=dict)
    append_system_prompt: str = ""
    max_turns: int = 0
    allowed_tools: list[str] = Field(default_factory=list)

    # python step fields
    function: str = ""
    args: dict[str, str] = Field(default_factory=dict)
    extract: dict[str, str] = Field(default_factory=dict)

    # skill step fields
    skill: str = ""

    # review_gate fields
    file: str = ""
    focus: str = ""
    question: str = ""
    options: list[str] = Field(default_factory=list)
    on_feedback: OnFeedback | None = None

    # parallel step fields
    steps: list[Step] = Field(default_factory=list)

    # session resume
    save_session: bool = False
    resume_from: str = ""

    # review_gate: skip if referenced file does not exist
    skip_if_file_missing: bool = True

    @model_validator(mode="after")
    def validate_step_type(self) -> Step:
        if self.type == "claude" and not self.prompt:
            raise ValueError(f"Step '{self.id}': claude step requires 'prompt'")
        if self.type == "python" and not self.function:
            raise ValueError(f"Step '{self.id}': python step requires 'function'")
        if self.type == "skill" and not self.skill:
            raise ValueError(f"Step '{self.id}': skill step requires 'skill'")
        if self.type == "review_gate" and not self.question:
            raise ValueError(f"Step '{self.id}': review_gate step requires 'question'")
        if self.type == "parallel" and not self.steps:
            raise ValueError(f"Step '{self.id}': parallel step requires 'steps'")
        return self


class Workflow(BaseModel):
    """Top-level workflow definition."""

    name: str
    description: str = ""
    vars: dict[str, VarDef] = Field(default_factory=dict)
    steps: list[Step] = Field(default_factory=list)

    def get_step(self, step_id: str) -> Step | None:
        """Find a step by ID (searches nested parallel steps too)."""
        for step in self.steps:
            if step.id == step_id:
                return step
            if step.type == "parallel":
                for sub in step.steps:
                    if sub.id == step_id:
                        return sub
        return None

    def step_ids(self) -> list[str]:
        """Return ordered list of top-level step IDs."""
        return [s.id for s in self.steps]
