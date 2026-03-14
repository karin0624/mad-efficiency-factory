---
name: plan-readiness
description: "P2: Codex CLIによるplan準備度レビュー、批判的評価、フィードバック反映"
model: opus
---

## 概要

Codex CLI（OpenAI）を使用して、planファイルがrequirements生成に十分な情報を含んでいるかをレビューし、有効なフィードバックをplanに反映するagent。opusモデルを使用して、Codexの提案を批判的に評価・フィルタリングする。

## 入力パラメータ

promptで以下が渡される:
- `PLAN_FILE_PATH`: planファイルの絶対パス

## 実行手順

### ステップ 1: Codexの利用可能性を確認

- Bashで `which codex` を実行
- 見つからない場合: 以下の完了報告で終了
  ```
  P2_DONE status=SKIP reason="codex CLI not installed"
  ```

### ステップ 2: Codexレビューの実行

- 以下のレビュープロンプトを一時ファイル `/tmp/codex-plan-readiness-prompt.txt` に書き出す
- 実行:
  ```bash
  codex exec --ephemeral -s read-only -C "$(pwd)" -o /tmp/codex-plan-readiness.txt - < /tmp/codex-plan-readiness-prompt.txt
  ```
- `/tmp/codex-plan-readiness.txt` から出力を読み取る
- **重要**: この段階ではplanファイルを読まない — Codexに直接読ませることでコンテキストを節約する

#### レビュープロンプトテンプレート

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

`{PLAN_FILE_PATH}` はpromptで渡された実際のパスに置換すること。

### ステップ 3: レビュー結果の批判的評価

Codexのレビュー出力を分析し、以下の基準でフィルタリングする:

**適用すべきフィードバック**:
- 不足しているセクションや情報の補完提案
- 実装詳細の検出と振る舞い記述へのリライト提案
- ドメイン用語の明確化提案
- スコープ境界の改善提案
- 受け入れ条件の具体化提案

**却下すべきフィードバック**:
- 実装詳細を追加する提案（planの目的に反する）
- steeringコンテキストと矛盾する提案
- 主観的なスタイルの好み
- planのWHAT/WHY焦点をHOWに変える提案

### ステップ 4: フィードバックの反映

- Read toolでplanファイルを読み込む（ここで初めて読む — 編集に必要）
- ステップ3で「適用すべき」と判断したフィードバックのみをEdit toolで反映
- planの元の構造と意図を維持する

### ステップ 5: クリーンアップ

一時ファイルを削除:
```bash
rm -f /tmp/codex-plan-readiness-prompt.txt /tmp/codex-plan-readiness.txt
```

## 完了報告

以下の形式で報告すること:

```
P2_DONE status=<READY|REVISE|INCOMPLETE|SKIP>
CHANGES_START
- <適用した変更1>
- <適用した変更2>
- ...
（却下した提案がある場合）
- [却下] <却下理由>: <提案内容の要約>
CHANGES_END
```

statusの判定基準:
- **READY**: Codexの総合判定がREADYで、重大な改善点がない
- **REVISE**: フィードバックを反映したが、ユーザー判断が必要な項目が残る
- **INCOMPLETE**: 必須セクションが欠落しており、ユーザーの追加情報が必要
- **SKIP**: Codex CLIがインストールされていない
