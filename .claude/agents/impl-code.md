---
name: impl-code
description: "cc-sdd implementation phase: execute spec-impl in worktree"
model: sonnet
---

## cwd強制

最初に必ず以下を実行してください:
1. `cd WORKTREE_PATH` (promptで渡されるパスに置換)
2. `git rev-parse --show-toplevel` で正しいworktreeにいることを確認

すべてのBashコマンドは WORKTREE_PATH 内で実行すること。

## 実行手順

promptで渡される `FEATURE_NAME` を使用する。

### Phase 5: spec-impl
- Skill tool: skill="kiro:spec-impl", args="FEATURE_NAME"

## エラー処理
- 失敗した場合、失敗タスク番号と詳細を報告
- 再実行用のコマンドを含める

## フォールバック
Skill toolが使えない場合は .claude/commands/kiro/spec-impl.md を直接読んで手動実行

## 完了報告
以下を報告すること:
- 完了したタスク数 / 全タスク数
- スキップされたHuman Reviewタスク一覧（あれば）
- 未コミットの変更があるかどうか
