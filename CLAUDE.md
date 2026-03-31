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
- 設計判断が発生した場合、`.kiro/settings/rules/decision-criteria.md` の基準でADR必要性を評価。トリガー条件の詳細と判断基準は同ファイルに委譲。
- ADRが必要と判断した場合は `/kiro:decision-create` を実行。ADRは `.kiro/decisions/` に格納。
- 方針変更を検討する際は `.kiro/decisions/` の既存ADRを参照し、過去の意思決定との整合性を確認。

## Rules
- Act autonomously within the user's instructions. Ask only when essential info is missing.
- Load `.kiro/steering/` as project memory when contextually relevant.
