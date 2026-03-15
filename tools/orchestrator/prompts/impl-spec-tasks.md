
## cwd強制

最初に必ず以下を実行してください:
1. `cd WORKTREE_PATH` (promptで渡されるパスに置換)
2. `git rev-parse --show-toplevel` で正しいworktreeにいることを確認

すべてのBashコマンドは WORKTREE_PATH 内で実行すること。

## 実行手順

promptで渡される `FEATURE_NAME` を使用する。

### Phase 4: spec-tasks
- Skill tool: skill="kiro:spec-tasks", args="FEATURE_NAME -y"

### Phase 4.5: タスク承認 + メタデータ記録
**Phase 4 (spec-tasks) が正常完了した直後に必ず実行すること。**
spec.jsonを直接編集して以下を設定:
  - `approvals.tasks.approved: true`

## エラー処理
- いずれかのフェーズが失敗した場合、そのフェーズで停止し詳細を報告
- 失敗フェーズ、エラー内容、再実行用のコマンドを含める

## フォールバック
Skill toolが使えない場合は .claude/commands/kiro/ の該当コマンドファイルを直接読んで手動実行

## 完了報告
以下を報告すること:
- tasks生成の完了有無
- タスク承認の完了有無
