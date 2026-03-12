---
description: Screenshot-based human review for Layer 3 tasks in tasks.md
allowed-tools: Read, Write, Edit, Glob, Grep, AskUserQuestion, editor_log_tail, editor_log_grep, editor_status, menu_items_execute
argument-hint: <feature-name>
---

# Scene Review

<background_information>
- **Mission**: Process uncompleted Human Review sub-tasks from tasks.md by presenting review criteria, collecting human judgment via Unity Editor visual confirmation, and marking tasks complete upon human approval
- **Success Criteria**:
  - All pending Human Review sub-tasks from tasks.md identified
  - Review criteria and confirmation steps presented to user
  - Human pass/fail judgment collected for each item
  - Passed tasks marked as `[x]` in tasks.md
  - Failed tasks reported with actionable feedback
</background_information>

<instructions>
## Core Task
Process Human Review sub-tasks for feature **$1** from tasks.md.

## Execution Steps

### Step 1: Load Context

**Read all necessary context**:
- `.kiro/specs/$1/spec.json` for language and metadata
- `.kiro/specs/$1/tasks.md` for pending Human Review sub-tasks
- `.kiro/specs/$1/requirements.md` for Layer 2/3 review criteria
- `.kiro/specs/$1/design.md` for visual design specifications
- **Entire `.kiro/steering/` directory** for project context

### Step 2: Extract Pending Human Review Tasks

**Parse tasks.md** for unchecked Human Review sub-tasks:
- Match pattern: `- [ ] X.Y Human review: [criteria]`
- Collect task number, review criteria, and associated requirement IDs
- If no Human Review tasks found, report and exit

### Step 3: Present Review Items

For each pending Human Review task, present to the user:
- **Task ID and description** (from tasks.md)
- **Review criteria** (from the task description and requirements.md Non-Testable Aspects)
- **What to evaluate**: Specific visual/feel/usability criteria
- **How to verify**: Steps the user should take in Unity Editor to visually confirm
- **Ask for judgment**: Pass or Fail, with optional feedback

**Note**: Screenshot tools (screenshot-game-view, screenshot-scene-view) are not available via Nyamu MCP. The user must visually confirm in Unity Editor directly.

Use AskUserQuestion to collect the user's pass/fail decision for each item.

### Step 4: Update tasks.md

**For passed items**:
- Update checkbox from `- [ ]` to `- [x]` in tasks.md

**For failed items**:
- Keep checkbox as `- [ ]`
- Record user feedback as actionable items
- Report which tasks need rework and what changes are needed

### Step 5: Summary

Provide a summary of all review results.

## Important Constraints
- **tasks.md driven**: Only process tasks that exist as unchecked Human Review items in tasks.md
- **Human-centered**: This command facilitates human judgment, not automated testing
- **Iterative**: Designed to be run multiple times during visual polish cycles
- **No auto-pass**: Never mark Human Review tasks as complete without explicit user approval
- **Manual verification**: User must verify in Unity Editor directly; no screenshot capture available
</instructions>

## Tool Guidance
- **Read for context**: Load spec requirements for review criteria
- **Edit for updates**: Use Edit tool to update task checkboxes in tasks.md
- **Interactive**: Use AskUserQuestion for each review item to collect pass/fail
- **Nyamu MCP**: Use `editor_log_tail`/`editor_log_grep` for console checks, `editor_status` for editor state, `menu_items_execute` for Play Mode if needed

## Output Description

Provide output in the language specified in spec.json:

1. **Pending Reviews**: List of Human Review tasks found in tasks.md
2. **Review Criteria**: What the user should verify in Unity Editor for each item
3. **Review Results**: Pass/fail for each item with user feedback
4. **Updated Tasks**: Which tasks were marked complete in tasks.md
5. **Remaining Work**: Failed items with actionable next steps
6. **Next Action**: If all passed, feature review complete. If failures, iterate with `/kiro:spec-impl` to fix, then re-run `/kiro:scene-review`

**Format**: Concise. Under 300 words of text.

## Safety & Fallback

### Error Scenarios

**Nyamu MCP Not Available**:
- Stop with guidance to configure Nyamu MCP in `.mcp.json`

**No Human Review Tasks Found**:
- Report that tasks.md has no pending Human Review sub-tasks
- Suggest: "All Human Review tasks may already be complete, or tasks were not generated with Layer 3 classifications"

**No Scene Open**:
- Warn and ask user which scene to review

**Missing Spec Files**:
- Stop with guidance to complete earlier phases

### Integration

**Workflow position**: Run after `/kiro:spec-impl` completes (which skips Human Review tasks)
- `/kiro:spec-impl $1` - executes all auto-executable tasks, skips Human Review
- `/kiro:scene-review $1` - picks up skipped Human Review tasks, gets human approval
- Repeat as needed during visual polish

**Relationship to validate-unity**:
- `validate-unity` provides comprehensive automated validation + Layer 3 checklist generation
- `scene-review` is the task-level review tool that actually marks Human Review tasks as done in tasks.md
- Recommended flow: `spec-impl` - `scene-review` - `validate-unity` (final verification)
