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

import json
import re
import datetime

from .party import Party
from .errors import PartyPermissionError

class PresenceGameplayStats:
    """Represents gameplaystats received from presence.
    
    Attributes
    ----------
    state: :class:`str`
        The state.
    playlist: :class:`str`
        The playlist.
    num_kills: :class:`int`
        The amount of kills the friend currently has.
    fell_to_death: :class:`bool`
        ``True`` if friend fell to death in its current game, else ``False``    
    """

    __slots__ = ('state', 'playlist', 'num_kills', 'fell_to_death')

    def __init__(self, data):
        self.state = data.get('state')
        self.playlist = data.get('playlist')
        self.num_kills = data.get('numKills')
        if self.num_kills is not None:
            self.num_kills = int(self.num_kills)
        self.fell_to_death = data.get('bFellToDeath')
        if self.fell_to_death is not None:
            self.fell_to_death = bool(self.fell_to_death)


class PresenceParty:
    """Represents a party received from presence.

    Before accessing any of this class' attributes or functions
    you should always check if the party is private: ::
    
        @client.event
        async def event_friend_presence(presence):

            # check if presence is from the account 'Terbau'
            # NOTE: you should always use id over display_name
            # but for this example i've use display_name just
            # to demonstrate.
            if presence.author.display_name != 'Terbau':
                return
            
            # check if party is private
            if presence.party.is_private:
                return
            
            # if all the checks above succeeds we join the party
            await presence.party.join()
        
    
    .. note::

        If the party is private all attributes below is_private will
        be ``None``.

    Attributes
    ----------
    client: :class:`str`
        The client.
    is_private: :class:`bool`
        ``True`` if the party is private else ``False``.
    platform: :class:`str`
        The platform of the friend.
    id: :class:`str`
        The party's id.
    party_type_id: :class:`str`
        The party's type id.
    key: :class:`str`
        The party's key.
    app_id: :class:`str`
        The party's app id.
    build_id: :class:`str`
        The party's build id. Similar format to :attr:`Client.party_build_id`.
    net_cl: :class:`str`
        The party's net_cl. Similar format to :attr:`Client.net_cl`.
    party_flags: :class:`str`
        The party's flags.
    not_accepting_reason: :class:`str`
        The party's not accepting reason.
    playercount: :class:`int`
        The party's playercount.
    """

    __slots__ = ('client', 'raw', 'is_private', 'platform', 'id', 'party_type_id',
                 'key', 'app_id', 'build_id', 'net_cl', 'party_flags', 
                 'not_accepting_reason', 'playercount')

    def __init__(self, client, data):
        self.client = client
        self.raw = data
        self.is_private = data.get('bIsPrivate', False)

        self.platform = data.get('sourcePlatform')
        self.id = data.get('partyId')
        self.party_type_id = data.get('partyTypeId')
        self.key = data.get('key')
        self.app_id = data.get('appId')
        self.build_id = data.get('buildId')
        self.net_cl = self.build_id[4:]
        self.party_flags = data.get('partyFlags')
        self.not_accepting_reason = data.get('notAcceptingReason')
        self.playercount = data.get('pc')
        if self.playercount is not None:
            self.playercount = int(self.playercount)

    async def join(self):
        """|coro|
        
        Joins the friends' party.

        Raises
        ------
        PartyPermissionError
            The party is private.
        HTTPException
            Something else went wrong when trying to join this party.
        """
        if self.is_private:
            raise PartyPermissionError('You cannot join a private party.')
        await self.client.join_to_party(self.id)


class Presence:
    """Represents a presence received from a friend
    
    Attributes
    ----------
    client: :class:`Client`
        The client.
    is_available: :class:`bool`
        The availability of this presence. ``True`` if presence is available,
        ``False`` if user went unavailable.
    friend: :class:`Friend`
        The friend you received this presence from.
    received_at: :class:`datetime.datetime`
        The UTC time of when the client received this presence.
    status: :class:`str`
        The friend's status.
    is_playing: :class:`bool`
        Says if friend is playing.
    is_joinable: :class:`bool`
        Says if friend is joinable.
    session_id: :class:`str`
        The friend's current session id. Often referred to as
        server key or game key.
    has_properties: :class:`bool`
        ``True`` if the presence has properties else ``False``.
        
        .. warning::

            All attributes below this point will be ``None`` if
            :attr:`has_properties` is ``False``.
    party: :class:`PresenceParty`
        The friend's party.
    gameplay_stats: :class:`PresenceGameplayStats`
        The friend's gameplay stats.
    homebase_rating: :class:`str`
        The friend's homebase rating
    lfg: :class:`bool`
        ``True`` if the friend is currently looking for a game.
    sub_game: :class:`str`
        The friend's current subgame.
    in_unjoinable_match: :class:`bool`
        ``True`` if friend is in unjoinable match else ``False``.
    playlist: :class:`str`
        The friend's current playlist.
    players_alive: :class:`int`
        The amount of players alive in the friend's current game.
    party_size: :class:`int`
        The size of the friend's party.
    max_party_size: :class:`int`
        The max size of the friend's party.
    game_session_join_key: :class:`str`
        The join key of the friend's session.
    server_player_count: :class:`str`
        The playercount of the friend's server.
    """

    __slots__ = ('client', 'raw', 'is_available', 'friend', 'received_at', 'status', 
                 'is_playing', 'is_joinable', 'has_voice_support', 'session_id', 
                 'raw_properties', 'has_properties', 'homebase_rating', 'lfg', 'sub_game',
                 'in_unjoinable_match', 'playlist', 'players_alive', 'party_size',
                 'max_party_size', 'game_session_join_key', 'server_player_count',
                 'gameplay_stats', 'party')

    def __init__(self, client, from_id, is_available, data):
        self.client = client
        self.raw = data
        self.is_available = is_available
        self.friend = self.client.get_friend(from_id)
        self.received_at = datetime.datetime.utcnow()

        self.status = data['Status']
        self.is_playing = bool(data['bIsPlaying'])
        self.is_joinable = bool(data['bIsJoinable'])
        self.has_voice_support = bool(data['bHasVoiceSupport'])
        self.session_id = data['SessionId'] if data['SessionId'] != "" else None

        self.raw_properties = data['Properties']
        self.has_properties = self.raw_properties != {}
        
        # all values below will be "None" if properties is empty
        _basic_info = self.raw_properties.get('FortBasicInfo_j', {})
        self.homebase_rating = _basic_info.get('homeBaseRating')
        if self.raw_properties.get('FortLFG_I') is None:
            self.lfg = None
        else:
            self.lfg = True if int(self.raw_properties.get('FortLFG_I')) == 1 else False

        self.sub_game = self.raw_properties.get('FortSubGame_i')
        self.in_unjoinable_match = self.raw_properties.get('InUnjoinableMatch_b')
        if self.in_unjoinable_match is not None:
            self.in_unjoinable_match = int(self.in_unjoinable_match)
        self.playlist = self.raw_properties.get('GamePlaylistName_s')
        self.players_alive = self.raw_properties.get('Event_PlayersAlive_s')
        if self.players_alive is not None:
            self.players_alive = int(self.players_alive)
        self.party_size = self.raw_properties.get('Event_PartySize_s')
        if self.party_size is not None:
            self.party_size = int(self.party_size)
        self.max_party_size = self.raw_properties.get('Event_PartyMaxSize_s')
        if self.max_party_size is not None:
            self.max_party_size = int(self.max_party_size)
        self.game_session_join_key = self.raw_properties.get('GameSessionJoinKey_s')
        self.server_player_count = self.raw_properties.get('ServerPlayerCount_i')
        if self.server_player_count is not None:
            self.server_player_count = int(self.server_player_count)

        if 'FortGameplayStats_j' in self.raw_properties.keys():
            self.gameplay_stats = PresenceGameplayStats(self.raw_properties['FortGameplayStats_j'])
        else:
            self.gameplay_stats = None
        
        key = None
        for k in self.raw_properties.keys():
            if re.search(r'party\.joininfodata\.\d+_j', k) is not None:
                key = k
        if key is None:
            self.party = None
        else:
            self.party = PresenceParty(self.client, self.raw_properties[key])
