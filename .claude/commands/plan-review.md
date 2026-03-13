---
description: Send a plan file to Codex CLI for independent review and incorporate feedback
allowed-tools: Bash, Read, Edit, Glob, Grep
argument-hint: <plan-file-or-name> [--dry-run]
---

# Codex CLIによるplanレビュー

<background_information>
- **ミッション**: Codex CLI（OpenAI）からplanファイルに対する独立したセカンドオピニオンを取得し、有効なフィードバックをplanに反映する
- **成功基準**:
  - planファイルが構造化レビューのためにCodexに送信されていること
  - レビューが以下をカバーしていること: 実現可能性、網羅性、リスク、不足項目、提案
  - 有効なフィードバックがplanに反映されていること（デフォルト動作）
  - ユーザーがレビュー内容と変更点の両方を確認できること
</background_information>

<instructions>
## コアタスク
Codex CLIを使用してplanファイルをレビューし、フィードバックを反映する。引数: **$ARGUMENTS**

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
  codex exec --ephemeral -s read-only -C "$(pwd)" -o /tmp/codex-plan-review.txt - < /tmp/codex-plan-review-prompt.txt
  ```
- `/tmp/codex-plan-review.txt` から出力を読み取る
- **重要**: この段階ではplanファイルを読まない — Codexに直接読ませることでコンテキストを節約する

### ステップ 5: レビュー結果の表示
- 以下のヘッダー付きでCodexレビューをユーザーに表示:
  - レビュー対象のplan
  - レビュアー: Codex CLI

### ステップ 6: フィードバックの反映（デフォルト動作）
- **`--dry-run` が指定された場合はこのステップをスキップ** — 結果を表示して終了
- **ここで**Read toolを使用してplanファイルを読む（初めて読む — 編集の適用に必要）
- Codexレビューのフィードバックを分析
- アクション可能な改善点を特定:
  - 追加すべき不足ステップや考慮事項
  - planで対処すべきリスクや問題
  - 構造的な改善
  - 不正確な内容の修正
- Edit toolを使用してplanファイルを変更し、有効なフィードバックを反映
- 変更内容の簡潔なサマリをユーザーに表示
- すべての提案を盲目的に適用しない — 以下を判断してフィルタリング:
  - 主観的なスタイルの好み
  - planの意図に反する提案
  - 過度に投機的な懸念

## レビュープロンプトテンプレート
Codexに送信する際は以下のプロンプト構造を使用:

```
You are a senior technical reviewer. Review the implementation plan located at the following file path and provide structured, actionable feedback.

## Plan File
Read and review: {PLAN_FILE_PATH}

## Review Criteria

Evaluate across these dimensions:

### 1. Feasibility
- Can this plan be implemented as described?
- Are the technical approaches sound?
- Are there unrealistic assumptions?

### 2. Completeness
- Are all necessary steps covered?
- Are dependencies identified?
- Is the sequencing logical?

### 3. Risks and Issues
- What could go wrong?
- Are there edge cases not addressed?
- Performance, security, or maintainability concerns?

### 4. Missing Items
- What should be covered but isn't?
- Are prerequisite tasks missing?
- Are error handling and rollback strategies addressed?

### 5. Suggestions
- Specific, concrete improvements
- Alternative approaches worth considering
- Priority recommendations

## Output Format

Provide your review as structured Markdown:
- A section for each dimension above
- Concrete, actionable feedback (not vague)
- Overall assessment: APPROVE / REVISE / REJECT with brief rationale
- Keep concise but thorough (300-500 words)
```

## 重要な制約事項
- Codexは**読み取り専用サンドボックス**で動作する — ワークスペースの変更はできないが、ファイルの読み取りは可能
- セッションは**エフェメラル** — 永続的な状態はない
- シェルのエスケープ問題を避けるため、プロンプトには一時ファイルを使用する
- 実行後に一時ファイルをクリーンアップする
- デフォルトはフィードバックの反映; `--dry-run` で変更をスキップ
- フィードバックを反映する際は、planの元の構造と意図を維持する
- **コンテキスト効率**: 変更が必要な場合（ステップ6）のみ、Claudeのコンテキストでplanファイルを読む
</instructions>

## ツールガイド
- **Read**: planファイルの内容をステップ6でのみ読み込む（フィードバック反映用）、およびCodex出力の読み取り
- **Bash**: `codex exec` の実行、一時ファイルの書き込み、codexインストールの確認
- **Edit**: レビューフィードバックを反映するためのplanファイルの変更
- **Glob**: 識別子が正確に一致しない場合のplanファイル検索
- **Grep**: フィードバック反映時に必要に応じて関連コンテキストを検索

## 出力内容
1. **レビューヘッダー**: レビュー対象のplan、レビュアーの識別
2. **Codexレビュー**: Codexからの完全な構造化レビュー
3. **変更内容**（`--dry-run` でない場合）: planに適用された変更のサマリ

## 安全性とフォールバック

### エラーシナリオ
- **planが見つからない場合**: 解決されたパスを表示し、`docs/plans/` 内の利用可能なplanを一覧表示
- **Codexがインストールされていない場合**: インストール手順を表示して停止
- **Codex実行失敗**: stderrを表示し、リトライを提案
- **出力が空の場合**: ユーザーに警告し、codexの設定確認を提案
- **一時ファイルの問題**: 常に書き込み可能な `/tmp/` を使用

### クリーンアップ
- レビュー完了後（成功・失敗問わず）、作成した一時ファイルを削除（例: `/tmp/codex-plan-review-*.txt`）
</output>
