import asyncio
import os
from pathlib import Path
from typing import Optional


async def _git(project_path: Path, *args: str, check: bool = True) -> tuple[int, str]:
    cmd = ["git", "-C", str(project_path), *args]
    flags = 0x08000000 if os.name == "nt" else 0
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        creationflags=flags,
    )
    out, _ = await proc.communicate()
    text = out.decode("utf-8", errors="replace").strip()
    return proc.returncode or 0, text


async def ensure_git_repo(project_path: Path) -> bool:
    if not (project_path / ".git").exists():
        await _git(project_path, "init", "-b", "main")
        import subprocess

        subprocess.run(
            ["git", "-C", str(project_path), "config", "user.name", "Arynox AI"],
            capture_output=True,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        subprocess.run(
            ["git", "-C", str(project_path), "config", "user.email", "arynox@localhost"],
            capture_output=True,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        return True
    return False


async def git_status(project_path: Path) -> dict:
    code, text = await _git(project_path, "status", "--porcelain=v1")
    code2, branch = await _git(project_path, "rev-parse", "--abbrev-ref", "HEAD")
    if not code2 == 0 or not branch or "fatal" in branch:
        branch = "main (no commits)"
    entries = []
    for line in text.splitlines():
        if len(line) > 3:
            entries.append({"status": line[:2], "path": line[3:]})
    return {"branch": branch or "main", "entries": entries, "dirty": bool(entries)}


async def git_diff(project_path: Path, staged: bool = False) -> str:
    args = ["diff", "--cached"] if staged else ["diff"]
    code, text = await _git(project_path, *args)
    if not text:
        code, text = await _git(project_path, "diff", "HEAD")
    return text


async def git_diff_files(project_path: Path, staged: bool = False) -> list[dict]:
    args = ["diff", "--name-status", "--cached"] if staged else ["diff", "--name-status"]
    code, text = await _git(project_path, *args)
    files = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            files.append({"status": parts[0], "path": parts[1]})
    return files


async def git_commit(project_path: Path, message: str) -> dict:
    await _git(project_path, "add", "-A")
    code, text = await _git(project_path, "commit", "-m", message)
    code2, rev = await _git(project_path, "rev-parse", "HEAD")
    return {"ok": code == 0, "message": text, "commit": rev}


async def git_branches(project_path: Path) -> list[str]:
    code, text = await _git(project_path, "branch", "--format=%(refname:short)")
    return [b for b in text.splitlines() if b]


async def git_create_branch(project_path: Path, name: str) -> dict:
    code, text = await _git(project_path, "checkout", "-b", name)
    return {"ok": code == 0, "message": text}


async def git_checkout_branch(project_path: Path, name: str) -> dict:
    code, text = await _git(project_path, "checkout", name)
    return {"ok": code == 0, "message": text}


async def git_log(project_path: Path, limit: int = 20) -> list[dict]:
    code, text = await _git(
        project_path, "log", f"-{limit}", "--pretty=format:%h%x09%ad%x09%s", "--date=short"
    )
    commits = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            commits.append({"hash": parts[0], "date": parts[1], "message": parts[2]})
    return commits


async def git_reset_hard(project_path: Path, commit: str) -> dict:
    code, text = await _git(project_path, "reset", "--hard", commit)
    if code == 0:
        await _git(project_path, "clean", "-fd")
    return {"ok": code == 0, "message": text}


async def git_checkpoint(project_path: Path, name: str, message: str) -> dict:
    await _git(project_path, "add", "-A")
    code, text = await _git(project_path, "commit", "-m", f"[checkpoint:{name}] {message}")
    code2, rev = await _git(project_path, "rev-parse", "HEAD")
    if code == 0 or "nothing to commit" in text:
        return {"ok": True, "commit": rev, "message": text, "new": code == 0}
    return {"ok": False, "commit": rev, "message": text, "new": False}


async def git_has_changes(project_path: Path) -> bool:
    code, text = await _git(project_path, "status", "--porcelain")
    return bool(text.strip())
