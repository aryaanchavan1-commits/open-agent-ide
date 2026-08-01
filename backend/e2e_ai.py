import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://localhost:8000"


def call(method, path, body=None, timeout=30):
    req = urllib.request.Request(BASE + path, method=method)
    if body is not None:
        req.data = json.dumps(body).encode()
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def approve_loop(project_id, duration):
    deadline = time.time() + duration
    while time.time() < deadline:
        try:
            pending = []
            try:
                req = urllib.request.Request(f"{BASE}/api/projects/{project_id}/runs")
                with urllib.request.urlopen(req, timeout=5) as r:
                    pass
            except Exception:
                pass
            for aid in range(1, 500):
                try:
                    st, body = call(
                        "POST",
                        f"/api/approvals/{aid}/respond",
                        {"decision": "approve"},
                        timeout=5,
                    )
                    if st == 200:
                        print(f"  [auto-approve] {aid}: {body.get('status')}")
                except Exception:
                    break
        except Exception:
            pass
        time.sleep(2)


# --- setup ---
st, projects = call("GET", "/api/projects")
project = None
for p in projects:
    if p["name"] == "E2E Pharmacy":
        project = p
        break
if not project:
    st, project = call("POST", "/api/projects", {
        "name": "E2E Pharmacy",
        "description": "FastAPI backend for a pharmacy inventory system with products, stock and low-stock alerts",
        "permission_mode": "auto",
    })
    print(f"created project {project['id']}")
else:
    print(f"reusing project {project['id']}")

pid = project["id"]

# --- subscribe to SSE ---
import threading
events_log = []
stop = threading.Event()


def sse_thread():
    req = urllib.request.Request(f"{BASE}/api/projects/{pid}/events")
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            while not stop.is_set():
                line = r.readline().decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                events_log.append(line)
    except Exception as e:
        events_log.append(f"SSE-ERROR {e}")


t = threading.Thread(target=sse_thread, daemon=True)
t.start()

approver = threading.Thread(target=approve_loop, args=(pid, 900), daemon=True)
approver.start()

# --- run the orchestrator ---
print(">>> Sending build request to orchestrator...")
st, resp = call("POST", f"/api/projects/{pid}/chat", {
    "message": "Create a FastAPI backend for a pharmacy inventory system. Include products, stock levels, low-stock alerts and tests.",
})
print(f">>> chat accepted: {resp}")

# --- wait for completion ---
seen = set()
deadline = time.time() + 1200
while time.time() < deadline:
    time.sleep(3)
    try:
        st, runs = call("GET", f"/api/projects/{pid}/runs", timeout=10)
        running = [r for r in runs if r["status"] == "running"]
        for r in runs:
            if r["id"] not in seen:
                seen.add(r["id"])
                status = "running" if r["status"] == "running" else "done"
                print(f"  run {r['id']}: {r['agent_type']} [{status}]")
        if not running:
            print(">>> All agent runs finished")
            break
    except Exception as e:
        print(f"  poll error: {e}")

# --- summary ---
st, runs = call("GET", f"/api/projects/{pid}/runs")
print("\n=== RUNS ===")
for r in runs:
    print(f"{r['agent_type']:16s} {r['status']:10s} out_len={len(r['output_text'] or '')} err={r['error'][:120] if r['error'] else '-'}")

st, tasks = call("GET", f"/api/projects/{pid}/tasks")
print("\n=== TASKS ===")
for t in tasks:
    print(f"{t['task_id']} [{t['status']}] {t['title']}")

st, tree = call("GET", f"/api/projects/{pid}/files/tree")
print("\n=== FILES ===")


def walk(nodes, prefix=""):
    for n in nodes:
        if n["type"] == "directory":
            print(f"{prefix}{n['name']}/")
            walk(n.get("children", []), prefix + "  ")
        else:
            print(f"{prefix}{n['name']} ({n.get('size', 0)} B)")


walk(tree)

st, convs = call("GET", f"/api/projects/{pid}/conversations")
if convs:
    st, msgs = call("GET", f"/api/projects/{pid}/conversations/{convs[0]['id']}/messages")
    print("\n=== LAST MESSAGE ===")
    print((msgs[-1]["content"] if msgs else "-")[:2000])

stop.set()
print("\nE2E COMPLETE")
