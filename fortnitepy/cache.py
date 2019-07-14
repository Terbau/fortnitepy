# -*- coding: utf-8 -*-

"""
MIT License

Copyright (c) 2019 Terbau

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

class Cache:
    def __init__(self, loop=None):
        self.loop = loop
        self._cache = {}
    
    def set(self, key, value, timeout=None):
        self._cache[key] = value

        if timeout is not None:
            asyncio.ensure_future(self.schedule_removal(key, timeout), loop=self.loop)

    def remove(self, key):
        return self._cache.pop(key)

    def get(self, key, silent=True):
        if silent:
            return self._cache.get(key)
        return self._cache[key]

    def keys(self):
        return self._cache.keys()

    def values(self):
        return self._cache.values()

    async def schedule_removal(self, key, seconds):
        await asyncio.sleep(seconds, loop=self.loop)
        try:
            del self._cache[key]
        except KeyError:
            pass


class WeakrefCache(Cache):
    def __init__(self, loop=None):
        super().__init__(loop=loop)
        self._cache = weakref.WeakValueDictionary()


