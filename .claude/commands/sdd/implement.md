---
description: Start implement pipeline — plan to PR via SDD orchestrator
allowed-tools: mcp__sdd__sdd_start, mcp__sdd__sdd_resume, mcp__sdd__sdd_status
disable-model-invocation: true
argument-hint: <plan-name>
---

# SDD Implement パイプライン

<background_information>
- **ミッション**: Planファイルから完全な実装パイプラインを実行する（Preflight → Spec生成 → 実装 → 検証 → PR作成）
- **使用MCPツール**: `mcp__sdd__sdd_start` (pipeline="implement")
- **特徴**: チェックポイント方式 — 各段階で一時停止し、対話的に進行できる
</background_information>

<instructions>

## ステップ 1: パイプライン開始

`mcp__sdd__sdd_start` を呼び出す:

```
pipeline: "implement"
plan: "$ARGUMENTS"
```

`$ARGUMENTS` が空の場合は「Plan名を指定してください（例: `/sdd:implement my-feature`）」と案内して終了。

## ステップ 2: レスポンス処理

レスポンスの `status` フィールドに応じて処理する:

### `completed`
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
- `error`: エラー内容
- `step_output`: ステップの出力（あれば）
- `suggested_actions`: 推奨アクション（retry/skip/abort）

ユーザーの選択を受け取ったら `mcp__sdd__sdd_resume` で再開:
```
session_id: <レスポンスのsession_id>
action: <retry|skip|abort>
```

### `failed`
回復不能なエラー。エラー内容を報告して終了。

## ステップ 3: 繰り返し

`completed` または `failed` になるまでステップ 2 を繰り返す。

</instructions>

## 出力

簡潔に以下を報告:
- 現在のステップと進捗（`progress`）
- 質問やエラーがあればその内容
- 完了時はPR URLとブランチ名

## パイプラインの段階

参考: implement パイプラインは以下の段階で構成される:
1. **Preflight** — git状態チェック（behind/ahead検出）
2. **Setup** — Plan解決 + worktree作成
3. **A1** — Spec WHAT（要件定義）
4. **A2** — Spec HOW（設計）
5. **A3** — Spec Tasks（タスク生成）
6. **B** — Implementation（実装）
7. **B2** — Validation（検証）
8. **Steering** — Steering同期
9. **C** — Commit
10. **L4** — Scene Review（該当時）
11. **D** — Push + PR作成
