import asyncio
import json
from collections import defaultdict
from typing import Any, Optional

_subs: dict[int, set[asyncio.Queue]] = defaultdict(set)
_approvals: dict[int, asyncio.Event] = {}


async def subscribe(project_id: int) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=1000)
    _subs[project_id].add(q)
    return q


def unsubscribe(project_id: int, q: asyncio.Queue):
    _subs[project_id].discard(q)
    if not _subs[project_id]:
        _subs.pop(project_id, None)


async def emit(project_id: int, event_type: str, data: Any = None):
    payload = json.dumps(data or {}, default=str)
    message = f"event: {event_type}\ndata: {payload}\n\n"
    for q in list(_subs.get(project_id, ())):
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            try:
                q.get_nowait()
                q.put_nowait(message)
            except Exception:
                pass


def register_approval(approval_id: int):
    _approvals[approval_id] = asyncio.Event()


def resolve_approval(approval_id: int):
    ev = _approvals.get(approval_id)
    if ev:
        ev.set()


async def wait_approval(approval_id: int, timeout: float = 1800.0) -> bool:
    ev = _approvals.get(approval_id)
    if not ev:
        return False
    try:
        await asyncio.wait_for(ev.wait(), timeout)
        return True
    except asyncio.TimeoutError:
        return False


class EventStream:
    def __init__(self, project_id: int):
        self.project_id = project_id

    async def emit(self, event_type: str, data: Any = None):
        await emit(self.project_id, event_type, data)
