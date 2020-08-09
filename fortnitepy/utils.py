import asyncio

from typing import Optional


class MaybeLock:
    def __init__(self, lock: asyncio.Lock,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self.lock = lock
        self.loop = loop or asyncio.get_event_loop()
        self._cleanup = False

    async def _acquire(self) -> None:
        await self.lock.acquire()
        self._cleanup = True

    async def __aenter__(self) -> 'MaybeLock':
        self._task = self.loop.create_task(self._acquire())
        return self

    async def __aexit__(self, *args: list) -> None:
        if not self._task.cancelled():
            self._task.cancel()

        if self._cleanup:
            self.lock.release()


class LockEvent(asyncio.Lock):
    def __init__(self) -> None:
        super().__init__()

        self._event = asyncio.Event()
        self._event.set()
        self.wait = self._event.wait
        self.priority = 0

    async def acquire(self) -> None:
        await super().acquire()
        self._event.clear()

    def release(self) -> None:
        super().release()

        # Only set if no new acquire waiters exists. This is because we
        # don't want any wait()'s to return if there immediately will
        # be a new acquirer.
        if not (self._waiters is not None and [w for w in self._waiters
                                               if not w.cancelled()]):
            self._event.set()
            self.priority = 0
