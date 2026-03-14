---
description: Execute spec modification workflow for an existing feature.
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, AskUserQuestion
argument-hint: <feature-name> [change-description]
---

# 仕様変更: 既存Spec → デルタ修正ワークフロー

<instructions>
## コアタスク
既存specの **$ARGUMENTS** に対して変更影響分析→specカスケード→デルタタスク生成→実装→検証→PR作成を実行する。

## 実行ステップ

### ステップ 0: プリフライトチェック

`/implement` Step 0と同一。

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
   - `git rev-list HEAD..origin/<base-branch> --count` でbehind数を取得
   - `git rev-list origin/<base-branch>..HEAD --count` でahead数を取得
   - **両方 0**: 続行
   - **behind > 0**: AskUserQuestion toolで確認（pullして続行 / そのまま続行）
   - **ahead > 0**: AskUserQuestion toolで確認（pushして続行 / そのまま続行）
   - **両方 > 0**: 分岐状態。手動解決を依頼して停止

### ステップ 1: Feature + 変更解決

1. `$ARGUMENTS` をパース:
   - 第1トークン = `FEATURE_NAME`（feature名）
   - 残りのトークン = `CHANGE_DESCRIPTION`（変更記述）
2. `.kiro/specs/{FEATURE_NAME}/` の存在を検証
   - 存在しない場合: `.kiro/specs/` 内のディレクトリ一覧を表示して停止
3. `.kiro/specs/{FEATURE_NAME}/spec.json` を読み、`phase` が `requirements-generated` 以降であることを確認
   - `initialized` の場合: 「要件生成が完了していません。先に `/implement` で要件を生成してください。」と報告して停止
4. `CHANGE_DESCRIPTION` が空の場合:
   - 現在の会話コンテキストを確認（直近で言及された変更内容があれば使用）
   - なければ AskUserQuestion toolで質問: 「どのような変更を加えますか？」
5. `FEATURE_NAME`, `CHANGE_DESCRIPTION` を保持

### ステップ 2: 変更影響分析 — Agent M1

```
Agent(
  description: "change-analysis {FEATURE_NAME}",
  model: "opus",
  subagent_type: "general-purpose",
  prompt: """
  指示ファイル: .claude/agents/modify-analyze.md を読んで従ってください。
  FEATURE_NAME: {FEATURE_NAME}
  CHANGE_DESCRIPTION: {CHANGE_DESCRIPTION}
  """
)
```

**M1の結果から抽出**:
- `CLASSIFICATION` (major/minor)
- `CHANGE_TYPE` (additive/modifying/removal/mixed)
- `CASCADE_DEPTH` (requirements-only/requirements+design/requirements+design+tasks/full)
- `AFFECTED_REQUIREMENTS`, `AFFECTED_DESIGN_SECTIONS`, `AFFECTED_TASKS`
- `DELTA_SUMMARY`

M1出力全体を `M1_OUTPUT` として保持（後続Agentに渡す）。

### ステップ 3: 再開検出 + worktree作成

1. ブランチ名生成: `modify/{FEATURE_NAME}`
2. 既存worktree/ブランチの確認:
   - `.claude/worktrees/modify/{FEATURE_NAME}` にworktreeが存在する場合:
     a. `spec.json` の `modifications` 配列の最後のエントリの `modify_phase` で再開ポイントを判定:
        - `analysis-completed` → ステップ 4（M2）から再開
        - `spec-cascaded` → ステップ 5（M3）から再開
        - `delta-tasks-generated` → ステップ 6（Agent B）から再開
        - `impl-completed` → ステップ 7（Agent B2）から再開
        - `validated` → ステップ 8（Agent C）から再開
     b. 既存worktreeを使用し、適切なステップにスキップ
   - ブランチは存在するがworktreeがない場合: 既存ブランチ用にworktreeを作成
   - どちらも存在しない場合: 新しいブランチ + worktreeを作成
3. worktreeを作成（必要な場合）:
   ```
   git worktree add -b modify/{FEATURE_NAME} .claude/worktrees/modify/{FEATURE_NAME} origin/{BASE_BRANCH}
   ```
   - ブランチが既に存在する場合（再開時）: `git worktree add .claude/worktrees/modify/{FEATURE_NAME} modify/{FEATURE_NAME}`
4. `WORKTREE_PATH`, `BRANCH_NAME` を保持

**注意**: 各Agentの `isolation` パラメータは使用しない。全Agentが同一worktreeを共有する。

### ステップ 4: Specカスケード再生成 — Agent M2

```
Agent(
  description: "spec-cascade {FEATURE_NAME}",
  model: "opus",
  subagent_type: "general-purpose",
  prompt: """
  指示ファイル: .claude/agents/modify-cascade.md を読んで従ってください。
  WORKTREE_PATH: {WORKTREE_PATH}
  FEATURE_NAME: {FEATURE_NAME}
  CHANGE_IMPACT_REPORT: {M1_OUTPUT}
  CASCADE_DEPTH: {CASCADE_DEPTH}
  """
)
```

**M2の結果による分岐**:
- **CASCADE_DONE** → 次のステップに進む
- **CASCADE_FAILED (REJECT)** → パイプラインを停止し、フィードバックとworktreeパスを報告

M2完了後、spec.json の `modifications[-1].modify_phase` は `spec-cascaded` に更新済み。

### ステップ 5: デルタタスク生成 — Agent M3

CASCADE_DEPTH が `requirements-only` の場合はこのステップをスキップ（タスク変更不要）。

```
Agent(
  description: "delta-tasks {FEATURE_NAME}",
  model: "sonnet",
  subagent_type: "general-purpose",
  prompt: """
  指示ファイル: .claude/agents/modify-tasks.md を読んで従ってください。
  WORKTREE_PATH: {WORKTREE_PATH}
  FEATURE_NAME: {FEATURE_NAME}
  CHANGE_IMPACT_REPORT: {M1_OUTPUT}
  CASCADE_DEPTH: {CASCADE_DEPTH}
  """
)
```

M3完了後、worktree内の spec.json の `modifications[-1].modify_phase` を `delta-tasks-generated` に更新する。

### ステップ 6: Agent B — 実装

CASCADE_DEPTH が `requirements-only` または `requirements+design` の場合はスキップ（実装変更不要）。

```
Agent(
  description: "impl {FEATURE_NAME}",
  model: "sonnet",
  subagent_type: "impl-code",
  prompt: """
  指示ファイル: .claude/agents/impl-code.md を読んで従ってください。
  WORKTREE_PATH: {WORKTREE_PATH}
  FEATURE_NAME: {FEATURE_NAME}
  """
)
```

Agent B完了後、worktree内の spec.json の `modifications[-1].modify_phase` を `impl-completed` に更新する。

### ステップ 7: Agent B2 — validate-impl

CASCADE_DEPTH が `requirements-only` の場合はスキップ。

```
Agent(
  description: "validate-impl {FEATURE_NAME}",
  model: "opus",
  subagent_type: "impl-validate",
  prompt: """
  指示ファイル: .claude/agents/impl-validate.md を読んで従ってください。
  WORKTREE_PATH: {WORKTREE_PATH}
  FEATURE_NAME: {FEATURE_NAME}
  """
)
```

**B2の結果による分岐**:
- **VALIDATION_PASSED** → Agent Cに進む。worktree内のspec.jsonの `modifications[-1].modify_phase` を `validated` に更新
- **VALIDATION_FAILED** → パイプラインを停止し、バリデーション結果・worktreeパス・再開案内を出力

### ステップ 8: Agent C — コミット

```
Agent(
  description: "commit {FEATURE_NAME}",
  model: "sonnet",
  subagent_type: "impl-commit",
  prompt: """
  指示ファイル: .claude/agents/impl-commit.md を読んで従ってください。
  WORKTREE_PATH: {WORKTREE_PATH}
  BRANCH_NAME: {BRANCH_NAME}
  FEATURE_NAME: {FEATURE_NAME}
  """
)
```

### ステップ 8.5: L4 Human Review 分岐判定

Agent C完了後、`/implement` と同じロジック:
1. `{WORKTREE_PATH}/.kiro/specs/{FEATURE_NAME}/tasks.md` を読み込む
2. 未チェックのL4 Human Reviewサブタスク（パターン: `- [ ] X.Y Human review:`）を検索
3. **あり** → ステップ 9A へ / **なし** → ステップ 9B へ

### ステップ 9A: scene-review（L4 Human Reviewタスクがある場合）

1. `Skill(skill="kiro:scene-review", args="{FEATURE_NAME}")`
2. 結果:
   - **不合格あり**: worktreeを保持し、修正→再実行の案内をして停止（最終出力A）
   - **全合格**: ステップ 9B に進む

### ステップ 9B: Agent D — Push + PR + クリーンアップ

```
Agent(
  description: "push-pr {FEATURE_NAME}",
  model: "sonnet",
  subagent_type: "impl-push-pr",
  prompt: """
  指示ファイル: .claude/agents/impl-push-pr.md を読んで従ってください。
  WORKTREE_PATH: {WORKTREE_PATH}
  BRANCH_NAME: {BRANCH_NAME}
  FEATURE_NAME: {FEATURE_NAME}
  BASE_BRANCH: {BASE_BRANCH}
  MODIFY_MODE: true
  CHANGE_SUMMARY: {DELTA_SUMMARYの1行要約}
  """
)
```

Agent DがPR作成に成功した場合、worktreeを削除する:
1. `git worktree remove {WORKTREE_PATH}`（未コミットの変更がある場合は `--force` は使わず警告してスキップ）
2. `rmdir --ignore-fail-on-non-empty .claude/worktrees/modify/`
3. ブランチはPRに紐付いているため削除しない

worktree内のspec.jsonの `modifications[-1].modify_phase` を `completed` に更新する。

### 最終出力A（scene-reviewで不合格あり / バリデーション失敗時）

以下を出力:
- ブランチ名、spec名、変更分類（CLASSIFICATION）、影響範囲
- タスク完了状況（既存タスク / 新規タスク / reworkタスク）
- バリデーション結果（あれば）
- worktreeパス
- 次のステップ案内

### 最終出力B（PR作成完了）

以下を出力:
- ブランチ名、spec名、変更分類（CLASSIFICATION）、影響範囲
- タスク完了状況（既存タスク / 新規タスク / reworkタスク）
- バリデーション結果
- PR URL
- worktree削除状況

</instructions>
