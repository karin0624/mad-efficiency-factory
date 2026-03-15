"""Human input bridge — interactive prompts for pipeline decisions."""

from __future__ import annotations

from rich.console import Console
from rich.prompt import Prompt, Confirm


console = Console()


def ask_choice(question: str, options: list[str]) -> str:
    """Ask the user to select from a list of options.

    Returns the selected option string.
    """
    console.print(f"\n[bold yellow]?[/] {question}")
    for i, opt in enumerate(options, 1):
        console.print(f"  [cyan]{i}[/]. {opt}")

    while True:
        choice = Prompt.ask("選択 (番号)", console=console)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        console.print("[red]無効な選択です。もう一度入力してください。[/]")


def ask_confirm(question: str, default: bool = True) -> bool:
    """Ask a yes/no confirmation question."""
    return Confirm.ask(f"[bold yellow]?[/] {question}", default=default, console=console)


def ask_text(question: str) -> str:
    """Ask for free-text input."""
    return Prompt.ask(f"[bold yellow]?[/] {question}", console=console)


def ask_sync_action(direction: str, count: int, base_branch: str) -> str:
    """Ask what to do about behind/ahead sync status.

    Args:
        direction: "behind" or "ahead".
        count: Number of commits.
        base_branch: The base branch name.

    Returns:
        "pull", "push", or "continue" action.
    """
    if direction == "behind":
        question = f"リモートに {count} 件の新しいコミットがあります。どうしますか？"
        options = [f"pull して続行 (git pull origin {base_branch})", "そのまま続行"]
        choice = ask_choice(question, options)
        return "pull" if "pull" in choice else "continue"
    else:
        question = f"ローカルに {count} 件の未プッシュコミットがあります。どうしますか？"
        options = [f"push して続行 (git push origin {base_branch})", "そのまま続行"]
        choice = ask_choice(question, options)
        return "push" if "push" in choice else "continue"
