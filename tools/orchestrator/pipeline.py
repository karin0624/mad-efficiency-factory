"""Pipeline base class — shared run structure and error handling."""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .agent_runner import AgentRunner, AgentStep, AgentResult
from .config import OrchestratorConfig
from .progress import PipelineProgress, StepRecord


class PipelineError(Exception):
    """Raised when a pipeline step fails fatally."""

    def __init__(self, message: str, worktree_path: Path | None = None) -> None:
        super().__init__(message)
        self.worktree_path = worktree_path


class Pipeline(ABC):
    """Base class for orchestration pipelines."""

    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config
        self.runner = AgentRunner(config)
        self.progress: PipelineProgress | None = None

    @abstractmethod
    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the pipeline. Returns a result summary dict."""
        ...

    async def run_agent_step(
        self,
        step: AgentStep,
        cwd: Path | None = None,
    ) -> AgentResult:
        """Execute an agent step with progress tracking.

        Creates a StepRecord, starts it, runs the step, and marks
        it as completed or failed.
        """
        record = None
        if self.progress:
            record = self.progress.add_step(step.name, step.model)
            self.progress.start_step(record)

        result = await self.runner.run_step(
            step,
            progress=self.progress,
            step_record=record,
            cwd=cwd,
        )

        if self.progress and record:
            if result.is_error:
                self.progress.fail_step(record, result.error_message)
            else:
                self.progress.complete_step(record, result.input_tokens, result.output_tokens)

        return result

    def skip_step(self, name: str, model: str, reason: str = "") -> None:
        """Register and immediately skip a step."""
        if self.progress:
            record = self.progress.add_step(name, model)
            self.progress.skip_step(record, reason)

    def _run_tests_subprocess(self, wt_path: Path) -> tuple[bool, str]:
        """scripts/run-tests.sh をsubprocessで実行。(passed, output) を返す。"""
        script = wt_path / "scripts" / "run-tests.sh"
        try:
            result = subprocess.run(
                [str(script)],
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                timeout=300,
            )
            output = (result.stdout + "\n" + result.stderr).strip()
            return (result.returncode == 0, output)
        except subprocess.TimeoutExpired:
            return (False, "Test execution timed out (300s)")
        except Exception as e:
            return (False, f"Test execution error: {e}")

    async def _run_steering_sync(self, wt_path: Path) -> None:
        """/kiro:steering スキルを呼び出してsteering同期を実行する。"""
        from claude_agent_sdk import (
            ClaudeAgentOptions,
            query,
        )

        record = None
        if self.progress:
            record = self.progress.add_step("steering-sync", "sonnet")
            self.progress.start_step(record)

        options = ClaudeAgentOptions(
            model=self.config.resolve_model("sonnet"),
            cwd=str(wt_path),
            setting_sources=["project"],
            permission_mode=self.config.permission_mode,
            allowed_tools=list(self.config.allowed_tools),
            max_turns=50,
            system_prompt={"type": "preset", "preset": "claude_code"},
        )

        async for _ in query(
            prompt='以下のSkillを実行してください:\nSkill(skill="kiro:steering")',
            options=options,
        ):
            pass

        if self.progress and record:
            self.progress.complete_step(record, 0, 0)

    async def run_test_step(
        self,
        wt_path: Path,
        *,
        step_name: str = "T: tests",
        max_retries: int = 2,
    ) -> None:
        """テスト実行。失敗時はAIエージェントで修正を試みる（最大max_retries回）。"""
        record = None
        if self.progress:
            record = self.progress.add_step(step_name, "-")
            self.progress.start_step(record)

        passed, output = self._run_tests_subprocess(wt_path)

        if passed:
            if self.progress and record:
                self.progress.complete_step(record, 0, 0)
            return

        # テスト失敗 → AIエージェントで修正を試みる
        for attempt in range(1, max_retries + 1):
            if self.progress:
                self.progress.print_warning(
                    f"テスト失敗。AI修正を試行 ({attempt}/{max_retries})"
                )

            fix_result = await self.run_agent_step(
                AgentStep(
                    name=f"T: test-fix (attempt {attempt})",
                    instruction_path="tools/orchestrator/prompts/test-fix.md",
                    model="sonnet",
                    params={
                        "WORKTREE_PATH": str(wt_path),
                        "TEST_OUTPUT": output[-10000:],
                    },
                ),
                cwd=wt_path,
            )

            # エージェントがテストを再実行して成功した場合
            if fix_result.parsed.test_fix_passed:
                if self.progress and record:
                    self.progress.complete_step(
                        record, fix_result.input_tokens, fix_result.output_tokens
                    )
                return

            # エージェント自身がFAILEDを報告した場合、次の試行へ
            # 出力を更新して次のリトライに渡す
            if fix_result.output_text:
                output = fix_result.output_text[-10000:]

        # 全リトライ失敗
        if self.progress and record:
            self.progress.fail_step(record, f"Tests failed after {max_retries} fix attempts")
        raise PipelineError(f"テストが{max_retries}回の修正試行後も失敗。", wt_path)
