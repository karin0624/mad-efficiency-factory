---
description: Create a requirements-optimized plan file for the cc-sdd pipeline
disable-model-invocation: true
allowed-tools: Bash, Read, Glob, Agent, AskUserQuestion
argument-hint: <plan-name>
---

# Plan作成: thinオーケストレータ

<instructions>
## コアタスク
ユーザーの機能説明（$ARGUMENTS + 会話コンテキスト）から、requirements最適化されたplanファイルを `docs/plans/` に生成する。重い処理はsubagentに委譲し、メインコンテキストにはサマリのみ残す。

## 実行ステップ

### ステップ 0: 引数の解析

- `$ARGUMENTS` の最初のトークンをplan名として抽出
- 残りのトークンをユーザーの機能説明テキスト（`USER_DESCRIPTION`）として結合
- 説明テキストが空の場合、会話コンテキストから機能説明を取得する

### ステップ 1: 出力パスの解決

- 出力先: `docs/plans/<plan-name>.md`
- `docs/plans/` ディレクトリが存在しない場合: Bashで作成する
- 絶対パスに変換: `PLAN_FILE_PATH="$(pwd)/docs/plans/<plan-name>.md"`

### ステップ 2: 上書き確認

- 同名のファイルが既に存在する場合: AskUserQuestion toolで上書きするか別名にするか確認する
  - question: "docs/plans/<plan-name>.md は既に存在します。どうしますか？"
  - options: "上書きする" / "別名を指定する"
  - 「別名を指定する」の場合: AskUserQuestion toolで新しいplan名を入力させ、ステップ1に戻る
- 存在しない場合: そのまま続行

### ステップ 2.5: P0 — 入力充足度判定

`USER_DESCRIPTION` の充足度を判定し、不足があればヒアリングで補完する。

**判定基準** — 以下をすべて含む場合は「充足」:
- 実現したい機能の目的が明確
- 主要なユースケースが1つ以上記述されている
- スコープの手がかりがある（何を含み、何を含まないか）

**充足の場合**: そのままステップ 3（P1）へ進む。

**不足の場合**: AskUserQuestion tool で焦点を絞った質問を提示する。
- 不足している情報に直接対応する質問のみ（汎用的な質問リストではない）
- 最大 3〜5 問に制限する
- 質問例:
  - 目的が不明確な場合: 「この機能で解決したい課題は何ですか？」
  - ユースケースが不足: 「主要なユーザーシナリオを1つ教えてください」
  - スコープが不明: 「この機能に含めないもの（スコープ外）はありますか？」
- ユーザーの回答を `USER_DESCRIPTION` に統合してステップ 3 へ

**既存の GAPS メカニズムとの棲み分け**:
- P0: 生成**前**の入力品質向上（入力が曖昧すぎて生成しても無駄になるケースを防ぐ）
- P1 GAPS: 生成**後**の不足情報報告（生成はできたが補足情報があれば改善できるケース）

**注意**: ヒアリングは Plan コマンドに限定する。implement/modify パイプライン内にはヒアリングを組み込まない。

### ステップ 3: Agent P1 — plan生成

```
Agent(
  description: "plan-gen <plan-name>",
  model: "opus",
  prompt: """
  .claude/agents/plan-gen.md をRead toolで読み込み、その指示に従ってください。

  ## パラメータ
  - PLAN_FILE_PATH: {PLAN_FILE_PATH}
  - USER_DESCRIPTION: {USER_DESCRIPTION}

  ## 完了報告形式
  P1_DONE
  SUMMARY_START
  ...
  SUMMARY_END
  GAPS: ...
  """
)
```

### ステップ 4: P1サマリの表示

Agent P1の返却結果から `SUMMARY_START` / `SUMMARY_END` 間のサマリと `GAPS:` 行を抽出してユーザーに表示する。

表示形式:
```
## Plan生成完了: <plan-name>

<サマリ内容>

**不足情報**: <GAPS内容>
**ファイル**: docs/plans/<plan-name>.md
```

### ステップ 5: Agent P2 — plan-readiness

```
Agent(
  description: "plan-readiness <plan-name>",
  model: "opus",
  prompt: """
  .claude/agents/plan-readiness.md をRead toolで読み込み、その指示に従ってください。

  ## パラメータ
  - PLAN_FILE_PATH: {PLAN_FILE_PATH}

  ## 完了報告形式
  P2_DONE status=<READY|REVISE|INCOMPLETE|SKIP>
  CHANGES_START
  ...
  CHANGES_END
  """
)
```

### ステップ 6: P2結果の表示

Agent P2の返却結果から status と `CHANGES_START` / `CHANGES_END` 間の変更サマリを抽出してユーザーに表示する。

表示形式:
```
## Readinessレビュー: <status>

<変更サマリ>
```

- `status=SKIP` の場合: "Codex CLIが未インストールのため、readinessレビューをスキップしました" と表示

### ステップ 7: 次のステップの提示

AskUserQuestion toolでユーザーに選択肢を提示する:
- question: "planの準備が完了しました。次のステップを選択してください。"
- options:
  - "フィードバックで改善する"（具体的な改善ポイントも併せて提案する）
  - "`make impl plan=<plan-name>` でcc-sddパイプラインを開始する"

### ステップ 8: イテレーション（「フィードバックで改善する」選択時）

ユーザーのフィードバック内容を取得し、Agent P1eを起動する:

```
Agent(
  description: "plan-edit <plan-name>",
  model: "sonnet",
  prompt: """
  .claude/agents/plan-edit.md をRead toolで読み込み、その指示に従ってください。

  ## パラメータ
  - PLAN_FILE_PATH: {PLAN_FILE_PATH}
  - USER_FEEDBACK: {ユーザーのフィードバック内容}

  ## 完了報告形式
  P1E_DONE
  CHANGES_START
  ...
  CHANGES_END
  """
)
```

P1e完了後:
1. 変更サマリをユーザーに表示
2. ステップ 5（P2: plan-readiness）に戻る

## 安全策とフォールバック

### エラーシナリオ
- **ユーザーの説明が不足している場合**: P1が最低限のテンプレートを生成し、GAPSで不足情報を報告する
- **steeringが空の場合**: P1がプロジェクトコンテキスト不足の警告をサマリに含める
- **Agent失敗時**: エラー内容を表示し、手動での対応方法を案内する

</instructions>
