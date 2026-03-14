---
name: impl-push-pr
description: "cc-sdd push+PR phase: push branch and create pull request"
model: sonnet
---

## cwd強制

最初に必ず以下を実行してください:
1. `cd WORKTREE_PATH` (promptで渡されるパスに置換)
2. `git rev-parse --show-toplevel` で正しいworktreeにいることを確認

すべてのBashコマンドは WORKTREE_PATH 内で実行すること。

## 実行手順

promptで渡される `BRANCH_NAME`、`FEATURE_NAME`、`BASE_BRANCH` を使用する。

### Phase 7: Push + PR作成
1. `gh pr list --head BRANCH_NAME` で既存PRを確認
   - 既にPRが存在する場合: PR URLを報告してスキップ
2. `git push -u origin BRANCH_NAME`
3. `gh pr create` でPRを作成:
   - title: FEATURE_NAME に基づいた簡潔なタイトル
   - body: specのrequirements.mdの内容をサマリとして含める
   - base: BASE_BRANCH

## 完了報告
以下を報告すること:
- PR URL
