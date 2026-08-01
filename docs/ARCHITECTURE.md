# Arynox AI — Architecture

## Overview

Arynox AI is a local-first platform where a user describes a software project in natural language and multiple specialized AI agents plan, build, test and debug it inside an isolated workspace. All orchestration, persistence, and safety enforcement happens in the backend; the frontend is a thin IDE-style client.

```
┌──────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                    │
│  Monaco editor · file explorer · chat · terminal · git   │
└───────────────┬───────────────────────────┬──────────────┘
                │ REST (JSON)               │ SSE stream
┌───────────────▼───────────────────────────▼──────────────┐
│                     Backend (FastAPI)                     │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐ ┌───────────┐ │
│  │  API     │ │Orchestrator│ │  Agents    │ │ Providers │ │
│  │ routers  │ │  intent   │ │  (8 types) │ │ ollama    │ │
│  └────┬─────┘ └────┬─────┘ └──────┬──────┘ │ openai    │ │
│       │            │              │        │ openrouter│ │
│  ┌────▼─────┐ ┌────▼─────┐ ┌──────▼──────┐ └─────┬─────┘ │
│  │ Services │ │  Tools   │ │   Security  │       │       │
│  │ workspace│ │ registry │ │ allow/deny  │  ┌────▼─────┐ │
│  │ git      │ │ files    │ │ approvals   │  │   MCP    │ │
│  │ context  │ │ commands │ │ modes       │  │ bridge   │ │
│  └────┬─────┘ └──────────┘ └──────┬──────┘  └──────────┘ │
│  ┌────▼───────────────────────────▼──────┐                │
│  │            SQLite (SQLAlchemy)        │                │
│  └────────────────────────────────────────┘               │
└───────────────────────────────────────────────────────────┘
```

## Key flows

### 1. User request → agent pipeline

`POST /api/projects/{id}/chat` spawns a background orchestrator task:

1. User message is persisted to the conversation.
2. Intent detection (`app/orchestrator/intent.py`) classifies the request: `build`, `plan`, `code`, `debug`, `test`, `review`, `document`, `architect`, `product`.
3. A sequence of agents runs (e.g. `build` on a new project → Product Manager → Architect → Planner → Coding ×N → Testing).
4. Every agent run is a row in `agent_runs`; every AI call, tool use, approval and error is persisted and streamed via SSE.

### 2. Change proposal & approval

Coding/Debugging/Architecture/Docs agents return structured JSON (`files[]`, `commands[]`). The backend (`agents/base.py::propose_changes`) computes unified diffs and:

- `ask` mode → stores a `plan_changes` row, emits `changes.proposed`, waits for the user (SSE), then applies or rejects.
- `auto` mode → applies immediately.
- The workspace is a git repo, so every applied change set is reversible.

### 3. Command execution & safety

`security/command_safety.py`:

- **Denylist** (always blocked): destructive filesystem ops, shutdown/reboot, disk formatting, fork bombs, `curl | sh`, encoded PowerShell, credential exfiltration, `git push`.
- **Allowlist**: common dev commands (`pytest`, `python`, `npm`, `git status/diff/log/add/commit/...`).
- Modes: `safe` (allowlist only) · `ask` (default; non-allowlisted commands → `command_approvals` row + SSE `permission.request`) · `auto` (deny-list only).
- Execution is async subprocess with streaming output, bounded by timeout, always `cwd` = the project's `source/` directory.

### 4. Model management

`app/api/models.py` + `app/providers/ollama.py`:

- `GET /api/models/system-check` detects OS/RAM/GPU and recommends a model.
- `ensure_model()` auto-pulls missing Ollama models (streaming progress via SSE `model.pull`).
- `GET /api/models/available?provider=…` lists models per provider; `POST /api/models/test` validates a model responds.

## Providers

`app/providers/` implements the `AIProvider` interface (`chat`, `stream_chat`, `list_models`, `is_available`, plus `generate_plan/generate_code/analyze_code` defaults):

- `ollama.py` — `POST /api/chat` (+ `/api/pull` for auto-download).
- `openai_compat.py` — any OpenAI-compatible `/chat/completions` (SSE streaming).
- `openrouter.py` — subclass with default base URL/headers.
- Factory in `providers/__init__.py` selects by `AI_PROVIDER` env var; adding a provider = implement the interface + register.

## Agents

Each agent (`app/agents/`) is a class with a system prompt + `run(ctx)`. Agents receive a **context bundle** (`services/context.py`) instead of the whole project: project metadata, task list, recent conversation, and only the most relevant files (keyword scoring of paths against the task). The model returns strict JSON, parsed with tolerant extraction (`providers/json_utils.py`), with one retry on malformed output.

| Agent | Output |
|---|---|
| product_manager | `docs/requirements.md`, clarifying questions |
| architect | `docs/architecture.md`, `docs/database-schema.md`, `docs/api-specification.md` |
| planner | `tasks[]` persisted to `tasks` table |
| coder | `files[]` + `commands[]` + `tests[]` (approval flow) |
| tester | detects framework (pytest/npm test), runs tests, parses pass/fail |
| debugger | root cause + `fixes[]` + `verify[]` |
| reviewer | critical/warnings/suggestions JSON |
| documentation | README.md, setup, architecture docs |

## Data model

`projects` · `conversations` · `messages` · `agent_runs` · `tasks` · `file_meta` · `tool_calls` · `test_runs` · `error_logs` · `project_settings` · `command_approvals` · `checkpoints` · `plan_changes`

SQLAlchemy ORM with SQLite (`WAL` mode) by default; swap `DATABASE_URL` for PostgreSQL without code changes.

## Streaming (SSE)

`app/events.py` — per-project pub/sub of asyncio queues. Events: `agent.status`, `chat.message`, `command.output/finish`, `permission.request/response`, `changes.proposed/applied/rejected`, `test.result`, `run.status`, `plan.created`, `model.pull`, `file.changed`. The frontend `EventSource` consumes them and updates the store.

## Frontend

`src/store/ide.ts` (zustand) holds all UI state; `src/lib/api.ts` REST client; `src/lib/sse.ts` EventSource with auto-reconnect. Layout: left sidebar (Files/Tasks/Agents/Git), center Monaco + terminal, right chat panel, modal dialogs for diffs and permission requests.

## Directory layout

```
backend/
  app/
    api/           # FastAPI routers (projects, files, git, models, approvals, settings)
    agents/        # 8 agents + base (ChangeSet/approval flow)
    orchestrator/  # intent detection + pipeline sequencing
    providers/     # AI provider abstraction + implementations
    tools/         # file tools + registry
    security/      # command safety, allowlist/denylist, modes
    services/      # workspace, git, checkpoints, context selection
    mcp_bridge.py  # MCP client (stdio + streamable HTTP)
    events.py      # SSE pub/sub + approval wait
    models.py      # SQLAlchemy ORM
    schemas.py     # Pydantic DTOs
frontend/
  src/app/         # pages: / (projects), /project/[id] (IDE), /settings
  src/components/ide/   # editor, explorer, chat, terminal, panels, dialogs
  src/lib/         # api, sse, types, utils
  src/store/       # zustand store
```
