---
description: Show SDD pipeline session status
allowed-tools: mcp__sdd__sdd_status
disable-model-invocation: true
argument-hint: [session-id]
---

# SDD セッション状態確認

<background_information>
- **ミッション**: SDDパイプラインのセッション状態を確認する
- **使用MCPツール**: `mcp__sdd__sdd_status`
</background_information>

<instructions>

## 実行

`mcp__sdd__sdd_status` を呼び出す:

- `$ARGUMENTS` が指定されている場合 → `session_id: "$ARGUMENTS"` で特定セッションを照会
- `$ARGUMENTS` が空の場合 → 全アクティブセッションを一覧表示

## 表示フォーマット

### 全セッション一覧の場合

各セッションについて以下を表示:

| Session ID | Pipeline | Status | Checkpoint | Feature |
|---|---|---|---|---|

- **paused** セッションがあれば `/sdd:resume <session-id>` の案内を付記
- アクティブセッションがなければ「アクティブなセッションはありません」と報告

### 特定セッションの場合

以下を表示:
- **Session ID**
- **Pipeline**: implement / modify / modify-plan
- **Status**: running / paused / completed / failed
- **Checkpoint**: 現在のチェックポイント名
- **Feature**: フィーチャー名（あれば）
- **Branch**: ブランチ名（あれば）
- **Worktree**: worktreeパス（あれば）
- **Progress**: 完了済みステップ一覧
- **Checkpoint Data**: チェックポイント固有のデータ（質問内容、エラー等）

statusが `paused` の場合は再開方法を案内:
- interaction_required → `/sdd:resume <session-id> <回答>`
- error_occurred → `/sdd:resume <session-id> retry` (or skip/abort)

</instructions>
