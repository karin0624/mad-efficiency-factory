---
description: Send a design document to Codex CLI for independent structural review and incorporate feedback
allowed-tools: Bash, Read, Edit, Glob, Grep
argument-hint: <feature-name> [--dry-run]
---

# Codex CLIによる設計レビュー

<background_information>
- **ミッション**: Codex CLI（OpenAI）からdesign.mdに対する独立したクロスモデルレビューを取得し、構造・整合性チェックを自動実行する
- **成功基準**:
  - design.mdが構造化レビューのためにCodexに送信されていること
  - レビューが既存アーキテクチャ整合性、設計一貫性、拡張性、型安全性をカバーしていること
  - 判定が `STATUS: APPROVE|REVISE|REJECT` で機械可読に返されること
  - REVISE判定時にフィードバックがdesign.mdに反映されていること
  - spec.jsonに `codex_reviewed`, `codex_status` が記録されていること
</background_information>

<instructions>
## コアタスク
Codex CLIを使用してdesign.mdをレビューし、フィードバックを反映する。引数: **$ARGUMENTS**

## 実行ステップ

### ステップ 1: 引数の解析
- `$ARGUMENTS` をfeature名とフラグに分割
- `--dry-run` フラグを検出（存在する場合、design変更およびspec.json更新をスキップ）
- 残りの引数がfeature名

### ステップ 2: ファイルパスの解決
- `.kiro/specs/<feature-name>/design.md` の存在を確認
- `.kiro/specs/<feature-name>/requirements.md` の存在を確認
- `.kiro/specs/<feature-name>/spec.json` の存在を確認
- いずれかが見つからない場合: エラーで停止し、利用可能なspecを一覧表示

### ステップ 3: Codexの利用可能性を確認
- Bashで `which codex` を実行
- 見つからない場合、エラーで停止: "codex CLIがインストールされていません。以下でインストールしてください: npm install -g @openai/codex"

### ステップ 4: Codexレビューの実行
- レビュープロンプトを構築（下記テンプレート参照）
- プロンプトを一時ファイルに書き出す: `/tmp/codex-design-review-prompt.txt`
- 実行:
  ```bash
  codex exec --ephemeral -s read-only -C "$(pwd)" -o /tmp/codex-design-review.txt - < /tmp/codex-design-review-prompt.txt
  ```
  - タイムアウト: 300秒
- `/tmp/codex-design-review.txt` からRead toolで出力を読み取る
- **重要**: design.mdはCodexに直接読ませる — コンテキスト節約のためこの段階では読まない

### ステップ 5: レビュー結果の表示
- 以下のヘッダー付きでCodexレビューをユーザーに表示:
  - レビュー対象: `.kiro/specs/<feature-name>/design.md`
  - レビュアー: Codex CLI

### ステップ 6: STATUS判定のパース
- Codex出力の先頭行から `STATUS:` をパース
- 有効な値: `APPROVE`, `REVISE`, `REJECT`
- パースできない場合: 出力全体を表示し、手動確認を提案して停止

### ステップ 7: 判定に基づくアクション

#### APPROVE の場合
- `--dry-run` でなければ spec.json を更新:
  - `approvals.design.codex_reviewed: true`
  - `approvals.design.codex_status: "APPROVE"`
  - `updated_at` を現在時刻に更新
- 完了報告

#### REVISE の場合
- **`--dry-run` が指定された場合**: 結果を表示して終了（design変更もspec.json更新もしない）
- **ここで** Read toolを使用してdesign.mdを読む（初めて読む — 編集の適用に必要）
- Codexレビューのフィードバックを分析
- アクション可能な改善点を特定し、Edit toolでdesign.mdを更新:
  - 構造的な問題の修正
  - 要件とのトレーサビリティ改善
  - アーキテクチャ整合性の修正
- 主観的なスタイルの好みや過度に投機的な懸念はフィルタリング
- spec.json を更新:
  - `approvals.design.codex_reviewed: true`
  - `approvals.design.codex_status: "REVISE"`
  - `updated_at` を現在時刻に更新
- 変更内容の簡潔なサマリをユーザーに表示

#### REJECT の場合
- spec.json を更新（`--dry-run` でなければ）:
  - `approvals.design.codex_reviewed: true`
  - `approvals.design.codex_status: "REJECT"`
  - `updated_at` を現在時刻に更新
- エラー報告して停止: 手動介入が必要である旨を表示

## レビュープロンプトテンプレート
Codexに送信する際は以下のプロンプト構造を使用:

```
You are a senior software architect performing an automated structural review of a technical design document. Provide a deterministic, machine-readable assessment.

## Files to Review
Read and review the following files:
- Design document: .kiro/specs/{FEATURE_NAME}/design.md
- Requirements: .kiro/specs/{FEATURE_NAME}/requirements.md
- Project conventions: .kiro/steering/ (read all files in this directory)

## Review Criteria

Evaluate the design document against these dimensions:

### 1. Existing Architecture Alignment (Critical)
- Integration with existing system boundaries and layers
- Consistency with established architectural patterns
- Proper dependency direction and coupling management
- Alignment with current module organization

### 2. Design Consistency & Standards
- Adherence to project naming conventions and code standards
- Consistent error handling and logging strategies
- Uniform configuration and dependency management
- Alignment with established data modeling patterns

### 3. Extensibility & Maintainability
- Design flexibility for future requirements
- Clear separation of concerns and single responsibility
- Testability and debugging considerations
- Appropriate complexity for requirements

### 4. Type Safety & Interface Design
- Proper type definitions and interface contracts
- Avoidance of unsafe patterns
- Clear API boundaries and data structures
- Input validation and error handling coverage

### 5. Requirements Traceability
- All functional requirements from requirements.md are addressed in the design
- No design elements without corresponding requirements (gold plating)
- Non-functional requirements (performance, security) are considered

## Output Format

IMPORTANT: Your response MUST start with the following line (no prefix, no markdown):

STATUS: APPROVE|REVISE|REJECT

Followed by a blank line, then a structured Markdown review (300-500 words):

### Design Review Summary
2-3 sentences on overall quality and readiness.

### Critical Issues (if any, max 3)
For each issue:
- **Issue**: Brief title
- **Impact**: Why it matters
- **Recommendation**: Concrete fix
- **Traceability**: Requirement ID/section

### Design Strengths
1-2 positive aspects.

### Assessment Rationale
Brief explanation of the STATUS decision.

## Decision Criteria
- **APPROVE**: No critical architectural misalignment, requirements addressed, clear implementation path
- **REVISE**: Addressable issues found — structural problems, traceability gaps, or consistency issues that can be fixed with targeted edits
- **REJECT**: Fundamental conflicts, critical gaps, or architectural misalignment requiring complete redesign
```

## 重要な制約事項
- Codexは**読み取り専用サンドボックス**で動作する — ワークスペースの変更はできないが、ファイルの読み取りは可能
- セッションは**エフェメラル** — 永続的な状態はない
- シェルのエスケープ問題を避けるため、プロンプトには一時ファイルを使用する
- 実行後に一時ファイルをクリーンアップする
- フィードバックを反映する際は、designの元の構造と意図を維持する
- **コンテキスト効率**: REVISE判定時のみ、Claudeのコンテキストでdesign.mdを読む
</instructions>

## ツールガイド
- **Read**: design.mdの内容をステップ7(REVISE)でのみ読み込む（フィードバック反映用）、spec.jsonの読み書き、およびCodex出力の読み取り
- **Bash**: `codex exec` の実行、一時ファイルの書き込み、codexインストールの確認
- **Edit**: REVISEフィードバックを反映するためのdesign.mdの変更、spec.jsonの更新
- **Glob**: specディレクトリの検索
- **Grep**: フィードバック反映時に必要に応じて関連コンテキストを検索

## 出力内容
1. **レビューヘッダー**: レビュー対象のdesign、レビュアーの識別
2. **Codexレビュー**: Codexからの完全な構造化レビュー（STATUS行含む）
3. **変更内容**（REVISE + `--dry-run` でない場合）: design.mdに適用された変更のサマリ
4. **spec.json更新結果**: codex_reviewed, codex_status の値

## 安全性とフォールバック

### エラーシナリオ
- **specが見つからない場合**: 解決されたパスを表示し、利用可能なspecを一覧表示
- **Codexがインストールされていない場合**: インストール手順を表示して停止
- **Codex実行失敗**: stderrを表示し、リトライを提案
- **出力が空の場合**: ユーザーに警告し、codexの設定確認を提案
- **STATUS行がパースできない場合**: 出力全体を表示し、手動確認を提案

### クリーンアップ
- レビュー完了後（成功・失敗問わず）、作成した一時ファイルを削除:
  - `/tmp/codex-design-review-prompt.txt`
  - `/tmp/codex-design-review.txt`
