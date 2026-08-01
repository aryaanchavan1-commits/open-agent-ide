import subprocess, sys, time, urllib.request, os, json

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.chdir(os.path.dirname(os.path.abspath(__file__)))
py = os.path.join(os.getcwd(), ".venv", "Scripts", "python.exe")
proc = subprocess.Popen(
    [py, "-m", "uvicorn", "app.main:app", "--port", "8000"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=0x08000000,
)
try:
    ok = False
    for i in range(40):
        time.sleep(0.5)
        try:
            with urllib.request.urlopen("http://localhost:8000/health", timeout=2) as r:
                print("HEALTH:", r.read().decode())
                ok = True
                break
        except Exception:
            continue
    if not ok:
        print("SERVER DID NOT COME UP")
        out = proc.stdout.read() if proc.stdout else ""
        print(out[-3000:])
        sys.exit(1)
    # exercise a few endpoints
    def call(method, path, body=None):
        req = urllib.request.Request("http://localhost:8000" + path, method=method)
        if body is not None:
            req.data = json.dumps(body).encode()
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    print("CREATE:", call("POST", "/api/projects", {"name": "Test App", "description": "A test pharmacy inventory system"}))
    print("LIST:", call("GET", "/api/projects"))
    print("AGENTS:", call("GET", "/api/projects/1/agents"))
    print("MODELS:", call("GET", "/api/models/providers"))
    print("SYSTEM:", call("GET", "/api/models/system-check"))
    print("FILES:", call("GET", "/api/projects/1/files/tree"))
    print("TASKS:", call("GET", "/api/projects/1/tasks"))
    print("GIT:", call("GET", "/api/projects/1/git/status"))
    print("CHECKPOINT:", call("POST", "/api/projects/1/git/checkpoints", {"name": "checkpoint-001", "message": "initial"}))
    print("ALL ENDPOINTS OK")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
