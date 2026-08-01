import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.context import build_context
from app.services.git_service import (
    git_branches,
    git_checkpoint,
    git_commit,
    git_status,
    ensure_git_repo,
)

client = TestClient(app)


@pytest.fixture(scope="module")
def project_id():
    resp = client.post("/api/projects", json={"name": "Pytest App", "description": "test project"})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_health():
    assert client.get("/health").status_code == 200


def test_projects_crud(project_id):
    assert client.get("/api/projects").status_code == 200
    assert client.get(f"/api/projects/{project_id}").status_code == 200
    resp = client.patch(f"/api/projects/{project_id}", json={"permission_mode": "auto"})
    assert resp.status_code == 200
    assert resp.json()["permission_mode"] == "auto"


def test_agents_list(project_id):
    resp = client.get(f"/api/projects/{project_id}/agents")
    assert resp.status_code == 200
    names = [a["id"] for a in resp.json()]
    assert {"planner", "coder", "tester", "debugger"} <= set(names)


def test_file_roundtrip(project_id):
    resp = client.post(f"/api/projects/{project_id}/files", json={"path": "hello.py", "content": "print(1)"})
    assert resp.status_code == 200
    resp = client.get(f"/api/projects/{project_id}/files/content", params={"path": "hello.py"})
    assert resp.json()["content"] == "print(1)"
    resp = client.post(f"/api/projects/{project_id}/files/edit", json={"path": "hello.py", "old_snippet": "print(1)", "new_snippet": "print(2)"})
    assert resp.status_code == 200
    resp = client.get(f"/api/projects/{project_id}/files/tree")
    assert any(n["name"] == "hello.py" for n in resp.json())


def test_file_path_traversal_blocked(project_id):
    resp = client.get(f"/api/projects/{project_id}/files/content", params={"path": "../../secrets.txt"})
    assert resp.status_code in (400, 404)


def test_task_roundtrip(project_id):
    resp = client.post(
        f"/api/projects/{project_id}/tasks",
        json={"task_id": "TASK-001", "title": "Init", "description": "setup", "priority": "high"},
    )
    assert resp.status_code == 201
    resp = client.get(f"/api/projects/{project_id}/tasks")
    assert resp.json()[0]["task_id"] == "TASK-001"


def test_denied_command(project_id):
    resp = client.post(f"/api/projects/{project_id}/execute", json={"command": "rm -rf /", "reason": "test"})
    assert resp.status_code == 200
    assert resp.json()["denied"] is True


def test_allowlisted_command_runs(project_id):
    resp = client.post(
        f"/api/projects/{project_id}/execute",
        json={"command": "python -c \"print('ok')\"", "reason": "test"},
    )
    assert resp.status_code == 200
    assert resp.json()["exit_code"] == 0


def test_git_endpoints(project_id):
    assert client.get(f"/api/projects/{project_id}/git/status").status_code == 200
    assert client.get(f"/api/projects/{project_id}/git/diff").status_code == 200
    assert client.get(f"/api/projects/{project_id}/git/log").status_code == 200


def test_checkpoint_roundtrip(project_id):
    resp = client.post(
        f"/api/projects/{project_id}/git/checkpoints",
        json={"name": "checkpoint-test", "message": "before change"},
    )
    assert resp.status_code == 201
    cp = resp.json()
    resp = client.get(f"/api/projects/{project_id}/git/checkpoints")
    assert any(c["id"] == cp["id"] for c in resp.json())
    resp = client.post(f"/api/projects/{project_id}/git/checkpoints/{cp['id']}/restore")
    assert resp.status_code == 200


def test_conversation_flow(project_id):
    resp = client.post(f"/api/projects/{project_id}/chat", json={"message": "hello"})
    assert resp.status_code == 200
    convs = []
    import time

    for _ in range(40):
        convs = client.get(f"/api/projects/{project_id}/conversations").json()
        if convs:
            break
        time.sleep(0.25)
    assert len(convs) == 1
    messages = client.get(f"/api/projects/{project_id}/conversations/{convs[0]['id']}/messages").json()
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello"


def test_models_providers():
    resp = client.get("/api/models/providers")
    assert resp.status_code == 200
    ids = {p["id"] for p in resp.json()["providers"]}
    assert {"ollama", "openai", "openrouter"} <= ids


def test_system_check_shape():
    resp = client.get("/api/models/system-check")
    assert resp.status_code == 200
    body = resp.json()
    assert "os" in body and "recommended_model" in body


def test_task_to_dict(project_id):
    resp = client.post(
        f"/api/projects/{project_id}/tasks",
        json={"title": "Build module", "description": "create the module", "priority": "high"},
    )
    assert resp.status_code == 201
    from app.database import SessionLocal
    from app.models import Project

    with SessionLocal() as db:
        project = db.get(Project, project_id)
        context = build_context(db, project, "test query")
        assert "tasks" in context
        for t in context["tasks"]:
            assert "task_id" in t and "title" in t and "status" in t
        assert "current_task" in context


@pytest.mark.asyncio
async def test_git_service_direct(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    assert await ensure_git_repo(repo) is True
    assert await ensure_git_repo(repo) is False
    (repo / "f.txt").write_text("hello")
    result = await git_commit(repo, "first commit")
    assert result["ok"]
    status = await git_status(repo)
    assert status["dirty"] is False
    cp = await git_checkpoint(repo, "cp-1", "test checkpoint")
    assert cp["ok"]
    branches = await git_branches(repo)
    assert "main" in branches
