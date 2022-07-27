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
import datetime
import re

from typing import Optional

uuid_match_comp = re.compile(r'^[a-f0-9]{32}$')


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


def from_iso(iso: str) -> datetime.datetime:
    """Converts an iso formatted string to a
    :class:`datetime.datetime` object

    Parameters
    ----------
    iso: :class:`str`:
        The iso formatted string to convert to a datetime object.

    Returns
    -------
    :class:`datetime.datetime`
    """
    if isinstance(iso, datetime.datetime):
        return iso

    try:
        return datetime.datetime.strptime(iso, '%Y-%m-%dT%H:%M:%S.%fZ')
    except ValueError:
        return datetime.datetime.strptime(iso, '%Y-%m-%dT%H:%M:%SZ')


def to_iso(dt: datetime.datetime) -> str:
    """Converts a :class:`datetime.datetime`
    object to an iso formatted string

    Parameters
    ----------
    dt: :class:`datetime.datetime`
        The datetime object to convert to an iso formatted string.

    Returns
    -------
    :class:`str`
    """
    iso = dt.strftime('%Y-%m-%dT%H:%M:%S.%f')

    # fortnite's services expect three digit precision on millis
    return iso[:23] + 'Z'


def is_id(value: str) -> bool:
    """Simple function that finds out if a :class:`str` is a valid id to
    use with fortnite services.

    Parameters
    ----------
    value: :class:`str`
        The string you want to check.

    Returns
    -------
    :class:`bool`
        ``True`` if string is valid else ``False``
    """
    return isinstance(value, str) and bool(uuid_match_comp.match(value))


def is_display_name(value: str) -> bool:
    """Simple function that finds out if a :class:`str` is a valid displayname

    Parameters
    ----------
    value: :class:`str`
        The string you want to check.

    Returns
    -------
    :class:`bool`
        ``True`` if string is valid else ``False``
    """
    return isinstance(value, str) and 3 <= len(value) <= 16
