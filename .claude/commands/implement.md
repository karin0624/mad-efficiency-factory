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
2. Verify `.mcp.json` exists in workspace root
   - If missing: warn and stop
3. Detect base branch:
   - Try: `git symbolic-ref refs/remotes/origin/HEAD` → extract branch name (e.g., `origin/master` → `master`)
   - Fallback: `git remote show origin | grep 'HEAD branch'`
   - If both fail: ask user and stop

### Step 1: Base Branch Validation + Worktree Creation

1. Confirm current branch matches the detected base branch
   - If on a different branch: warn user and stop
2. `git fetch origin` to sync with remote (do NOT git pull)
3. Generate feature branch name: `feat/<plan-name>`
   - If branch/worktree already exists:
     a. Check existing worktree for spec with matching `source_plan_path` in spec.json
     b. If resumable: use existing worktree, skip to Step 3 at the appropriate phase
     c. If not resumable: append suffix (e.g., `feat/<plan-name>-2`)
4. `git worktree add <worktree-path> -b <branch-name> origin/<base-branch>`
   - Use `/mnt/c/Users/karin0624/work/.worktrees/<branch-name>` as worktree path (Windows filesystem for Unity compatibility)
   - Store worktree path for all subsequent Agents

### Step 2: Plan File Resolution

Resolve `$ARGUMENTS` to a plan file path:
- If contains `/` or ends with `.md`: use as-is (relative to workspace root)
- Otherwise: resolve to `docs/plans/<identifier>.md`
- If not found: Glob `docs/plans/*<identifier>*` to search
  - Multiple candidates: show list and stop (ask user to choose)
- If still not found: list available plans in `docs/plans/` and stop

**Important**: Only resolve the path here. Do NOT read the plan content (token conservation). Pass the path to Agent A.

### Step 3: Agent A — Spec Generation

Launch Agent A to handle Phases 1-4.5 in the worktree. Pass the plan file path and worktree path. Do NOT use `isolation: "worktree"` — the worktree is already created.

```
Agent(
  description: "spec-gen <plan-name>",
  prompt: """
  以下のplanファイルを読み込み、cc-sddパイプラインのspec生成フェーズを実行してください。
  パイプラインの各フェーズは直列に実行してください。
  作業ディレクトリ: {WORKTREE_PATH}

  ## Planファイル
  {PLAN_FILE_PATH}
  このファイルをRead toolで読み込んでください。

  ## 実行手順

  ### Phase 1: spec-init
  - Skill tool: skill="kiro:spec-init", args="<plan内容から抽出した説明文>"
  - 生成された .kiro/specs/ 配下のディレクトリを確認
  - spec.json を読んで実際のfeature名を取得

  ### Phase 2: spec-requirements
  - Skill tool: skill="kiro:spec-requirements", args="<feature-name> --plan {PLAN_FILE_PATH}"
  - planの内容が追加コンテキストとしてrequirements生成に反映される

  ### Phase 3: spec-design
  - Skill tool: skill="kiro:spec-design", args="<feature-name> -y"

  ### Phase 4: spec-tasks
  - Skill tool: skill="kiro:spec-tasks", args="<feature-name> -y"

  ### Phase 4.5: タスク承認 + メタデータ記録
  - spec.jsonを直接編集して以下を設定:
    - `approvals.tasks.approved: true`
    - `ready_for_implementation: true`
    - `source_plan_path: "{PLAN_FILE_PATH}"`

  ## エラー処理
  - いずれかのフェーズが失敗した場合、そのフェーズで停止し詳細を報告
  - 失敗フェーズ、エラー内容、再実行用のコマンドを含める

  ## フォールバック
  - Skill toolが使えない場合、.claude/commands/kiro/ のコマンドファイルを
    直接読み、その指示に従って手動で実行してください

  ## 完了報告
  - 作成されたspec名（feature name）
  - 完了したフェーズ一覧
  - ブランチ名
  - requires_unity: タスク内容にUnity MCPツール（assets_refresh, scripts_compile等）の
    使用が含まれるかどうかのboolean判定
  """
)
```

**Extract from Agent A result**: worktree path, branch name, feature name, requires_unity.

### Step 4: Unity Editor Launch (if requires_unity)

Only execute if Agent A returned `requires_unity: true`. Skip otherwise.

1. Resolve Unity EXE path dynamically (in priority order):
   a. Environment variable: `powershell.exe -Command '$env:UNITY_EDITOR_PATH'`
   b. Auto-detect from Unity Hub: find the latest installed editor version:
      ```bash
      powershell.exe -Command '(Get-ChildItem "C:\Program Files\Unity\Hub\Editor" -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName + "\Editor\Unity.exe"'
      ```
   c. If neither works: warn and stop
2. Check existence: `powershell.exe -Command 'Test-Path "<resolved-path>"'`
   - If not found: warn and stop
3. Convert WSL worktree path to Windows path (`/mnt/c/` → `C:\`)
4. Launch Unity Editor:
   ```bash
   powershell.exe -Command '$p = Start-Process "<resolved-path>" -ArgumentList "-projectPath","{WIN_WORKTREE}\unity" -PassThru; $p.Id'
   ```
5. Wait for Unity ready (timeout: 300 seconds):
   a. Wait for `{worktree}/unity/.nyamu/NyamuSettings.json` to appear
   b. Read `serverPort` from the settings file
   c. Poll `curl http://localhost:{port}/editor-status` until `{"isCompiling":false}` (5-second interval)
   d. `-32603` errors (server initializing) → continue retrying

### Step 5: Agent B — Implementation

Launch Agent B for Phase 5 in the same worktree. New agent (no resume), pass only feature name and worktree path.

```
Agent(
  description: "impl <feature-name>",
  prompt: """
  以下のfeatureのspec-implを実行してください。
  作業ディレクトリ: {WORKTREE_PATH}

  ## Feature
  {FEATURE_NAME}

  ## 実行手順

  ### Phase 5: spec-impl
  - Skill tool: skill="kiro:spec-impl", args="{FEATURE_NAME}"

  ## エラー処理
  - 失敗した場合、失敗タスク番号と詳細を報告
  - 再実行用のコマンドを含める

  ## フォールバック
  - Skill toolが使えない場合、.claude/commands/kiro/spec-impl.md を
    直接読み、その指示に従って手動で実行してください

  ## 完了報告
  - 完了したタスク数 / 全タスク数
  - スキップされたHuman Reviewタスク一覧（あれば）
  - 未コミットの変更があるかどうか
  """
)
```

### Step 5.5: Unity Editor Cleanup

After Agent B completes (success or failure), if Unity was launched in Step 4:
```bash
cmd.exe /c "taskkill /PID {pid} /F"
```

### Step 6: Agent C — Commit + Push + PR

Launch Agent C for Phases 6-7 in the same worktree.

```
Agent(
  description: "commit-push-pr <feature-name>",
  prompt: """
  以下のworktreeブランチで、未コミットの変更を確認し、Push・PR作成を行ってください。
  作業ディレクトリ: {WORKTREE_PATH}

  ## ブランチ
  {BRANCH_NAME}

  ## 実行手順

  ### Phase 6: コミット確認
  1. git status で未コミットの変更を確認
  2. 未コミットの変更がある場合:
     - git diff --name-only で変更ファイル一覧を取得
     - .kiro/specs/ 配下、ソースコード、テストファイルなど意図した変更のみをステージング
     - Unity自動生成ファイル（*.meta以外のLibrary/、Temp/等）は除外
     - 変更内容に基づいた適切なコミットメッセージで git commit
  3. すべてコミット済みの場合: このステップをスキップ

  ### Phase 7: Push + PR作成
  1. git push -u origin {BRANCH_NAME}
  2. gh pr create でPRを作成:
     - title: feature名に基づいた簡潔なタイトル
     - body: specのrequirements.mdの内容をサマリとして含める
     - base: {BASE_BRANCH}

  ## 完了報告
  - コミットの有無と内容
  - PR URL
  """
)
```

### Step 7: Final Output

Display combined results from all Agents:
- Worktree branch name
- Created spec name
- Task completion status
- Skipped Human Review tasks (if any, guide to `/kiro:scene-review`)
- PR URL
- Worktree cleanup guidance (delete after merge)

## Error Handling

| Scenario | Action |
|----------|--------|
| Preflight check failure | Report missing component and stop |
| Not on base branch | Warn and stop |
| git fetch failure | Report error and stop |
| Branch/worktree conflict | Try resume existing spec, else append suffix |
| Plan file not found | Show available plans and stop |
| Skill tool unavailable in Agent | Fallback to reading command files directly |
| spec-init failure | Stop, report error details and retry command |
| Mid-pipeline failure | Stop, report failed phase and feature name |
| Unity launch timeout (300s) | Kill PID, report error |
| spec-impl failure | Cleanup Unity → report failed task, worktree path, branch, manual retry command |
| Existing spec detected | Resume from interrupted phase (skip spec-init) |
| Push/PR failure | Report error (preserve worktree and branch) |

## Important Design Decisions

1. **Always worktree-isolated**: Every invocation uses a worktree regardless of plan size. Main session stays minimal.
2. **Subagent split for token optimization**: Spec generation (A) and implementation (B) use separate agents to avoid context carryover.
3. **Steering auto-loaded**: Each spec command automatically reads `.kiro/steering/`. No need to pass steering in Agent prompts.
4. **Feature name from spec.json**: After spec-init, always read spec.json for the actual feature name (may differ from plan name).
5. **Resume support**: Existing specs are detected via `source_plan_path` in spec.json, allowing mid-pipeline resume.
6. **Auto-approve with `-y`**: Plan serves as the approved source, so approval gates are skipped. Tasks are auto-approved in Phase 4.5.
7. **Plan content via `--plan` flag**: Passed to spec-requirements for context-aware requirement generation without polluting requirements.md.
</instructions>

## Tool Guidance
- **Bash**: Preflight checks, git operations, worktree management, Unity lifecycle
- **Read**: Only for checking spec.json during resume detection
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
- **Unity unavailable**: Skip Unity steps if EXE not found (warn but don't block non-Unity specs)
- **Agent failure**: Report which agent failed, preserve worktree for manual recovery
