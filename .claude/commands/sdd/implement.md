---
description: Start implement pipeline — SDD orchestrator
allowed-tools: mcp__sdd__sdd_start, mcp__sdd__sdd_resume, mcp__sdd__sdd_status
disable-model-invocation: true
argument-hint: [plan-name-or-description]
---

# SDD Implement パイプライン

<background_information>
- **ミッション**: 機能の実装パイプラインを実行する（Preflight → Plan作成/解決 → Worktree → Spec生成 → 実装 → 検証 → PR作成）
- **使用MCPツール**: `mcp__sdd__sdd_start` (pipeline="implement")
- **特徴**: チェックポイント方式 — 各段階で一時停止し、対話的に進行できる。Plan作成もワークフローに統合されており、既存Planがなければ自動的に作成フェーズに入る
</background_information>

<instructions>

## ステップ 1: パイプライン開始

`mcp__sdd__sdd_start` を呼び出す:

```
pipeline: "implement"
plan: "$ARGUMENTS"
```

`$ARGUMENTS` には既存のPlan名または機能の説明を指定できる。空の場合は「Plan名または機能の説明を指定してください（例: `/sdd:implement my-feature`）」と案内して終了。

## ステップ 2: レスポンス処理

レスポンスの `type` フィールドに応じて処理する:

### `pipeline_completed`
パイプライン完了。以下を報告:
- PR URL（`pr_url`）
- ブランチ名（`branch`）
- フィーチャー名（`feature`）

### `interaction_required`
ユーザーへの質問が発生。以下を表示:
- `question`: 質問内容
- `options`: 選択肢（あれば）
- `context`: 補足情報（あれば）

ユーザーの回答を受け取ったら `mcp__sdd__sdd_resume` で再開:
```
session_id: <レスポンスのsession_id>
user_input: <ユーザーの回答>
```

### `error_occurred`
エラー発生。以下を表示:
- `error_message`: エラー内容
- `step_output`: ステップの出力（あれば）
- `suggested_actions`: 推奨アクション（retry/skip/abort）

ユーザーの選択を受け取ったら `mcp__sdd__sdd_resume` で再開:
```
session_id: <レスポンスのsession_id>
action: <retry|skip|abort>
```

### `pipeline_failed`
回復不能なエラー。エラー内容を報告して終了。

## ステップ 3: 繰り返し

`pipeline_completed` または `pipeline_failed` になるまでステップ 2 を繰り返す。

</instructions>

## 出力

簡潔に以下を報告:
- 現在のステップと進捗（`progress`）
- 質問やエラーがあればその内容
- 完了時はPR URLとブランチ名

## パイプラインの段階

参考: implement パイプラインは `workflows/implement.yaml` で定義される（Plan作成フェーズを含む統合ワークフロー）
