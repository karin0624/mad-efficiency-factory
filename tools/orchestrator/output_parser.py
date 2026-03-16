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

# M1 ADR fields
RE_ADR_REQUIRED = re.compile(r"\bADR_REQUIRED:\s*(yes|no)\b")
RE_ADR_CATEGORY = re.compile(r"\bADR_CATEGORY:\s*(spec|architecture|governance)\b")
RE_ADR_REASON = re.compile(r"\bADR_REASON:\s*(.+)")
RE_ADR_CREATED = re.compile(r"\bADR_CREATED\b")
RE_ADR_PATH = re.compile(r"\bADR_PATH:\s*(\S+)")

# Steering sync
RE_STEERING_SYNC_DONE = re.compile(r"\bSTEERING_SYNC_DONE\b")
RE_STEERING_SYNC_SKIPPED = re.compile(r"\bSTEERING_SYNC_SKIPPED\b")

# M2 (cascade)
RE_CASCADE_DONE = re.compile(r"\bCASCADE_DONE\b")
RE_CASCADE_FAILED = re.compile(r"\bCASCADE_FAILED\b")

# M3 (delta tasks)
RE_DELTA_TASKS_DONE = re.compile(r"\bDELTA_TASKS_DONE\b")

# Test-fix markers
RE_TEST_FIX_PASSED = re.compile(r"\bTEST_FIX_PASSED\b")
RE_TEST_FIX_FAILED = re.compile(r"\bTEST_FIX_FAILED\b")

# L4 Human Review pattern in tasks.md
RE_L4_HUMAN_REVIEW = re.compile(r"^- \[ \] \d+\.\d+ Human review:", re.MULTILINE)

# ── Modify-plan pipeline markers ──────────────────────────────────

# MP0 (investigate)
RE_MP0_DONE = re.compile(r"\bMP0_DONE\b")
RE_MP0_NO_MATCH = re.compile(r"\bMP0_NO_MATCH\b")
RE_MP0_NEW_SPEC_RECOMMENDED = re.compile(r"\bMP0_NEW_SPEC_RECOMMENDED\b")
RE_PLAN_SLUG = re.compile(r"\bPLAN_SLUG:\s*(\S+)")
RE_TARGET_SPECS = re.compile(r"\bTARGET_SPECS:\s*(.+)")
RE_EXECUTION_ORDER = re.compile(r"\bEXECUTION_ORDER:\s*(.+)")
RE_PROPAGATION_MAP_START = re.compile(r"\bPROPAGATION_MAP_START\b")
RE_PROPAGATION_MAP_END = re.compile(r"\bPROPAGATION_MAP_END\b")

# MP1 (plan-gen)
RE_MP1_DONE = re.compile(r"\bMP1_DONE\b")
RE_MP1_SUMMARY_START = re.compile(r"\bSUMMARY_START\b")
RE_MP1_SUMMARY_END = re.compile(r"\bSUMMARY_END\b")
RE_MP1_GAPS = re.compile(r"\bGAPS:\s*(.+)")

# MP2 (review)
RE_MP2_DONE = re.compile(r"\bMP2_DONE\b")
RE_MP2_STATUS = re.compile(r"\bMP2_DONE\s+status=(\w+)\b")
RE_MP2_CHANGES_START = re.compile(r"\bCHANGES_START\b")
RE_MP2_CHANGES_END = re.compile(r"\bCHANGES_END\b")

# MP1e (edit)
RE_MP1E_DONE = re.compile(r"\bMP1E_DONE\b")


@dataclass
class ParsedOutput:
    """Structured data extracted from agent output."""

    raw_text: str = ""
    markers: dict[str, bool] = field(default_factory=dict)
    values: dict[str, str] = field(default_factory=dict)
    delta_summary: str = ""
    _blocks: dict[str, str] = field(default_factory=dict)

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

    @property
    def adr_required(self) -> bool:
        return self.values.get("ADR_REQUIRED", "no") == "yes"

    @property
    def adr_category(self) -> str:
        return self.values.get("ADR_CATEGORY", "")

    @property
    def adr_reason(self) -> str:
        return self.values.get("ADR_REASON", "")

    @property
    def adr_path(self) -> str:
        return self.values.get("ADR_PATH", "")

    @property
    def steering_sync_done(self) -> bool:
        return self.markers.get("STEERING_SYNC_DONE", False)

    # ── Modify-plan pipeline properties ───────────────────────────

    @property
    def plan_slug(self) -> str:
        return self.values.get("PLAN_SLUG", "")

    @property
    def mp0_done(self) -> bool:
        return self.markers.get("MP0_DONE", False)

    @property
    def mp0_no_match(self) -> bool:
        return self.markers.get("MP0_NO_MATCH", False)

    @property
    def mp0_new_spec_recommended(self) -> bool:
        return self.markers.get("MP0_NEW_SPEC_RECOMMENDED", False)

    @property
    def target_specs(self) -> str:
        return self.values.get("TARGET_SPECS", "")

    @property
    def execution_order(self) -> str:
        return self.values.get("EXECUTION_ORDER", "")

    @property
    def propagation_map(self) -> str:
        return self._blocks.get("PROPAGATION_MAP", "")

    @property
    def mp1_done(self) -> bool:
        return self.markers.get("MP1_DONE", False)

    @property
    def mp1_summary(self) -> str:
        return self._blocks.get("SUMMARY", "")

    @property
    def mp1_gaps(self) -> str:
        return self.values.get("GAPS", "")

    @property
    def mp2_done(self) -> bool:
        return self.markers.get("MP2_DONE", False)

    @property
    def mp2_status(self) -> str:
        return self.values.get("MP2_STATUS", "")

    @property
    def mp2_changes(self) -> str:
        return self._blocks.get("CHANGES", "")

    @property
    def mp1e_done(self) -> bool:
        return self.markers.get("MP1E_DONE", False)

    @property
    def test_fix_passed(self) -> bool:
        return self.markers.get("TEST_FIX_PASSED", False)

    @property
    def test_fix_failed(self) -> bool:
        return self.markers.get("TEST_FIX_FAILED", False)


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
        ("ADR_CREATED", RE_ADR_CREATED),
        ("STEERING_SYNC_DONE", RE_STEERING_SYNC_DONE),
        ("STEERING_SYNC_SKIPPED", RE_STEERING_SYNC_SKIPPED),
        # Modify-plan markers
        ("MP0_DONE", RE_MP0_DONE),
        ("MP0_NO_MATCH", RE_MP0_NO_MATCH),
        ("MP0_NEW_SPEC_RECOMMENDED", RE_MP0_NEW_SPEC_RECOMMENDED),
        ("MP1_DONE", RE_MP1_DONE),
        ("MP2_DONE", RE_MP2_DONE),
        ("MP1E_DONE", RE_MP1E_DONE),
        # Test-fix markers
        ("TEST_FIX_PASSED", RE_TEST_FIX_PASSED),
        ("TEST_FIX_FAILED", RE_TEST_FIX_FAILED),
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
        ("ADR_REQUIRED", RE_ADR_REQUIRED),
        ("ADR_CATEGORY", RE_ADR_CATEGORY),
        ("ADR_REASON", RE_ADR_REASON),
        ("ADR_PATH", RE_ADR_PATH),
        # Modify-plan values
        ("PLAN_SLUG", RE_PLAN_SLUG),
        ("TARGET_SPECS", RE_TARGET_SPECS),
        ("EXECUTION_ORDER", RE_EXECUTION_ORDER),
        ("GAPS", RE_MP1_GAPS),
    ]:
        m = pattern.search(text)
        if m:
            result.values[name] = m.group(1).strip()

    # MP2 status (extracted from MP2_DONE status=<VALUE>)
    m = RE_MP2_STATUS.search(text)
    if m:
        result.values["MP2_STATUS"] = m.group(1).strip()

    # Delta summary (multiline block)
    start_m = RE_DELTA_SUMMARY_START.search(text)
    end_m = RE_DELTA_SUMMARY_END.search(text)
    if start_m and end_m and end_m.start() > start_m.end():
        result.delta_summary = text[start_m.end() : end_m.start()].strip()

    # Generic multiline block extraction
    _extract_block(text, RE_PROPAGATION_MAP_START, RE_PROPAGATION_MAP_END, "PROPAGATION_MAP", result)
    _extract_block(text, RE_MP1_SUMMARY_START, RE_MP1_SUMMARY_END, "SUMMARY", result)
    _extract_block(text, RE_MP2_CHANGES_START, RE_MP2_CHANGES_END, "CHANGES", result)

    return result


def _extract_block(
    text: str,
    start_re: re.Pattern[str],
    end_re: re.Pattern[str],
    name: str,
    result: ParsedOutput,
) -> None:
    """Extract a multiline block between start/end markers."""
    start_m = start_re.search(text)
    end_m = end_re.search(text)
    if start_m and end_m and end_m.start() > start_m.end():
        result._blocks[name] = text[start_m.end() : end_m.start()].strip()


def has_l4_human_review(tasks_md_content: str) -> bool:
    """Check if tasks.md contains unchecked L4 Human Review tasks."""
    return bool(RE_L4_HUMAN_REVIEW.search(tasks_md_content))
