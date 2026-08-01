import asyncio
import json
import sys
import time

import httpx

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

async def main():
    url = "http://localhost:11434/api/pull"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        try:
            async with client.stream("POST", url, json={"model": "qwen2.5-coder:7b", "stream": True}) as r:
                print("status:", r.status_code)
                last = 0
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except Exception:
                        continue
                    status = data.get("status", "")
                    total = data.get("total", 0)
                    done = data.get("completed", 0)
                    if status != last and status in ("downloading",):
                        last = status
                        print(f"[{time.strftime('%H:%M:%S')}] downloading start total={total/1e9:.2f}GB", flush=True)
                    if status == "success":
                        print("PULL SUCCESS", flush=True)
                        return
                    if data.get("error"):
                        print("PULL ERROR:", data["error"], flush=True)
                        return
                    if done % (500_000_000) < 1_000_000 and done > 0:
                        print(f"[{time.strftime('%H:%M:%S')}] {done/1e9:.2f}/{total/1e9:.2f} GB", flush=True)
        except Exception as e:
            print("EXCEPTION:", type(e).__name__, e, flush=True)

asyncio.run(main())
