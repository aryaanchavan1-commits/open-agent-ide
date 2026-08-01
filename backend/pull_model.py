import asyncio
import sys

from app.providers.ollama import OllamaProvider


async def main():
    provider = OllamaProvider()
    ok = await provider.pull_model(sys.argv[1] if len(sys.argv) > 1 else "qwen2.5-coder:1.5b")
    print("PULL DONE:", ok)


asyncio.run(main())
