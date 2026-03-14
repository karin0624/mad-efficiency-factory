---
description: Reconcile impl-journal entries into design.md
allowed-tools: Read, Write, Edit, Glob, Grep
argument-hint: <feature-name>
---

# 設計リコンサイル

<background_information>
- **ミッション**: `spec-impl` 実行中に記録された設計ジャーナル（impl-journal.md）を読み込み、design.md を更新する
- **成功基準**:
  - ジャーナルの全エントリが design.md の該当セクションに反映されている
  - Implementation Changelog に変更履歴が追記されている
  - 処理済みエントリがジャーナルからクリアされている
  - design.md が実装の実態と整合している
</background_information>

<instructions>
## コアタスク
`.kiro/specs/$1/impl-journal.md` のエントリを design.md に反映し、設計書を実装の実態に合わせる。

## 実行ステップ

### ステップ 1: コンテキストの読み込み

以下を読み込む:
- `.kiro/specs/$1/impl-journal.md` — ジャーナルエントリ
- `.kiro/specs/$1/design.md` — 現在の設計書
- `.kiro/specs/$1/spec.json` — メタデータ（言語設定等）

**バリデーション**:
- impl-journal.md が存在しない、または空の場合: 「ジャーナルエントリなし — リコンサイル不要」と報告して終了
- design.md が存在しない場合: エラーで停止

### ステップ 2: ジャーナルエントリの解析

impl-journal.md から各エントリを解析する:
- タスク番号とカテゴリ（`## Task X.Y — [CATEGORY]`）
- 設計の記述（`Design says`）
- 実際の実装（`Actually implemented`）
- 乖離の理由（`Reason`）

### ステップ 3: design.md のセクションマッピング

各エントリのカテゴリに基づき、design.md の更新対象セクションを特定する:

| カテゴリ | 主な更新対象セクション |
|---------|---------------------|
| `[INTERFACE]` | Components and Interfaces（メソッドシグネチャ・API定義） |
| `[ARCHITECTURE]` | Architecture（パターン・構成・フロー） |
| `[CONSTRAINT]` | Architecture / Implementation Notes（制約・前提条件） |
| `[DATA_MODEL]` | Data Models（構造・定数・設定値） |

複数セクションにまたがる場合は、最も関連性の高いセクションを優先的に更新する。

### ステップ 4: design.md の更新

確認なしで即座に以下を実行:

1. **該当セクションの更新**: 各エントリの「実際の実装」に基づき、design.md の該当箇所を実態に合わせて書き換える
   - 設計の意図・構造を尊重しつつ、実装と一致するよう修正
   - 新規コンポーネントやインターフェースが追加された場合は適切なセクションに追記
   - 不要になった記述は削除（コメントアウトではなく完全削除）

2. **Implementation Changelog への追記**: `## Implementation Changelog` セクションのテーブルにエントリを追加
   - Date: ジャーナルの日付
   - Category: `[INTERFACE]` / `[ARCHITECTURE]` / `[CONSTRAINT]` / `[DATA_MODEL]`
   - Change: 変更内容の簡潔な説明
   - Reason: 乖離の理由
   - Implementation Changelog セクションが存在しない場合は design.md 末尾に作成

### ステップ 5: ジャーナルのクリア

処理完了後、impl-journal.md の内容をヘッダーのみにリセットする:

```markdown
# Implementation Journal — $1
_Design deviations captured during implementation. Run `/kiro:design-reconcile $1` to reconcile._
```

これにより、次回の `spec-impl` 実行時に新しいエントリのみが記録される。

## 重要な制約
- **自動適用**: ユーザー承認を求めず、即座に design.md を更新する
- **理由の保存**: ジャーナルに記録された「理由」を Implementation Changelog に必ず含める（Bアプローチの最大の利点）
- **設計意図の尊重**: 機械的な置換ではなく、設計書としての可読性・一貫性を維持する更新を行う
- **べき等性**: 同じジャーナルエントリを2回処理しても結果が同じになること（クリア処理で担保）
</instructions>

## ツールガイダンス

- **Read**: ジャーナル・設計書・spec.json の読み込み
- **Edit**: design.md の部分更新（該当セクションのみ変更）
- **Write**: impl-journal.md のリセット
- **Grep**: design.md 内の該当セクション検索
- **Glob**: ファイルの存在確認

## 出力の説明

spec.json で指定された言語で以下を報告:

1. **処理エントリ数**: ジャーナルから処理したエントリの件数
2. **更新内容**: 各エントリについて — カテゴリ、変更箇所（design.md のセクション名）、変更の要約
3. **Implementation Changelog**: 追記された変更履歴の一覧
4. **ステータス**: 「リコンサイル完了 — design.md 更新済み、ジャーナルクリア済み」

**フォーマット**: 簡潔（200語以下）

## 安全対策とフォールバック

### エラーシナリオ
- **ジャーナルが空の場合**: 「ジャーナルエントリなし」と報告して正常終了
- **design.md が不足している場合**: エラーで停止し、`/kiro:spec-design` の実行を推奨
- **パース失敗**: ジャーナルエントリのフォーマットが不正な場合、該当エントリをスキップしてログ出力
