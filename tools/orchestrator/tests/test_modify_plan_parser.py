"""Tests for modify-plan pipeline markers in output_parser.py."""

import pytest

from tools.orchestrator.output_parser import parse_agent_output


# ── MP0 (investigate) markers ────────────────────────────────────

class TestMP0Markers:
    def test_mp0_done(self):
        text = """\
MP0_DONE
TARGET_SPECS: spec2 (high), spec1 (medium)
EXECUTION_ORDER: spec2, spec1
PROPAGATION_MAP_START
## spec2 (confidence: high)
- change: add port filtering
- downstream_impact: spec1 interface change
- depends_on: none (upstream)
PROPAGATION_MAP_END
"""
        p = parse_agent_output(text)
        assert p.mp0_done
        assert not p.mp0_no_match
        assert not p.mp0_new_spec_recommended
        assert p.target_specs == "spec2 (high), spec1 (medium)"
        assert p.execution_order == "spec2, spec1"
        assert "spec2 (confidence: high)" in p.propagation_map
        assert "add port filtering" in p.propagation_map

    def test_mp0_no_match(self):
        text = "MP0_NO_MATCH\nNo specs affected by this change."
        p = parse_agent_output(text)
        assert p.mp0_no_match
        assert not p.mp0_done

    def test_mp0_new_spec_recommended(self):
        text = "MP0_NEW_SPEC_RECOMMENDED\nThis change requires a new feature spec."
        p = parse_agent_output(text)
        assert p.mp0_new_spec_recommended
        assert not p.mp0_done


# ── MP1 (plan-gen) markers ───────────────────────────────────────

class TestMP1Markers:
    def test_mp1_done(self):
        text = """\
MP1_DONE
SUMMARY_START
- Feature: machine-port-system
- Added behaviors: 2
- Modified behaviors: 1
- Predicted scale: minor
SUMMARY_END
GAPS: none
"""
        p = parse_agent_output(text)
        assert p.mp1_done
        assert "machine-port-system" in p.mp1_summary
        assert "Added behaviors: 2" in p.mp1_summary
        assert p.mp1_gaps == "none"

    def test_mp1_with_gaps(self):
        text = """\
MP1_DONE
SUMMARY_START
- Feature: inventory-system
- Added behaviors: 0
- Modified behaviors: 3
- Predicted scale: major
SUMMARY_END
GAPS: unclear how filtering interacts with existing validation
"""
        p = parse_agent_output(text)
        assert p.mp1_done
        assert "major" in p.mp1_summary
        assert "unclear" in p.mp1_gaps

    def test_mp1_no_summary(self):
        p = parse_agent_output("MP1_DONE\nGAPS: none")
        assert p.mp1_done
        assert p.mp1_summary == ""


# ── MP2 (review) markers ────────────────────────────────────────

class TestMP2Markers:
    def test_mp2_done_ready(self):
        text = """\
MP2_DONE status=READY
CHANGES_START
- clarified scope of behavior change
- [cross-spec] verified no impact on downstream specs
CHANGES_END
"""
        p = parse_agent_output(text)
        assert p.mp2_done
        assert p.mp2_status == "READY"
        assert "clarified scope" in p.mp2_changes
        assert "[cross-spec]" in p.mp2_changes

    def test_mp2_done_revise(self):
        text = """\
MP2_DONE status=REVISE
CHANGES_START
- missing acceptance criteria for edge case
- [cross-spec] potential conflict with inventory-system
CHANGES_END
"""
        p = parse_agent_output(text)
        assert p.mp2_done
        assert p.mp2_status == "REVISE"
        assert "missing acceptance criteria" in p.mp2_changes

    def test_mp2_no_changes(self):
        text = "MP2_DONE status=READY"
        p = parse_agent_output(text)
        assert p.mp2_done
        assert p.mp2_status == "READY"
        assert p.mp2_changes == ""


# ── MP1e (edit) markers ──────────────────────────────────────────

class TestMP1eMarkers:
    def test_mp1e_done(self):
        text = """\
MP1E_DONE
CHANGES_START
- incorporated user feedback on scope
- [guardrail] added missing constraint
- [cross-spec-warning] may affect inventory-system interface
CHANGES_END
"""
        p = parse_agent_output(text)
        assert p.mp1e_done
        assert "[guardrail]" in p.mp2_changes  # reuses CHANGES block
        assert "[cross-spec-warning]" in p.mp2_changes


# ── Full MP0 output ──────────────────────────────────────────────

class TestFullMP0Output:
    def test_full_mp0_output(self):
        text = """\
Investigation complete.

MP0_DONE
TARGET_SPECS: machine-port-system (high), inventory-system (medium)
EXECUTION_ORDER: machine-port-system, inventory-system
PROPAGATION_MAP_START
## machine-port-system (confidence: high)
- change: Add item type filtering to port transfer
- downstream_impact: inventory-system interface change
- depends_on: none (upstream)

## inventory-system (confidence: medium)
- change: Update item validation for new filter types
- downstream_impact: none
- depends_on: machine-port-system
PROPAGATION_MAP_END
"""
        p = parse_agent_output(text)
        assert p.mp0_done
        assert "machine-port-system (high)" in p.target_specs
        assert "machine-port-system, inventory-system" == p.execution_order
        assert "machine-port-system (confidence: high)" in p.propagation_map
        assert "inventory-system (confidence: medium)" in p.propagation_map
