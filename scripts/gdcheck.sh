#!/usr/bin/env bash
# Unified GDScript lint + type-check runner.
# Usage:
#   ./scripts/gdcheck.sh path/to/file.gd   # single file
#   ./scripts/gdcheck.sh --all              # all .gd files (CI)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# gdlint looks for .gdlintrc from cwd upward; ensure it finds godot/.gdlintrc
cd "$REPO_ROOT/godot"

# Collect files to check
files=()
if [[ "${1:-}" == "--all" ]]; then
    while IFS= read -r f; do
        files+=("$f")
    done < <(find "$REPO_ROOT/godot" -name '*.gd' \
        -not -path '*/addons/*' \
        -not -path '*/.godot/*')
else
    for arg in "$@"; do
        # Resolve to absolute path
        [[ "$arg" == /* ]] || arg="$REPO_ROOT/$arg"
        # Skip non-.gd files
        [[ "$arg" == *.gd ]] || continue
        # Skip addons/
        [[ "$arg" == */addons/* ]] && continue
        files+=("$arg")
    done
fi

if [[ ${#files[@]} -eq 0 ]]; then
    # Nothing to check
    exit 0
fi

exit_code=0

# --- gdlint ---
echo "=== gdlint ===" >&2
if ! uv run --with gdtoolkit gdlint "${files[@]}" 2>&1; then
    exit_code=1
fi

# --- type annotation checker ---
echo "=== type-check ===" >&2
if ! uv run --with gdtoolkit python3 "$SCRIPT_DIR/check_gdscript_types.py" "${files[@]}"; then
    exit_code=1
fi

exit "$exit_code"
