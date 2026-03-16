"""Modify-plan pipeline: investigate → plan-gen → review → feedback loop.

Steps: Change resolve → MP0(Investigate) → User confirm
       → MP1×N(Plan-gen, parallel) → MP2×N(Review, parallel)
       → Result display → User accept/feedback → [MP1e → MP2 loop]
"""

from __future__ import annotations

import asyncio
import re
from datetime import date
from pathlib import Path
from typing import Any

from ..agent_runner import AgentRunner, AgentStep, AgentResult
from ..config import OrchestratorConfig
from ..human_input import ask_choice, ask_text
from ..pipeline import Pipeline, PipelineError
from ..progress import PipelineProgress


def _slugify(text: str) -> str:
    """Generate a URL-friendly slug from text."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:60] if slug else "modify-plan"


class ModifyPlanPipeline(Pipeline):
    """Modify-plan pipeline: investigate affected specs and generate plans."""

    async def run(
        self,
        *,
        change_description: str = "",
    ) -> dict[str, Any]:
        self.progress = PipelineProgress("Modify-Plan Pipeline")
        self.progress.print_header()

        # ── Step 0: Change description resolution ─────────────────
        if not change_description:
            change_description = ask_text("どのような変更を計画していますか？")
        self.progress.print_info(f"Change: {change_description[:80]}")

        # ── Step 1: MP0 — Investigate ─────────────────────────────
        result_mp0 = await self._run_or_fail(
            "MP0: investigate",
            "tools/orchestrator/prompts/modify-plan-investigate.md",
            "opus",
            {"CHANGE_DESCRIPTION": change_description},
            self.config.project_root,
        )

        # Handle special cases
        if result_mp0.parsed.mp0_no_match:
            self.progress.print_info(
                "対象specが見つかりませんでした。`/plan` で新規featureとして作成してください。"
            )
            self.progress.print_summary()
            return {"status": "no-match", "change": change_description}

        if result_mp0.parsed.mp0_new_spec_recommended:
            self.progress.print_info(
                "この変更は新規featureとして実装することを推奨します。`/plan` を使用してください。"
            )
            self.progress.print_summary()
            return {"status": "new-spec-recommended", "change": change_description}

        if not result_mp0.parsed.mp0_done:
            raise PipelineError("MP0: 調査結果のマーカーが見つかりません。")

        target_specs_str = result_mp0.parsed.target_specs
        execution_order_str = result_mp0.parsed.execution_order
        propagation_map = result_mp0.parsed.propagation_map

        self.progress.print_info(f"Target specs: {target_specs_str}")
        self.progress.print_info(f"Execution order: {execution_order_str}")

        # Parse target specs into list
        target_specs = self._parse_target_specs(target_specs_str)
        if not target_specs:
            raise PipelineError("MP0: 対象specリストの解析に失敗しました。")

        # ── Step 2: User confirmation (with feedback re-run loop) ──
        while True:
            spec_list_display = "\n".join(
                f"  - {name} ({conf})" for name, conf in target_specs
            )
            self.progress.print_info(f"対象spec:\n{spec_list_display}")

            confirm = ask_choice(
                "この対象specリストで進めますか？",
                ["はい、進める", "キャンセル"],
                allow_freetext=True,
            )
            if confirm == "キャンセル":
                self.progress.print_info("キャンセルしました。")
                self.progress.print_summary()
                return {"status": "cancelled", "change": change_description}

            if confirm == "はい、進める":
                break

            # Free text feedback — re-run MP0 with user's correction
            self.progress.print_info(f"フィードバックを反映してMP0を再実行します...")
            feedback_prompt = (
                f"{change_description}\n\n"
                f"--- ユーザーフィードバック ---\n"
                f"前回の調査結果に対する修正指示: {confirm}"
            )
            result_mp0 = await self._run_or_fail(
                "MP0: investigate (retry)",
                "tools/orchestrator/prompts/modify-plan-investigate.md",
                "opus",
                {"CHANGE_DESCRIPTION": feedback_prompt},
                self.config.project_root,
            )

            if result_mp0.parsed.mp0_no_match:
                self.progress.print_info("対象specが見つかりませんでした。")
                self.progress.print_summary()
                return {"status": "no-match", "change": change_description}

            if not result_mp0.parsed.mp0_done:
                raise PipelineError("MP0: 調査結果のマーカーが見つかりません。")

            target_specs_str = result_mp0.parsed.target_specs
            execution_order_str = result_mp0.parsed.execution_order
            propagation_map = result_mp0.parsed.propagation_map

            self.progress.print_info(f"Target specs: {target_specs_str}")
            target_specs = self._parse_target_specs(target_specs_str)
            if not target_specs:
                raise PipelineError("MP0: 対象specリストの解析に失敗しました。")

        # ── Step 3: Output directory resolution ───────────────────
        slug = _slugify(change_description)
        output_dir = self.config.project_root / "docs" / "modify-plans" / slug

        if output_dir.exists():
            dir_action = ask_choice(
                f"出力ディレクトリ '{slug}' は既に存在します。",
                ["上書き", "別名で作成"],
            )
            if dir_action == "別名で作成":
                new_slug = ask_text("新しいslugを入力してください")
                slug = new_slug
                output_dir = self.config.project_root / "docs" / "modify-plans" / slug

        output_dir.mkdir(parents=True, exist_ok=True)
        self.progress.print_info(f"Output: docs/modify-plans/{slug}/")

        # ── Step 4: MP1 × N — Plan generation (parallel) ─────────
        spec_names = [name for name, _ in target_specs]
        mp1_results, mp1_failures = await self._run_mp1_parallel(
            spec_names, change_description, propagation_map, output_dir,
            target_specs_str,
        )

        if not mp1_results and mp1_failures:
            raise PipelineError(
                "MP1: 全てのplan生成が失敗しました。\n"
                + "\n".join(f"  - {name}: {err}" for name, err in mp1_failures)
            )

        if mp1_failures:
            fail_names = [name for name, _ in mp1_failures]
            self.progress.print_info(
                f"MP1: 一部失敗 — {', '.join(fail_names)}"
            )
            retry = ask_choice(
                "失敗したspecをどうしますか？",
                ["スキップして続行", "キャンセル"],
            )
            if retry == "キャンセル":
                self.progress.print_summary()
                return {"status": "cancelled-partial-failure", "change": change_description}

        # ── Step 5: MP2 × N — Plan review (parallel) ──────────────
        all_summaries = self._collect_mp1_summaries(mp1_results)
        mp2_results = await self._run_mp2_parallel(
            mp1_results, change_description, propagation_map, all_summaries,
        )

        # ── Step 6: Result display ────────────────────────────────
        self._display_results(mp2_results, output_dir)

        # ── Step 7: User decision — Accept / Feedback loop ────────
        result = await self._feedback_loop(
            mp2_results, change_description, propagation_map, all_summaries,
            output_dir,
        )

        # Write _index.md
        self._write_index(
            output_dir, slug, change_description, target_specs,
            propagation_map, execution_order_str, mp2_results,
        )

        self.progress.print_summary()
        self.progress.print_success(f"Plan出力: docs/modify-plans/{slug}/")

        return {
            "status": "completed",
            "change": change_description,
            "slug": slug,
            "specs": [name for name, _ in target_specs],
            "output_dir": str(output_dir),
        }

    # ── Parallel execution helpers ────────────────────────────────

    async def _run_mp1_parallel(
        self,
        spec_names: list[str],
        change_description: str,
        propagation_map: str,
        output_dir: Path,
        all_target_specs: str,
    ) -> tuple[list[tuple[str, AgentResult]], list[tuple[str, str]]]:
        """Run MP1 plan-gen in parallel for each spec."""

        async def run_single(name: str) -> tuple[str, AgentResult | Exception]:
            plan_path = output_dir / f"{name}.md"
            entry = self._extract_propagation_entry(propagation_map, name)
            try:
                result = await self.run_agent_step(
                    AgentStep(
                        name=f"MP1: {name}",
                        instruction_path="tools/orchestrator/prompts/modify-plan-gen.md",
                        model="sonnet",
                        params={
                            "FEATURE_NAME": name,
                            "CHANGE_DESCRIPTION": change_description,
                            "PROPAGATION_ENTRY": entry,
                            "OUTPUT_PATH": str(plan_path),
                            "ALL_TARGET_SPECS": all_target_specs,
                        },
                    ),
                    cwd=self.config.project_root,
                )
                return name, result
            except Exception as e:
                return name, e

        tasks = [run_single(name) for name in spec_names]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        successes: list[tuple[str, AgentResult]] = []
        failures: list[tuple[str, str]] = []

        for item in raw_results:
            if isinstance(item, Exception):
                failures.append(("unknown", str(item)))
                continue
            name, result = item
            if isinstance(result, Exception):
                failures.append((name, str(result)))
            elif isinstance(result, AgentResult) and result.is_error:
                failures.append((name, result.error_message))
            else:
                successes.append((name, result))

        return successes, failures

    async def _run_mp2_parallel(
        self,
        mp1_results: list[tuple[str, AgentResult]],
        change_description: str,
        propagation_map: str,
        all_summaries: str,
    ) -> list[tuple[str, AgentResult]]:
        """Run MP2 review in parallel for each successfully generated plan."""

        async def run_single(
            name: str, mp1_result: AgentResult
        ) -> tuple[str, AgentResult | Exception]:
            plan_path = self._get_plan_path_from_results(name)
            try:
                result = await self.run_agent_step(
                    AgentStep(
                        name=f"MP2: {name}",
                        instruction_path="tools/orchestrator/prompts/modify-plan-review.md",
                        model="opus",
                        params={
                            "FEATURE_NAME": name,
                            "PLAN_PATH": plan_path,
                            "CHANGE_DESCRIPTION": change_description,
                            "PROPAGATION_MAP": propagation_map,
                            "ALL_PLANS_SUMMARY": all_summaries,
                        },
                    ),
                    cwd=self.config.project_root,
                )
                return name, result
            except Exception as e:
                return name, e

        tasks = [run_single(name, result) for name, result in mp1_results]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[tuple[str, AgentResult]] = []
        for item in raw_results:
            if isinstance(item, Exception):
                continue
            name, result = item
            if isinstance(result, Exception):
                self.progress.print_info(f"MP2: {name} レビュー失敗 — {result}")
                continue
            results.append((name, result))

        return results

    # ── Feedback loop ─────────────────────────────────────────────

    async def _feedback_loop(
        self,
        mp2_results: list[tuple[str, AgentResult]],
        change_description: str,
        propagation_map: str,
        all_summaries: str,
        output_dir: Path,
    ) -> list[tuple[str, AgentResult]]:
        """Handle accept/feedback user decision loop."""
        current_results = mp2_results

        while True:
            # Check for REVISE status
            revise_specs = [
                name for name, r in current_results
                if r.parsed.mp2_status == "REVISE"
            ]

            if revise_specs:
                self.progress.print_info(
                    f"REVISE対象: {', '.join(revise_specs)}"
                )

            choice = ask_choice(
                "planを確認してください。",
                ["Accept — 確定", "Feedback — 修正指示"],
            )

            if choice.startswith("Accept"):
                return current_results

            # Get feedback
            feedback = ask_text("修正内容を入力してください")

            # Determine which specs to re-edit
            if revise_specs:
                edit_specs = revise_specs
            else:
                edit_target = ask_text(
                    f"対象spec名 (カンマ区切り、または 'all'): "
                )
                if edit_target.strip().lower() == "all":
                    edit_specs = [name for name, _ in current_results]
                else:
                    edit_specs = [s.strip() for s in edit_target.split(",")]

            # Run MP1e for target specs
            for spec_name in edit_specs:
                mp2_result = next(
                    (r for name, r in current_results if name == spec_name),
                    None,
                )
                review_changes = mp2_result.parsed.mp2_changes if mp2_result else ""

                plan_path = str(output_dir / f"{spec_name}.md")
                result_mp1e = await self._run_or_fail(
                    f"MP1e: {spec_name}",
                    "tools/orchestrator/prompts/modify-plan-edit.md",
                    "sonnet",
                    {
                        "FEATURE_NAME": spec_name,
                        "PLAN_PATH": plan_path,
                        "FEEDBACK": feedback,
                        "REVIEW_CHANGES": review_changes,
                        "PROPAGATION_MAP": propagation_map,
                    },
                    self.config.project_root,
                )

                # Re-run MP2 for edited spec
                result_mp2 = await self.run_agent_step(
                    AgentStep(
                        name=f"MP2: {spec_name} (re-review)",
                        instruction_path="tools/orchestrator/prompts/modify-plan-review.md",
                        model="opus",
                        params={
                            "FEATURE_NAME": spec_name,
                            "PLAN_PATH": plan_path,
                            "CHANGE_DESCRIPTION": change_description,
                            "PROPAGATION_MAP": propagation_map,
                            "ALL_PLANS_SUMMARY": all_summaries,
                        },
                    ),
                    cwd=self.config.project_root,
                )

                # Update results
                current_results = [
                    (spec_name, result_mp2) if name == spec_name else (name, r)
                    for name, r in current_results
                ]

            self._display_results(current_results, output_dir)

    # ── Index file generation ─────────────────────────────────────

    def _write_index(
        self,
        output_dir: Path,
        slug: str,
        change_description: str,
        target_specs: list[tuple[str, str]],
        propagation_map: str,
        execution_order: str,
        mp2_results: list[tuple[str, AgentResult]],
    ) -> None:
        """Write _index.md execution guide."""
        today = date.today().isoformat()

        # Build spec table
        spec_rows: list[str] = []
        for name, confidence in target_specs:
            status = "READY"
            for rname, r in mp2_results:
                if rname == name:
                    status = r.parsed.mp2_status or "READY"
                    break
            spec_rows.append(
                f"| {name} | {confidence} | [{name}.md](./{name}.md) | {status} |"
            )
        spec_table = "\n".join(spec_rows)

        # Build execution commands
        exec_order = [s.strip() for s in execution_order.split(",")]
        exec_commands: list[str] = []
        for i, spec_name in enumerate(exec_order, 1):
            plan_path = output_dir / f"{spec_name}.md"
            exec_commands.append(
                f'{i}. `make modify feature={spec_name} change="<{spec_name}.mdの変更記述>"`'
            )

        exec_section = "\n".join(exec_commands)

        content = f"""# Modify Plan: {slug}
**Generated**: {today}
**Change**: {change_description}

## 対象Spec
| Spec | 信頼度 | Plan | Status |
|------|--------|------|--------|
{spec_table}

## 伝播マップ
{propagation_map}

## 推奨実行順序
{exec_section}

> 各 `make modify` は独立したworktreeを作成します。
> 複数specの場合、先行specのPRをマージしてから次を実行してください。
"""

        index_path = output_dir / "_index.md"
        index_path.write_text(content)

    # ── Display helpers ───────────────────────────────────────────

    def _display_results(
        self,
        mp2_results: list[tuple[str, AgentResult]],
        output_dir: Path,
    ) -> None:
        """Display review results summary."""
        for name, r in mp2_results:
            status = r.parsed.mp2_status or "unknown"
            icon = "[green]READY[/]" if status == "READY" else "[yellow]REVISE[/]"
            if self.progress:
                self.progress.console.print(
                    f"  {icon} {name} → docs/modify-plans/.../{name}.md"
                )

    # ── Parsing helpers ───────────────────────────────────────────

    @staticmethod
    def _parse_target_specs(specs_str: str) -> list[tuple[str, str]]:
        """Parse 'spec2 (high), spec1 (medium)' into [(name, confidence)]."""
        result: list[tuple[str, str]] = []
        for item in specs_str.split(","):
            item = item.strip()
            m = re.match(r"(\S+)\s*\((\w+)\)", item)
            if m:
                result.append((m.group(1), m.group(2)))
            elif item:
                result.append((item, "unknown"))
        return result

    @staticmethod
    def _extract_propagation_entry(propagation_map: str, spec_name: str) -> str:
        """Extract the propagation map entry for a specific spec."""
        lines = propagation_map.split("\n")
        entry_lines: list[str] = []
        capturing = False

        for line in lines:
            if line.startswith(f"## {spec_name}"):
                capturing = True
                entry_lines.append(line)
            elif capturing and line.startswith("## "):
                break
            elif capturing:
                entry_lines.append(line)

        return "\n".join(entry_lines).strip() if entry_lines else ""

    def _get_plan_path_from_results(self, spec_name: str) -> str:
        """Resolve plan file path for a spec name."""
        # Walk up from progress to find output_dir — stored via convention
        # Simplification: reconstruct from project root
        plans_dir = self.config.project_root / "docs" / "modify-plans"
        for d in sorted(plans_dir.iterdir(), reverse=True):
            if d.is_dir():
                candidate = d / f"{spec_name}.md"
                if candidate.exists():
                    return str(candidate)
        return str(plans_dir / f"{spec_name}.md")

    def _collect_mp1_summaries(
        self, mp1_results: list[tuple[str, AgentResult]]
    ) -> str:
        """Collect MP1 summaries for cross-spec review."""
        parts: list[str] = []
        for name, result in mp1_results:
            summary = result.parsed.mp1_summary
            gaps = result.parsed.mp1_gaps
            parts.append(f"## {name}\n{summary}\nGaps: {gaps}")
        return "\n\n".join(parts)

    async def _run_or_fail(
        self,
        name: str,
        instruction_path: str,
        model: str,
        params: dict[str, str],
        cwd: Path,
    ) -> AgentResult:
        """Run an agent step; raise PipelineError on failure."""
        result = await self.run_agent_step(
            AgentStep(name=name, instruction_path=instruction_path, model=model, params=params),
            cwd=cwd,
        )
        if result.is_error:
            raise PipelineError(f"{name} failed: {result.error_message}")
        return result
