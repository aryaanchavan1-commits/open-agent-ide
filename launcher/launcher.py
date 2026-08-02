"""Arynox AI one-click launcher.

Starts Ollama (if installed), runs the embedded FastAPI backend, and opens the
IDE in the default browser. When frozen with PyInstaller, the static frontend
is served from the bundled ``out/`` data dir, so no Node/Python install is
required on the target machine.
"""

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

OLLAMA_PORT = 11434
BACKEND_PORT_RANGE = range(8000, 8012)
BASE_URL_ENV = "ARYNOX_DATA_DIR"


def _is_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _find_ollama() -> Path | None:
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    if local.exists():
        return local
    pf = Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe"
    return pf if pf.exists() else None


def _ensure_ollama() -> None:
    if _is_open(OLLAMA_PORT, "localhost", timeout=2.0):
        print("[ollama] already running")
        return
    exe = _find_ollama()
    if not exe:
        print(
            "[ollama] not found - local models unavailable. "
            "Install from https://ollama.com or use OpenAI/OpenRouter providers."
        )
        return
    print("[ollama] starting...")
    try:
        subprocess.Popen(
            [str(exe), "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
    except Exception as e:
        print(f"[ollama] failed to start: {e}")
        return
    for _ in range(30):
        if _is_open(OLLAMA_PORT, "localhost", timeout=1.0):
            print("[ollama] ready")
            return
        time.sleep(1)
    print("[ollama] still starting (model requests may fail briefly)")


def _open_when_ready(url: str, port: int) -> None:
    for _ in range(60):
        if _http_ok(f"{url}/health"):
            webbrowser.open(url)
            print(f"[launcher] browser opened at {url}")
            return
        time.sleep(0.5)
    print("[launcher] backend did not come up in time - check the log above")


def main() -> int:
    frozen = getattr(sys, "frozen", False)
    meipass = Path(getattr(sys, "_MEIPASS", "."))

    if frozen:
        static = meipass / "out"
        static_dir = static if (static / "index.html").exists() else None
        data_dir_env = None
    else:
        repo_root = Path(__file__).resolve().parents[1]
        out = repo_root / "frontend" / "out"
        static_dir = out if (out / "index.html").exists() else None
        data_dir_env = None  # dev: keep using backend/ as before

    if static_dir:
        os.environ["ARYNOX_STATIC_DIR"] = str(static_dir)
    if data_dir_env:
        os.environ[BASE_URL_ENV] = data_dir_env

    print("=" * 56)
    print("  Arynox AI - local-first AI software engineering")
    print("=" * 56)

    _ensure_ollama()

    if _http_ok("http://127.0.0.1:8000/", timeout=2.0):
        print("[launcher] an instance is already running - opening browser")
        webbrowser.open("http://127.0.0.1:8000/")
        return 0

    port = next(
        (p for p in BACKEND_PORT_RANGE if not _is_open(p)),
        8000,
    )
    url = f"http://127.0.0.1:{port}"

    if static_dir:
        print(f"[launcher] serving IDE from bundled build at http://127.0.0.1:{port}")
    else:
        print(f"[launcher] static frontend not found; API only at http://127.0.0.1:{port}")

    threading.Thread(target=_open_when_ready, args=(url, port), daemon=True).start()

    import uvicorn

    from app.main import app

    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
