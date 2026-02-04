import asyncio
import os
from typing import Optional

from task_manager.worker import dispatch_scheduled_tasks


class TaskScheduler:
    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = interval_seconds
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop_event.set()
        await self._task
        self._task = None

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            dispatch_scheduled_tasks()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                continue


def create_scheduler_from_env() -> Optional[TaskScheduler]:
    mode = os.getenv("TASK_SCHEDULER_MODE", "celery")
    if mode != "internal":
        return None
    interval = int(os.getenv("TASK_SCHEDULER_INTERVAL_SEC", "60"))
    return TaskScheduler(interval_seconds=interval)
