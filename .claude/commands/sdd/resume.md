---
description: Resume a paused SDD pipeline session
allowed-tools: mcp__sdd__sdd_resume, mcp__sdd__sdd_status
disable-model-invocation: true
argument-hint: <session-id> [user-input-or-action]
---

# SDD セッション再開

<background_information>
- **ミッション**: 一時停止中のSDDパイプラインセッションを再開する
- **使用MCPツール**: `mcp__sdd__sdd_resume`
- **特徴**: `interaction_required`（対話待ち）と `error_occurred`（エラー待ち）の両方に対応
</background_information>

<instructions>

## ステップ 1: 引数の解析

`$ARGUMENTS` を解析する:
- 最初のトークン → `session_id`
- 残り → ユーザー入力（`user_input` または `action`）

### session_id が空の場合

`mcp__sdd__sdd_status` を呼び出して全アクティブセッションを表示し、再開対象を選ばせる。

paused セッションが1つだけの場合はそれを自動選択する。

## ステップ 2: セッション状態の確認

`mcp__sdd__sdd_status` で対象セッションの状態を確認する:

- **paused でない場合**: 「このセッションは一時停止していません（status=...）」と報告して終了
- **paused の場合**: checkpoint の種類を確認して適切なパラメータを決定

## ステップ 3: resume パラメータの決定

### interaction_required チェックポイントの場合
ユーザー入力が必要。`$ARGUMENTS` に回答が含まれていればそれを使用、なければ質問内容を表示して回答を待つ。

```
session_id: <session_id>
user_input: <ユーザーの回答>
```

### error_occurred チェックポイントの場合
アクション選択が必要。`$ARGUMENTS` に action が含まれていればそれを使用、なければ選択肢を表示。

```
session_id: <session_id>
action: <retry|skip|abort>
```

## ステップ 4: 再開実行

`mcp__sdd__sdd_resume` を呼び出す。

## ステップ 5: レスポンス処理

レスポンスの `status` に応じて処理（implement/modify/modify-plan コマンドと同じロジック）:

- **completed**: 完了結果を報告
- **interaction_required**: 次の質問を表示し、回答を待って再度 `mcp__sdd__sdd_resume`
- **error_occurred**: エラーと推奨アクションを表示
- **failed**: エラー内容を報告して終了

`completed` または `failed` になるまで繰り返す。

</instructions>

## 出力

簡潔に以下を報告:
- セッションID、パイプライン種別、現在のステップ
- 質問やエラーがあればその内容
- 完了時は結果サマリー
