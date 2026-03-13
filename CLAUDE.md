# Spec-Driven Development (AI-DLC)

## Paths
- Steering: `.kiro/steering/` — project-wide rules and context
- Specs: `.kiro/specs/` — per-feature development specs

## Language
Think in English, respond in Japanese. Project files (requirements.md, design.md, tasks.md等) are written in the language set by `spec.json.language`.

## Workflow
Flow: Requirements → Design → Tasks → Implementation. Human review required each phase (`-y` skips review).
Spec slash commands (`/kiro:spec-*`, `/kiro:validate-*`, `/kiro:steering*`) are defined in `.claude/commands/kiro/`.

## Knowledge Management
- Use `remember` / `recall` / `forget` / `update_memory` / `list_memories` MCP tools for persistent knowledge.
- Before starting work, `recall` relevant context. After learning something reusable, `remember` it.
- Types: `user` (about user), `feedback` (corrections), `project` (project context), `reference` (external pointers).

## Rules
- Act autonomously within the user's instructions. Ask only when essential info is missing.
- Load `.kiro/steering/` as project memory when contextually relevant.
