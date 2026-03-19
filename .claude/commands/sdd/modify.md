---
description: Start modify pipeline — apply delta changes to existing spec
allowed-tools: mcp__sdd__sdd_start, mcp__sdd__sdd_resume, mcp__sdd__sdd_status
disable-model-invocation: true
argument-hint: <feature-name> <change-description>
---

# SDD Modify パイプライン

<background_information>
- **ミッション**: 既存Specに対して差分変更を適用する（影響分析 → ADR判定 → Spec更新 → 実装 → 検証 → PR）
- **使用MCPツール**: `mcp__sdd__sdd_start` (pipeline="modify")
- **特徴**: 変更影響分析とカスケード更新を自動化する
</background_information>

<instructions>

## ステップ 1: 引数の解析

`$ARGUMENTS` を解析する:
- 最初のトークン → `feature`（フィーチャー名）
- 残り → `change`（変更内容の説明）

例: `/sdd:modify belt-system ベルトの速度を2倍にする`
→ feature=`belt-system`, change=`ベルトの速度を2倍にする`

`$ARGUMENTS` が空または feature のみの場合は使い方を案内して終了:
「使い方: `/sdd:modify <feature-name> <変更内容>`」

## ステップ 2: パイプライン開始

`mcp__sdd__sdd_start` を呼び出す:

```
pipeline: "modify"
feature: <feature>
change: <change>
```

modify-planが存在する場合は `modify_plan` パラメータも指定可能。

## ステップ 3: レスポンス処理

レスポンスの `status` フィールドに応じて処理する:

### `completed`
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

### `failed`
エラー内容を報告して終了。

## ステップ 4: 繰り返し

`completed` または `failed` になるまでステップ 3 を繰り返す。

</instructions>

## 出力

簡潔に以下を報告:
- 現在のステップと進捗
- 質問やエラーがあればその内容
- 完了時はPR URLと変更サマリー

## パイプラインの段階

参考: modify パイプラインは以下の段階で構成される:
1. **Preflight** — git状態チェック
2. **Feature resolve** — 対象Spec特定
3. **M1** — 変更影響分析（cascade depth, classification, ADR判定）
4. **Worktree** — worktree作成
5. **ADR Gate** — ADR必要時は作成
6. **M2** — カスケード更新（requirements → design → tasks）
7. **M2R** — Cascade Review Gate（カスケード更新レビュー）
8. **M3** — デルタタスク生成
9. **B** — Implementation
10. **B2** — Validation
11. **C** — Commit
12. **L4** — Scene Review（該当時）
13. **D** — Push + PR
