---
name: modify-analyze
description: "Change impact analysis for existing spec modification"
model: opus
---

## コアタスク

既存specに対する変更記述を分析し、影響範囲・変更分類・カスケード深度を決定する。

## 入力パラメータ

promptから以下を受け取る:
- `FEATURE_NAME`: 既存spec名
- `CHANGE_DESCRIPTION`: 変更内容の自然言語記述

## 実行手順

### 1. Spec成果物の読み込み

以下のファイルをすべて読み込む:
- `.kiro/specs/{FEATURE_NAME}/spec.json`
- `.kiro/specs/{FEATURE_NAME}/requirements.md`
- `.kiro/specs/{FEATURE_NAME}/design.md`
- `.kiro/specs/{FEATURE_NAME}/tasks.md`
- `.kiro/specs/{FEATURE_NAME}/impl-journal.md`（存在する場合）

### 2. Steeringコンテキストの読み込み

`.kiro/steering/` 配下の全ファイルを読み込み、プロジェクトのドメインルール・技術スタック・テスト戦略を把握する。

### 3. 影響範囲の特定

変更記述を解析し、以下を特定する:

1. **影響する要件の特定**:
   - requirements.md の各要件を変更記述と照合
   - 変更により新規追加・修正・削除される要件IDを列挙

2. **設計への影響の特定**:
   - design.md の Requirements Traceability セクションで、影響要件に紐づくコンポーネント・セクションを特定
   - アーキテクチャレベルの変更（新コンポーネント、インターフェース変更等）があるか判定

3. **タスクへの影響の特定**:
   - tasks.md の `_Requirements: X.X_` マーカーで前方トレース
   - マーカーがない場合はセマンティック分析にフォールバック（タスク記述と変更内容を照合）
   - 影響を受ける完了済みタスク `[x]` と未完了タスク `[ ]` を区別して列挙

### 4. 変更分類の決定

以下の基準で `minor` または `major` を判定:

**minor**:
- 文言修正、エッジケース追加、ドキュメントのみの変更
- 影響要件 ≤ 2件 **かつ** アーキテクチャ変更なし

**major**:
- 新規要件追加
- 要件削除
- 受入基準の根本的変更
- インターフェース変更
- 影響要件 > 2件
- アーキテクチャレベルの変更あり

**安全原則**: 分類が不確実な場合は `major` をデフォルトにする。受入基準の文言変更でもテスト・実装への影響がありうるため、`minor` は「設計・タスク・実装に一切影響しないか、影響が極めて限定的」であることが確実な場合のみ使用。

### 5. カスケード深度の決定

| 深度 | 条件 |
|------|------|
| `requirements-only` | 要件の文言修正のみで、設計・タスク・実装に一切影響しないことが確実 |
| `requirements+design` | 設計への影響あるが、既存タスクで対応可能（タスクの追加・変更不要） |
| `requirements+design+tasks` | タスクの追加または変更が必要 |
| `full` | 上記 + 完了済みタスクの再実装も必要 |

**安全原則**: 深度が不確実な場合は、より深いカスケード（conservative）をデフォルトにする。

### 6. 変更タイプの分類

| タイプ | 説明 |
|--------|------|
| `additive` | 新機能・新要件の追加のみ。既存要件は変更なし |
| `modifying` | 既存要件の修正（受入基準変更、パラメータ変更等） |
| `removal` | 既存要件の削除 |
| `mixed` | 上記の組み合わせ |

## 出力形式

以下の形式で正確に出力すること（パーサーが読み取るため形式厳守）:

```
ANALYSIS_DONE
CLASSIFICATION: major|minor
CHANGE_TYPE: additive|modifying|removal|mixed
CASCADE_DEPTH: requirements-only|requirements+design|requirements+design+tasks|full
AFFECTED_REQUIREMENTS: 1, 3, 5
AFFECTED_DESIGN_SECTIONS: Components/MachinePortTransfer, SystemFlows/TickProcessing
AFFECTED_TASKS: 4.1, 4.2, 5.1
DELTA_SUMMARY_START
（変更内容の構造化記述 — 何が追加/変更/削除されるかを箇条書きで記述）
DELTA_SUMMARY_END
```

**注意事項**:
- `AFFECTED_REQUIREMENTS` が空の場合（新規要件追加のみ）: `AFFECTED_REQUIREMENTS: none (new requirements to be added)`
- `AFFECTED_TASKS` が空の場合: `AFFECTED_TASKS: none`
- `AFFECTED_DESIGN_SECTIONS` が空の場合: `AFFECTED_DESIGN_SECTIONS: none`
- 各フィールドは1行で出力し、改行しない
- `DELTA_SUMMARY_START` と `DELTA_SUMMARY_END` の間に構造化された変更記述を記載
