"""CLI entry point — argparse for implement / modify subcommands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import anyio

from .config import OrchestratorConfig
from .pipeline import PipelineError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cc-sdd",
        description="cc-sdd external orchestrator — implement & modify pipelines",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # implement
    impl_p = sub.add_parser(
        "implement",
        aliases=["impl"],
        help="Execute cc-sdd pipeline from a plan file",
    )
    impl_p.add_argument(
        "plan",
        help="Plan file name, path, or identifier (e.g. 'nested-doodling-cat')",
    )
    impl_p.add_argument(
        "--max-turns",
        type=int,
        default=200,
        help="Max agentic turns per step (default: 200)",
    )

    # modify
    mod_p = sub.add_parser(
        "modify",
        aliases=["mod"],
        help="Execute spec modification workflow",
    )
    mod_p.add_argument(
        "feature",
        help="Feature name (spec directory name)",
    )
    mod_p.add_argument(
        "change",
        nargs="*",
        help="Change description (can be omitted — will prompt interactively)",
    )
    mod_p.add_argument(
        "--max-turns",
        type=int,
        default=200,
        help="Max agentic turns per step (default: 200)",
    )

    # spike (Phase 0 verification)
    sub.add_parser(
        "spike",
        help="Run SDK parity spike (Phase 0 verification)",
    )

    return parser


async def _run_implement(args: argparse.Namespace, config: OrchestratorConfig) -> int:
    from .pipelines.implement import ImplementPipeline

    pipeline = ImplementPipeline(config)
    try:
        result = await pipeline.run(plan_argument=args.plan)
        if result["status"] == "completed":
            return 0
        return 1
    except PipelineError as e:
        if pipeline.progress:
            pipeline.progress.print_error(str(e))
            if e.worktree_path:
                pipeline.progress.print_info(f"Worktree: {e.worktree_path}")
            pipeline.progress.print_summary()
        return 1


async def _run_modify(args: argparse.Namespace, config: OrchestratorConfig) -> int:
    from .pipelines.modify import ModifyPipeline

    change_desc = " ".join(args.change) if args.change else ""

    pipeline = ModifyPipeline(config)
    try:
        result = await pipeline.run(
            feature_name=args.feature,
            change_description=change_desc,
        )
        if result["status"] == "completed":
            return 0
        return 1
    except PipelineError as e:
        if pipeline.progress:
            pipeline.progress.print_error(str(e))
            if e.worktree_path:
                pipeline.progress.print_info(f"Worktree: {e.worktree_path}")
            pipeline.progress.print_summary()
        return 1


async def _run_spike() -> int:
    from .spike import run_spike

    await run_spike()
    return 0


async def _async_main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    project_root = Path.cwd().resolve()

    config = OrchestratorConfig(
        project_root=project_root,
        max_turns=getattr(args, "max_turns", 200),
    )

    if args.command in ("implement", "impl"):
        return await _run_implement(args, config)
    elif args.command in ("modify", "mod"):
        return await _run_modify(args, config)
    elif args.command == "spike":
        return await _run_spike()
    else:
        parser.print_help()
        return 1


def main() -> None:
    """Entry point for CLI."""
    exit_code = anyio.run(_async_main)
    sys.exit(exit_code)
