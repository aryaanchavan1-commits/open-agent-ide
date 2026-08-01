# Arynox AI

**Local-first AI software engineering platform.**

Describe a software project in natural language — Arynox AI plans it, designs its architecture, breaks it into tasks, and specialized AI agents write the code, run the tests, and debug the failures, all inside an isolated local workspace with an IDE-style web UI.

Everything runs on `localhost`. No cloud, no account, no data leaves your machine (unless you configure a hosted API provider).

---

## Features

- **8 specialized AI agents** orchestrated automatically:
  🧠 Planner · 📋 Product Manager · 🏗️ Architect · 💻 Coding · 🧪 Testing · 🐛 Debugging · 🔍 Code Review · 📝 Documentation
- **Multi-provider AI layer** — Ollama (local, auto-downloads missing models), any OpenAI-compatible API, OpenRouter, plus **MCP** server tool support. Switch providers without touching agent code.
- **IDE-style UI** — Monaco code editor, file explorer, tasks, agent status, AI chat, terminal, test results, git panel, diff review.
- **Safety-first**: every agent action is reviewable. Commands go through an allowlist/denylist with three permission modes (`safe`, `ask`, `auto`) and an approve/reject flow.
- **Approval-based changes**: the AI proposes file changes as diffs; you review and apply.
- **Git-native**: auto-initialized repos, commits, branches, checkpoints — every AI change is reversible, and checkpoints can be restored.
- **Agent memory**: context selection only feeds relevant files to the model (keyword scoring; RAG-ready architecture).
- **Streaming**: SSE for agent status, chat, terminal output, test progress, and model downloads.

---

## Quick start

### 1. Start Ollama (for local models)

```bash
ollama serve
```

Arynox will detect the server and **automatically download** the model when it is missing (the recommended model is picked from your system — OS, RAM, GPU — e.g. `qwen2.5-coder:7b`). You can also download any model from the Settings page.

### 2. Backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate          # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
cp .env.example .env              # then edit if needed
uvicorn app.main:app --reload
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**, create a project, and describe your application — e.g. *"Create a FastAPI backend for a pharmacy inventory system with products, stock levels and low-stock alerts."*

Other URLs:
- Backend API: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs

---

## Providers

Set the provider in `backend/.env` (see `.env.example`):

| Provider | `AI_PROVIDER` | Notes |
|---|---|---|
| Ollama (local) | `ollama` | Auto-pulls missing models from `OLLAMA_BASE_URL` |
| OpenAI-compatible | `openai` | Any `/v1/chat/completions` endpoint (OpenAI, LM Studio, vLLM, Groq...) |
| OpenRouter | `openrouter` | One key, hundreds of models |

Arynox never exposes API keys to the frontend; they live only in `backend/.env`.

### Integrations (Settings → Integrations)

Everything can also be configured at runtime from the Settings UI — no `.env` editing:

- **GitHub (PAT)** — paste a personal access token (scope `repo`), test it, save it, and push any
  project workspace to one of your repositories from the project's Git panel. Token and username
  are stored in the local database.
- **API keys** — set the OpenAI / OpenRouter keys at runtime; provider connections refresh
  immediately.
- **MCP servers** — edit the server map as JSON and reconnect on the fly.
- **Auto-push** — enable "auto-push to GitHub after every agent run": once an agent run finishes,
  the workspace is committed and pushed automatically (requires a connected GitHub token).

### MCP servers

Configure servers as JSON in `MCP_SERVERS` (or via Settings → Integrations):

```env
MCP_SERVERS={"filesystem":{"command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","C:\\projects"]}}
```

Tools exposed by MCP servers are registered automatically and available to agents.

---

## Project workspace layout

```
projects/
  my-project/
    source/          # the generated application (agents work here)
    .arynox/         # internal platform metadata
    logs/            # run logs
    tests/           # test workspace
```

---

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design: provider abstraction, agent system, tool registry, security layer, streaming, and data model.

```
frontend/   Next.js 14 · React · TypeScript · Tailwind · shadcn-style UI · Monaco
backend/    FastAPI · SQLAlchemy · SQLite (PostgreSQL-ready) · SSE streaming
```

---

## Development

```bash
# backend tests
cd backend && .\.venv\Scripts\python -m pytest tests -q

# frontend typecheck / build
cd frontend && npx tsc --noEmit && npm run build
```

Docker (optional):

```bash
docker-compose up --build
```

---

## Security model

- All file tools are jailed to the project workspace (path traversal blocked).
- Command execution uses an allowlist + denylist. Dangerous commands (`rm -rf /`, `format`, `shutdown`, credential exfiltration, fork bombs, `git push`...) are always blocked.
- Permission modes: **Safe** (allowlist only) · **Ask** (default — every non-allowlisted command requires your approval) · **Auto** (approve everything non-denied).
- Every approval dialog shows: command, working directory, requesting agent, and reason.

---

## Roadmap

- Embeddings/RAG for agent memory
- GitHub remote integration
- WebSocket terminal (xterm.js)
- Multi-session agent parallelism

## License

MIT
