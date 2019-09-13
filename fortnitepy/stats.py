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
    stats: :class:`dict`
        :class:`dict` including stats.
    start_time: :class:`datetime.datetime`
        The UTC start time of the stats retrieved.
    end_time: :class:`datetime`
        The UTC end time of the stats retrieved. 
    """
    def __init__(self, data):
        self.raw = data

        self.stats = {}
        # self.start_time = datetime.datetime.fromtimestamp(data['startTime'] / 1000)
        # self.end_time = datetime.datetime.fromtimestamp(data['endTime'] / 1000)

        self._parse()

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

                return stats.get_kd(stats.stats['touch']['defaultsolo'])
        
        Parameters
        ----------
        data: :class:`dict`
            A :class:`dict` which includes the keys: ``kills``, ``matchesplayed`` and ``wins``.

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

                return stats.get_winpercentage(stats.stats['touch']['defaultsolo'])

        Parameters
        ----------
        data: :class:`dict`
            A :class:`dict` which includes the keys: matchesplayed`` and ``wins``.

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
            
            if inp not in result.keys():
                result[inp] = {}
            if playlist not in result[inp].keys():
                result[inp][playlist] = {}
            
            result[inp][playlist][name] = stat
        self.stats = result

