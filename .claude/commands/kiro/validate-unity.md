---
description: Unity-specific comprehensive validation using Unity MCP tools
allowed-tools: Bash, Glob, Grep, Read, LS, run_tests, Unity_ReadConsole, Unity_ManageEditor, screenshot-game-view
argument-hint: <feature-name>
---

# Unity Validation

<background_information>
- **Mission**: Comprehensive Unity-specific validation combining automated tests, console checks, runtime verification, and human review checklist generation
- **Success Criteria**:
  - All EditMode and PlayMode tests pass
  - No compilation errors or critical runtime warnings
  - Game runs without crashes (play mode verification)
  - Layer 2 constraints verified against screenshots/logs
  - Layer 3 human review checklist generated with screenshots
</background_information>

<instructions>
## Core Task
Execute comprehensive Unity validation for feature **$1** using Unity MCP tools.

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
   - Use `run_tests` to execute EditMode tests
   - Use `run_tests` to execute PlayMode tests
   - Collect pass/fail results for each test

2. **Analyze results**:
   - If all pass: Record success
   - If failures: Use `Unity_ReadConsole` to get detailed error info including stack traces
   - Map test failures to requirement IDs

### Step 3: Console and Compilation Check

1. **Use `Unity_ReadConsole`** to collect all console output:
   - Check for compilation errors (severity: Critical)
   - Check for runtime exceptions (severity: Critical)
   - Check for warnings (severity: Warning)
   - Filter noise (Debug.Log informational messages)

2. **Report findings** categorized by severity

### Step 4: Runtime Verification

1. **Use `Unity_ManageEditor`** action `play` to start Play Mode
2. **Wait briefly** for initialization
3. **Use `screenshot-game-view`** to capture runtime state
4. **Use `Unity_ReadConsole`** to check for runtime errors during play
5. **Use `Unity_ManageEditor`** action `stop` to exit Play Mode

### Step 5: Layer 2 Constraint Verification

For each Layer 2 requirement:
- Cross-reference test results with constraint specifications
- Note which constraints passed automated verification
- Note which aspects require screenshot review
- Attach relevant screenshots

### Step 6: Layer 3 Human Review Checklist

For each Layer 3 requirement:
- Generate a review checklist item with:
  - Requirement ID and description
  - What to evaluate (specific visual/feel criteria)
  - Attached screenshot(s) for reference
  - Pass/fail checkbox for human to complete
- Present complete checklist to user

### Step 7: Generate Validation Report

Compile all results into a structured report.

## Important Constraints
- **Non-destructive**: Do not modify any files; read and execute only
- **Layer-aware**: Different validation strategies per testability layer
- **Human gate for Layer 3**: Never auto-pass Layer 3 items
- **Screenshot evidence**: Attach screenshots for all visual validation
</instructions>

## Tool Guidance
- **Unity MCP primary**: Use run_tests, Unity_ReadConsole, Unity_ManageEditor, screenshot-game-view
- **Read for context**: Load specs and steering before validation
- **Grep for traceability**: Search codebase for requirement coverage evidence

## Output Description

Provide output in the language specified in spec.json:

1. **Test Results Summary**: EditMode pass/fail counts, PlayMode pass/fail counts
2. **Console Health**: Compilation errors (0 expected), warnings count, runtime exceptions
3. **Runtime Check**: Play mode start/stop success, screenshot attached
4. **Layer 2 Constraints**: Per-requirement pass/fail with evidence
5. **Layer 3 Review Checklist**: Human-actionable checklist with screenshots
6. **Overall Decision**: GO / NO-GO / CONDITIONAL (waiting for Layer 3 human review)

**Format**: Structured Markdown with tables and embedded screenshots

## Safety & Fallback

### Error Scenarios

**Unity MCP Not Available**:
- Check `.mcp.json` for unity-mcp configuration
- If not configured: Stop with message "Unity MCP not configured. Add unity-mcp to .mcp.json"

**Test Runner Errors**:
- If run_tests fails to execute: Report infrastructure error
- Use Unity_ReadConsole to diagnose
- Suggest: "Check Unity Test Framework package is installed"

**Play Mode Crash**:
- If Unity_ManageEditor play fails or crashes: Report as Critical
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
