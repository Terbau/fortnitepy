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

class BattleRoyaleNewsPost:
    def __init__(self, data):
        self._image = data['image']
        self._hidden = data['hidden']
        self._type = data['_type']
        self._title = data['title']
        self._body = data['body']
        self._spotlight = data['spotlight']
        self._adspace = data.get('adspace')
    
    @property
    def image(self):
        """:class:`str`: The image url of this post."""
        return self._image

    @property
    def hidden(self):
        """:class:`bool`: ``True`` if post is hidden else ``False``."""
        return self._hidden

    @property
    def type(self):
        """:class:`str`: The type of this message."""
        return self._type

    @property
    def title(self):
        """:class:`str`: The title of this post."""
        return self._title

    @property
    def body(self):
        """:class:`str`: The actual message of this post."""
        return self._body

    @property
    def spotlight(self):
        """:class:`bool`: ``True`` if this post is in the spotlight else ``False``."""
        return self._spotlight

    @property
    def adspace(self):
        """:class:`str`: The adspace of this post. ``None`` if no adspace is found."""
        return self._adspace
