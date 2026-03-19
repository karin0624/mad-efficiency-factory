# Spec-Driven Development (AI-DLC)

## Paths
- Steering: `.kiro/steering/` — project-wide rules and context
- Specs: `.kiro/specs/` — per-feature development specs

## Language
Think in English, respond in Japanese. Project files (requirements.md, design.md, tasks.md等) are written in the language set by `spec.json.language`.

## Workflow
Flow: Requirements → Design → Tasks → Implementation. Human review required each phase (`-y` skips review).
Spec slash commands (`/kiro:spec-*`, `/kiro:validate-*`, `/kiro:steering*`) are defined in `.claude/commands/kiro/`.

## Knowledge Management (MANDATORY)
Use the MCP memory tools (`remember` / `recall` / `forget` / `update_memory` / `list_memories`) as your persistent brain. These are NOT optional — they are a core part of how you operate in this project.

### When to `recall`
- **Every conversation start**: Always `recall` with a broad query (e.g., the user's request keywords) to load prior context.
- **Before modifying code**: Recall relevant project/feedback memories to avoid repeating past mistakes.

### When to `remember` (ALWAYS do this — do NOT skip)
You MUST call `remember` when ANY of the following occur during a conversation:
- **User corrections/feedback**: "Don't do X", "Use Y instead", "That's wrong because..." → type: `feedback`
- **User preferences or role info**: Job role, expertise level, communication style → type: `user`
- **Project decisions**: Architecture choices, tool selections, why something was done a certain way → type: `project`
- **External resource pointers**: URLs, service names, dashboard locations → type: `reference`
- **Non-obvious learnings**: Anything you discovered that isn't obvious from the code alone.

Do NOT wait for the user to say "remember this". Proactively save knowledge as it emerges.

### Memory types
- `user`: About the user — role, preferences, expertise, communication style.
- `feedback`: Corrections to Claude's behavior — what to do/not do and why.
- `project`: Project context — decisions, goals, constraints, architecture rationale.
- `reference`: Pointers to external resources — URLs, dashboards, issue trackers.

### Rules
- Prefer `update_memory` over creating duplicates. Check existing memories first with `recall` or `list_memories`.
- Keep memories atomic — one concept per memory. Use clear, searchable names.
- Include **why** in every memory, not just **what**. The reason is what makes it useful later.

## Decision Records
- 設計判断が発生した場合、`.kiro/settings/rules/decision-criteria.md` の基準でADR必要性を評価。トリガー条件の詳細と判断基準は同ファイルに委譲。
- ADRが必要と判断した場合は `/kiro:decision-create` を実行。ADRは `.kiro/decisions/` に格納。
- 方針変更を検討する際は `.kiro/decisions/` の既存ADRを参照し、過去の意思決定との整合性を確認。

## Rules
- Act autonomously within the user's instructions. Ask only when essential info is missing.
- Load `.kiro/steering/` as project memory when contextually relevant.
