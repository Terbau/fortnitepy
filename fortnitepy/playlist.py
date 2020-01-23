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

from typing import Optional


class Playlist:

    __slots__ = ('_image', '_internal_name', '_special_border', '_type',
                 '_violator', '_display_subname', '_description')

    def __init__(self, data: dict) -> None:
        self._image = data['image']
        self._internal_name = data['playlist_name']
        self._special_border = data.get('special_border')
        self._type = data.get('_type')
        self._violator = data.get('violator')
        self._display_subname = data.get('display_subname')
        self._description = data.get('description')

    def __str__(self) -> str:
        return self.internal_name

    def __repr__(self) -> str:
        return ('<Playlist internal_name={0.internal_name!r} '
                'image_url={0.image_url!r}type={0.type!r}>'.format(self))

    @property
    def image_url(self) -> str:
        """:class:`str`: Image url for the playlist."""
        return self._image

    @property
    def internal_name(self) -> str:
        """:class:`str`: The internal name of the playlist."""
        return self._internal_name

    @property
    def type(self) -> str:
        """:class:`str`: The type of this playlist object."""
        return self._type

    @property
    def special_border(self) -> Optional[str]:
        """Optional[:class:`str`]: Special border of the playlist.
        Will be ``None`` if no special border is found for this playlist.
        """
        if self._special_border == 'None':
            return None
        return self._special_border

    @property
    def violator(self) -> Optional[str]:
        """Optional[:class:`str`]: The violater displayed for this playlist. This is
        the little red tag displaying short text on some of the playlists
        in-game.
        Will be ``None`` if no violator is found for this playlist.
        """
        if self._violator == '':
            return None
        return self._violator

    @property
    def display_subname(self) -> Optional[str]:
        """Optional[:class:`str`]: The display subname of this playlist.
        Will be ``None`` if no display subname is found for this playlist.
        """
        return self._display_subname

    @property
    def description(self) -> Optional[str]:
        """Optional[:class:`str`]: The description of this playlist.
        Will be ``None`` if no description is found for this playlist.
        """
        return self._description
