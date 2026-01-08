# Feature Specification: Unified Multi-Provider Model Routing

**Feature Branch**: `[001-unified-provider-routing]`  
**Created**: 2026-01-08  
**Status**: Draft  
**Input**: User description: "Single repo, select any model for any phase; e.g., Opus 4.5 for planning and GLM 4.7 for coding. Use Auto-Claude + Z.AI with provider+model per phase."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Per-phase provider selection (Priority: P1)

As a user, I can choose provider+model per phase (spec/planning/coding/qa) in one app so I never need to launch a second repo.

**Why this priority**: Removes pipeline conflicts caused by running multiple instances for different providers.

**Independent Test**: Create a task with planning=Opus 4.5 and coding=GLM 4.7, run the pipeline, and verify logs show the correct providers per phase.

**Acceptance Scenarios**:

1. **Given** a new task, **When** I set planning=Opus and coding=GLM, **Then** the planner uses Opus and the coder uses GLM in the same run.
2. **Given** provider credentials are configured, **When** I start a build, **Then** no second app instance is required.

---

### User Story 2 - Provider-aware validation and errors (Priority: P1)

As a user, I get clear errors if a selected provider is missing credentials or is rate-limited.

**Why this priority**: Prevents long-running tasks from failing mid-phase with unclear errors.

**Independent Test**: Select GLM for coding without a GLM key and confirm the task fails fast with a clear provider-specific error.

**Acceptance Scenarios**:

1. **Given** GLM is selected but no GLM key, **When** the coding phase starts, **Then** the task fails fast with a provider-specific auth error.
2. **Given** Opus hits rate limits, **When** planning runs, **Then** the UI shows the correct provider rate-limit message and recovery options.

---

### User Story 3 - Preserve existing Claude workflows (Priority: P2)

As a user, existing Claude profiles, auto-switch behavior, and OAuth flows continue to work unchanged.

**Why this priority**: Avoids breaking established Claude-only usage.

**Independent Test**: Run a Claude-only task and verify profile switching still works.

**Acceptance Scenarios**:

1. **Given** Claude profiles exist, **When** I run a Claude-only task, **Then** behavior is unchanged.

### Edge Cases

- What happens when a phase is assigned a provider that does not support tool-calling?
- What happens when a provider becomes unavailable mid-phase?
- How do we handle mixed providers within a single task metadata file?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST support provider+model selection per phase (spec, planning, coding, qa).
- **FR-002**: System MUST run all phases from a single repo instance without conflicts.
- **FR-003**: System MUST validate provider credentials before executing a phase.
- **FR-004**: System MUST surface provider-specific rate-limit/auth errors.
- **FR-005**: System MUST preserve existing Claude-only workflows.
- **FR-006**: System MUST allow selecting any model for any phase.
- **FR-007**: System MUST define provider capability constraints (e.g., tool-calling required for coding).

### Key Entities *(include if feature involves data)*

- **ProviderProfile**: Stores provider, base URL, API key, optional model mappings.
- **PhaseRouting**: Per-phase provider+model selection used by runners.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single run can use Opus 4.5 for planning and GLM 4.7 for coding, end-to-end.
- **SC-002**: Zero need to run a second repo instance for any phase.
- **SC-003**: Provider auth/limit failures are detected with actionable UI feedback.
