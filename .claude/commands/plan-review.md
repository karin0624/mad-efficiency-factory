---
description: Send a plan file to Codex CLI for independent review and incorporate feedback
allowed-tools: Bash, Read, Edit, Glob, Grep
argument-hint: <plan-file-or-name> [--dry-run]
---

# Plan Review via Codex CLI

<background_information>
- **Mission**: Get an independent second opinion on a plan file from Codex CLI (OpenAI), then incorporate valid feedback to improve the plan
- **Success Criteria**:
  - Plan file is sent to Codex for structured review
  - Review covers: feasibility, completeness, risks, missing items, suggestions
  - Valid feedback is incorporated back into the plan (default)
  - User sees both the review and what was changed
</background_information>

<instructions>
## Core Task
Review plan file using Codex CLI and incorporate feedback. Argument: **$ARGUMENTS**

## Execution Steps

### Step 1: Parse Arguments
- Split `$ARGUMENTS` into plan identifier and flags
- Detect `--dry-run` flag (if present, skip plan modification step)
- The remaining argument is the plan file identifier

### Step 2: Resolve Plan File Path
- If identifier contains `/` or ends with `.md`: use as-is (relative to workspace root)
- Otherwise: resolve to `docs/plans/<identifier>.md`
- If file not found: use Glob `docs/plans/*<identifier>*` to search
- If still not found: list available plans in `docs/plans/` and stop

### Step 3: Read Plan Content
- Use Read tool to load the full plan file
- Store the content for prompt construction

### Step 4: Verify Codex Availability
- Run `which codex` via Bash
- If not found, stop with error: "codex CLI is not installed. Install it with: npm install -g @openai/codex"

### Step 5: Execute Codex Review
- Construct the review prompt (see Review Prompt section below)
- Write the prompt to a temporary file to avoid shell escaping issues
- Execute:
  ```bash
  codex exec --ephemeral -s read-only -C "$(pwd)" -o /tmp/codex-plan-review.txt - < /tmp/codex-plan-review-prompt.txt
  ```
- Read the output from `/tmp/codex-plan-review.txt`

### Step 6: Present Review Results
- Display the Codex review to the user with a header indicating:
  - Which plan was reviewed
  - Reviewer: Codex CLI

### Step 7: Incorporate Feedback (default behavior)
- **Skip this step if `--dry-run` was specified** — just display results and stop
- Analyze the Codex review feedback
- Identify actionable improvements:
  - Missing steps or considerations to add
  - Risks or issues to address in the plan
  - Structural improvements
  - Corrections to inaccuracies
- Use Edit tool to modify the plan file, incorporating valid feedback
- Show a brief summary of what was changed to the user
- Do NOT blindly apply all suggestions — use judgment to filter out:
  - Subjective style preferences
  - Suggestions that contradict the plan's intent
  - Overly speculative concerns

## Review Prompt Template
Use this prompt structure when sending to Codex:

```
You are a senior technical reviewer. Review the following implementation plan and provide structured, actionable feedback.

## Plan to Review

<plan>
{PLAN_CONTENT}
</plan>

## Review Criteria

Evaluate across these dimensions:

### 1. Feasibility
- Can this plan be implemented as described?
- Are the technical approaches sound?
- Are there unrealistic assumptions?

### 2. Completeness
- Are all necessary steps covered?
- Are dependencies identified?
- Is the sequencing logical?

### 3. Risks and Issues
- What could go wrong?
- Are there edge cases not addressed?
- Performance, security, or maintainability concerns?

### 4. Missing Items
- What should be covered but isn't?
- Are prerequisite tasks missing?
- Are error handling and rollback strategies addressed?

### 5. Suggestions
- Specific, concrete improvements
- Alternative approaches worth considering
- Priority recommendations

## Output Format

Provide your review as structured Markdown:
- A section for each dimension above
- Concrete, actionable feedback (not vague)
- Overall assessment: APPROVE / REVISE / REJECT with brief rationale
- Keep concise but thorough (300-500 words)
```

## Important Constraints
- Codex runs in **read-only sandbox** — it cannot modify the workspace
- Session is **ephemeral** — no persistent state
- Use a temp file for the prompt to avoid shell escaping issues with plan content
- Clean up temp files after execution
- Default is to incorporate feedback; `--dry-run` skips modification
- When incorporating feedback, preserve the plan's original structure and intent
</instructions>

## Tool Guidance
- **Read**: Load plan file content and Codex output
- **Bash**: Execute `codex exec`, write temp files, verify codex installation
- **Edit**: Modify plan file to incorporate review feedback
- **Glob**: Find plan files when identifier doesn't match exactly
- **Grep**: Search for related context if needed during feedback incorporation

## Output Description
1. **Review Header**: Which plan was reviewed, reviewer identification
2. **Codex Review**: Full structured review from Codex
3. **Changes Made** (unless `--dry-run`): Summary of modifications applied to the plan

## Safety & Fallback

### Error Scenarios
- **Plan not found**: Show resolved path, list available plans in `docs/plans/`
- **Codex not installed**: Stop with install instructions
- **Codex execution failure**: Show stderr, suggest retrying
- **Empty output**: Warn user, suggest checking codex configuration
- **Temp file issues**: Use `/tmp/` which is always writable
