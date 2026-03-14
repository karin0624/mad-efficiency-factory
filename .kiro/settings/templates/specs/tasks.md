# Implementation Plan

## Task Format Template

Use whichever pattern fits the work breakdown:

### Major task only
- [ ] {{NUMBER}}. {{TASK_DESCRIPTION}}{{PARALLEL_MARK}}
  - {{DETAIL_ITEM_1}} *(Include details only when needed. If the task stands alone, omit bullet items.)*
  - _Requirements: {{REQUIREMENT_IDS}}_

### Major + Sub-task structure
- [ ] {{MAJOR_NUMBER}}. {{MAJOR_TASK_SUMMARY}}
- [ ] {{MAJOR_NUMBER}}.{{SUB_NUMBER}} {{SUB_TASK_DESCRIPTION}}{{SUB_PARALLEL_MARK}}
  - {{DETAIL_ITEM_1}}
  - {{DETAIL_ITEM_2}}
  - _Requirements: {{REQUIREMENT_IDS}}_ *(IDs only; do not add descriptions or parentheses.)*

> **Parallel marker**: Append ` (P)` only to tasks that can be executed in parallel. Omit the marker when running in `--sequential` mode.
>
> **Optional test coverage**: When a sub-task is deferrable test work tied to acceptance criteria, mark the checkbox as `- [ ]*` and explain the referenced requirements in the detail bullets.

### Layer 3: E2E Checkpoint

```markdown
- [ ] X.Y E2E checkpoint: [検証内容の説明]
  - SceneRunnerでフルシーンを起動し、スクショを `godot/test_screenshots/<name>.png` に保存
  - AI（Readツール）でスクショを評価: [具体的な評価ポイント]
  - _Requirements: N.N_
```

### Layer 4: Human Review

```markdown
- [ ] X.Y Human review: [評価基準の説明]
  - [評価方法]
  - [受け入れ閾値]
  - _Requirements: N.N_
```
