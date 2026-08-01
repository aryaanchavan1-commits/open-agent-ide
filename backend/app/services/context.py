import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Conversation, Message, Project, Task
from .workspace import project_source_dir

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "with", "this", "that", "to", "in", "on", "of",
    "is", "are", "add", "create", "new", "make", "please", "can", "you", "me", "my", "it",
    "i", "we", "our", "using", "use", "as", "at", "by", "from", "project", "app", "application",
}

MAX_FILES = 10
MAX_CHARS = 60000


def tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    return {t for t in tokens if len(t) > 2 and t not in STOPWORDS}


def score_path(rel: str, tokens: set[str]) -> int:
    score = 0
    parts = rel.lower().split("/")
    for token in tokens:
        for part in parts:
            if token in part:
                score += 2
            if part.startswith(token):
                score += 1
    ext = Path(rel).suffix.lower()
    code_exts = {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".toml", ".html", ".css", ".sql"}
    if ext in code_exts:
        score += 1
    return score


def find_relevant_files(project: Project, query: str, max_files: int = MAX_FILES) -> list[str]:
    source = project_source_dir(project)
    if not source.exists():
        return []
    tokens = tokenize(query or "")
    ignore_dirs = {".git", ".arynox", "node_modules", "__pycache__", ".venv", "venv", ".next", "dist", "build"}
    candidates: list[tuple[int, Path]] = []
    for path in source.rglob("*"):
        if path.is_dir() or any(part in ignore_dirs for part in path.parts):
            continue
        try:
            if path.stat().st_size > 300 * 1024:
                continue
        except OSError:
            continue
        rel = str(path.relative_to(source)).replace("\\", "/")
        score = score_path(rel, tokens) if tokens else 1
        if score:
            candidates.append((score, path))
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [str(p.relative_to(source)).replace("\\", "/") for _, p in candidates[:max_files]]


def build_context(
    db: Session,
    project: Project,
    query: str,
    task: Task | None = None,
    include_file_contents: bool = True,
) -> dict:
    source = project_source_dir(project)
    tasks = (
        db.execute(
            select(Task).where(Task.project_id == project.id).order_by(Task.id).limit(15)
        )
        .scalars()
        .all()
    )
    latest_conv = (
        select(Conversation.id)
        .where(Conversation.project_id == project.id)
        .order_by(Conversation.id.desc())
        .limit(1)
    )
    messages = (
        db.execute(
            select(Message)
            .where(Message.conversation_id.in_(latest_conv))
            .order_by(Message.id.desc())
            .limit(8)
        )
        .scalars()
        .all()
    )
    search_query = query or ""
    if task:
        search_query += " " + task.title + " " + task.description
    rel_files = find_relevant_files(project, search_query)
    file_contents = {}
    if include_file_contents:
        for rel in rel_files:
            try:
                p = source / rel
                content = p.read_text(encoding="utf-8", errors="replace")
                if len(content) > 15000:
                    content = content[:15000] + "\n... (truncated)"
                file_contents[rel] = content
            except Exception:
                continue
            total = sum(len(c) for c in file_contents.values())
            if total > MAX_CHARS:
                break

    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "tech_stack": project.tech_stack,
            "status": project.status,
            "permission_mode": project.permission_mode,
            "model": project.default_model,
        },
        "current_task": task.to_dict() if task else None,
        "tasks": [t.to_dict() for t in tasks],
        "recent_conversation": [m.content[:1000] for m in reversed(messages)],
        "relevant_files": rel_files,
        "file_contents": file_contents,
        "search_query": search_query,
    }
