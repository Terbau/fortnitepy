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

import json

from typing import List, Optional, Dict, Any, Union
from .enums import DefaultCharactersChapter1, KairosBackgroundColorPreset

ListOrPreset = Optional[Union[List[str], KairosBackgroundColorPreset]]


def get_random_default_avatar() -> 'Avatar':
    return Avatar(
        asset=DefaultCharactersChapter1.get_random_name(),
        background_colors=KairosBackgroundColorPreset.get_random_value()
    )


class Avatar:
    """Dataclass which represents a kairos avatar.

    Parameters
    ----------
    asset: Optional[:class:`str`]
        The CID to use as the asset.
    background_colors: Optional[List[:class:`str`]]
        A list of exactly three hex color values represented as strings.
        In Kairos (PartyHub) these values will be used to create a gradiant
        background. Fortnite however will find the average
        of the three colors and use that.

    Attributes
    ----------
    asset: Optional[:class:`str`]
        The CID used for this asset.
    background: Optional[Union[List[:class:`str`], :class:`KairosBackgroundColorPreset`]]
        A list of exactly three hex color values represented as strings.
    """  # noqa

    __slots__ = ('asset', 'background_colors')

    def __init__(self, *, asset: Optional[str] = None,
                 background_colors: ListOrPreset = None) -> None:
        self.asset = asset

        if isinstance(background_colors, KairosBackgroundColorPreset):
            self.background_colors = background_colors.value
        else:
            self.background_colors = background_colors

    def __repr__(self) -> str:
        return ('<Avatar asset={0.asset!r} '
                'background_colors={0.background_colors!r}>'.format(self))

    def __eq__(self, other):
        return isinstance(other, Avatar) and other.to_dict() == self.to_dict()

    def __ne__(self, other):
        return not self.__eq__(other)

    def to_dict(self) -> Dict[str, Any]:
        """Converts it into a fortnite friendly dict.

        Returns
        -------
        Dict[:class:`str`, Any]
            The values transformed into a fortnite friendly dictionary.
        """
        data = {'appInstalled': 'init'}

        if self.asset:
            data['avatar'] = self.asset.lower()

        if self.background_colors:
            colors = [c.upper() for c in self.background_colors]
            dumped = json.dumps(colors)

            # For some reason we have to remove the spaces or else it won't
            # show correctly client sided.
            data['avatarBackground'] = dumped.replace(' ', '')

        return data
