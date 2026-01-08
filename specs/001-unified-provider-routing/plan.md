# Implementation Plan: Unified Multi-Provider Model Routing

**Branch**: `[001-unified-provider-routing]` | **Date**: 2026-01-08 | **Spec**: specs/001-unified-provider-routing/spec.md
**Input**: Feature specification from `/specs/001-unified-provider-routing/spec.md`

## Summary

Unify Auto-Claude into a single repo that can route provider+model per phase. Add a provider abstraction to the backend, introduce an OpenAI-compatible client for Z.AI (GLM), and extend the UI to select provider+model per phase with clear credential validation.

## Technical Context

**Language/Version**: Python backend + TypeScript/Electron frontend  
**Primary Dependencies**: claude-agent-sdk, openai (OpenAI-compatible)  
**Storage**: settings.json (app), .auto-claude/.env (project)  
**Testing**: pytest, vitest  
**Target Platform**: desktop app  
**Project Type**: web app (frontend + backend)  
**Performance Goals**: maintain current pipeline throughput  
**Constraints**: Claude OAuth flow must remain intact  
**Scale/Scope**: Single app instance handling multi-provider routing

## Constitution Check

[Gates determined based on constitution file]

## Project Structure

### Documentation (this feature)

```text
specs/001-unified-provider-routing/
├── plan.md
├── spec.md
└── tasks.md
```

### Source Code (repository root)

```text
apps/
├── backend/
│   ├── core/
│   ├── agents/
│   ├── providers/         # NEW provider routing + OpenAI-compatible client
│   └── ...
└── frontend/
    ├── src/
    │   ├── main/
    │   ├── renderer/
    │   └── shared/
```

**Structure Decision**: Extend existing backend/frontend modules; add a new providers/ module to isolate provider-specific logic.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |

## Design Overview

1) **Provider Router (backend)**
- Introduce provider normalization + credential resolution.
- Claude path uses existing `claude-agent-sdk` client.
- Z.AI path uses OpenAI-compatible API with tool-calling.

2) **Phase Routing Schema**
- Extend task metadata to include `phaseProviders` and `provider`.
- Update `phase_config.py` to resolve provider+model per phase.

3) **OpenAI-Compatible Tool Execution**
- Implement Read/Write/Edit/Glob/Grep/Bash tools with safe path and command validation.
- Filter unsupported tools for non-Claude providers.

4) **UI/Settings**
- Add provider selection per phase in Agent Profile settings.
- Add Z.AI credentials (API key + base URL) in Settings > Integrations.
- Allow free-form model IDs per phase for non-Claude providers.

5) **Preflight Validation**
- Validate provider credentials before phase start.
- Block unsupported provider/tool combinations with clear errors.

## Risks & Mitigations

- **Tool parity gaps**: Restrict OpenAI-compatible providers to supported tools; document limitations.
- **Provider outages**: Fast-fail per phase with actionable error messages.
