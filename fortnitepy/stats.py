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

import datetime

from .user import User
from .enums import Platform

replacers = {
    'placetop1': 'wins',
}

skips = (
    's11_social_bp_level',
    's13_social_bp_level',
)


class _StatsBase:
    __slots__ = ('raw', '_user', '_stats', '_start_time', '_end_time')

    def __init__(self, user: User, data: dict) -> None:
        self.raw = data
        self._user = user
        self._stats = None

        self._start_time = datetime.datetime.utcfromtimestamp(data['startTime'])  # noqa

        if data['endTime'] == 9223372036854775807:
            self._end_time = datetime.datetime.utcnow()
        else:
            self._end_time = datetime.datetime.utcfromtimestamp(data['endTime'])  # noqa

    @property
    def user(self) -> User:
        """:class:`User`: The user these stats belongs to."""
        return self._user

    @property
    def start_time(self) -> datetime.datetime:
        """:class:`datetime.datetime`: The UTC start time of
        the stats retrieved.
        """
        return self._start_time

    @property
    def end_time(self) -> datetime.datetime:
        """:class:`datetime.datetime`: The UTC end time of the
        stats retrieved.
        """
        return self._end_time

    def parse(self) -> None:
        raise NotImplementedError

    def get_stats(self) -> dict:
        if self._stats is None:
            self.parse()

        return self._stats


class StatsV2(_StatsBase):
    """Represents a users Battle Royale stats on Fortnite."""

    __slots__ = _StatsBase.__slots__ + ('_combined_stats',
                                        '_platform_specific_combined_stats')

    def __init__(self, user: User, data: dict) -> None:
        super().__init__(user, data)

        self._platform_specific_combined_stats = None
        self._combined_stats = None

    def __repr__(self) -> str:
        return ('<StatsV2 user={0.user!r} start_time={0.start_time!r} '
                'end_time={0.end_time!r}>'.format(self))

    @staticmethod
    def create_stat(stat: str, platform: Platform, playlist: str) -> str:
        if stat in replacers.values():
            for k, v in replacers.items():
                if v == stat:
                    stat = k

        return 'br_{0}_{1}_m0_playlist_{2}'.format(stat,
                                                   platform.value,
                                                   playlist)

    def get_kd(self, data: dict) -> float:
        """Gets the kd of a gamemode

        Usage: ::

            # gets ninjas kd in solo on input touch
            async def get_ninja_touch_solo_kd():
                user = await client.fetch_user('Ninja')
                stats = await client.fetch_br_stats(user.id)

                return stats.get_kd(stats.get_stats()['touch']['defaultsolo'])

        Parameters
        ----------
        data: :class:`dict`
            A :class:`dict` which atleast includes the keys: ``kills``,
            ``matchesplayed`` and ``wins``.

        Returns
        -------
        :class:`float`
            Returns the kd with a decimal point accuracy of two.
        """

        kills = data.get('kills', 0)
        matches = data.get('matchesplayed', 0)
        wins = data.get('wins', 0)

        try:
            kd = kills / (matches - wins)
        except ZeroDivisionError:
            kd = 0
        return float(format(kd, '.2f'))

    def get_winpercentage(self, data: dict) -> float:
        """Gets the winpercentage of a gamemode

        Usage: ::

            # gets ninjas winpercentage in solo on input touch
            async def get_ninja_touch_solo_winpercentage():
                user = await client.fetch_user('Ninja')
                stats = await client.fetch_br_stats(user.id)

                return stats.get_winpercentage(stats.get_stats()['touch']['defaultsolo'])

        Parameters
        ----------
        data: :class:`dict`
            A :class:`dict` which atleast includes the keys: matchesplayed`` and ``wins``.

        Returns
        -------
        :class:`float`
            Returns the winpercentage with a decimal point accuracy of two.
        """  # noqa

        matches = data.get('matchesplayed', 0)
        wins = data.get('wins', 0)

        try:
            winper = (wins * 100) / matches
        except ZeroDivisionError:
            winper = 0
        if winper > 100:
            winper = 100
        return float(format(winper, '.2f'))

    def parse(self) -> None:
        result = {}
        for fullname, stat in self.raw['stats'].items():
            if fullname in skips:
                continue

            parts = fullname.split('_')

            name = parts[1]
            inp = parts[2]
            playlist = '_'.join(parts[5:])

            try:
                name = replacers[name]
            except KeyError:
                pass

            if name == 'lastmodified':
                stat = datetime.datetime.utcfromtimestamp(stat)

            if inp not in result:
                result[inp] = {}
            if playlist not in result[inp]:
                result[inp][playlist] = {}

            result[inp][playlist][name] = stat
        self._stats = result

    def _construct_platform_specific_combined_stats(self) -> None:
        result = {}

        for platform, values in self.get_stats().items():
            if platform not in result:
                result[platform] = {}

            for stats in values.values():
                for stat, value in stats.items():
                    try:
                        try:
                            result[platform][stat] += value
                        except TypeError:
                            if value > result[platform][stat]:
                                result[platform][stat] = value
                    except KeyError:
                        result[platform][stat] = value

        self._platform_specific_combined_stats = result

    def _construct_combined_stats(self) -> None:
        result = {}

        for values in self.get_stats().values():
            for stats in values.values():
                for stat, value in stats.items():
                    try:
                        try:
                            result[stat] += value
                        except TypeError:
                            if value > result[stat]:
                                result[stat] = value
                    except KeyError:
                        result[stat] = value

        self._combined_stats = result

    def get_stats(self) -> dict:
        """Gets the stats for this user. This function returns the users stats.

        Returns
        -------
        :class:`dict`
            Mapping of the users stats. All stats are mapped to their
            respective gamemodes.
        """
        return super().get_stats()

    def get_combined_stats(self, platforms: bool = True) -> dict:
        """Gets combined stats for this user.

        Parameters
        ----------
        platforms: :class:`bool`
            | ``True`` if the combined stats should be mapped to their
            respective region.
            | ``False`` to return all stats combined across platforms.

        Returns
        -------
        :class:`dict`
            Mapping of the users stats combined. All stats are added together
            and no longer sorted into their respective gamemodes.
        """
        if platforms:
            if self._platform_specific_combined_stats is None:
                self._construct_platform_specific_combined_stats()

            return self._platform_specific_combined_stats

        else:
            if self._combined_stats is None:
                self._construct_combined_stats()

            return self._combined_stats


class StatsCollection(_StatsBase):
    """Represents a users Battle Royale stats collection on Fortnite."""

    __slots__ = _StatsBase.__slots__ + ('_name',)

    def __init__(self, user: User, data: dict) -> None:
        super().__init__(user, data)

        self._name = None

    def __repr__(self) -> str:
        return ('<StatsCollection user={0.user!r} start_time={0.start_time!r} '
                'end_time={0.end_time!r}>'.format(self))

    def parse(self) -> None:
        result = {}

        # stat example: br_collection_fish_flopper_orange_length_s14
        for stat, value in self.raw['stats'].items():
            split = stat.split('_')
            name = '_'.join(split[3:-1])
            self._name = '_'.join(split[1:3])

            result[name] = value

        self._stats = result

    @property
    def name(self) -> str:
        """:class:`str`: The collection name."""
        if self._stats is None:
            self.parse()

        return self._name

    def get_stats(self) -> dict:
        """Gets the stats collection for this user. This function returns the
        users collection.

        Returns
        -------
        :class:`dict`
            Mapping of the users collection.
        """
        return super().get_stats()
