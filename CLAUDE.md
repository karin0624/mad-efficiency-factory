# Spec-Driven Development (AI-DLC)

## Paths
- Steering: `.kiro/steering/` — project-wide rules and context
- Specs: `.kiro/specs/` — per-feature development specs
- SDD commands: `.claude/commands/sdd/` — pipeline orchestrators (implement, modify, resume, status)
- Kiro commands: `.claude/commands/kiro/` — individual spec phase commands

## Language
Think in English, respond in Japanese. Project files (requirements.md, design.md, tasks.md etc.) are written in the language set by `spec.json.language`.

## Workflow
Flow: Requirements → Design → Tasks → Implementation. Human review required each phase (`-y` skips review).

- **SDD pipelines** (`/sdd:implement`, `/sdd:modify`) are the primary entry points. They orchestrate the full flow via MCP tools (`sdd_start` / `sdd_resume` / `sdd_status`).
  - `/sdd:implement` — end-to-end: Preflight → Plan → Worktree → Spec → Implement → Verify → PR
  - `/sdd:modify` — delta changes to existing specs: Impact Analysis → ADR → Spec Update → Implement → Verify → PR
  - `/sdd:resume` — resume a paused pipeline session
  - `/sdd:status` — show pipeline session status
- **Kiro commands** (`/kiro:spec-*`, `/kiro:validate-*`, `/kiro:steering*`) handle individual spec phases when granular control is needed.

## Knowledge Management
Use the MCP memory tools (`remember` / `recall` / `forget` / `update_memory` / `list_memories`) as your persistent brain.

### What NOT to save
Before saving, ask: **"Could a future session derive this by reading the code or git history?"** If yes, do NOT save it.
- Code patterns, architecture snapshots, API listings — read the code instead
- Implementation/completion logs — check git log instead
- Config summaries, file structure — read the files instead
- Anything that becomes wrong when the code changes

### What TO save
- **Decision rationale**: Why a choice was made (not what the code looks like)
- **User corrections/feedback**: "Don't do X", "Use Y instead" → type: `feedback`
- **User preferences/role**: Job role, expertise, communication style → type: `user`
- **Non-obvious gotchas**: Things that surprised you and aren't documented
- **External references**: URLs, service names, dashboard locations → type: `reference`

### When to `recall`
- **Every conversation start**: Always `recall` with a broad query to load prior context.
- **Before modifying code**: Recall relevant project/feedback memories to avoid repeating past mistakes.

### Rules
- Prefer `update_memory` over creating duplicates. Check existing memories first with `recall` or `list_memories`.
- Keep memories atomic — one concept per memory. Use clear, searchable names.
- Include **why** in every memory, not just **what**. The reason is what makes it useful later.

## Decision Records
- When a design decision arises, evaluate ADR necessity using the criteria in `.kiro/settings/rules/decision-criteria.md`. Trigger conditions and judgment criteria are delegated to that file.
- If an ADR is warranted, run `/kiro:decision-create`. ADRs are stored in `.kiro/decisions/`.
- When considering policy changes, review existing ADRs in `.kiro/decisions/` to ensure consistency with past decisions.

## General Rules
- Act autonomously within the user's instructions. Ask only when essential info is missing.
- Load `.kiro/steering/` as project memory when contextually relevant.
