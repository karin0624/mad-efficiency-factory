#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(git rev-parse --show-toplevel)"

# エスケープハッチ: SKIP_TEST_GATE=1 でバイパス（インフラ障害・フレイキーテスト時）
[[ "${SKIP_TEST_GATE:-}" != "1" ]] || exit 0

# Read stdin JSON (Stop hook input)
input="$(cat)"

# godot/ ディレクトリが無ければ非Godotプロジェクト → スキップ
[[ -d "$REPO_ROOT/godot" ]] || exit 0

# 変更された .gd ファイルを検出（staged + unstaged + untracked、addons除外）
changed="$(cd "$REPO_ROOT" && {
    git diff --name-only HEAD -- '*.gd' 2>/dev/null || true
    git ls-files --others --exclude-standard -- '*.gd' 2>/dev/null || true
} | grep -v '/addons/' | grep -v '/.godot/' || true)"

# .gd ファイルに変更なし → 即座に停止許可
[[ -n "$changed" ]] || exit 0

# --- Test gate（30-60秒）---
# lintはPostToolUse hookで個別ファイルごとに実行済みのため、ここではテストのみ
echo "STOP HOOK: .gdファイルの変更を検出。テストスイートを実行します..." >&2
if ! "$REPO_ROOT/scripts/run-tests.sh" 1>&2; then
    echo "" >&2
    echo "STOP HOOK: テストが失敗しています。修正してください。" >&2
    exit 2
fi

exit 0
