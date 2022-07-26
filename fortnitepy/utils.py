# -*- coding: utf-8 -*-

"""
MIT License

Copyright (c) 2019-2021 Terbau

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import asyncio

from typing import Optional


class MaybeLock:
    def __init__(self, lock: asyncio.Lock,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self.lock = lock
        self.loop = loop or asyncio.get_running_loop()
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
