"""WorkflowRunner — main execution loop for YAML-defined workflows."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from ..config import OrchestratorConfig
from ..progress import StepTracker
from ..response import (
    error_occurred,
    interaction_required,
    pipeline_completed,
    pipeline_failed,
)
from ..session import PipelineSession, save_session
from .claude_p import ClaudePRunner
from .executors import (
    StepResult,
    execute_claude,
    execute_parallel,
    execute_python,
    execute_review_gate,
    execute_skill,
)
from .loader import load_workflow
from .schema import Step, Workflow
from .template import evaluate_condition, resolve

logger = logging.getLogger(__name__)


class WorkflowRunner:
    """Executes a YAML-defined workflow with checkpoint/resume support."""

    def __init__(
        self,
        config: OrchestratorConfig,
        session: PipelineSession | None = None,
        session_dir: Path | None = None,
    ) -> None:
        self.config = config
        self.session_dir = session_dir or (config.project_root / config.session_dir)
        self.runner = ClaudePRunner(config)
        self.tracker = StepTracker()

        # Session will be set in run() or resume()
        self.session = session or PipelineSession(
            session_id=uuid.uuid4().hex[:12],
            pipeline="",
        )

    async def run(
        self,
        workflow_path: Path | str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a workflow from the beginning.

        Args:
            workflow_path: Path to the YAML workflow file.
            params: Initial parameters to pass to the workflow.

        Returns:
            Response dict (interaction_required, error_occurred,
            pipeline_completed, or pipeline_failed).
        """
        workflow = load_workflow(workflow_path)

        # Initialize session
        self.session.pipeline = workflow.name
        self.session.status = "running"
        self.session.params = params or {}

        # Initialize variables from workflow vars + params
        variables = self._init_variables(workflow, params or {})

        return await self._execute_steps(workflow, variables, start_index=0)

    async def resume(
        self,
        workflow_path: Path | str,
        user_input: str = "",
        action: str = "",
    ) -> dict[str, Any]:
        """Resume a paused workflow from its checkpoint.

        Args:
            workflow_path: Path to the YAML workflow file.
            user_input: User's response (for review gates).
            action: Action to take for error recovery ("retry"/"skip"/"abort").

        Returns:
            Response dict.
        """
        workflow = load_workflow(workflow_path)
        self.session.status = "running"
        self.session.checkpoint_data["user_input"] = user_input
        if action:
            self.session.checkpoint_data["action"] = action

        # Restore variables
        variables = self._restore_variables(workflow)
        # Make user input available to subsequent steps
        variables["_user_input"] = user_input

        checkpoint = self.session.checkpoint
        if not checkpoint:
            return pipeline_failed(
                session_id=self.session.session_id,
                pipeline=self.session.pipeline,
                current_step="unknown",
                error_message="No checkpoint to resume from.",
            )

        # Find checkpoint step
        step = workflow.get_step(checkpoint)
        if not step:
            return pipeline_failed(
                session_id=self.session.session_id,
                pipeline=self.session.pipeline,
                current_step=checkpoint,
                error_message=f"Checkpoint step '{checkpoint}' not found in workflow.",
            )

        # Handle resume based on checkpoint type
        step_index = self._get_step_index(workflow, checkpoint)

        # Handle error resume
        if action:
            resume_result = self._handle_error_resume(action, step, workflow)
            if resume_result is not None:
                return resume_result
            # retry — re-execute from the same step
            return await self._execute_steps(workflow, variables, start_index=step_index)

        # Handle on_marker resume (Conditional GO, Retry, Abort, etc.)
        marker_resume = await self._handle_marker_resume(
            workflow, variables, step, user_input, step_index
        )
        if marker_resume is not None:
            return marker_resume

        # Handle review gate feedback
        if step.type == "review_gate" and step.on_feedback and user_input:
            return await self._handle_feedback_resume(
                workflow, variables, step, user_input
            )

        # Default: continue from next step
        return await self._execute_steps(
            workflow, variables, start_index=step_index + 1
        )

    async def _execute_steps(
        self,
        workflow: Workflow,
        variables: dict[str, Any],
        start_index: int = 0,
    ) -> dict[str, Any]:
        """Execute workflow steps from start_index until completion or pause."""
        for i in range(start_index, len(workflow.steps)):
            step = workflow.steps[i]

            # Evaluate when condition
            if step.when and not evaluate_condition(step.when, variables):
                logger.info("Skipping step %s (condition false)", step.id)
                record = self.tracker.add_step(step.id, step.model)
                self.tracker.skip_step(record, "condition false")
                continue

            # Dispatch to executor
            result = await self._dispatch(step, variables)

            # Handle pause (review gates, on_marker pause)
            if result.is_pause:
                self.session.checkpoint = step.id
                self.session.status = "paused"
                self._save_variables(variables)
                self._save()
                pause_data = result.pause_data or {}
                return interaction_required(
                    session_id=self.session.session_id,
                    pipeline=self.session.pipeline,
                    current_step=step.id,
                    question=pause_data.get("question", ""),
                    options=pause_data.get("options"),
                    context=pause_data.get("context", ""),
                    progress=self.tracker.to_progress_list(),
                )

            # Handle error
            if result.is_error:
                self.session.checkpoint = step.id
                self.session.status = "paused"
                self._save_variables(variables)
                self._save()
                return error_occurred(
                    session_id=self.session.session_id,
                    pipeline=self.session.pipeline,
                    current_step=f"step_{step.id}_failed",
                    error_message=result.error_message,
                    step_output=result.output_text[:2000] if result.output_text else "",
                    recoverable=True,
                    suggested_actions=["retry", "skip", "abort"],
                    progress=self.tracker.to_progress_list(),
                )

            # Apply extractions to variables
            if result.extracted:
                variables.update(result.extracted)

            # Save session_id for potential resume
            if result.session_id:
                variables[f"_session_{step.id}"] = result.session_id

            # Check on_marker actions
            marker_response = self._check_markers(step, result, variables)
            if marker_response is not None:
                return marker_response

            # Checkpoint after each step
            self.session.checkpoint = step.id
            self._save_variables(variables)
            self._save()

        # All steps completed
        self.session.status = "completed"
        self.session.checkpoint = "done"
        self.session.completed_steps = self.tracker.to_progress_list()
        self._save()
        return pipeline_completed(
            session_id=self.session.session_id,
            pipeline=self.session.pipeline,
            current_step="done",
            result={"variables": {k: v for k, v in variables.items() if not k.startswith("_")}},
            progress=self.tracker.to_progress_list(),
        )

    async def _dispatch(
        self,
        step: Step,
        variables: dict[str, Any],
    ) -> StepResult:
        """Dispatch a step to its executor."""
        if step.type == "claude":
            return await execute_claude(
                step, variables, self.config, self.runner, self.tracker
            )
        elif step.type == "python":
            return await execute_python(
                step, variables, self.config, self.tracker
            )
        elif step.type == "skill":
            return await execute_skill(
                step, variables, self.config, self.runner, self.tracker
            )
        elif step.type == "review_gate":
            return await execute_review_gate(
                step, variables, self.config, self.tracker
            )
        elif step.type == "parallel":
            return await execute_parallel(
                step, variables, self.config, self.runner, self.tracker
            )
        else:
            return StepResult(
                is_error=True,
                error_message=f"Unknown step type: {step.type}",
            )

    def _check_markers(
        self,
        step: Step,
        result: StepResult,
        variables: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Check on_marker actions after a claude step. Returns response or None."""
        if not step.on_marker or not result.markers:
            return None

        for marker_name, action in step.on_marker.items():
            if result.markers.get(marker_name):
                if action.pause:
                    self.session.checkpoint = step.id
                    self.session.status = "paused"
                    if action.save_session and result.session_id:
                        variables[f"_session_{step.id}"] = result.session_id
                    self._save_variables(variables)
                    self._save()
                    question = action.question or f"Marker {marker_name} detected at step {step.id}."
                    options = action.options or None
                    return interaction_required(
                        session_id=self.session.session_id,
                        pipeline=self.session.pipeline,
                        current_step=action.pause,
                        question=question,
                        options=options,
                        context=result.output_text[-2000:] if result.output_text else "",
                        progress=self.tracker.to_progress_list(),
                    )
        return None

    async def _handle_marker_resume(
        self,
        workflow: Workflow,
        variables: dict[str, Any],
        step: Step,
        user_input: str,
        step_index: int,
    ) -> dict[str, Any] | None:
        """Handle resume from an on_marker pause using on_resume dispatch.

        Matches user_input prefix against on_resume keys. Returns response
        dict if handled, or None to fall through to default behavior (GO).
        """
        if not step.on_marker or not user_input:
            return None

        # Find the marker action that has on_resume defined
        for _marker_name, marker_action in step.on_marker.items():
            if not marker_action.on_resume:
                continue

            # Prefix-match user_input against on_resume keys
            for prefix, resume_action in marker_action.on_resume.items():
                if not user_input.startswith(prefix):
                    continue

                # Abort
                if resume_action.goto == "_abort":
                    return pipeline_failed(
                        session_id=self.session.session_id,
                        pipeline=self.session.pipeline,
                        current_step=step.id,
                        error_message=f"User aborted at step '{step.id}'.",
                        progress=self.tracker.to_progress_list(),
                    )

                # Goto a specific step
                if resume_action.goto:
                    goto_idx = self._get_step_index(workflow, resume_action.goto)
                    if goto_idx < 0:
                        return pipeline_failed(
                            session_id=self.session.session_id,
                            pipeline=self.session.pipeline,
                            current_step=step.id,
                            error_message=f"Goto target '{resume_action.goto}' not found.",
                        )
                    return await self._execute_steps(
                        workflow, variables, start_index=goto_idx
                    )

                # Resume saved session
                if resume_action.resume_session:
                    session_id = variables.get(f"_session_{step.id}", "")
                    if session_id:
                        extra = resolve(resume_action.extra_prompt, {
                            **variables, "user_input": user_input,
                        }) if resume_action.extra_prompt else ""
                        await self.runner.run(
                            extra or user_input,
                            model=step.model,
                            cwd=resolve(step.cwd, variables) if step.cwd else None,
                            resume_session_id=session_id,
                        )
                    # After resume (or no session), continue to next step
                    return await self._execute_steps(
                        workflow, variables, start_index=step_index + 1
                    )

            # If we checked on_resume keys but none matched, fall through (GO case)

        return None

    async def _handle_feedback_resume(
        self,
        workflow: Workflow,
        variables: dict[str, Any],
        gate_step: Step,
        user_input: str,
    ) -> dict[str, Any]:
        """Handle review gate feedback by rerunning the specified step."""
        fb = gate_step.on_feedback
        if not fb:
            # No on_feedback defined, continue to next step
            idx = self._get_step_index(workflow, gate_step.id)
            return await self._execute_steps(workflow, variables, start_index=idx + 1)

        # Apply extra_params from feedback
        for key, expr in fb.extra_params.items():
            variables[key] = resolve(expr, {**variables, "user_input": user_input})

        # Find and rerun the target step
        rerun_idx = self._get_step_index(workflow, fb.rerun)
        if rerun_idx < 0:
            return pipeline_failed(
                session_id=self.session.session_id,
                pipeline=self.session.pipeline,
                current_step=gate_step.id,
                error_message=f"Rerun target '{fb.rerun}' not found.",
            )

        # If 'then' is specified, execute rerun step then jump to 'then' step
        if fb.then:
            then_idx = self._get_step_index(workflow, fb.then)
            if then_idx < 0:
                return pipeline_failed(
                    session_id=self.session.session_id,
                    pipeline=self.session.pipeline,
                    current_step=gate_step.id,
                    error_message=f"Then target '{fb.then}' not found.",
                )
            # Execute from rerun to then (inclusive)
            return await self._execute_steps(workflow, variables, start_index=rerun_idx)

        # Otherwise continue from rerun step
        return await self._execute_steps(workflow, variables, start_index=rerun_idx)

    def _handle_error_resume(
        self,
        action: str,
        step: Step,
        workflow: Workflow,
    ) -> dict[str, Any] | None:
        """Handle error resume actions. Returns response or None to retry."""
        if action == "abort":
            return pipeline_failed(
                session_id=self.session.session_id,
                pipeline=self.session.pipeline,
                current_step=step.id,
                error_message=f"User aborted at step '{step.id}'.",
                progress=self.tracker.to_progress_list(),
            )

        if action == "skip":
            # Advance to next step
            idx = self._get_step_index(workflow, step.id)
            self.session.checkpoint = workflow.steps[idx + 1].id if idx + 1 < len(workflow.steps) else "done"
            self._save()
            return None

        # "retry" — return None to re-execute
        return None

    def _init_variables(
        self,
        workflow: Workflow,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Initialize variables from workflow var defs + params."""
        variables: dict[str, Any] = {
            "project_root": str(self.config.project_root),
        }

        for name, var_def in workflow.vars.items():
            if var_def.from_param and var_def.from_param in params:
                variables[name] = params[var_def.from_param]
            elif var_def.default is not None:
                variables[name] = var_def.default
            else:
                variables[name] = ""

        # Merge any extra params
        variables.update(params)
        return variables

    def _restore_variables(self, workflow: Workflow) -> dict[str, Any]:
        """Restore variables from session state."""
        return dict(self.session.checkpoint_data.get("_variables", {}))

    def _save_variables(self, variables: dict[str, Any]) -> None:
        """Save variables to session for resume."""
        self.session.checkpoint_data["_variables"] = dict(variables)

    def _get_step_index(self, workflow: Workflow, step_id: str) -> int:
        """Get the index of a step by ID. Returns -1 if not found."""
        for i, step in enumerate(workflow.steps):
            if step.id == step_id:
                return i
        return -1

    def _save(self) -> None:
        """Persist session state to disk."""
        save_session(self.session, self.session_dir)
