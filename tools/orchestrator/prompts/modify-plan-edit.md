
## コアタスク

ユーザーフィードバックを受けて、既存のmodify-planファイルを修正する。修正後のplanはMP2による再レビューに回される。

## 入力パラメータ

promptから以下を受け取る:
- `FEATURE_NAME`: 対象spec名
- `PLAN_PATH`: 修正対象のplanファイルパス
- `FEEDBACK`: ユーザーからのフィードバック
- `REVIEW_CHANGES`: MP2のレビュー結果（CHANGES_START/END間のテキスト）
- `PROPAGATION_MAP`: MP0の伝播マップ全体

## 実行手順

### 1. 現在のPlanファイルの読み込み

`PLAN_PATH` のplanファイルを読み込む。

### 2. 対応するSpec成果物の読み込み

- `.kiro/specs/{FEATURE_NAME}/requirements.md`
- `.kiro/specs/{FEATURE_NAME}/design.md`（存在する場合）

### 3. Steeringコンテキストの読み込み

`.kiro/steering/` 配下の全ファイルを読み込む。

### 4. フィードバックの分析

ユーザーフィードバックとMP2のレビュー結果を分析し、以下を特定:
- **修正すべき箇所**: planのどのセクションが影響を受けるか
- **追加すべき内容**: フィードバックで求められている新規記述
- **削除すべき内容**: フィードバックで不要とされた記述

### 5. ガードレールチェック

修正が以下のガードレールに違反しないか確認:
- 修正によってスコープが元の変更記述の範囲を大幅に超えていないか
- 他specへの影響が新たに発生していないか（発生している場合は警告）
- `/modify 実行パラメータ` の整合性が保たれているか

### 6. Planファイルの修正

Edit toolでplanファイルを直接修正する。修正内容:
- フィードバックに基づく内容の追加・変更・削除
- `/modify 実行パラメータ` の `change_description` の更新（変更内容が変わった場合）
- 「影響の予測」セクションの更新（影響範囲が変わった場合）

## 出力形式

```
MP1E_DONE
CHANGES_START
- <適用した変更の記述>
- [guardrail] <ガードレールによる修正>
- [cross-spec-warning] <他specへの新たな影響の警告>
CHANGES_END
```

**注意事項**:
- ガードレールによる修正には `[guardrail]` プレフィックスを付与
- 他specへの新たな影響がある場合は `[cross-spec-warning]` プレフィックスで警告
- 修正後のplanファイルが整合性を保っていることを確認
- `/modify 実行パラメータ` の `change_description` は修正内容を正確に反映すること
