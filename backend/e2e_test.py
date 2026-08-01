import sys
import traceback

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient

from app.main import app

with TestClient(app) as c:
    steps = [
        ("git_status", lambda: c.get("/api/projects/2/git/status", timeout=30)),
        ("git_diff", lambda: c.get("/api/projects/2/git/diff", timeout=30)),
        ("file_write", lambda: c.post("/api/projects/2/files", json={"path": "app.py", "content": 'print("hello")'}, timeout=30)),
        ("file_tree", lambda: c.get("/api/projects/2/files/tree", timeout=30)),
        ("file_read", lambda: c.get("/api/projects/2/files/content", params={"path": "app.py"}, timeout=30)),
        ("checkpoint_create", lambda: c.post("/api/projects/2/git/checkpoints", json={"name": "checkpoint-001", "message": "initial"}, timeout=30)),
        ("checkpoint_list", lambda: c.get("/api/projects/2/git/checkpoints", timeout=30)),
        ("execute", lambda: c.post("/api/projects/2/execute", json={"command": "python app.py", "reason": "test"}, timeout=30)),
        ("task_create", lambda: c.post("/api/projects/2/tasks", json={"task_id": "TASK-001", "title": "Init", "description": "scaffold"}, timeout=30)),
        ("task_list", lambda: c.get("/api/projects/2/tasks", timeout=30)),
        ("search_text", lambda: c.get("/api/projects/2/files/search-text", params={"query": "hello"}, timeout=30)),
        ("models_available", lambda: c.get("/api/models/available", timeout=30)),
        ("providers_status", lambda: c.get("/api/models/providers-status", timeout=30)),
    ]
    for name, fn in steps:
        try:
            r = fn()
            print(f"{name}: {r.status_code} {r.text[:150]}")
        except Exception as e:
            print(f"{name}: EXCEPTION {type(e).__name__}: {e}")
            traceback.print_exc()
            break
print("E2E DONE")
