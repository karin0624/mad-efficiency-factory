---
description: Start modify pipeline — apply delta changes to existing spec
allowed-tools: mcp__sdd__sdd_start, mcp__sdd__sdd_resume, mcp__sdd__sdd_status
disable-model-invocation: true
argument-hint: <change-description>
---

# SDD Modify パイプライン

<background_information>
- **ミッション**: 既存Specに対して差分変更を適用する（影響分析 → ADR判定 → Spec更新 → 実装 → 検証 → PR）
- **使用MCPツール**: `mcp__sdd__sdd_start` (pipeline="modify")
- **特徴**: 変更影響分析とカスケード更新を自動化する
</background_information>

<instructions>

## ステップ 1: 引数の解析

`$ARGUMENTS` 全体を `change`（変更内容の説明）として扱う。

例: `/sdd:modify ベルトの速度を2倍にする`
→ change=`ベルトの速度を2倍にする`

`$ARGUMENTS` が空の場合は使い方を案内して終了:
「使い方: `/sdd:modify <変更内容>`」

## ステップ 2: パイプライン開始

`mcp__sdd__sdd_start` を呼び出す:

```
pipeline: "modify"
change: "$ARGUMENTS"
```

## ステップ 3: レスポンス処理

レスポンスの `type` フィールドに応じて処理する:

### `pipeline_completed`
パイプライン完了。以下を報告:
- PR URL
- ブランチ名
- 変更サマリー

### `interaction_required`
ユーザーへの質問が発生。質問内容・選択肢を表示し、回答を `mcp__sdd__sdd_resume` で送信:
```
session_id: <session_id>
user_input: <ユーザーの回答>
```

### `error_occurred`
エラー内容と推奨アクションを表示。ユーザーの選択を `mcp__sdd__sdd_resume` で送信:
```
session_id: <session_id>
action: <retry|skip|abort>
```

### `pipeline_failed`
エラー内容を報告して終了。

## ステップ 4: 繰り返し

`pipeline_completed` または `pipeline_failed` になるまでステップ 3 を繰り返す。

</instructions>

## 出力

簡潔に以下を報告:
- 現在のステップと進捗
- 質問やエラーがあればその内容
- 完了時はPR URLと変更サマリー

## パイプラインの段階

参考: modify パイプラインは `workflows/modify.yaml` で定義される
