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

import datetime

replacers = {
    'placetop1': 'wins'
}


class StatsV2:
    """Represents a users Battle Royale stats on Fortnite.
    
    Attributes
    ----------
    user: :class:`User`
        The user these stats belongs to.
    start_time: :class:`datetime.datetime`
        The UTC start time of the stats retrieved.
    end_time: :class:`datetime`
        The UTC end time of the stats retrieved. 
    """

    __slots__ = ('raw', 'user', '_stats', '_platform_specific_combined_stats',
                 '_combined_stats', 'start_time', 'end_time', )

    def __init__(self, user, data):
        self.raw = data
        self.user = user

        self._stats = None
        self._platform_specific_combined_stats = None
        self._combined_stats = None
        self.start_time = datetime.datetime.fromtimestamp(data['startTime'])

        if data['endTime'] == 9223372036854775807:
            self.end_time = datetime.datetime.utcnow()
        else:
            self.end_time = datetime.datetime.fromtimestamp(data['endTime'])

    @staticmethod
    def create_stat(stat, platform, playlist):
        if stat in replacers.values():
            for k, v in replacers.items():
                if v == stat:
                    stat = k

        return 'br_{0}_{1}_m0_playlist_{2}'.format(stat, platform.value, playlist)

    def get_kd(self, data):
        """Gets the kd of a gamemode
        
        Usage: ::
            
            # gets ninjas kd in solo on input touch
            async def get_ninja_touch_solo_kd():
                profile = await client.fetch_profile('Ninja)
                stats = await client.fetch_br_stats(profile.id)

                return stats.get_kd(stats.get_stats()['touch']['defaultsolo'])
        
        Parameters
        ----------
        data: :class:`dict`
            A :class:`dict` which atleast includes the keys: ``kills``, ``matchesplayed`` and ``wins``.

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
    
    def get_winpercentage(self, data):
        """Gets the winpercentage of a gamemode
        
        Usage: ::
            
            # gets ninjas winpercentage in solo on input touch
            async def get_ninja_touch_solo_winpercentage():
                profile = await client.fetch_profile('Ninja)
                stats = await client.fetch_br_stats(profile.id)

                return stats.get_winpercentage(stats.get_stats()['touch']['defaultsolo'])

        Parameters
        ----------
        data: :class:`dict`
            A :class:`dict` which atleast includes the keys: matchesplayed`` and ``wins``.

        Returns
        -------
        :class:`float`
            Returns the winpercentage with a decimal point accuracy of two.
        """

        matches = data.get('matchesplayed', 0)
        wins = data.get('wins', 0)

        try:
            winper = (wins * 100) / matches
        except ZeroDivisionError:
            winper = 0
        if winper > 100:
            winper = 100
        return float(format(winper, '.2f'))

    def _parse(self):
        result = {}
        for fullname, stat in self.raw['stats'].items():
            parts = fullname.split('_')

            name = parts[1]
            inp = parts[2]
            playlist = '_'.join(parts[5:])

            try:
                name = replacers[name]
            except KeyError:
                pass

            if name == 'lastmodified':
                stat = datetime.datetime.fromtimestamp(stat)
            
            if inp not in result:
                result[inp] = {}
            if playlist not in result[inp]:
                result[inp][playlist] = {}
            
            result[inp][playlist][name] = stat
        self._stats = result

    def _construct_platform_specific_combined_stats(self):
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

    def _construct_combined_stats(self):
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
                    
    def get_stats(self):
        """Gets the stats for this user. This function returns the users stats
        .
        
        Returns
        -------
        :class:`dict`
            Mapping of the users stats. All stats are mapped to their respective 
            gamemodes.
        """
        if self._stats is None:
            self._parse()

        return self._stats

    def get_combined_stats(self, platforms=True):
        """Gets combined stats for this user.

        Parameters
        ----------
        platforms: :class:`bool`
            | ``True`` if the combined stats should be mapped to their respective region.
            | ``False`` to return all stats combined across platforms.
        
        Returns
        -------
        :class:`dict`
            Mapping of the users stats combined. All stats are added together and
            no longer sorted into their respective gamemodes.
        """
        if platforms:
            if self._platform_specific_combined_stats is None:
                self._construct_platform_specific_combined_stats()
    
            return self._platform_specific_combined_stats
        
        else:
            if self._combined_stats is None:
                self._construct_combined_stats()
            
            return self._combined_stats
