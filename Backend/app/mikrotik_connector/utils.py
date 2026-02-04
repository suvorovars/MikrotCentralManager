import asyncio
import os
from typing import Optional

_MAX_PARALLEL_CONNECTIONS = int(os.getenv("MIKROTIK_MAX_PARALLEL_CONNECTIONS", "10"))
_connection_semaphore: Optional[asyncio.Semaphore] = None


def _get_connection_semaphore() -> asyncio.Semaphore:
    global _connection_semaphore
    if _connection_semaphore is None:
        _connection_semaphore = asyncio.Semaphore(_MAX_PARALLEL_CONNECTIONS)
    return _connection_semaphore


async def acquire_connection_slot() -> None:
    await _get_connection_semaphore().acquire()


def release_connection_slot() -> None:
    _get_connection_semaphore().release()


def get_parallel_connection_limit() -> int:
    return _MAX_PARALLEL_CONNECTIONS
