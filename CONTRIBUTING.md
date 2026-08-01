# Contributing to Arynox AI

Thanks for wanting to help! This project is a local-first AI software engineering
platform: a FastAPI backend orchestrating multiple LLM agents, plus a Next.js IDE.

## Getting started

1. Fork the repository and clone it.
2. Set up the backend:

   ```bash
   cd backend
   python -m venv .venv
   .venv/Scripts/activate        # Windows
   # or: source .venv/bin/activate  (macOS/Linux)
   pip install -r requirements.txt
   cp .env.example .env
   ```

3. Set up the frontend:

   ```bash
   cd frontend
   npm install
   ```

4. Install Ollama and pull a model (e.g. `qwen2.5-coder:1.5b`), then start
   `ollama serve` in a terminal.

5. Run the stack:

   ```bash
   # Terminal 1 — backend on :8000
   cd backend && .venv/Scripts/python -m uvicorn app.main:app --port 8000
   # Terminal 2 — frontend on :3000
   cd frontend && npm run dev
   ```

## Code style and checks

- Backend: Python 3.11, SQLAlchemy 2 style, type hints everywhere.
  Run the suite before pushing: `cd backend && pytest tests -q`.
- Frontend: TypeScript strict; run `npx tsc --noEmit` and `npm run build`.
- No new dependencies without a good reason; keep the local-first philosophy.

## Pull request checklist

- [ ] Tests pass (`pytest tests -q`)
- [ ] Frontend typechecks and builds
- [ ] No secrets, keys, or `.env` files committed
- [ ] README updated if user-facing behavior changed

## Project layout

```
backend/            FastAPI app: agents, orchestrator, providers, tools, security
frontend/           Next.js IDE: editor, chat, terminal, git, approvals
projects/           Generated agent workspaces (gitignored)
docs/               Architecture documentation
```

## Reporting issues

Use the issue templates: bug reports and feature requests. Include the
backend `.env` *contents redacted* if relevant, OS version, model used, and
the failing request.
