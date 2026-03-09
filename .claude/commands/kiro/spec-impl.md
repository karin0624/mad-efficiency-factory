---
description: Execute spec tasks using TDD methodology
allowed-tools: Bash, Read, Write, Edit, MultiEdit, Grep, Glob, LS, WebFetch, WebSearch, Unity_ManageScript, run_tests, Unity_ReadConsole, screenshot-game-view, manage_components, manage_prefabs, Unity_ManageGameObject
argument-hint: <feature-name> [task-numbers]
---

# Implementation Task Executor

<background_information>
- **Mission**: Execute implementation tasks using Test-Driven Development methodology based on approved specifications
- **Success Criteria**:
  - All tests written before implementation code
  - Code passes all tests with no regressions
  - Tasks marked as completed in tasks.md
  - Implementation aligns with design and requirements
</background_information>

<instructions>
## Core Task
Execute implementation tasks for feature **$1** using Test-Driven Development.

## Execution Steps

### Step 1: Load Context

**Read all necessary context**:
- `.kiro/specs/$1/spec.json`, `requirements.md`, `design.md`, `tasks.md`
- **Entire `.kiro/steering/` directory** for complete project memory
- **`.mcp.json`**: Verify `unity-mcp` server is configured. If absent, **stop with error**: "Unity MCP server not found in .mcp.json. This project requires Unity MCP for test execution and scene construction."

**Validate approvals**:
- Verify tasks are approved in spec.json (stop if not, see Safety & Fallback)

### Step 2: Select Tasks

**Determine which tasks to execute**:
- If `$2` provided: Execute specified task numbers (e.g., "1.1" or "1,2,3")
- Otherwise: Execute all pending tasks (unchecked `- [ ]` in tasks.md)

### Step 3: Execute with TDD

For each selected task, follow Kent Beck's TDD cycle:

1. **RED - Write Failing Test**:
   - Write test for the next small piece of functionality
   - Test should fail (code doesn't exist yet)
   - Use descriptive test names

2. **GREEN - Write Minimal Code**:
   - Implement simplest solution to make test pass
   - Focus only on making THIS test pass
   - Avoid over-engineering

3. **REFACTOR - Clean Up**:
   - Improve code structure and readability
   - Remove duplication
   - Apply design patterns where appropriate
   - Ensure all tests still pass after refactoring

4. **VERIFY - Validate Quality**:
   - All tests pass (new and existing)
   - No regressions in existing functionality
   - Code coverage maintained or improved

5. **MARK COMPLETE**:
   - Update checkbox from `- [ ]` to `- [x]` in tasks.md

### Unity MCP TDD Cycle

**When the project uses Unity MCP** (check `.mcp.json` for `unity-mcp` server), replace generic Bash test execution with Unity MCP tools:

1. **RED - Write Failing Test**:
   - Generate NUnit test from the task's requirement (Layer 1: EditMode, Layer 2: PlayMode)
   - Use `Unity_ManageScript` to create test file in `Assets/Tests/EditMode/` or `Assets/Tests/PlayMode/`
   - Use `run_tests` to confirm test fails (expected: test exists but implementation missing)
   - If compilation error: Use `Unity_ReadConsole` to diagnose, fix test, retry

2. **GREEN - Write Minimal Implementation**:
   - Use `Unity_ManageScript` to create/edit implementation code
   - Layer 1: Pure C# class in `Assets/Scripts/Core/` (no MonoBehaviour dependency)
   - Use `run_tests` to confirm test passes
   - If test fails: `Unity_ReadConsole` for error details → fix → `run_tests` again

3. **REFACTOR** (same as generic TDD):
   - Improve code structure
   - Run `run_tests` to confirm no regressions

4. **SCENE CONSTRUCTION** (when task involves GameObjects/Prefabs):
   - Use `Unity_ManageGameObject` to create/configure GameObjects
   - Use `manage_components` to add and configure components
   - Use `manage_prefabs` to create Prefabs from configured GameObjects
   - Use `screenshot-game-view` to capture visual result

5. **LAYER-BASED VERIFICATION**:
   - **Layer 1**: `run_tests` only. Fully automated. No human intervention.
   - **Layer 2**: `run_tests` for constraint checks + `screenshot-game-view` for visual reference. Report results with screenshots.
   - **Layer 3**: Not applicable — Human Review sub-tasks are skipped by spec-impl (see below).

6. **ERROR RECOVERY LOOP**:
   - On test failure: `Unity_ReadConsole` → analyze error → `Unity_ManageScript` to fix → `run_tests`
   - On compilation error: `Unity_ReadConsole` → fix syntax/reference → `run_tests`
   - Maximum 5 retry iterations before reporting failure to user

## Critical Constraints
- **TDD Mandatory**: Tests MUST be written before implementation code
- **Task Scope**: Implement only what the specific task requires
- **Test Coverage**: All new code must have tests
- **No Regressions**: Existing tests must continue to pass
- **Design Alignment**: Implementation must follow design.md specifications
- **Layer Awareness**: Check requirement's Testability Layer before choosing test type (EditMode vs PlayMode)
- **Human Review Skip**: Sub-tasks matching `Human review:` pattern are NOT executed by spec-impl. Detect and skip them during task selection, and include skipped task list in output. Use `/kiro:scene-review` to handle these tasks.
- **Unity MCP Priority**: When Unity MCP is available, prefer MCP tools over Bash for all Unity operations
</instructions>

## Tool Guidance
- **Read first**: Load all context before implementation
- **Test first**: Write tests before code
- Use **WebSearch/WebFetch** for library documentation when needed
- **Unity MCP tools**: Use `Unity_ManageScript` for script creation, `run_tests` for test execution, `Unity_ReadConsole` for error diagnosis
- **Visual verification**: Use `screenshot-game-view` for Layer 2 tasks

## Output Description

Provide brief summary in the language specified in spec.json:

1. **Tasks Executed**: Task numbers and test results
2. **Skipped Human Review Tasks**: List of sub-tasks skipped (if any), with guidance to run `/kiro:scene-review`
3. **Status**: Completed tasks marked in tasks.md, remaining tasks count

**Format**: Concise (under 150 words)

## Safety & Fallback

### Error Scenarios

**Tasks Not Approved or Missing Spec Files**:
- **Stop Execution**: All spec files must exist and tasks must be approved
- **Suggested Action**: "Complete previous phases: `/kiro:spec-requirements`, `/kiro:spec-design`, `/kiro:spec-tasks`"

**Test Failures**:
- **Stop Implementation**: Fix failing tests before continuing
- **Action**: Debug and fix, then re-run

### Task Execution

**Execute specific task(s)**:
- `/kiro:spec-impl $1 1.1` - Single task
- `/kiro:spec-impl $1 1,2,3` - Multiple tasks

**Execute all pending**:
- `/kiro:spec-impl $1` - All unchecked tasks
