"""Structured marker extraction from agent output text."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ── Implement pipeline markers ──────────────────────────────────────

# A2 (design-review)
RE_REJECT = re.compile(r"\bREJECT\b")
RE_APPROVE = re.compile(r"\bAPPROVE\b")
RE_REVISE = re.compile(r"\bREVISE\b")

# B2 (validate-impl)
RE_VALIDATION_PASSED = re.compile(r"\bVALIDATION_PASSED\b")
RE_VALIDATION_FAILED = re.compile(r"\bVALIDATION_FAILED\b")

# ── Modify pipeline markers ────────────────────────────────────────

# M1 (change-analysis)
RE_ANALYSIS_DONE = re.compile(r"\bANALYSIS_DONE\b")
RE_CLASSIFICATION = re.compile(r"\bCLASSIFICATION:\s*(major|minor)\b")
RE_CHANGE_TYPE = re.compile(
    r"\bCHANGE_TYPE:\s*(additive|modifying|removal|mixed)\b"
)
RE_CASCADE_DEPTH = re.compile(
    r"\bCASCADE_DEPTH:\s*(requirements\+design\+tasks|requirements\+design|"
    r"requirements-only|full)\b"
)
RE_AFFECTED_REQS = re.compile(r"\bAFFECTED_REQUIREMENTS:\s*(.+)")
RE_AFFECTED_DESIGN = re.compile(r"\bAFFECTED_DESIGN_SECTIONS:\s*(.+)")
RE_AFFECTED_TASKS = re.compile(r"\bAFFECTED_TASKS:\s*(.+)")

# Delta summary (multiline)
RE_DELTA_SUMMARY_START = re.compile(r"\bDELTA_SUMMARY_START\b")
RE_DELTA_SUMMARY_END = re.compile(r"\bDELTA_SUMMARY_END\b")

# M2 (cascade)
RE_CASCADE_DONE = re.compile(r"\bCASCADE_DONE\b")
RE_CASCADE_FAILED = re.compile(r"\bCASCADE_FAILED\b")

# M3 (delta tasks)
RE_DELTA_TASKS_DONE = re.compile(r"\bDELTA_TASKS_DONE\b")

# L4 Human Review pattern in tasks.md
RE_L4_HUMAN_REVIEW = re.compile(r"^- \[ \] \d+\.\d+ Human review:", re.MULTILINE)


@dataclass
class ParsedOutput:
    """Structured data extracted from agent output."""

    raw_text: str = ""
    markers: dict[str, bool] = field(default_factory=dict)
    values: dict[str, str] = field(default_factory=dict)
    delta_summary: str = ""

    @property
    def has_reject(self) -> bool:
        return self.markers.get("REJECT", False)

    @property
    def has_approve(self) -> bool:
        return self.markers.get("APPROVE", False)

    @property
    def validation_passed(self) -> bool:
        return self.markers.get("VALIDATION_PASSED", False)

    @property
    def validation_failed(self) -> bool:
        return self.markers.get("VALIDATION_FAILED", False)

    @property
    def analysis_done(self) -> bool:
        return self.markers.get("ANALYSIS_DONE", False)

    @property
    def cascade_done(self) -> bool:
        return self.markers.get("CASCADE_DONE", False)

    @property
    def cascade_failed(self) -> bool:
        return self.markers.get("CASCADE_FAILED", False)

    @property
    def delta_tasks_done(self) -> bool:
        return self.markers.get("DELTA_TASKS_DONE", False)

    @property
    def classification(self) -> str:
        return self.values.get("CLASSIFICATION", "")

    @property
    def change_type(self) -> str:
        return self.values.get("CHANGE_TYPE", "")

    @property
    def cascade_depth(self) -> str:
        return self.values.get("CASCADE_DEPTH", "")

    @property
    def affected_requirements(self) -> str:
        return self.values.get("AFFECTED_REQUIREMENTS", "")

    @property
    def affected_design_sections(self) -> str:
        return self.values.get("AFFECTED_DESIGN_SECTIONS", "")

    @property
    def affected_tasks(self) -> str:
        return self.values.get("AFFECTED_TASKS", "")


def parse_agent_output(text: str) -> ParsedOutput:
    """Extract structured markers and values from agent output text."""
    result = ParsedOutput(raw_text=text)

    # Boolean markers
    for name, pattern in [
        ("REJECT", RE_REJECT),
        ("APPROVE", RE_APPROVE),
        ("REVISE", RE_REVISE),
        ("VALIDATION_PASSED", RE_VALIDATION_PASSED),
        ("VALIDATION_FAILED", RE_VALIDATION_FAILED),
        ("ANALYSIS_DONE", RE_ANALYSIS_DONE),
        ("CASCADE_DONE", RE_CASCADE_DONE),
        ("CASCADE_FAILED", RE_CASCADE_FAILED),
        ("DELTA_TASKS_DONE", RE_DELTA_TASKS_DONE),
    ]:
        if pattern.search(text):
            result.markers[name] = True

    # Value markers
    for name, pattern in [
        ("CLASSIFICATION", RE_CLASSIFICATION),
        ("CHANGE_TYPE", RE_CHANGE_TYPE),
        ("CASCADE_DEPTH", RE_CASCADE_DEPTH),
        ("AFFECTED_REQUIREMENTS", RE_AFFECTED_REQS),
        ("AFFECTED_DESIGN_SECTIONS", RE_AFFECTED_DESIGN),
        ("AFFECTED_TASKS", RE_AFFECTED_TASKS),
    ]:
        m = pattern.search(text)
        if m:
            result.values[name] = m.group(1).strip()

    # Delta summary (multiline block)
    start_m = RE_DELTA_SUMMARY_START.search(text)
    end_m = RE_DELTA_SUMMARY_END.search(text)
    if start_m and end_m and end_m.start() > start_m.end():
        result.delta_summary = text[start_m.end() : end_m.start()].strip()

    return result


def has_l4_human_review(tasks_md_content: str) -> bool:
    """Check if tasks.md contains unchecked L4 Human Review tasks."""
    return bool(RE_L4_HUMAN_REVIEW.search(tasks_md_content))
