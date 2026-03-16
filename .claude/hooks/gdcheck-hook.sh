#!/usr/bin/env bash
# PostToolUse hook: runs gdcheck on .gd files after Write/Edit.
# Reads tool_input JSON from stdin, extracts file_path, runs gdcheck.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(git rev-parse --show-toplevel)"

# DEBUG: hook発火確認用（検証後に削除）
echo "[GDCHECK HOOK] fired at $(date '+%H:%M:%S') | cwd=$(pwd) | REPO_ROOT=$REPO_ROOT" >> /tmp/hook-debug.log

# Read JSON from stdin
input="$(cat)"

# Extract file_path from tool_input
file_path="$(echo "$input" | python3 -c "import sys, json; d = json.load(sys.stdin); print(d.get('tool_input', {}).get('file_path', ''))" 2>/dev/null || true)"

# No file_path → exit silently
[[ -n "$file_path" ]] || exit 0

# Only .gd files
[[ "$file_path" == *.gd ]] || exit 0

# Skip addons/
[[ "$file_path" != */addons/* ]] || exit 0

# Run gdcheck.sh — errors go to stderr for Claude to see
exec "$REPO_ROOT/scripts/gdcheck.sh" "$file_path"
