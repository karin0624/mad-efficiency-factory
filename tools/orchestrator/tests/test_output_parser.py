"""Tests for output_parser.py — marker extraction from agent output."""

import pytest

from tools.orchestrator.output_parser import (
    parse_agent_output,
    has_l4_human_review,
)


# ── Boolean markers ───────────────────────────────────────────────

class TestBooleanMarkers:
    def test_validation_passed(self):
        text = "All checks passed.\nVALIDATION_PASSED\nDone."
        p = parse_agent_output(text)
        assert p.validation_passed
        assert not p.validation_failed

    def test_validation_failed(self):
        text = "Issues found.\nVALIDATION_FAILED\nSee details."
        p = parse_agent_output(text)
        assert p.validation_failed
        assert not p.validation_passed

    def test_reject(self):
        text = "Design review: REJECT\nFeedback: ..."
        p = parse_agent_output(text)
        assert p.has_reject
        assert not p.has_approve

    def test_approve(self):
        text = "Design review: APPROVE\nProceeding."
        p = parse_agent_output(text)
        assert p.has_approve
        assert not p.has_reject

    def test_analysis_done(self):
        text = "ANALYSIS_DONE\nCLASSIFICATION: major"
        p = parse_agent_output(text)
        assert p.analysis_done

    def test_cascade_done(self):
        text = "CASCADE_DONE\nREQUIREMENTS_UPDATED: true"
        p = parse_agent_output(text)
        assert p.cascade_done
        assert not p.cascade_failed

    def test_cascade_failed(self):
        text = "CASCADE_FAILED\nREASON: design-review REJECT"
        p = parse_agent_output(text)
        assert p.cascade_failed
        assert not p.cascade_done

    def test_delta_tasks_done(self):
        text = "DELTA_TASKS_DONE\nTASKS_ADDED: 3"
        p = parse_agent_output(text)
        assert p.delta_tasks_done

    def test_no_markers(self):
        p = parse_agent_output("Just some regular text.")
        assert not p.validation_passed
        assert not p.validation_failed
        assert not p.has_reject
        assert not p.has_approve
        assert not p.analysis_done


# ── Value markers ─────────────────────────────────────────────────

class TestValueMarkers:
    def test_classification_major(self):
        text = "CLASSIFICATION: major\nCHANGE_TYPE: additive"
        p = parse_agent_output(text)
        assert p.classification == "major"

    def test_classification_minor(self):
        text = "CLASSIFICATION: minor"
        p = parse_agent_output(text)
        assert p.classification == "minor"

    def test_change_type_all_variants(self):
        for ct in ("additive", "modifying", "removal", "mixed"):
            p = parse_agent_output(f"CHANGE_TYPE: {ct}")
            assert p.change_type == ct

    def test_cascade_depth_all_variants(self):
        for cd in (
            "requirements-only",
            "requirements+design",
            "requirements+design+tasks",
            "full",
        ):
            p = parse_agent_output(f"CASCADE_DEPTH: {cd}")
            assert p.cascade_depth == cd

    def test_affected_requirements(self):
        text = "AFFECTED_REQUIREMENTS: 1, 3, 5"
        p = parse_agent_output(text)
        assert p.affected_requirements == "1, 3, 5"

    def test_affected_design_sections(self):
        text = "AFFECTED_DESIGN_SECTIONS: Components/Grid, SystemFlows/Placement"
        p = parse_agent_output(text)
        assert p.affected_design_sections == "Components/Grid, SystemFlows/Placement"

    def test_affected_tasks(self):
        text = "AFFECTED_TASKS: 4.1, 4.2, 5.1"
        p = parse_agent_output(text)
        assert p.affected_tasks == "4.1, 4.2, 5.1"


# ── Delta summary extraction ─────────────────────────────────────

class TestDeltaSummary:
    def test_extracts_delta_summary(self):
        text = """\
Some preamble.
DELTA_SUMMARY_START
Add new grid validation for 2x2 entities.
Update placement logic to check bounds.
DELTA_SUMMARY_END
Some epilogue."""
        p = parse_agent_output(text)
        assert "grid validation" in p.delta_summary
        assert "Update placement" in p.delta_summary

    def test_no_delta_summary(self):
        p = parse_agent_output("No summary here.")
        assert p.delta_summary == ""


# ── Full M1 output ────────────────────────────────────────────────

class TestFullM1Output:
    def test_full_m1_output(self):
        text = """\
Analysis complete.

ANALYSIS_DONE
CLASSIFICATION: major
CHANGE_TYPE: modifying
CASCADE_DEPTH: requirements+design+tasks
AFFECTED_REQUIREMENTS: 2, 4
AFFECTED_DESIGN_SECTIONS: Components/Grid
AFFECTED_TASKS: 3.1, 3.2
DELTA_SUMMARY_START
Modify grid to support 3x3 entities.
DELTA_SUMMARY_END
"""
        p = parse_agent_output(text)
        assert p.analysis_done
        assert p.classification == "major"
        assert p.change_type == "modifying"
        assert p.cascade_depth == "requirements+design+tasks"
        assert p.affected_requirements == "2, 4"
        assert p.affected_design_sections == "Components/Grid"
        assert p.affected_tasks == "3.1, 3.2"
        assert "3x3" in p.delta_summary


# ── L4 Human Review detection ────────────────────────────────────

class TestL4HumanReview:
    def test_detects_unchecked_l4(self):
        tasks = """\
- [x] 1.1 Create grid class
- [ ] 1.2 Human review: Verify grid rendering
- [x] 2.1 Add tests
"""
        assert has_l4_human_review(tasks)

    def test_ignores_checked_l4(self):
        tasks = """\
- [x] 1.1 Create grid class
- [x] 1.2 Human review: Verify grid rendering
"""
        assert not has_l4_human_review(tasks)

    def test_no_l4_tasks(self):
        tasks = """\
- [x] 1.1 Create grid class
- [ ] 1.2 Add tests
"""
        assert not has_l4_human_review(tasks)
