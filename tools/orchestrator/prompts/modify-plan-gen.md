
## コアタスク

指定されたspecに対する変更のmodify-planを生成する。変更記述と伝播マップから、specレベルの具体的な変更計画を作成し、planファイルとして出力する。

## 入力パラメータ

promptから以下を受け取る:
- `FEATURE_NAME`: 対象spec名
- `CHANGE_DESCRIPTION`: 元の変更記述
- `PROPAGATION_ENTRY`: 伝播マップのうち、このspecに関するエントリ
- `OUTPUT_PATH`: planファイルの出力先パス
- `ALL_TARGET_SPECS`: 全対象specリスト（クロスspec参照用）

## 実行手順

### 1. Spec成果物の読み込み

以下のファイルをすべて読み込む:
- `.kiro/specs/{FEATURE_NAME}/spec.json`
- `.kiro/specs/{FEATURE_NAME}/requirements.md`
- `.kiro/specs/{FEATURE_NAME}/design.md`（存在する場合）
- `.kiro/specs/{FEATURE_NAME}/tasks.md`（存在する場合）

### 2. Steeringコンテキストの読み込み

`.kiro/steering/` 配下の全ファイルを読み込み、ドメインルール・技術スタック・制約を把握する。

### 3. 変更内容の具体化

`PROPAGATION_ENTRY` の `change` フィールドと元の `CHANGE_DESCRIPTION` から、このspec固有の具体的な変更内容を以下の粒度で記述:
- **追加する振る舞い**: 新たに追加される要件・受入基準
- **変更する振る舞い**: 既存の要件・受入基準への修正
- **削除する振る舞い**: 不要になる要件・受入基準

### 4. 影響の予測

- **影響する要件**: 変更の影響を受ける既存要件のID
- **変更の規模感**: `minor` / `major`（modify-analyze.md と同じ基準）
- **カスケード深度**: `requirements-only` / `requirements+design` / `requirements+design+tasks` / `full`

### 5. Planファイルの書き出し

`OUTPUT_PATH` に以下のテンプレートでplanファイルを書き出す:

```markdown
# Modify Plan: <Feature Name> -- <Change Title>

## 対象Spec
- **Feature**: <feature-name>
- **現在のPhase**: <spec.jsonのphase>

## 現在の仕様サマリ
### 要件の概要
- Req 1: <1行要約>
### 設計のポイント
- <振る舞いレベルの設計概要>

## 変更の目的
- **動機**: ...
- **期待される効果**: ...

## 変更内容
### 追加する振る舞い
### 変更する振る舞い
### 削除する振る舞い

## 影響の予測
- **影響する要件（予測）**: Req X, Y
- **変更の規模感**: minor | major
- **カスケード深度（予測）**: requirements-only | requirements+design | requirements+design+tasks | full

## 関連する変更（他spec）
## 制約と前提
## スコープ外

## /modify 実行パラメータ
  ```yaml
  feature_name: <feature-name>
  change_description: |
    <精製された変更記述>
  ```
```

### 6. 出力マーカー

planファイル書き出し完了後、以下を標準出力する:

```
MP1_DONE
SUMMARY_START
- Feature: <feature-name>
- Added behaviors: <追加する振る舞い数>
- Modified behaviors: <変更する振る舞い数>
- Predicted scale: minor|major
SUMMARY_END
GAPS: <不足情報の説明 or "none">
```

**注意事項**:
- planファイルはMarkdownとして正しく構造化すること
- `/modify 実行パラメータ` のYAMLブロックは、`make modify` でそのまま使用可能な形式にすること
- `GAPS` にはplanの品質に影響する不足情報があれば記載（ない場合は `none`）
- `ALL_TARGET_SPECS` を参照して「関連する変更（他spec）」セクションを充実させること
