---
description: Unity-specific comprehensive validation using Unity MCP tools
allowed-tools: Bash, Glob, Grep, Read, LS, tests_run_all, tests_run_single, tests_run_regex, tests_run_status, assets_refresh, scripts_compile, scripts_compile_status, editor_status, editor_log_tail, editor_log_grep, editor_log_head, editor_log_path, menu_items_execute
argument-hint: <feature-name>
---

# Unity Validation

<background_information>
- **Mission**: Comprehensive Unity-specific validation combining automated tests, console checks, runtime verification, and human review checklist generation
- **Success Criteria**:
  - All EditMode and PlayMode tests pass
  - No compilation errors or critical runtime warnings
  - Game runs without crashes (play mode verification)
  - Layer 2 constraints verified against logs
  - Layer 3 human review checklist generated
</background_information>

<instructions>
## Core Task
Execute comprehensive Unity validation for feature **$1** using Nyamu MCP tools.

## Execution Steps

### Step 1: Load Context

**Read all necessary context**:
- `.kiro/specs/$1/spec.json`, `requirements.md`, `design.md`, `tasks.md`
- **Entire `.kiro/steering/` directory** for complete project memory

**Classify requirements by layer**:
- Extract Layer 1, Layer 2, Layer 3 requirements from requirements.md
- Build validation checklist per layer

### Step 2: Automated Test Validation (Layer 1 + Layer 2)

1. **Run all tests**:
   - Use `tests_run_all` to execute EditMode tests
   - Use `tests_run_status` to poll for results
   - Use `tests_run_all` to execute PlayMode tests
   - Use `tests_run_status` to poll for results
   - Collect pass/fail results for each test

2. **Analyze results**:
   - If all pass: Record success
   - If failures: Use `editor_log_tail`/`editor_log_grep` to get detailed error info including stack traces
   - Map test failures to requirement IDs

### Step 3: Console and Compilation Check

1. **Use `editor_log_tail`/`editor_log_grep`** to collect console output:
   - Check for compilation errors (severity: Critical)
   - Check for runtime exceptions (severity: Critical)
   - Check for warnings (severity: Warning)
   - Filter noise (Debug.Log informational messages)

2. **Report findings** categorized by severity

### Step 4: Runtime Verification

1. **Use `menu_items_execute`** to start Play Mode (no dedicated Play Mode start tool exists)
2. **Wait briefly** for initialization
3. **Use `editor_log_tail`** to check for runtime errors during play
4. **Note**: Screenshot capture is not available via Nyamu MCP. For visual verification, use `/kiro:scene-review` for manual human confirmation.

### Step 5: Layer 2 Constraint Verification

For each Layer 2 requirement:
- Cross-reference test results with constraint specifications
- Note which constraints passed automated verification
- Note which aspects require manual review

### Step 6: Layer 3 Human Review Checklist

For each Layer 3 requirement:
- Generate a review checklist item with:
  - Requirement ID and description
  - What to evaluate (specific visual/feel criteria)
  - Pass/fail checkbox for human to complete
- Present complete checklist to user
- **Note**: Screenshots must be captured manually by the user in Unity Editor, as Nyamu MCP does not provide screenshot tools.

### Step 7: Generate Validation Report

Compile all results into a structured report.

## Important Constraints
- **Non-destructive**: Do not modify any files; read and execute only
- **Layer-aware**: Different validation strategies per testability layer
- **Human gate for Layer 3**: Never auto-pass Layer 3 items
- **Manual screenshot**: Screenshot tools are not available; instruct user to capture manually when needed
</instructions>

## Tool Guidance
- **Nyamu MCP primary**: Use `tests_run_all`/`tests_run_single` + `tests_run_status` for tests, `editor_log_tail`/`editor_log_grep` for console, `editor_status` for editor state, `menu_items_execute` for Play Mode
- **Read for context**: Load specs and steering before validation
- **Grep for traceability**: Search codebase for requirement coverage evidence

## Output Description

Provide output in the language specified in spec.json:

1. **Test Results Summary**: EditMode pass/fail counts, PlayMode pass/fail counts
2. **Console Health**: Compilation errors (0 expected), warnings count, runtime exceptions
3. **Runtime Check**: Play mode start/stop success
4. **Layer 2 Constraints**: Per-requirement pass/fail with evidence
5. **Layer 3 Review Checklist**: Human-actionable checklist
6. **Overall Decision**: GO / NO-GO / CONDITIONAL (waiting for Layer 3 human review)

**Format**: Structured Markdown with tables

## Safety & Fallback

### Error Scenarios

**Nyamu MCP Not Available**:
- Check `.mcp.json` for `nyamu` server configuration
- If not configured: Stop with message "Nyamu MCP not configured. Add nyamu server to .mcp.json"

**Test Runner Errors**:
- If `tests_run_all` fails to execute: Report infrastructure error
- Use `editor_log_tail`/`editor_log_grep` to diagnose
- Suggest: "Check Unity Test Framework package is installed"

**Play Mode Crash**:
- If `menu_items_execute` play fails or crashes: Report as Critical
- Capture console output before and after
- Do not retry automatically

**Missing Spec Files**:
- If spec files missing: Stop with guidance to complete earlier phases

### Integration with Other Commands

**After validate-unity**:
- If GO: Feature is validated, proceed to next feature or deployment
- If NO-GO: Address failures, re-run `/kiro:spec-impl $1 [failed-tasks]`, then re-validate
- If CONDITIONAL: Complete Layer 3 human review via `/kiro:scene-review $1`, then re-run to confirm

**Relationship to validate-impl**:
- `validate-impl` checks general implementation alignment (code structure, test existence, requirement traceability)
- `validate-unity` checks Unity-specific runtime behavior (actual test execution via MCP, console health, play mode)
- Recommended: Run both for comprehensive validation
