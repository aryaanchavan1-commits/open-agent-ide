import asyncio
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Optional

import sqlalchemy
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import events
from ..models import CommandApproval

DENY_PATTERNS = [
    r"rm\s+(-[a-z]*r[a-z]*f[a-z]*\s+)+[~/\s]|rm\s+-rf\s+(/|~)",
    r"rm\s+-rf\s+\*\s*$",
    r"del\s+/s\s+/q\s+[a-z]:",
    r"rd\s+/s\s+/q\s+[a-z]:",
    r"format\s+[a-z]:",
    r"^\s*format\b",
    r"\bshutdown\b|\breboot\b|\bhalt\b|\bpoweroff\b",
    r"\bmkfs\b|\bdiskpart\b|\bfdisk\b",
    r"dd\s+if=/dev/|dd\s+of=/dev/",
    r"\bblkid\b|\bmbr2gpt\b",
    r":\(\)\s*\{\s*:\|\s*:\s*&\s*\}\s*;",
    r"\bcurl\b.*\|\s*(ba)?sh\b|\bwget\b.*\|\s*(ba)?sh\b",
    r"powershell.*-enc\b|pwsh.*-enc\b",
    r"certutil\s+-decode\b",
    r"reg\s+delete\b|reg\s+add\b",
    r"sc\s+delete\b|schtasks\s+/delete\b|bcdedit\b",
    r"taskkill\s+/f\b.*\b(explorer|winlogon|svchost|csrss)\b",
    r"Remove-Item\s+(-Recurse\s+)?-Force\s+[c-z]:",
    r"Clear-Item\s+[c-z]:|Format-Volume\b",
    r"git\s+push\b|git\s+remote\s+add\b",
    r"net\s+user\b|net\s+localgroup\b",
    r"whoami\s+/all\b|netsh\s+wlan\s+show",
    r"curl\b.*\.env\b|type\s+.*\.env\b|cat\s+.*\.env\b|\.ssh[\\/](id_rsa|id_ed25519)",
    r"Get-Content\s+.*\.env\b|select-string\s+.*token\b",
    r"chmod\s+777\s+/",
    r"python\s+-c\s+['\"].*(eval|exec|__import__|os\.system|subprocess)",
]

ALLOWLIST_DEFAULTS = [
    "pytest",
    "python",
    "python3",
    "node",
    "npm",
    "npx",
    "pip",
    "pip3",
    "git",
    "uvicorn",
    "dotnet",
    "cargo",
    "go",
    "make",
    "mvn",
    "gradle",
    "java",
    "echo",
    "dir",
    "ls",
    "cd",
    "type",
    "cat",
    "find",
    "where",
    "git-bash",
]

ALLOWED_GIT_SUBCOMMANDS = {
    "status", "diff", "log", "add", "commit", "branch", "checkout", "rev-parse",
    "show", "stash", "tag", "reset",
}


def is_denied(command: str) -> tuple[bool, str]:
    cmd = command.strip()
    for pattern in DENY_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            return True, f"Command matches blocked pattern: {pattern}"
    if not cmd:
        return True, "Empty command"
    return False, ""


def is_allowed_allowlist(command: str) -> tuple[bool, str]:
    try:
        parts = shlex.split(command, posix=(os.name != "nt"))
    except Exception:
        parts = command.split()
    if not parts:
        return False, "Empty command"
    head = os.path.basename(parts[0].strip('"'))
    if head in ALLOWLIST_DEFAULTS:
        if head == "git" and len(parts) > 1 and parts[1] not in ALLOWED_GIT_SUBCOMMANDS:
            return False, f"git subcommand '{parts[1]}' is not allowed in allowlist mode"
        return True, ""
    return False, f"Command '{head}' is not in the allowlist"


def check_command(command: str, mode: str) -> tuple[str, str]:
    """Return (verdict, reason). Verdicts: allow | deny | ask."""
    denied, reason = is_denied(command)
    if denied:
        return "deny", reason
    allowed, reason = is_allowed_allowlist(command)
    if mode == "safe":
        if allowed:
            return "allow", ""
        return "deny", f"Safe mode: {reason}"
    if mode == "auto":
        return "allow", ""
    if mode == "ask":
        if allowed:
            return "allow", ""
        return "ask", "Not in allowlist"
    return "deny", f"Unknown permission mode '{mode}'"


async def run_command_streaming(
    command: str,
    cwd: Path,
    project_id: int,
    timeout: int = 300,
    output_buffer: Optional[list] = None,
) -> dict:
    import asyncio

    shell_prefix = ["cmd", "/c"] if os.name == "nt" else ["bash", "-lc"]
    flags = 0
    if os.name == "nt":
        flags = 0x08000000  # CREATE_NO_WINDOW
    process = await asyncio.create_subprocess_exec(
        *shell_prefix,
        command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        stdin=asyncio.subprocess.DEVNULL,
        creationflags=flags,
    )
    lines = []
    killed = False
    try:
        assert process.stdout is not None
        while True:
            try:
                line = await asyncio.wait_for(process.stdout.readline(), timeout=timeout)
            except asyncio.TimeoutError:
                killed = True
                await kill_process_tree(process)
                break
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip("\r\n")
            lines.append(text)
            if output_buffer is not None:
                output_buffer.append(text)
            await events.emit(project_id, "command.output", {"line": text})
    finally:
        try:
            exit_code = await process.wait()
        except Exception:
            exit_code = -1
    await events.emit(project_id, "command.finish", {"exit_code": exit_code, "killed": killed})
    output = "\n".join(lines)
    return {"exit_code": exit_code, "output": output, "killed": killed, "lines": lines}


async def kill_process_tree(process):
    try:
        if os.name == "nt":
            proc = await asyncio.create_subprocess_exec(
                "taskkill", "/pid", str(process.pid), "/t", "/f",
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                creationflags=0x08000000,
            )
            await proc.wait()
        else:
            proc = await asyncio.create_subprocess_exec(
                "kill", "-9", "-" + str(process.pid),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
    except Exception:
        try:
            process.kill()
        except Exception:
            pass


async def execute_with_approval(
    db: Session,
    project_id: int,
    command: str,
    cwd: Path,
    agent: str,
    reason: str,
    mode: str,
    timeout: int = 300,
    output_buffer: Optional[list] = None,
) -> dict:
    verdict, why = check_command(command, mode)
    if verdict == "deny":
        return {"ok": False, "denied": True, "reason": why, "exit_code": -1, "output": ""}
    if verdict == "ask":
        approval = CommandApproval(
            project_id=project_id,
            command=command,
            cwd=str(cwd),
            agent=agent,
            reason=reason or "Command not in the allowlist",
            status="pending",
        )
        db.add(approval)
        db.commit()
        db.refresh(approval)
        events.register_approval(approval.id)
        await events.emit(
            project_id,
            "permission.request",
            {
                "approval_id": approval.id,
                "command": command,
                "cwd": str(cwd),
                "agent": agent,
                "reason": reason,
            },
        )
        responded = await events.wait_approval(approval.id, timeout=1800)
        db.refresh(approval)
        if not responded or approval.status != "approved":
            return {
                "ok": False,
                "denied": True,
                "reason": "Approval rejected or expired",
                "exit_code": -1,
                "output": "",
                "approval_id": approval.id,
            }
    await events.emit(project_id, "command.start", {"command": command, "cwd": str(cwd), "agent": agent, "reason": reason})
    result = await run_command_streaming(command, cwd, project_id, timeout=timeout, output_buffer=output_buffer)
    result["ok"] = result["exit_code"] == 0
    return result


async def run_simple_command(
    project_id: int, command: str, cwd: Path, timeout: int = 300
) -> dict:
    return await run_command_streaming(command, cwd, project_id, timeout=timeout)
