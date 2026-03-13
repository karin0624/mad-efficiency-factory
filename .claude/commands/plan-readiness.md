---
description: Validate plan readiness for requirements generation via Codex CLI
allowed-tools: Bash, Read, Edit, Glob, Grep
argument-hint: <plan-file-or-name> [--dry-run]
---

# Codex CLIによるplan準備度レビュー

<background_information>
- **ミッション**: Codex CLI（OpenAI）を使用して、planファイルがrequirements生成に十分な情報を含んでいるかをレビューし、有効なフィードバックをplanに反映する
- **成功基準**:
  - planがrequirements最適化された構造を持っていること（WHAT/WHYに集中、HOWを排除）
  - レビューが以下をカバーしていること: 要件適合性、情報網羅性、ドメイン明確性、スコープ妥当性、アンチパターン検出
  - 有効なフィードバックがplanに反映されていること（デフォルト動作）
  - 実装詳細の混入がフラグされ、振る舞い記述へのリライト案が提示されていること
</background_information>

<instructions>
## コアタスク
Codex CLIを使用してplanファイルのrequirements準備度をレビューし、フィードバックを反映する。引数: **$ARGUMENTS**

## 実行ステップ

### ステップ 1: 引数の解析
- `$ARGUMENTS` をplan識別子とフラグに分割
- `--dry-run` フラグを検出（存在する場合、plan変更ステップをスキップ）
- 残りの引数がplanファイル識別子

### ステップ 2: planファイルパスの解決
- 識別子が `/` を含むか `.md` で終わる場合: そのまま使用（ワークスペースルートからの相対パス）
- それ以外: `docs/plans/<identifier>.md` に解決
- ファイルが見つからない場合: Glob `docs/plans/*<identifier>*` で検索
- それでも見つからない場合: `docs/plans/` 内の利用可能なplanを一覧表示して停止

### ステップ 3: Codexの利用可能性を確認
- Bashで `which codex` を実行
- 見つからない場合、エラーで停止: "codex CLIがインストールされていません。以下でインストールしてください: npm install -g @openai/codex"

### ステップ 4: Codexレビューの実行
- **解決済みファイルパス**（ファイル内容ではない）を使用してレビュープロンプトを構築 — 下記のレビュープロンプトセクションを参照
- プロンプトを一時ファイルに書き出す
- 実行:
  ```bash
  codex exec --ephemeral -s read-only -C "$(pwd)" -o /tmp/codex-plan-readiness.txt - < /tmp/codex-plan-readiness-prompt.txt
  ```
- `/tmp/codex-plan-readiness.txt` から出力を読み取る
- **重要**: この段階ではplanファイルを読まない — Codexに直接読ませることでコンテキストを節約する

### ステップ 5: レビュー結果の表示
- 以下のヘッダー付きでCodexレビューをユーザーに表示:
  - レビュー対象のplan
  - レビュアー: Codex CLI (Requirements Readiness)

### ステップ 6: フィードバックの反映（デフォルト動作）
- **`--dry-run` が指定された場合はこのステップをスキップ** — 結果を表示して終了
- **ここで**Read toolを使用してplanファイルを読む（初めて読む — 編集の適用に必要）
- Codexレビューのフィードバックを分析
- アクション可能な改善点を特定:
  - 不足しているセクションや情報の補完
  - 実装詳細のフラグ → 振る舞い記述へのリライト
  - ドメイン用語の明確化
  - スコープ境界の改善
  - 受け入れ条件の具体化
- Edit toolを使用してplanファイルを変更し、有効なフィードバックを反映
- 変更内容の簡潔なサマリをユーザーに表示
- すべての提案を盲目的に適用しない — 以下を判断してフィルタリング:
  - 実装詳細を追加する提案（planの目的に反する）
  - 主観的なスタイルの好み
  - steeringコンテキストと矛盾する提案

## レビュープロンプトテンプレート
Codexに送信する際は以下のプロンプト構造を使用:

```
You are a senior requirements analyst. Review the plan located at the following file path and evaluate its readiness for automated EARS-format requirements generation. This plan will be consumed by a spec-requirements generator that produces testable, structured requirements — NOT directly by developers.

The plan should focus on WHAT and WHY (requirements-level information), not HOW (implementation details). Implementation decisions are made in a later design phase.

## Plan File
Read and review: {PLAN_FILE_PATH}

## Review Criteria

Evaluate across these dimensions:

### 1. Requirements Readiness (要件適合性)
- Does the plan focus on WHAT/WHY (requirements-level), not HOW (implementation)?
- Are there implementation details that should be removed? (class names, data structures, architecture patterns, system names)
- Can each scope item be directly translated into EARS-format acceptance criteria?
- Are domain-specific parameters (sizes, rates, quantities) specified where needed?

### 2. Information Completeness (情報網羅性)
- Does the plan clearly state: purpose, target user, provided value, problem being solved?
- Are functional scope items described as behaviors (verb + object)?
- Are constraints and assumptions documented (business/domain constraints, not technical)?
- Are dependencies on other features/systems identified?
- Are testability hints provided (what is auto-testable vs. needs human review)?
- Are acceptance overview conditions defined?
- Is out-of-scope explicitly stated?

### 3. Domain Clarity (ドメイン明確性)
- Are domain terms defined with clear meanings?
- Can an EARS generator select appropriate subjects for "shall" statements from the terminology?
- Are user roles clearly identified?
- Is the problem domain well enough described that a non-expert could write requirements?

### 4. Scope Appropriateness (スコープ妥当性)
- Is the feature appropriately sized for a single specification (not too broad, not too narrow)?
- Are feature boundaries clear (no overlapping responsibilities with other features)?
- Are acceptance conditions specific enough to be testable?

### 5. Anti-Pattern Detection (アンチパターン検出)
- Flag any: class/component/system names, data structure definitions, architecture patterns, type definitions
- Flag any: technology-specific terms that constrain design phase choices (e.g., specific frameworks, patterns, libraries)
- Flag any: vague scope items that cannot be converted to testable requirements
- For each flagged item: provide the offending text and a suggested behavior-focused rewrite

## Output Format

Provide your review as structured Markdown:
- A section for each dimension above
- Concrete, actionable feedback (not vague)
- For each flagged anti-pattern: the offending text and a suggested rewrite
- Overall assessment: READY / REVISE / INCOMPLETE with brief rationale
- Keep concise but thorough (400-600 words)
```

## 重要な制約事項
- Codexは**読み取り専用サンドボックス**で動作する — ワークスペースの変更はできないが、ファイルの読み取りは可能
- セッションは**エフェメラル** — 永続的な状態はない
- シェルのエスケープ問題を避けるため、プロンプトには一時ファイルを使用する
- 実行後に一時ファイルをクリーンアップする
- デフォルトはフィードバックの反映; `--dry-run` で変更をスキップ
- フィードバックを反映する際は、planの元の構造と意図を維持する
- **コンテキスト効率**: 変更が必要な場合（ステップ6）のみ、Claudeのコンテキストでplanファイルを読む
- **plan-reviewとの違い**: `plan-review` は実装の技術的実現可能性をレビューする汎用ツール。本スキルはrequirements生成への準備度に特化している。用途に応じて使い分ける
</instructions>

## ツールガイド
- **Read**: planファイルの内容をステップ6でのみ読み込む（フィードバック反映用）、およびCodex出力の読み取り
- **Bash**: `codex exec` の実行、一時ファイルの書き込み、codexインストールの確認
- **Edit**: レビューフィードバックを反映するためのplanファイルの変更
- **Glob**: 識別子が正確に一致しない場合のplanファイル検索
- **Grep**: フィードバック反映時に必要に応じて関連コンテキストを検索

## 出力内容
1. **レビューヘッダー**: レビュー対象のplan、レビュアーの識別（Codex CLI — Requirements Readiness）
2. **Codexレビュー**: Codexからの完全な構造化レビュー（5基準 + 総合判定）
3. **変更内容**（`--dry-run` でない場合）: planに適用された変更のサマリ
4. **次のステップ**:
   - READY: `/implement <plan-name>` でパイプライン開始を提案
   - REVISE: 具体的な改善ポイントと再レビューを提案
   - INCOMPLETE: 不足セクションの追加を案内

## 安全策とフォールバック

### エラーシナリオ
- **planが見つからない場合**: 解決されたパスを表示し、`docs/plans/` 内の利用可能なplanを一覧表示
- **Codexがインストールされていない場合**: インストール手順を表示して停止
- **Codex実行失敗**: stderrを表示し、リトライを提案
- **出力が空の場合**: ユーザーに警告し、codexの設定確認を提案
- **一時ファイルの問題**: 常に書き込み可能な `/tmp/` を使用

### クリーンアップ
- レビュー完了後（成功・失敗問わず）、作成した一時ファイルを削除（例: `/tmp/codex-plan-readiness-*.txt`）
