---
description: Execute cc-sdd pipeline from a plan file in an isolated worktree.
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, AskUserQuestion
argument-hint: <plan-file-or-name>
---

# 実装: Plan → cc-sdd 自動実行

<instructions>
## コアタスク
plan **$ARGUMENTS** に対してcc-sddパイプライン全体を隔離されたworktreeで実行する。
引数が未指定の場合、現在の会話コンテキスト内で作成されたplanファイルを自動的に使用する。

## 実行ステップ

### ステップ 0: プリフライトチェック

1. GitHub CLIの確認: `which gh` および `gh auth status`
   - 利用不可または未認証の場合: 報告して停止
2. ベースブランチの検出:
   - 試行: `git symbolic-ref refs/remotes/origin/HEAD` → ブランチ名を抽出（例: `origin/master` → `master`）
   - フォールバック: `git remote show origin | grep 'HEAD branch'`
   - 両方失敗した場合: ユーザーに確認して停止
3. 現在のブランチが検出されたベースブランチと一致することを確認
   - 別のブランチにいる場合: ユーザーに警告して停止
4. `git fetch origin` でリモートと同期
5. ローカルとリモートの差分を確認:
   - `git rev-list HEAD..origin/<base-branch> --count` でリモートの未取得コミット数（behind）を取得
   - `git rev-list origin/<base-branch>..HEAD --count` でローカルの未プッシュコミット数（ahead）を取得
   - **両方 0** の場合: そのまま続行
   - **behind > 0（リモートが先行）** の場合: AskUserQuestion toolで確認
     - question: 「リモートに {N} 件の新しいコミットがあります。どうしますか？」
     - options: 「pullして続行」（`git pull origin <base-branch>` を実行）/ 「そのまま続行」（何もせず続行）
     - ユーザーの選択に応じて実行
   - **ahead > 0（ローカルが先行）** の場合: AskUserQuestion toolで確認
     - question: 「ローカルに {N} 件の未プッシュコミットがあります。どうしますか？」
     - options: 「pushして続行」（`git push origin <base-branch>` を実行）/ 「そのまま続行」（何もせず続行）
     - ユーザーの選択に応じて実行
   - **両方 > 0（分岐）** の場合: 「ローカルが {ahead} 件先行、リモートが {behind} 件先行しており、ブランチが分岐しています。手動で解決してください。」と報告して停止

### ステップ 1: planファイルの解決

`$ARGUMENTS` をplanファイルの**絶対パス**に解決する:

#### 引数が空の場合
`$ARGUMENTS` が空文字列または未指定の場合、以下の優先順位で解決する:
1. **コンテキスト内のplanファイル**: 現在の会話で `/plan` コマンドなどにより作成・言及されたplanファイルがある場合、そのファイルを使用する（会話履歴から直近のplanファイルパスを特定）
2. **フォールバック**: コンテキスト内にplanファイルが見つからない場合、`docs/plans/` 内の利用可能なplanを一覧表示して停止

#### 引数がある場合
- `/` を含むか `.md` で終わる場合: そのまま使用（ワークスペースルートからの相対パス）
- それ以外: `docs/plans/<identifier>.md` に解決
- 見つからない場合: Glob `docs/plans/*<identifier>*` で検索
  - 候補が2〜4件の場合: AskUserQuestion toolで選択肢として提示（各候補をoptionとして表示）
  - 候補が5件以上の場合: 一覧を表示して停止（ユーザーに選択を依頼）
- それでも見つからない場合: `docs/plans/` 内の利用可能なplanを一覧表示して停止
- **絶対パスに変換**: `PLAN_FILE_ABSOLUTE_PATH="$(pwd)/<resolved-relative-path>"`
- ブランチ名用にplan名を抽出（拡張子なしのファイル名）
  - ブランチ名用にサニタイズ: 小文字化、スペースや特殊文字をハイフンに置換

**重要**: ここではパスの解決のみ行う。planの内容は読まない（トークン節約）。絶対パスをAgent A1に渡す。

### ステップ 2: 再開検出 + worktree作成

1. フィーチャーブランチ名を生成: `feat/<sanitized-plan-name>`
2. ブランチ/worktreeが既に存在するか確認:
   - `.claude/worktrees/feat/<sanitized-plan-name>` にworktreeが存在する場合:
     a. `<worktree-path>/.kiro/specs/*/spec.json` を読んで既存specを検索
     b. `spec.json.phase` と `approvals.design` で再開ポイントを判定:
        - `validated` → Agent A1, A2, A3, B, B2をスキップ → Agent C（commit）から開始
        - `impl-completed` → Agent A1, A2, A3, Bをスキップ → Agent B2（validate-impl）から開始
        - `tasks-generated` + `approvals.tasks.approved: true` → Agent A1, A2, A3をスキップ、Agent Bから開始
        - `tasks-generated`（未承認） → Agent A3を再開（tasks承認から）
        - `design-generated` + `approvals.design.codex_reviewed: true` → Agent A3から開始（tasks生成から）
        - `design-generated` + `approvals.design.codex_reviewed: false` → Agent A2から開始（design-reviewから — spec-designはスキップ）
        - `requirements-generated` → Agent A2から開始（design生成 + review）
        - `initialized` → Agent A1をPhase 2から起動
     c. `spec.json.feature_name` からフィーチャー名を抽出
     d. 既存のworktreeを使用し、適切なAgentにスキップ
   - ブランチは存在するがworktreeがない場合: 既存ブランチ用にworktreeを作成
   - どちらも存在しない場合: 新しいブランチ + worktreeを作成
3. worktreeを作成（必要な場合）:
   ```
   git worktree add -b feat/<sanitized-plan-name> .claude/worktrees/feat/<sanitized-plan-name> origin/<base-branch>
   ```
   - ブランチが既に存在する場合（再開時）: `git worktree add .claude/worktrees/feat/<sanitized-plan-name> feat/<sanitized-plan-name>`
   - ブランチ名が無関係の作業と競合する場合: サフィックスを付加（例: `feat/<plan-name>-2`）
4. 以降のすべてのAgentのためにworktreeの絶対パスとブランチ名を保持

**注意**: 各Agentの `isolation` パラメータは使用しない。全Agentが同一worktreeを共有する必要がある。

### ステップ 3: Agent A1 — WHAT（init + requirements）

再開検出でスキップ対象でない場合のみ実行。

```
Agent(
  description: "spec-what <plan-name>",
  model: "opus",
  prompt: """
  指示ファイル: .claude/agents/impl-spec-what.md を読んで従ってください。
  WORKTREE_PATH: {WORKTREE_PATH}
  PLAN_FILE_ABSOLUTE_PATH: {PLAN_FILE_ABSOLUTE_PATH}
  """
)
```

**注意**: 各specコマンドは自動的に `.kiro/steering/` を読み込む。Agentプロンプトにsteeringを渡す必要はない。

**A1の結果から抽出**: worktreeパス、ブランチ名、フィーチャー名（フィーチャー名は常に `spec.json` から取得すること）。

### ステップ 3.5: Agent A2 — HOW + レビュー（design + design-review）

再開時の特殊ケース:
- `requirements-generated` → RESUME_MODE="full"
- `design-generated` + `codex_reviewed: false` → RESUME_MODE="review-only"

```
Agent(
  description: "spec-how <feature-name>",
  model: "opus",
  prompt: """
  指示ファイル: .claude/agents/impl-spec-how.md を読んで従ってください。
  WORKTREE_PATH: {WORKTREE_PATH}
  FEATURE_NAME: {FEATURE_NAME}
  RESUME_MODE: {full or review-only}
  """
)
```

**A2の結果による分岐**:
- **完了（APPROVE or REVISE後の完了）** → Agent A3に進む
- **REJECT** → パイプラインを停止し、Codexフィードバックとworktreeパスを報告

### ステップ 3.75: Agent A3 — 実行計画（tasks + 承認）

```
Agent(
  description: "spec-tasks <feature-name>",
  model: "sonnet",
  prompt: """
  指示ファイル: .claude/agents/impl-spec-tasks.md を読んで従ってください。
  WORKTREE_PATH: {WORKTREE_PATH}
  FEATURE_NAME: {FEATURE_NAME}
  """
)
```

### ステップ 4: Agent B — 実装

```
Agent(
  description: "impl <feature-name>",
  model: "sonnet",
  prompt: """
  指示ファイル: .claude/agents/impl-code.md を読んで従ってください。
  WORKTREE_PATH: {WORKTREE_PATH}
  FEATURE_NAME: {FEATURE_NAME}
  """
)
```

### ステップ 4.5: Agent B2 — validate-impl

```
Agent(
  description: "validate-impl <feature-name>",
  model: "opus",
  prompt: """
  指示ファイル: .claude/agents/impl-validate.md を読んで従ってください。
  WORKTREE_PATH: {WORKTREE_PATH}
  FEATURE_NAME: {FEATURE_NAME}
  """
)
```

**B2の結果による分岐**:
- **VALIDATION_PASSED（GO / CONDITIONAL GO）** → Agent C（commit）に進む
- **VALIDATION_FAILED（NO-GO）** → パイプラインを停止し、バリデーション結果・worktreeパス・再開案内を出力

### ステップ 5: Agent C — コミット

```
Agent(
  description: "commit <feature-name>",
  model: "sonnet",
  prompt: """
  指示ファイル: .claude/agents/impl-commit.md を読んで従ってください。
  WORKTREE_PATH: {WORKTREE_PATH}
  BRANCH_NAME: {BRANCH_NAME}
  FEATURE_NAME: {FEATURE_NAME}
  """
)
```

### ステップ 5.5: L4 Human Review 分岐判定

Agent C完了後、worktree内の `tasks.md` を確認してL4 Human Reviewタスクの有無を判定する:
1. `{WORKTREE_PATH}/.kiro/specs/{FEATURE_NAME}/tasks.md` を読み込む
2. 未チェックのL4 Human Reviewサブタスク（パターン: `- [ ] X.Y Human review:`）を検索
3. 結果に応じて次のステップを分岐:
   - **L4 Human Reviewタスクあり** → ステップ 6A へ
   - **L4 Human Reviewタスクなし** → ステップ 6B へ

### ステップ 6A: scene-review（L4 Human Reviewタスクがある場合）

1. Skill toolで scene-review を起動:
   - `Skill(skill="kiro:scene-review", args="{FEATURE_NAME}")`
   - **注意**: scene-reviewはインタラクティブ（AskUserQuestionでユーザーの合格/不合格判断を収集する）
2. scene-review完了後の分岐:
   - **不合格の項目がある場合**: worktreeを保持し、修正→再実行の案内をして停止（ステップ 7A へ）
   - **全項目合格の場合**: ステップ 6B に進む

### ステップ 6B: Agent D — Push + PR + クリーンアップ

```
Agent(
  description: "push-pr <feature-name>",
  model: "sonnet",
  prompt: """
  指示ファイル: .claude/agents/impl-push-pr.md を読んで従ってください。
  WORKTREE_PATH: {WORKTREE_PATH}
  BRANCH_NAME: {BRANCH_NAME}
  FEATURE_NAME: {FEATURE_NAME}
  BASE_BRANCH: {BASE_BRANCH}
  """
)
```

Agent DがPR作成に成功した場合、worktreeを削除する:
1. `git worktree remove {WORKTREE_PATH}` を実行（未コミットの変更がある場合は `--force` は使わず警告してスキップ）
2. `rmdir --ignore-fail-on-non-empty .claude/worktrees/feat/`
3. ブランチはPRに紐付いているため削除しない

Agent Dが失敗した場合はworktreeを保持し、手動リカバリ用にパスを報告する。

### ステップ 7A: 最終出力（scene-reviewで不合格あり）

worktreeを保持し、以下を出力: ブランチ名、spec名、タスク完了状況、バリデーション結果、scene-review結果、worktreeパス、次のステップ案内（worktreeで修正 → `/kiro:scene-review` で再レビュー）。

### ステップ 7B: 最終出力（PR作成完了）

以下を出力: ブランチ名、spec名、タスク完了状況、バリデーション結果、PR URL、worktree削除状況。

</instructions>
