import difflib
import fnmatch
import os
import re
from pathlib import Path


class WorkspaceError(Exception):
    pass


def resolve_path(workspace: Path, rel_path: str) -> Path:
    base = workspace.resolve()
    candidate = (base / rel_path).resolve()
    if not (candidate == base or base in candidate.parents):
        raise WorkspaceError(f"Path escapes workspace: {rel_path}")
    return candidate


def read_file(workspace: Path, path: str, max_lines: int = 2000) -> dict:
    target = resolve_path(workspace, path)
    if not target.exists() or target.is_dir():
        return {"ok": False, "error": f"File not found: {path}"}
    if target.stat().st_size > 2 * 1024 * 1024:
        return {"ok": False, "error": f"File too large to read: {path}"}
    content = target.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    truncated = len(lines) > max_lines
    if truncated:
        content = "\n".join(lines[:max_lines]) + f"\n... (truncated, {len(lines)} total lines)"
    return {"ok": True, "path": path, "content": content, "truncated": truncated}


def write_file(workspace: Path, path: str, content: str, overwrite: bool = True) -> dict:
    target = resolve_path(workspace, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        return {"ok": False, "error": f"File exists and overwrite is disabled: {path}"}
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "path": path, "size": target.stat().st_size}


def edit_file(workspace: Path, path: str, old_snippet: str, new_snippet: str) -> dict:
    target = resolve_path(workspace, path)
    if not target.exists():
        return {"ok": False, "error": f"File not found: {path}"}
    content = target.read_text(encoding="utf-8")
    if old_snippet in content:
        updated = content.replace(old_snippet, new_snippet, 1)
    else:
        updated = fuzzy_edit(content, old_snippet, new_snippet)
        if updated is None:
            return {
                "ok": False,
                "error": (
                    f"Could not find the old snippet in {path}. "
                    "The snippet must match the file content exactly. Read the file first and retry."
                ),
            }
    target.write_text(updated, encoding="utf-8")
    return {"ok": True, "path": path}


def fuzzy_edit(content: str, old_snippet: str, new_snippet: str) -> str | None:
    old_lines = old_snippet.strip().splitlines()
    content_lines = content.splitlines()
    if not old_lines:
        return None
    sm = difflib.SequenceMatcher(None, content_lines, old_lines, autojunk=False)
    opcodes = sm.get_opcodes()
    best = None
    best_ratio = 0.6
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal" and (i2 - i1) == (j2 - j1) and i2 > i1:
            ratio = (i2 - i1) / max(len(old_lines), 1)
            if ratio > best_ratio:
                best = (i1, i2)
                best_ratio = ratio
    if not best:
        return None
    i1, i2 = best
    new_lines = new_snippet.strip("\n").splitlines()
    return "\n".join(content_lines[:i1] + new_lines + content_lines[i2:]) + "\n"


def delete_file(workspace: Path, path: str) -> dict:
    target = resolve_path(workspace, path)
    if not target.exists():
        return {"ok": False, "error": f"File not found: {path}"}
    if target.is_dir():
        if target.name in (".git", ".arynox"):
            return {"ok": False, "error": f"Refusing to delete protected directory: {path}"}
        import shutil

        shutil.rmtree(target)
    else:
        target.unlink()
    return {"ok": True, "deleted": path}


def list_directory(workspace: Path, path: str = ".") -> dict:
    target = resolve_path(workspace, path)
    if not target.exists():
        return {"ok": False, "error": f"Directory not found: {path}"}
    ignore = {".git", ".arynox", "node_modules", "__pycache__", ".venv", "venv", ".next", "dist", "build"}
    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if child.name in ignore:
            continue
        if child.is_dir():
            entries.append({"name": child.name, "type": "directory"})
        else:
            entries.append({"name": child.name, "type": "file", "size": child.stat().st_size})
    return {"ok": True, "path": str(path), "entries": entries}


def search_files(workspace: Path, pattern: str, path: str = ".") -> dict:
    target = resolve_path(workspace, path)
    if not target.exists():
        return {"ok": False, "error": f"Directory not found: {path}"}
    regex = re.compile(fnmatch.translate(pattern), re.IGNORECASE)
    ignore_dirs = {".git", ".arynox", "node_modules", "__pycache__", ".venv", "venv", ".next"}
    matches = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            if regex.match(f):
                full = Path(root) / f
                rel = full.relative_to(workspace)
                matches.append(str(rel).replace("\\", "/"))
        if len(matches) > 500:
            break
    return {"ok": True, "matches": matches}


def search_text(workspace: Path, query: str, path: str = ".") -> dict:
    target = resolve_path(workspace, path)
    if not target.exists():
        return {"ok": False, "error": f"Directory not found: {path}"}
    ignore_dirs = {".git", ".arynox", "node_modules", "__pycache__", ".venv", "venv", ".next"}
    binary_exts = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".db", ".sqlite", ".bin"}
    results = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for f in files:
            ext = Path(f).suffix.lower()
            if ext in binary_exts or len(f) > 100:
                continue
            full = Path(root) / f
            try:
                if full.stat().st_size > 2 * 1024 * 1024:
                    continue
                text = full.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if query.lower() in line.lower():
                    rel = full.relative_to(workspace)
                    results.append({"file": str(rel).replace("\\", "/"), "line": lineno, "text": line.strip()[:200]})
            if len(results) > 500:
                break
        if len(results) > 500:
            break
    return {"ok": True, "matches": results}


def create_directory(workspace: Path, path: str) -> dict:
    target = resolve_path(workspace, path)
    target.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "created": str(path)}
