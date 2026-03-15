#!/usr/bin/env python3
"""GDScript type annotation checker using gdtoolkit's AST parser.

Checks that function arguments, return types, and class variables have
explicit type annotations. Local variables with := inference are OK.

Exit codes:
  0 - no errors
  1 - type annotation errors found
  2 - parse error or usage error
"""
from __future__ import annotations

import sys
from pathlib import Path

from gdtoolkit.parser import parser as gdparser
from lark import Token, Tree


def _first_token_line(tree: Tree) -> int:
    """Get the line number from the first Token in a tree."""
    for node in tree.iter_subtrees():
        for child in node.children:
            if isinstance(child, Token) and child.line is not None:
                return int(child.line)
    return 0


def check_file(filepath: Path) -> list[str]:
    """Check a single .gd file and return a list of error messages."""
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = gdparser.parse(source)
    except Exception as exc:
        return [f"{filepath}:0: parse error: {exc}"]

    errors: list[str] = []

    for node in tree.iter_subtrees():
        # --- Function arguments without type ---
        if node.data == "func_arg_regular":
            name = str(node.children[0])
            line = int(node.children[0].line) if isinstance(node.children[0], Token) else 0
            errors.append(f"{filepath}:{line}: argument '{name}' has no type annotation")

        # --- Function header: check return type ---
        if node.data == "func_header":
            func_name = str(node.children[0])
            line = int(node.children[0].line) if isinstance(node.children[0], Token) else 0
            # func_header children: NAME, func_args, [return_type]
            # If there are only 2 children (name + args), no return type
            has_return_type = len(node.children) > 2
            if not has_return_type:
                errors.append(f"{filepath}:{line}: function '{func_name}' has no return type annotation")

        # --- Class variables without type annotation ---
        if node.data == "class_var_assigned":
            name = str(node.children[0])
            line = int(node.children[0].line) if isinstance(node.children[0], Token) else 0
            errors.append(f"{filepath}:{line}: class variable '{name}' has no type annotation (use : Type or := )")

        # --- Local variables: warn only (don't block) ---
        if node.data == "func_var_assigned":
            name = str(node.children[0])
            line = int(node.children[0].line) if isinstance(node.children[0], Token) else 0
            print(f"  warning: {filepath}:{line}: local variable '{name}' has no type annotation", file=sys.stderr)

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file.gd> [file2.gd ...]", file=sys.stderr)
        return 2

    all_errors: list[str] = []
    for arg in sys.argv[1:]:
        filepath = Path(arg)
        if not filepath.exists():
            print(f"  warning: {filepath} does not exist, skipping", file=sys.stderr)
            continue
        all_errors.extend(check_file(filepath))

    for err in all_errors:
        print(err, file=sys.stderr)

    if all_errors:
        print(f"\n{len(all_errors)} type annotation error(s) found.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
