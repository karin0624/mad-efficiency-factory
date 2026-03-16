
## コアタスク

MP1で生成されたmodify-planファイルをレビューし、品質・整合性を確認する。必要に応じてplanを修正し、READY/REVISEステータスを判定する。

## 入力パラメータ

promptから以下を受け取る:
- `FEATURE_NAME`: 対象spec名
- `PLAN_PATH`: レビュー対象のplanファイルパス
- `CHANGE_DESCRIPTION`: 元の変更記述
- `PROPAGATION_MAP`: MP0の伝播マップ全体
- `ALL_PLANS_SUMMARY`: 全対象specのMP1サマリ（クロスspec整合性チェック用）

## 実行手順

### 1. Planファイルの読み込み

`PLAN_PATH` のplanファイルを読み込む。

### 2. 対応するSpec成果物の読み込み

- `.kiro/specs/{FEATURE_NAME}/requirements.md`
- `.kiro/specs/{FEATURE_NAME}/design.md`（存在する場合）

### 3. Steeringコンテキストの読み込み

`.kiro/steering/` 配下の全ファイルを読み込む。

### 4. レビュー観点

以下の観点でplanをレビューする:

#### A. 内容の正確性
- 変更記述がspecの現在の仕様と整合しているか
- 影響する要件のIDが正しいか
- カスケード深度の判定が妥当か

#### B. 完全性
- 追加/変更/削除の振る舞いが漏れなく記述されているか
- スコープ外の記述が適切か
- 制約と前提が明確か

#### C. クロスspec整合性
- `PROPAGATION_MAP` と `ALL_PLANS_SUMMARY` を参照し、spec間の変更が整合しているか
- 上流specの変更が下流specのplanに正しく反映されているか
- インターフェース変更の一貫性

#### D. 実行可能性
- `/modify 実行パラメータ` のYAMLが正しく構造化されているか
- `change_description` が `make modify` で使用可能な品質か

### 5. 修正の適用

軽微な問題（typo、不正確な要件ID、不明確な記述）はplanファイルを直接修正する。
重大な問題（スコープの欠落、整合性の矛盾）はREVISEステータスで報告する。

### 6. ステータス判定

- **READY**: planが実行可能な品質。軽微な修正を適用した場合もREADY
- **REVISE**: 重大な問題があり、ユーザーフィードバックまたはMP1eによる修正が必要

## 出力形式

```
MP2_DONE status=READY|REVISE
CHANGES_START
- <適用した変更の記述>
- [cross-spec] <クロスspec整合性に関する指摘>
CHANGES_END
```

**注意事項**:
- 変更を適用した場合はplanファイルを直接Editで更新すること
- `CHANGES_START`/`CHANGES_END` ブロックには、適用した変更と指摘事項を箇条書きで記載
- クロスspec関連の指摘には `[cross-spec]` プレフィックスを付与
- 変更なしの場合も `CHANGES_START`/`CHANGES_END` ブロックは出力し、`- no changes` と記載
