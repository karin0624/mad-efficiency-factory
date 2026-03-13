---
description: Execute cc-sdd pipeline from a plan file in an isolated worktree
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent
argument-hint: <plan-file-or-name>
---

# Implement: Plan → cc-sdd Auto-Execution

<background_information>
- **Mission**: Execute the full cc-sdd pipeline (spec-init → requirements → design → tasks → spec-impl) from a plan file in an isolated worktree
- **Success Criteria**:
  - Plan file resolved and validated
  - Worktree created on a feature branch
  - Spec generated (Agent A) and implemented (Agent B) in isolated subagents
  - Changes committed, pushed, and PR created (Agent C)
  - Main session context remains minimal (orchestrator only)
</background_information>

<instructions>
## Core Task
Execute the full cc-sdd pipeline for plan **$ARGUMENTS** in an isolated worktree.

## Execution Steps

### Step 0: Preflight Checks

1. Verify GitHub CLI: `which gh` and `gh auth status`
   - If unavailable or not authenticated: report and stop
2. Detect base branch:
   - Try: `git symbolic-ref refs/remotes/origin/HEAD` → extract branch name (e.g., `origin/master` → `master`)
   - Fallback: `git remote show origin | grep 'HEAD branch'`
   - If both fail: ask user and stop
3. Confirm current branch matches the detected base branch
   - If on a different branch: warn user and stop
4. `git fetch origin` to sync with remote (do NOT git pull)

### Step 1: Plan File Resolution

Resolve `$ARGUMENTS` to a plan file **absolute path**:
- If contains `/` or ends with `.md`: use as-is (relative to workspace root)
- Otherwise: resolve to `docs/plans/<identifier>.md`
- If not found: Glob `docs/plans/*<identifier>*` to search
  - Multiple candidates: show list and stop (ask user to choose)
- If still not found: list available plans in `docs/plans/` and stop
- **Convert to absolute path**: `PLAN_FILE_ABSOLUTE_PATH="$(pwd)/<resolved-relative-path>"`
- Extract plan name (filename without extension) for branch naming
  - Sanitize for branch name: lowercase, replace spaces/special chars with hyphens

**Important**: Only resolve the path here. Do NOT read the plan content (token conservation). Pass the absolute path to Agent A.

### Step 2: Resume Detection + Worktree Creation

1. Generate feature branch name: `feat/<sanitized-plan-name>`
2. Check if branch/worktree already exists:
   - If worktree exists at `.claude/worktrees/feat/<sanitized-plan-name>`:
     a. Read `<worktree-path>/.kiro/specs/*/spec.json` to find existing spec
     b. Check `spec.json.phase` to determine resume point:
        - `tasks-generated` + `approvals.tasks.approved: true` → Skip Agent A, start from Agent B
        - `design-generated` or `tasks-generated` (unapproved) → Launch Agent A with resume instructions (Phase 4 onward)
        - `requirements-generated` → Launch Agent A with resume (Phase 3 onward)
        - `initialized` → Launch Agent A from Phase 2 onward
     c. Extract feature name from `spec.json.feature_name`
     d. Use existing worktree, skip to appropriate Agent
   - If branch exists but no worktree: create worktree for existing branch
   - If neither exists: create new branch + worktree
3. Create worktree (if needed):
   ```
   git worktree add -b feat/<sanitized-plan-name> .claude/worktrees/feat/<sanitized-plan-name> origin/<base-branch>
   ```
   - If branch already exists (from resume): `git worktree add .claude/worktrees/feat/<sanitized-plan-name> feat/<sanitized-plan-name>`
   - If branch name conflicts with unrelated work: append suffix (e.g., `feat/<plan-name>-2`)
4. Store worktree absolute path and branch name for all subsequent Agents

### Step 3: Agent A — Spec Generation

Launch Agent A to handle Phases 1-4.5 in the worktree. Pass the plan file absolute path and worktree path. Do NOT use `isolation: "worktree"` — the worktree is already created.

If resuming from a later phase (detected in Step 2), include the resume phase and feature name in the prompt.

```
Agent(
  description: "spec-gen <plan-name>",
  prompt: """
  以下のplanファイルを読み込み、cc-sddパイプラインのspec生成フェーズを実行してください。
  パイプラインの各フェーズは直列に実行してください。

  ## cwd強制
  最初に必ず以下を実行してください:
  1. cd {WORKTREE_PATH}
  2. git rev-parse --show-toplevel で {WORKTREE_PATH} にいることを確認
  すべてのBashコマンドは {WORKTREE_PATH} で実行すること。

  ## Planファイル（絶対パス — main repoから読み込み可能）
  {PLAN_FILE_ABSOLUTE_PATH}
  このファイルをRead toolで読み込んでください。

  ## 実行手順

  ### Phase 1: spec-init
  - Skill tool: skill="kiro:spec-init", args="<plan内容から抽出した説明文>"
  - 生成された .kiro/specs/ 配下のディレクトリを確認
  - spec.json を読んで実際のfeature名を取得

  ### Phase 2: spec-requirements
  - Skill tool: skill="kiro:spec-requirements", args="<feature-name> --plan {PLAN_FILE_ABSOLUTE_PATH}"
  - planの内容が追加コンテキストとしてrequirements生成に反映される

  ### Phase 3: spec-design
  - Skill tool: skill="kiro:spec-design", args="<feature-name> -y"

  ### Phase 4: spec-tasks
  - Skill tool: skill="kiro:spec-tasks", args="<feature-name> -y"

  ### Phase 4.5: タスク承認 + メタデータ記録
  **Phase 4 (spec-tasks) が正常完了した直後に必ず実行すること。**
  spec.jsonを直接編集して以下を設定:
    - `approvals.tasks.approved: true`
    - `source_plan_path: "{PLAN_FILE_ABSOLUTE_PATH}"`（トレーサビリティ用）

  ## エラー処理
  - いずれかのフェーズが失敗した場合、そのフェーズで停止し詳細を報告
  - 失敗フェーズ、エラー内容、再実行用のコマンドを含める

  ## フォールバック
  Skill toolが使えない場合は .claude/commands/kiro/ の該当コマンドファイルを直接読んで手動実行

  ## 完了報告
  - 作成されたspec名（feature name）
  - 完了したフェーズ一覧
  - ブランチ名
  """
)
```

**Extract from Agent A result**: worktree path, branch name, feature name.

### Step 4: Agent B — Implementation

Launch Agent B for Phase 5 in the same worktree. New agent (no resume), pass only feature name and worktree path.

```
Agent(
  description: "impl <feature-name>",
  prompt: """
  以下のfeatureのspec-implを実行してください。

  ## cwd強制
  最初に必ず以下を実行してください:
  1. cd {WORKTREE_PATH}
  2. git rev-parse --show-toplevel で {WORKTREE_PATH} にいることを確認
  すべてのBashコマンドは {WORKTREE_PATH} で実行すること。

  ## Feature
  {FEATURE_NAME}

  ## 実行手順

  ### Phase 5: spec-impl
  - Skill tool: skill="kiro:spec-impl", args="{FEATURE_NAME}"

  ## エラー処理
  - 失敗した場合、失敗タスク番号と詳細を報告
  - 再実行用のコマンドを含める

  ## フォールバック
  Skill toolが使えない場合は .claude/commands/kiro/spec-impl.md を直接読んで手動実行

  ## 完了報告
  - 完了したタスク数 / 全タスク数
  - スキップされたHuman Reviewタスク一覧（あれば）
  - 未コミットの変更があるかどうか
  """
)
```

### Step 5: Agent C — Commit + Push + PR

Launch Agent C for Phases 6-7 in the same worktree.

```
Agent(
  description: "commit-push-pr <feature-name>",
  prompt: """
  以下のworktreeブランチで、未コミットの変更を確認し、Push・PR作成を行ってください。

  ## cwd強制
  最初に必ず以下を実行してください:
  1. cd {WORKTREE_PATH}
  2. git rev-parse --show-toplevel で {WORKTREE_PATH} にいることを確認
  すべてのBashコマンドは {WORKTREE_PATH} で実行すること。

  ## ブランチ
  {BRANCH_NAME}

  ## Feature
  {FEATURE_NAME}

  ## 実行手順

  ### Phase 6: コミット確認
  1. git status で未コミットの変更を確認
  2. 未コミットの変更がある場合:
     - git diff --name-only で変更ファイル一覧を取得
     - .kiro/specs/ 配下、ソースコード、テストファイルなど意図した変更のみをステージング
     - 変更内容に基づいた適切なコミットメッセージで git commit
  3. すべてコミット済みの場合: このステップをスキップ

  ### Phase 7: Push + PR作成
  1. gh pr list --head {BRANCH_NAME} で既存PRを確認
     - 既にPRが存在する場合: PR URLを報告してスキップ
  2. git push -u origin {BRANCH_NAME}
  3. gh pr create でPRを作成:
     - title: {FEATURE_NAME} に基づいた簡潔なタイトル
     - body: specのrequirements.mdの内容をサマリとして含める
     - base: {BASE_BRANCH}

  ## 完了報告
  - コミットの有無と内容
  - PR URL
  """
)
```

### Step 6: Final Output

Display combined results from all Agents:
- Worktree branch name
- Created spec name
- Task completion status
- Skipped Human Review tasks (if any, guide to `/kiro:scene-review`)
- PR URL
- Worktree cleanup guidance (delete after merge)

## Important Design Decisions

1. **Always worktree-isolated**: Every invocation uses a worktree regardless of plan size. Main session stays minimal.
2. **Subagent split for token optimization**: Spec generation (A) and implementation (B) use separate agents to avoid context carryover.
3. **Steering auto-loaded**: Each spec command automatically reads `.kiro/steering/`. No need to pass steering in Agent prompts.
4. **Feature name from spec.json**: After spec-init, always read spec.json for the actual feature name (may differ from plan name).
5. **Phase-based resume**: Existing specs are detected via `spec.json.phase`, allowing deterministic mid-pipeline resume.
6. **Auto-approve with `-y`**: Plan serves as the approved source, so approval gates are skipped. Tasks are auto-approved in Phase 4.5.
7. **Plan content via `--plan` flag**: Passed to spec-requirements for context-aware requirement generation without polluting requirements.md.
8. **Absolute paths for plan files**: Plan files are resolved to absolute paths so they remain accessible from worktree context.
9. **cwd enforcement**: Each Agent starts with `cd` + `git rev-parse --show-toplevel` verification to ensure worktree isolation.
</instructions>

## Tool Guidance
- **Bash**: Preflight checks, git operations, worktree management
- **Read**: Checking spec.json during resume detection
- **Glob**: Plan file resolution
- **Agent**: Launch subagents A, B, C sequentially (never use `isolation: "worktree"` — worktree is pre-created)

## Output Description
Concise final summary including:
1. Branch and worktree info
2. Spec name and completion status
3. PR URL
4. Next steps (Human Review tasks, worktree cleanup)

## Safety & Fallback
- **Plan not found**: List available plans in `docs/plans/` with full paths
- **Git conflicts**: Never force-push; report conflicts for manual resolution
- **Agent failure**: Report which agent failed, preserve worktree for manual recovery
