"""Tests for plan_resolver.py — plan file path resolution."""

import pytest
from pathlib import Path

from tools.orchestrator.config import OrchestratorConfig
from tools.orchestrator.plan_resolver import (
    resolve_plan,
    sanitize_branch_name,
    list_plans,
    PlanResolutionError,
)


@pytest.fixture
def config_with_plans(tmp_path: Path):
    """Create a config with a plans directory containing test files."""
    plans_dir = tmp_path / "docs" / "plans"
    plans_dir.mkdir(parents=True)

    (plans_dir / "nested-doodling-cat.md").write_text("# Plan A")
    (plans_dir / "tick-engine-v2.md").write_text("# Plan B")
    (plans_dir / "entity-placement.md").write_text("# Plan C")

    return OrchestratorConfig(project_root=tmp_path)


class TestSanitizeBranchName:
    def test_lowercase(self):
        assert sanitize_branch_name("Hello World") == "hello-world"

    def test_special_chars(self):
        assert sanitize_branch_name("my_plan (v2)") == "my-plan-v2"

    def test_collapse_hyphens(self):
        assert sanitize_branch_name("a---b") == "a-b"

    def test_strip_edge_hyphens(self):
        assert sanitize_branch_name("-hello-") == "hello"


class TestResolvePlan:
    def test_exact_name(self, config_with_plans):
        path, name = resolve_plan(config_with_plans, "nested-doodling-cat")
        assert path.name == "nested-doodling-cat.md"
        assert name == "nested-doodling-cat"

    def test_with_md_extension(self, config_with_plans):
        path, name = resolve_plan(
            config_with_plans, "docs/plans/tick-engine-v2.md"
        )
        assert path.name == "tick-engine-v2.md"

    def test_partial_match_single(self, config_with_plans):
        path, name = resolve_plan(config_with_plans, "doodling")
        assert path.name == "nested-doodling-cat.md"

    def test_not_found_raises(self, config_with_plans):
        with pytest.raises(PlanResolutionError, match="見つかりません"):
            resolve_plan(config_with_plans, "nonexistent")

    def test_multiple_matches_raises(self, config_with_plans):
        # "e" matches both "tick-engine-v2" and "entity-placement"
        with pytest.raises(PlanResolutionError, match="複数の候補"):
            resolve_plan(config_with_plans, "e")


class TestListPlans:
    def test_lists_all_plans(self, config_with_plans):
        plans = list_plans(config_with_plans)
        assert len(plans) == 3

    def test_empty_dir(self, tmp_path):
        config = OrchestratorConfig(project_root=tmp_path)
        plans = list_plans(config)
        assert plans == []
