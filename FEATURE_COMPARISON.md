# Auto-Claude Feature Comparison

**Local Repository** vs **Upstream Repository** (https://github.com/AndyMik90/Auto-Claude.git)

**Generated**: 2026-01-08  
**Local Version**: Based on codebase analysis  
**Upstream Version**: v2.7.2 (latest stable)

---

## Feature Status Legend

- ✅ **Both Repos** - Feature exists in both local and upstream
- 🟡 **Local Only** - Feature exists only in local repository
- 🔵 **Upstream Only** - Feature exists only in upstream repository
- 🚧 **Local (WIP)** - Feature in development in local repository

---

## Core Features

| Feature | Status | Notes |
|---------|--------|-------|
| **Autonomous Tasks** | ✅ Both Repos | Describe goal; agents handle planning, implementation, validation |
| **Parallel Execution** | ✅ Both Repos | Run multiple builds simultaneously with up to 12 agent terminals |
| **Isolated Workspaces** | ✅ Both Repos | All changes happen in git worktrees - main branch stays safe |
| **Self-Validating QA** | ✅ Both Repos | Built-in quality assurance loop catches issues before review |
| **AI-Powered Merge** | ✅ Both Repos | Automatic conflict resolution when integrating back to main |
| **Memory Layer (Graphiti)** | ✅ Both Repos | Agents retain insights across sessions for smarter builds |
| **Cross-Platform** | ✅ Both Repos | Native desktop apps for Windows, macOS, and Linux |
| **Auto-Updates** | ✅ Both Repos | App updates automatically when new versions are released |

---

## Integrations

| Feature | Status | Notes |
|---------|--------|-------|
| **GitHub Integration** | ✅ Both Repos | Import issues, investigate with AI, create merge requests |
| **GitLab Integration** | ✅ Both Repos | GitLab support for issues and merge requests |
| **Linear Integration** | ✅ Both Repos | Sync tasks with Linear for team progress tracking |
| **Graphiti Memory System** | ✅ Both Repos | Knowledge graph with semantic search (LadybugDB embedded) |
| **Electron MCP** | ✅ Both Repos | E2E testing integration for QA agents (Chrome DevTools Protocol) |

---

## UI Features

| Feature | Status | Notes |
|---------|--------|-------|
| **Kanban Board** | ✅ Both Repos | Visual task management from planning through completion |
| **Agent Terminals** | ✅ Both Repos | AI-powered terminals with one-click task context injection |
| **Roadmap** | ✅ Both Repos | AI-assisted feature planning with competitor analysis |
| **Insights** | ✅ Both Repos | Chat interface for exploring your codebase |
| **Ideation** | ✅ Both Repos | Discover improvements, performance issues, vulnerabilities |
| **Changelog** | ✅ Both Repos | Generate release notes from completed tasks |
| **Project Tabs** | ✅ Both Repos | Persistent tab management with GitHub organization initialization |
| **Task Creation Wizard** | ✅ Both Repos | Enhanced with drag-and-drop, file references, @ mentions |
| **Internationalization (i18n)** | ✅ Both Repos | Multi-language support (English, French) |
| **UI Scale** | ✅ Both Repos | 75-200% range for accessibility |
| **Theme System** | ✅ Both Repos | Multiple color schemes (Forest, Neo, Retro, Dusk, Ocean, Lime) |

---

## Memory & AI Providers

| Feature | Status | Notes |
|---------|--------|-------|
| **Graphiti Multi-Provider Support** | ✅ Both Repos | OpenAI, Anthropic, Azure OpenAI, Ollama, Google AI, OpenRouter |
| **OpenRouter Support** | ✅ Both Repos | LLM/embedding provider for Graphiti memory |
| **Ollama Support** | ✅ Both Repos | Local LLM and embedding provider |
| **Google AI (Gemini)** | ✅ Both Repos | LLM and embedding provider |
| **Voyage AI Embeddings** | ✅ Both Repos | Embedding provider (commonly used with Anthropic) |
| **Azure OpenAI** | ✅ Both Repos | LLM and embedding provider |
| **Z.AI/GLM Provider** | 🟡 Local Only | ZhipuAI GLM models integration (spec 001-unified-provider-routing) |
| **Per-Phase Provider Routing** | 🚧 Local (WIP) | Select different providers per phase (spec/planning/coding/qa) |

---

## Backend Features

| Feature | Status | Notes |
|---------|--------|-------|
| **Claude Agent SDK Integration** | ✅ Both Repos | All AI interactions use Claude Agent SDK |
| **Dynamic Command Allowlist** | ✅ Both Repos | Security based on detected project stack |
| **Phase Configuration** | ✅ Both Repos | Customizable phase configuration in app settings |
| **Agent Profiles** | ✅ Both Repos | Selectable agent profiles with model selection |
| **Spec Creation Pipeline** | ✅ Both Repos | Dynamic 3-8 phase pipeline based on task complexity |
| **QA Loop** | ✅ Both Repos | QA Reviewer and QA Fixer agents with E2E testing |
| **Recovery System** | ✅ Both Repos | Agent recovery from stuck/failed subtasks |
| **Provider Abstraction Layer** | 🟡 Local Only | Provider routing infrastructure (spec 001) |
| **OpenAI-Compatible Client** | 🟡 Local Only | For Z.AI and other OpenAI-compatible providers |
| **Provider Config Helpers** | 🟡 Local Only | `apps/backend/core/provider_config.py` |

---

## Security & Infrastructure

| Feature | Status | Notes |
|---------|--------|-------|
| **Three-Layer Security Model** | ✅ Both Repos | OS Sandbox, Filesystem Restrictions, Command Allowlist |
| **OAuth Authentication** | ✅ Both Repos | Claude account OAuth on onboarding |
| **Device Code Authentication** | ✅ Both Repos | Device code flow with timeout handling |
| **Secret Scanning** | ✅ Both Repos | Security scanning for secrets |
| **VirusTotal Scanning** | ✅ Both Repos | Release artifacts scanned before publishing |

---

## Development & Build

| Feature | Status | Notes |
|---------|--------|-------|
| **Python 3.12 Bundled** | ✅ Both Repos | Python 3.12 bundled with packaged Electron app |
| **Flatpak Support** | ✅ Both Repos | Linux Flatpak packaging |
| **CLI Tool Path Management** | ✅ Both Repos | Centralized CLI tool path management |
| **Project Stack Detection** | ✅ Both Repos | Auto-detect project type and stack |
| **iOS/Swift Detection** | ✅ Both Repos | iOS/Swift project detection |
| **Bun Support** | ✅ Both Repos | Bun 1.2.0+ lock file format detection |

---

## GitHub/PR Features

| Feature | Status | Notes |
|---------|--------|-------|
| **Automated PR Review** | ✅ Both Repos | AI-powered PR review with follow-up support |
| **PR Review Filtering** | ✅ Both Repos | Enhanced PR review page with filtering capabilities |
| **PR Review Isolation** | ✅ Both Repos | Uses temporary worktree for PR review |
| **GitHub Bot Detection** | ✅ Both Repos | Detect and handle GitHub bot comments |
| **PR Follow-up Support** | ✅ Both Repos | Structured outputs for PR reviews |

---

## Local-Only Features (Not in Upstream)

### 1. Z.AI/GLM Provider Integration 🟡
- **Location**: `apps/backend/core/provider_config.py`, `apps/backend/providers/openai_compat.py`
- **Status**: Implementation in progress (spec 001-unified-provider-routing)
- **Description**: Integration with ZhipuAI (Z.AI) GLM models as an alternative provider
- **Features**:
  - Z.AI API key configuration
  - Base URL configuration (default: `https://open.bigmodel.cn/api/anthropic`)
  - GLM model support (GLM-4.7, GLM-4.5, GLM-4, etc.)
  - OpenAI-compatible client for Z.AI
  - Model name mapping (Claude model names → GLM model names)

### 2. Unified Multi-Provider Model Routing 🚧
- **Location**: `specs/001-unified-provider-routing/`
- **Status**: Work in Progress (Draft spec)
- **Description**: Per-phase provider selection allowing different providers for spec/planning/coding/qa phases
- **Features**:
  - Select provider+model per phase
  - Single repo instance for all providers
  - Provider-aware validation and error handling
  - Preserve existing Claude workflows
- **User Stories**:
  - US1: Per-phase provider selection (e.g., Opus 4.5 for planning, GLM 4.7 for coding)
  - US2: Provider-aware validation and errors
  - US3: Preserve existing Claude workflows

### 3. Provider Abstraction Layer 🟡
- **Location**: `apps/backend/core/provider_config.py`, `apps/backend/providers/`
- **Status**: Implementation in progress
- **Description**: Infrastructure for routing requests to different AI providers
- **Components**:
  - Provider config helpers
  - OpenAI-compatible client wrapper
  - Provider detection and routing logic
  - Model name mapping utilities

### 4. Phase Provider Configuration 🟡
- **Location**: `apps/backend/phase_config.py`
- **Status**: Implementation in progress
- **Description**: Extend phase configuration to support per-phase provider selection
- **Features**:
  - `phaseProviders` configuration in task metadata
  - Provider-aware model resolution per phase
  - Default provider fallbacks

---

## Features Present in Both Repos

All standard features from the upstream repository are present in the local version, including:

- ✅ All core autonomous coding features
- ✅ All integrations (GitHub, GitLab, Linear, Graphiti)
- ✅ All UI features (Kanban, Terminals, Roadmap, Insights, Ideation)
- ✅ All memory system features (multi-provider Graphiti support)
- ✅ All security features
- ✅ All development/build features
- ✅ All GitHub/PR review features
- ✅ Electron MCP for E2E testing
- ✅ Internationalization (i18n)
- ✅ Theme system
- ✅ Auto-updates

---

## Summary

### Local Repository Additions
The local repository includes **4 additional features** not present in upstream:

1. **Z.AI/GLM Provider Integration** (🟡 Local Only) - Functional implementation
2. **Unified Multi-Provider Model Routing** (🚧 Local WIP) - Spec and partial implementation
3. **Provider Abstraction Layer** (🟡 Local Only) - Infrastructure code
4. **Phase Provider Configuration** (🟡 Local Only) - Configuration extensions

### Upstream Repository
The upstream repository (v2.7.2) contains all standard features and is the stable, production-ready version. The local repository appears to be a fork with experimental multi-provider routing features in development.

### Recommendation
If you want to contribute the multi-provider routing features back to upstream, ensure:
1. Complete the implementation of spec 001-unified-provider-routing
2. Add comprehensive tests
3. Update documentation
4. Follow the upstream contribution guidelines (target `develop` branch, not `main`)

---

## Notes

- **Spec 001 Status**: The unified provider routing feature is documented in `specs/001-unified-provider-routing/` but appears to be in draft/development status
- **Provider Support**: Local version has Z.AI provider code, but the full per-phase routing feature is still WIP
- **Backward Compatibility**: The implementation preserves existing Claude-only workflows (US3 requirement)
- **Testing**: Multi-provider routing requires end-to-end testing with mixed providers (Opus + GLM in same run)

---

**Last Updated**: 2026-01-08  
**Comparison Method**: Codebase analysis + upstream README/CHANGELOG review
