---

description: "Task list for unified multi-provider routing"
---

# Tasks: Unified Multi-Provider Model Routing

**Input**: Design documents from `/specs/001-unified-provider-routing/`  
**Prerequisites**: plan.md (required), spec.md (required for user stories)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Phase 1: Backend Foundation (US1)

- [ ] T001 [US1] Add provider config helpers in `apps/backend/core/provider_config.py`
- [ ] T002 [US1] Add OpenAI-compatible client in `apps/backend/providers/openai_compat.py`
- [ ] T003 [US1] Wire provider routing into `apps/backend/core/client.py` and `apps/backend/core/simple_client.py`
- [ ] T004 [US1] Add OpenAI dependency in `apps/backend/requirements.txt`

## Phase 2: Phase Routing + CLI (US1, US2)

- [ ] T005 [US1] Extend `apps/backend/phase_config.py` with `phaseProviders` and provider-aware model resolution
- [ ] T006 [US1] Pass provider through spec and build pipelines (`apps/backend/spec/pipeline/*`, `apps/backend/agents/*`, `apps/backend/qa/*`)
- [ ] T007 [US2] Add CLI `--provider` and provider-aware validation in `apps/backend/cli/*` and `apps/backend/runners/spec_runner.py`
- [ ] T008 [US2] Update `apps/backend/spec/compaction.py` to support provider selection

## Phase 3: Frontend UI + Settings (US1, US2, US3)

- [ ] T009 [US1] Add provider types and defaults in `apps/frontend/src/shared/types/*` and `apps/frontend/src/shared/constants/*`
- [ ] T010 [US1] Update Agent Profile settings + selector to support per-phase provider selection
- [ ] T011 [US1] Update Task creation/edit flows to store `provider` and `phaseProviders`
- [ ] T012 [US2] Add Z.AI API key + base URL in Integration settings and persist in settings store
- [ ] T013 [US1] Pass provider/env to backend processes in `apps/frontend/src/main/agent/*`
- [ ] T014 [US3] Preserve Claude auth checks when Claude is selected, skip otherwise

## Phase 4: Validation + Polish (US2, US3)

- [ ] T015 [US2] Add provider-specific error messages for missing credentials in backend validation
- [ ] T016 [US3] Update documentation snippets in `apps/backend/.env.example` and i18n labels
- [ ] T017 [US1] Manual verification: Opus planning + GLM coding end-to-end
