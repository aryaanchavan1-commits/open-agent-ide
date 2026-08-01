import asyncio
from pathlib import Path

API = "https://api.github.com"


async def _api(method: str, path: str, token: str, json_body: dict | None = None) -> dict:
    import httpx

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.request(method, f"{API}{path}", headers=headers, json=json_body)
        if resp.status_code >= 400:
            detail = resp.json().get("message", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise ValueError(f"GitHub API {resp.status_code}: {detail}")
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()


async def validate_token(token: str) -> dict:
    user = await _api("GET", "/user", token)
    return {"ok": True, "login": user.get("login", ""), "name": user.get("name") or user.get("login", "")}


async def list_repos(token: str) -> list[dict]:
    repos = await _api("GET", "/user/repos?per_page=100&sort=updated", token)
    return [
        {
            "full_name": r["full_name"],
            "private": r["private"],
            "default_branch": r.get("default_branch", "main"),
            "html_url": r.get("html_url", ""),
        }
        for r in repos
    ]


async def create_repo(token: str, name: str, private: bool = False, description: str = "") -> str:
    data = {"name": name, "private": private, "description": description, "auto_init": False}
    repo = await _api("POST", "/user/repos", token, data)
    return repo.get("full_name", name)


async def _run_git(workspace: Path, *args: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git",
        "-c",
        "core.askpass=",
        "-c",
        "credential.helper=",
        *args,
        cwd=str(workspace),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    text = out.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {text}")
    return text


def token_auth_url(token: str, repo_full_name: str) -> str:
    return f"https://x-access-token:{token}@github.com/{repo_full_name}.git"


async def push_workspace(workspace: Path, token: str, repo_full_name: str, branch: str = "main") -> dict:
    if not workspace.exists():
        raise ValueError("Workspace does not exist")
    await _run_git(workspace, "add", "-A")
    try:
        await _run_git(workspace, "commit", "-m", "AI workspace update")
    except RuntimeError:
        pass
    auth_url = token_auth_url(token, repo_full_name)
    try:
        await _run_git(workspace, "remote", "set-url", "origin", auth_url)
    except RuntimeError:
        await _run_git(workspace, "remote", "add", "origin", auth_url)
    try:
        await _run_git(workspace, "branch", "--set-upstream-to", f"origin/{branch}", branch)
    except RuntimeError:
        await _run_git(workspace, "push", "-u", "origin", f"HEAD:{branch}")
    else:
        await _run_git(workspace, "push", "origin", f"HEAD:{branch}")
    return {"ok": True, "repo": repo_full_name, "branch": branch}


async def ensure_and_push(workspace: Path, token: str, repo_full_name: str, branch: str = "main", create_if_missing: bool = False) -> dict:
    if create_if_missing:
        try:
            repos = await list_repos(token)
        except Exception:
            repos = []
        if not any(r["full_name"].lower() == repo_full_name.lower() for r in repos):
            name = repo_full_name.split("/")[-1]
            created = await create_repo(token, name, description="Created by Arynox AI")
            repo_full_name = created
    return await push_workspace(workspace, token, repo_full_name, branch)
