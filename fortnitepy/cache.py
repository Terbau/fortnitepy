# -*- coding: utf-8 -*-

"""
MIT License

Copyright (c) 2019-2020 Terbau

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
import weakref

from typing import Optional, Any


class Cache:
    def __init__(self,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self.loop = loop
        self._cache = {}

    def set(self, key: str, value: Any, *,
            timeout: int = None) -> None:
        self._cache[key] = value

        if timeout is not None:
            asyncio.ensure_future(self.schedule_removal(key, timeout),
                                  loop=self.loop)

    def remove(self, key: str, default: Optional[Any] = None) -> Any:
        if default is not None:
            return self._cache.pop(key, default)
        return self._cache.pop(key)

    def get(self, key: str, *,
            silent: bool = True) -> Any:
        if silent:
            return self._cache.get(key)
        return self._cache[key]

    async def schedule_removal(self, key: str, seconds: int) -> None:
        await asyncio.sleep(seconds, loop=self.loop)
        try:
            del self._cache[key]
        except KeyError:
            pass

    def clear(self) -> None:
        self._cache = {}


class WeakrefCache(Cache):
    def __init__(self,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        super().__init__(loop=loop)
        self._cache = weakref.WeakValueDictionary()
