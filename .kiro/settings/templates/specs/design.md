# Design Document Template

---
**Purpose**: コードから復元不可能な「判断」のみを記録する。実装詳細・具体的シグネチャ・図はコードやツールから復元可能なため含めない。

**Approach**:
- 「この要素を削除したら、なぜそう設計したか分からなくなるか？」— Yes なら残す
- コードから読み取れる情報（依存関係、シグネチャ、データモデル等）は書かない
- Mermaid図、traceability表、具体的コード例は含めない
- Match detail level to feature complexity

**Warning**: Approaching 500 lines indicates excessive scope that may require design simplification.
---

## Overview
2-3 paragraphs max
**Purpose**: This feature delivers [specific value] to [target users].
**Users**: [Target user groups] will utilize this for [specific workflows].
**Impact** (if applicable): Changes the current [system state] by [specific modifications].

### Goals
- Primary objective 1
- Primary objective 2
- Success criteria

### Non-Goals
- Explicitly excluded functionality
- Future considerations outside current scope
- Integration points deferred

## Architecture

### Architecture Pattern
**Selected pattern**: [name]
**Rationale**: Why this pattern was chosen over alternatives. Include trade-offs considered.

- Domain/feature boundaries: [how responsibilities are separated]
- Existing patterns preserved: [list key patterns]
- New components rationale: [why each is needed]

### Technology Stack

| Layer | Choice / Version | Role in Feature | Selection Rationale |
|-------|------------------|-----------------|---------------------|
| Simulation / Core Logic | | | |
| Presentation / UI | | | |
| Data / Storage | | | |
| Events / Messaging | | | |
| Infrastructure / Runtime | | | |

## Components

Provide a quick reference of components involved in this feature.

| Component | Domain/Layer | Intent | Req Coverage |
|-----------|--------------|--------|--------------|
| ExampleComponent | UI | Displays XYZ | 1, 2 |

Only components introducing new boundaries require detailed blocks below. Simple components can rely on the summary row.

### [Domain / Layer]

#### [Component Name]

| Field | Detail |
|-------|--------|
| Intent | 1-line description of the responsibility |
| Requirements | 2.1, 2.3 |

**Responsibilities & Constraints**
- Primary responsibility
- Domain boundary and transaction scope
- Data ownership / invariants

## Error Handling Strategy

### Error Categories
**User Errors** (4xx): Invalid input, unauthorized, not found — policy and user-facing behavior
**System Errors** (5xx): Infrastructure failures, timeouts, exhaustion — degradation strategy
**Business Logic Errors** (422): Rule violations, state conflicts — handling policy

### Recovery Strategy
- Retry policy and circuit breaker decisions
- Graceful degradation approach
- Error propagation boundaries

## Testing Strategy

### Layer 1: Unit Tests (Pure Logic)
- Target: Calculation logic, state machines, data validation, domain models
- Framework: Appropriate test framework for the project's language/runtime
- List 3-5 specific test targets from this feature's core logic

### Layer 2: Integration Tests (Constraint Verification)
- Target: Component integration, behavior range checks, layout/rendering validation
- List 3-5 constraint verification targets

### Layer 3: E2E Test (Screenshot + AI Visual Evaluation)
- Target: Visual quality verifiable via screenshots, performance metrics, scene-level behavior
- Framework: GdUnit4 SceneRunner + xvfb-run + AI evaluation (Read tool)
- Screenshot save path: `godot/test_screenshots/`
- List 2-4 specific E2E test targets

### Layer 4: Human Review (Non-Testable)
- Target: Subjective quality, game feel, art direction alignment
- List items requiring human judgment with specific review criteria

## Optional Sections (include when relevant)

### Security Considerations
_Include for features handling auth, sensitive data, external integrations, or user permissions. Policy-level decisions only._
- Threat model decisions and security control choices
- Authentication and authorization pattern selection
- Data protection policy decisions

### Performance & Scalability
_Include when performance targets, high load, or scaling concerns exist. Target values and policy only._
- Target metrics (specific numbers/thresholds)
- Scaling approach decisions (horizontal/vertical)
- Caching strategy choices and rationale
