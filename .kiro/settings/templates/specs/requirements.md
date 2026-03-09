# Requirements Document

## Introduction
{{INTRODUCTION}}

## Requirements

### Requirement 1: {{REQUIREMENT_AREA_1}} (Layer 1 example)
<!-- Requirement headings MUST include a leading numeric ID only (for example: "Requirement 1: ...", "1. Overview", "2 Feature: ..."). Alphabetic IDs like "Requirement A" are not allowed. -->
**Objective:** As a {{ROLE}}, I want {{CAPABILITY}}, so that {{BENEFIT}}
**Testability:** Layer 1 (Fully Testable)
<!-- Layer 1: Fully Testable - Pure logic, EditMode test verifiable -->
<!-- Layer 2: Range-Testable - Constraint/range verification possible, non-testable aspects documented -->
<!-- Layer 3: Human Review - Not automatically testable, review method and criteria required -->

#### Acceptance Criteria
1. When [event], the [system] shall [response/action]
2. If [trigger], then the [system] shall [response/action]
3. While [precondition], the [system] shall [response/action]
4. Where [feature is included], the [system] shall [response/action]
5. The [system] shall [response/action]

### Requirement 2: {{REQUIREMENT_AREA_2}} (Layer 2/3 example)
**Objective:** As a {{ROLE}}, I want {{CAPABILITY}}, so that {{BENEFIT}}
**Testability:** Layer {{N}} ({{CLASSIFICATION}})

#### Acceptance Criteria
1. When [event], the [system] shall [response/action]
2. When [event] and [condition], the [system] shall [response/action]

#### Non-Testable Aspects
- [Aspect that cannot be automatically verified]
- Review method: [How human reviewer should evaluate]
- Acceptance threshold: [Specific criteria for human judgment]

<!-- Additional requirements follow the same pattern -->
<!-- All requirements MUST include Testability classification. Layer 1 requirements need only Acceptance Criteria. Layer 2/3 requirements MUST include Non-Testable Aspects section. -->
