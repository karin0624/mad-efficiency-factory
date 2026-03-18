---
description: Start modify-plan pipeline — investigate change impact and generate plans
allowed-tools: mcp__sdd__sdd_start, mcp__sdd__sdd_resume, mcp__sdd__sdd_status
disable-model-invocation: true
argument-hint: <change-description>
---

# SDD Modify-Plan パイプライン

<background_information>
- **ミッション**: 変更の影響を調査し、対象Specごとの修正プランを生成する（調査 → Plan生成 → レビュー → 確定）
- **使用MCPツール**: `mcp__sdd__sdd_start` (pipeline="modify-plan")
- **特徴**: 複数Specへの横断的な変更を計画し、`make modify plan=<slug>` で一括実行できるプランを生成する
</background_information>

<instructions>

## ステップ 1: パイプライン開始

`mcp__sdd__sdd_start` を呼び出す:

```
pipeline: "modify-plan"
change: "$ARGUMENTS"
```

`$ARGUMENTS` が空の場合、パイプラインが対話的に変更内容を質問するのでそのまま開始して良い。

## ステップ 2: レスポンス処理

レスポンスの `status` フィールドに応じて処理する:

### `completed`
プラン生成完了。以下を報告:
- 出力ディレクトリ（`output_dir`）
- 対象Specリスト（`specs`）
- 次のステップ: `make modify plan=<slug>` または `/sdd:modify` の案内

### `interaction_required`
ユーザーへの質問が発生。典型的なチェックポイント:

- **change_description_needed**: 変更内容の入力を求めている
- **mp0_confirm_specs**: 対象Specリストの確認（「はい、進める」/「キャンセル」/自由入力でフィードバック）
- **output_dir_conflict**: 出力ディレクトリの上書き確認
- **mp2_review_decision**: プランのAccept/Feedback判定

質問内容・選択肢を表示し、回答を `mcp__sdd__sdd_resume` で送信:
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

## ステップ 3: 繰り返し

`completed` または `failed` になるまでステップ 2 を繰り返す。

</instructions>

## 出力

簡潔に以下を報告:
- 現在のステップと進捗
- 質問やエラーがあればその内容
- 完了時は出力ディレクトリ、対象Specリスト、次のステップ

## パイプラインの段階

参考: modify-plan パイプラインは以下の段階で構成される:
1. **Start** — 変更内容の確認
2. **MP0** — 影響調査（対象Spec特定、伝播マップ生成）
3. **Confirm specs** — ユーザーによる対象Spec確認
4. **Output dir** — 出力ディレクトリ解決
5. **MP1 x N** — Plan生成（並列）
6. **MP2 x N** — Planレビュー（並列）
7. **Review** — ユーザーによるAccept/Feedback判定
8. **Write index** — `_index.md` 生成
