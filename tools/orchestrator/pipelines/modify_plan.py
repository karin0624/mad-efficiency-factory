"""Modify-plan pipeline: investigate -> plan-gen -> review -> feedback loop (checkpoint-based).

Steps: Change resolve -> MP0(Investigate) -> User confirm
       -> MP1xN(Plan-gen, parallel) -> MP2xN(Review, parallel)
       -> Result display -> User accept/feedback -> [MP1e -> MP2 loop]
"""

from __future__ import annotations

import asyncio
import re
from datetime import date
from pathlib import Path
from typing import Any

from ..agent_runner import AgentStep, AgentResult
from ..config import OrchestratorConfig
from ..pipeline import InterruptiblePipeline
from ..session import PipelineSession


def _next_plan_id(plans_base: Path) -> str:
    """Auto-increment plan directory name (m1, m2, ...)."""
    existing = []
    if plans_base.is_dir():
        for d in plans_base.iterdir():
            if d.is_dir() and (m := re.match(r"^m(\d+)$", d.name)):
                existing.append(int(m.group(1)))
    return f"m{max(existing, default=0) + 1}"


class ModifyPlanPipeline(InterruptiblePipeline):
    """Modify-plan pipeline: investigate affected specs and generate plans."""

    def __init__(
        self,
        config: OrchestratorConfig,
        session: PipelineSession,
        session_dir: Path,
    ) -> None:
        super().__init__(config, session, session_dir)

    async def run_until_checkpoint(self) -> dict[str, Any]:
        cp = self.session.checkpoint

        if cp:
            result = self._handle_resume(cp)
            if result is not None:
                return result
            cp = self.session.checkpoint

        segments = [
            ("start", self._seg_start),
            ("MP0", self._seg_MP0),
            ("confirm_specs", self._seg_confirm_specs),
            ("output_dir", self._seg_output_dir),
            ("MP1", self._seg_MP1),
            ("MP2", self._seg_MP2),
            ("review", self._seg_review),
            ("write_index", self._seg_write_index),
        ]

        start_from = cp if cp in [n for n, _ in segments] else ""
        result = await self._run_segments(segments, start_from)
        if result is not None:
            return result

        return self._complete_pipeline()

    # ── Resume handling ──────────────────────────────────────────

    def _handle_resume(self, cp: str) -> dict[str, Any] | None:
        user_input = self.session.checkpoint_data.get("user_input", "")

        if cp == "change_description_needed":
            if user_input:
                self.session.params["change"] = user_input
                self.session.checkpoint = "MP0"
                self._save()
                return None
            return self.make_interaction(
                checkpoint="change_description_needed",
                question="どのような変更を計画していますか？",
            )

        if cp == "mp0_confirm_specs":
            if user_input == "キャンセル":
                return self.make_completed({
                    "status": "cancelled",
                    "change": self.session.params.get("change", ""),
                })
            if user_input == "はい、進める":
                self.session.checkpoint = "output_dir"
                self._save()
                return None
            # Freetext feedback — re-run MP0
            self.session.checkpoint_data["mp0_feedback"] = user_input
            self.session.checkpoint = "MP0"
            self._save()
            return None

        if cp == "output_dir_conflict":
            if user_input and user_input != "上書き":
                # User provided a new slug
                self.session.checkpoint_data["slug"] = user_input
            self.session.checkpoint = "MP1"
            self._save()
            return None

        if cp == "mp1_partial_failure":
            if "キャンセル" in user_input:
                return self.make_completed({
                    "status": "cancelled-partial-failure",
                    "change": self.session.params.get("change", ""),
                })
            # Skip failures and continue
            self.session.checkpoint = "MP2"
            self._save()
            return None

        if cp == "mp2_review_decision":
            if "Accept" in user_input or "確定" in user_input:
                self.session.checkpoint = "write_index"
                self._save()
                return None
            # Feedback — ask for details
            self.session.checkpoint_data["feedback_requested"] = True
            return self.make_interaction(
                checkpoint="mp2_feedback_specs",
                question="修正内容と対象spec名を入力してください (例: 'spec-nameのXXを修正')",
            )

        if cp == "mp2_feedback_specs":
            if user_input:
                self.session.checkpoint_data["feedback_text"] = user_input
                self.session.checkpoint = "review"
                self.session.checkpoint_data["do_feedback_loop"] = True
                self._save()
                return None
            return self.make_interaction(
                checkpoint="mp2_feedback_specs",
                question="修正内容を入力してください",
            )

        if cp.startswith("step_") and cp.endswith("_failed"):
            step_name = cp[5:].rsplit("_", 1)[0]
            return self._handle_step_error_resume(step_name)

        return None

    # ── Segments ─────────────────────────────────────────────────

    async def _seg_start(self) -> dict[str, Any] | None:
        """Change description resolution."""
        change = self.session.params.get("change", "")
        if not change:
            return self.make_interaction(
                checkpoint="change_description_needed",
                question="どのような変更を計画していますか？",
            )
        return None

    async def _seg_MP0(self) -> dict[str, Any] | None:
        """MP0 investigate."""
        change = self.session.params.get("change", "")
        feedback = self.session.checkpoint_data.pop("mp0_feedback", "")

        if feedback:
            change = (
                f"{change}\n\n"
                f"--- ユーザーフィードバック ---\n"
                f"前回の調査結果に対する修正指示: {feedback}"
            )

        result = await self.run_agent_step(
            AgentStep(
                "MP0: investigate",
                "tools/orchestrator/prompts/modify-plan-investigate.md",
                "opus",
                {"CHANGE_DESCRIPTION": change},
            ),
            cwd=self.config.project_root,
        )

        if result.is_error:
            return self.make_error(
                checkpoint="step_MP0_failed",
                error=result.error_message,
                step_output=result.output_text[-2000:],
            )

        if result.parsed.mp0_no_match:
            return self.make_completed({
                "status": "no-match",
                "change": self.session.params.get("change", ""),
                "message": "対象specが見つかりませんでした。`/plan` で新規featureとして作成してください。",
            })

        if result.parsed.mp0_new_spec_recommended:
            return self.make_completed({
                "status": "new-spec-recommended",
                "change": self.session.params.get("change", ""),
                "message": "この変更は新規featureとして実装することを推奨します。",
            })

        if not result.parsed.mp0_done:
            return self.make_failed(
                error_message="MP0: 調査結果のマーカーが見つかりません。"
            )

        target_specs_str = result.parsed.target_specs
        execution_order_str = result.parsed.execution_order
        propagation_map = result.parsed.propagation_map

        target_specs = self._parse_target_specs(target_specs_str)
        if not target_specs:
            return self.make_failed(
                error_message="MP0: 対象specリストの解析に失敗しました。"
            )

        self.session.checkpoint_data["target_specs_str"] = target_specs_str
        self.session.checkpoint_data["target_specs"] = [
            {"name": n, "confidence": c} for n, c in target_specs
        ]
        self.session.checkpoint_data["execution_order_str"] = execution_order_str
        self.session.checkpoint_data["propagation_map"] = propagation_map
        self.session.checkpoint_data["plan_slug"] = result.parsed.plan_slug or ""
        self._save()
        return None

    async def _seg_confirm_specs(self) -> dict[str, Any] | None:
        """User confirmation of target specs."""
        target_specs = self.session.checkpoint_data.get("target_specs", [])
        spec_list = "\n".join(
            f"  - {s['name']} ({s['confidence']})" for s in target_specs
        )
        return self.make_interaction(
            checkpoint="mp0_confirm_specs",
            question=f"この対象specリストで進めますか？\n{spec_list}",
            options=["はい、進める", "キャンセル"],
            context="自由入力でフィードバックを返すとMP0を再実行します",
        )

    async def _seg_output_dir(self) -> dict[str, Any] | None:
        """Output directory resolution."""
        plans_base = self.config.project_root / "docs" / "modify-plans"
        slug = self.session.checkpoint_data.get("slug") or \
               self.session.checkpoint_data.get("plan_slug") or \
               _next_plan_id(plans_base)
        output_dir = plans_base / slug

        if output_dir.exists() and "slug" not in self.session.checkpoint_data:
            return self.make_interaction(
                checkpoint="output_dir_conflict",
                question=f"出力ディレクトリ '{slug}' は既に存在します。上書きしますか？",
                options=["上書き"],
                context="別名を自由入力で指定できます",
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        self.session.checkpoint_data["slug"] = slug
        self.session.checkpoint_data["output_dir"] = str(output_dir)
        self._save()
        return None

    async def _seg_MP1(self) -> dict[str, Any] | None:
        """MP1 x N: plan generation (parallel)."""
        target_specs = self.session.checkpoint_data.get("target_specs", [])
        spec_names = [s["name"] for s in target_specs]
        change = self.session.params.get("change", "")
        propagation_map = self.session.checkpoint_data.get("propagation_map", "")
        target_specs_str = self.session.checkpoint_data.get("target_specs_str", "")
        output_dir = Path(self.session.checkpoint_data["output_dir"])

        successes, failures = await self._run_mp1_parallel(
            spec_names, change, propagation_map, output_dir, target_specs_str,
        )

        if not successes and failures:
            return self.make_failed(
                error_message=(
                    "MP1: 全てのplan生成が失敗しました。\n"
                    + "\n".join(f"  - {name}: {err}" for name, err in failures)
                )
            )

        # Store success data
        mp1_data: dict[str, dict] = {}
        for name, result in successes:
            mp1_data[name] = {
                "summary": result.parsed.mp1_summary,
                "gaps": result.parsed.mp1_gaps,
            }
        self.session.checkpoint_data["mp1_results"] = mp1_data
        self.session.checkpoint_data["mp1_succeeded"] = [n for n, _ in successes]
        self._save()

        if failures:
            fail_names = [name for name, _ in failures]
            return self.make_interaction(
                checkpoint="mp1_partial_failure",
                question=f"MP1: 一部失敗 — {', '.join(fail_names)}。どうしますか？",
                options=["スキップして続行", "キャンセル"],
            )

        return None

    async def _seg_MP2(self) -> dict[str, Any] | None:
        """MP2 x N: plan review (parallel)."""
        mp1_succeeded = self.session.checkpoint_data.get("mp1_succeeded", [])
        mp1_data = self.session.checkpoint_data.get("mp1_results", {})
        change = self.session.params.get("change", "")
        propagation_map = self.session.checkpoint_data.get("propagation_map", "")
        output_dir = Path(self.session.checkpoint_data["output_dir"])

        # Collect summaries for cross-spec review
        all_summaries = "\n\n".join(
            f"## {name}\n{data.get('summary', '')}\nGaps: {data.get('gaps', '')}"
            for name, data in mp1_data.items()
        )

        mp2_results = await self._run_mp2_parallel(
            mp1_succeeded, change, propagation_map, all_summaries, output_dir,
        )

        # Store MP2 results
        mp2_data: dict[str, dict] = {}
        for name, result in mp2_results:
            mp2_data[name] = {
                "status": result.parsed.mp2_status or "unknown",
                "changes": result.parsed.mp2_changes or "",
            }
        self.session.checkpoint_data["mp2_results"] = mp2_data
        self._save()
        return None

    async def _seg_review(self) -> dict[str, Any] | None:
        """User review decision — Accept or Feedback."""
        mp2_data = self.session.checkpoint_data.get("mp2_results", {})

        # Check if we need to run feedback loop
        if self.session.checkpoint_data.pop("do_feedback_loop", False):
            feedback_text = self.session.checkpoint_data.pop("feedback_text", "")
            await self._run_feedback_iteration(feedback_text)
            mp2_data = self.session.checkpoint_data.get("mp2_results", {})

        # Build results summary
        results_summary = "\n".join(
            f"  - {name}: {data.get('status', 'unknown')}"
            for name, data in mp2_data.items()
        )

        revise_specs = [
            name for name, data in mp2_data.items()
            if data.get("status") == "REVISE"
        ]

        context = f"結果:\n{results_summary}"
        if revise_specs:
            context += f"\n\nREVISE対象: {', '.join(revise_specs)}"

        return self.make_interaction(
            checkpoint="mp2_review_decision",
            question="planを確認してください。",
            options=["Accept — 確定", "Feedback — 修正指示"],
            context=context,
        )

    async def _seg_write_index(self) -> dict[str, Any] | None:
        """Write _index.md."""
        output_dir = Path(self.session.checkpoint_data["output_dir"])
        slug = self.session.checkpoint_data["slug"]
        change = self.session.params.get("change", "")
        target_specs = self.session.checkpoint_data.get("target_specs", [])
        propagation_map = self.session.checkpoint_data.get("propagation_map", "")
        execution_order_str = self.session.checkpoint_data.get("execution_order_str", "")
        mp2_data = self.session.checkpoint_data.get("mp2_results", {})

        self._write_index(
            output_dir, slug, change,
            [(s["name"], s["confidence"]) for s in target_specs],
            propagation_map, execution_order_str, mp2_data,
        )
        return None

    # ── Completion ───────────────────────────────────────────────

    def _complete_pipeline(self) -> dict[str, Any]:
        slug = self.session.checkpoint_data.get("slug", "")
        target_specs = self.session.checkpoint_data.get("target_specs", [])
        return self.make_completed({
            "status": "completed",
            "change": self.session.params.get("change", ""),
            "slug": slug,
            "specs": [s["name"] for s in target_specs],
            "output_dir": self.session.checkpoint_data.get("output_dir", ""),
            "next_step": f"make modify plan={slug}",
        })

    # ── Parallel execution ───────────────────────────────────────

    async def _run_mp1_parallel(
        self,
        spec_names: list[str],
        change_description: str,
        propagation_map: str,
        output_dir: Path,
        all_target_specs: str,
    ) -> tuple[list[tuple[str, AgentResult]], list[tuple[str, str]]]:

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
        spec_names: list[str],
        change_description: str,
        propagation_map: str,
        all_summaries: str,
        output_dir: Path,
    ) -> list[tuple[str, AgentResult]]:

        async def run_single(name: str) -> tuple[str, AgentResult | Exception]:
            plan_path = str(output_dir / f"{name}.md")
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

        tasks = [run_single(name) for name in spec_names]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[tuple[str, AgentResult]] = []
        for item in raw_results:
            if isinstance(item, Exception):
                continue
            name, result = item
            if isinstance(result, Exception):
                continue
            results.append((name, result))

        return results

    # ── Feedback loop ────────────────────────────────────────────

    async def _run_feedback_iteration(self, feedback: str) -> None:
        """Run MP1e + MP2 for specs that need revision."""
        mp2_data = self.session.checkpoint_data.get("mp2_results", {})
        output_dir = Path(self.session.checkpoint_data["output_dir"])
        change = self.session.params.get("change", "")
        propagation_map = self.session.checkpoint_data.get("propagation_map", "")
        mp1_data = self.session.checkpoint_data.get("mp1_results", {})

        # Determine which specs to edit
        revise_specs = [
            name for name, data in mp2_data.items()
            if data.get("status") == "REVISE"
        ]
        if not revise_specs:
            # Try to parse spec names from feedback
            all_specs = list(mp2_data.keys())
            revise_specs = all_specs  # Default to all

        all_summaries = "\n\n".join(
            f"## {name}\n{data.get('summary', '')}\nGaps: {data.get('gaps', '')}"
            for name, data in mp1_data.items()
        )

        for spec_name in revise_specs:
            review_changes = mp2_data.get(spec_name, {}).get("changes", "")
            plan_path = str(output_dir / f"{spec_name}.md")

            # MP1e: edit
            await self.run_agent_step(
                AgentStep(
                    name=f"MP1e: {spec_name}",
                    instruction_path="tools/orchestrator/prompts/modify-plan-edit.md",
                    model="sonnet",
                    params={
                        "FEATURE_NAME": spec_name,
                        "PLAN_PATH": plan_path,
                        "FEEDBACK": feedback,
                        "REVIEW_CHANGES": review_changes,
                        "PROPAGATION_MAP": propagation_map,
                    },
                ),
                cwd=self.config.project_root,
            )

            # MP2: re-review
            result_mp2 = await self.run_agent_step(
                AgentStep(
                    name=f"MP2: {spec_name} (re-review)",
                    instruction_path="tools/orchestrator/prompts/modify-plan-review.md",
                    model="opus",
                    params={
                        "FEATURE_NAME": spec_name,
                        "PLAN_PATH": plan_path,
                        "CHANGE_DESCRIPTION": change,
                        "PROPAGATION_MAP": propagation_map,
                        "ALL_PLANS_SUMMARY": all_summaries,
                    },
                ),
                cwd=self.config.project_root,
            )

            mp2_data[spec_name] = {
                "status": result_mp2.parsed.mp2_status or "unknown",
                "changes": result_mp2.parsed.mp2_changes or "",
            }

        self.session.checkpoint_data["mp2_results"] = mp2_data
        self._save()

    # ── Index file generation ────────────────────────────────────

    @staticmethod
    def _write_index(
        output_dir: Path,
        slug: str,
        change_description: str,
        target_specs: list[tuple[str, str]],
        propagation_map: str,
        execution_order: str,
        mp2_data: dict[str, dict],
    ) -> None:
        today = date.today().isoformat()

        spec_rows: list[str] = []
        for name, confidence in target_specs:
            status = mp2_data.get(name, {}).get("status", "READY")
            spec_rows.append(
                f"| {name} | {confidence} | [{name}.md](./{name}.md) | {status} |"
            )
        spec_table = "\n".join(spec_rows)

        exec_order = [s.strip() for s in execution_order.split(",")]
        exec_list = "\n".join(f"{i}. {name}" for i, name in enumerate(exec_order, 1))

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
```bash
make modify plan={slug}
```
上記コマンドを実行すると、以下の順序で全specを一括処理し、1つのPRを作成します。

{exec_list}
"""
        index_path = output_dir / "_index.md"
        index_path.write_text(content)

    # ── Parsing helpers ──────────────────────────────────────────

    @staticmethod
    def _parse_target_specs(specs_str: str) -> list[tuple[str, str]]:
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
