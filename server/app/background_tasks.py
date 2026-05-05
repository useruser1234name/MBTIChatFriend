"""Helpers for tracking detached background tasks."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from typing import Any, Coroutine

logger = logging.getLogger(__name__)

_pending_tasks: set[asyncio.Task[Any]] = set()


def create_tracked_task(coro: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task[Any]:
    """Create a detached task that is tracked for readiness and shutdown."""
    task = asyncio.create_task(coro, name=name)
    _pending_tasks.add(task)
    task.add_done_callback(_on_task_done)
    return task


def _on_task_done(task: asyncio.Task[Any]) -> None:
    _pending_tasks.discard(task)
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    except Exception as err:
        logger.warning("Background task inspection failed: %s", err)
        return

    if exc is not None:
        logger.warning("Background task failed [%s]: %s", task.get_name(), exc)


def snapshot_background_tasks() -> dict[str, Any]:
    names = Counter(task.get_name() or "unnamed" for task in _pending_tasks if not task.done())
    return {
        "pending": sum(names.values()),
        "tasks": dict(sorted(names.items())),
    }


async def drain_background_tasks(timeout: float = 5.0) -> dict[str, int]:
    """Wait briefly for detached tasks, then cancel remaining work."""
    pending = [task for task in _pending_tasks if not task.done()]
    if not pending:
        return {"completed": 0, "cancelled": 0}

    done, still_pending = await asyncio.wait(pending, timeout=timeout)
    cancelled = 0
    for task in still_pending:
        task.cancel()
        cancelled += 1

    if still_pending:
        await asyncio.gather(*still_pending, return_exceptions=True)

    return {"completed": len(done), "cancelled": cancelled}
