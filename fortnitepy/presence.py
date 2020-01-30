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

from typing import TYPE_CHECKING

from .errors import Forbidden, PartyError

if TYPE_CHECKING:
    from .client import Client
    from .friend import Friend
    from .party import ClientParty


class PresenceGameplayStats:
    """Represents gameplaystats received from presence.

    Attributes
    ----------
    friend: :class:`Friend`
        The friend these stats belong to.
    state: :class:`str`
        The state.
    playlist: :class:`str`
        The playlist.
    players_alive: :class:`int`
        The amount of players alive in the current game.
    num_kills: :class:`int`
        The amount of kills the friend currently has.
    fell_to_death: :class:`bool`
        ``True`` if friend fell to death in its current game, else ``False``
    """

    __slots__ = ('friend', 'state', 'playlist', 'players_alive', 'num_kills',
                 'fell_to_death')

    def __init__(self, friend: 'Friend',
                 data: str,
                 players_alive: int) -> None:
        self.friend = friend
        self.state = data.get('state')
        self.playlist = data.get('playlist')
        self.players_alive = players_alive

        self.num_kills = data.get('numKills')
        if self.num_kills is not None:
            self.num_kills = int(self.num_kills)

        self.fell_to_death = True if data.get('bFellToDeath') else False

    def __repr__(self):
        return ('<PresenceGameplayStats friend={0.friend!r} '
                'players_alive={0.players_alive} num_kills={0.num_kills} '
                'playlist={0.playlist!r}>'.format(self))


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
            if presence.friend.display_name != 'Terbau':
                return

            # check if party is private
            if presence.party.private:
                return

            # if all the checks above succeeds we join the party
            await presence.party.join()


    .. note::

        If the party is private, all attributes below private will
        be ``None``.

    Attributes
    ----------
    client: :class:`str`
        The client.
    private: :class:`bool`
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

    __slots__ = ('client', 'raw', 'private', 'platform', 'id', 'party_type_id',
                 'key', 'app_id', 'build_id', 'net_cl', 'party_flags',
                 'not_accepting_reason', 'playercount')

    def __init__(self, client: 'Client', data: dict) -> None:
        self.client = client
        self.raw = data
        self.private = data.get('bIsPrivate', False)

        self.platform = data.get('sourcePlatform')
        self.id = data.get('partyId')
        self.party_type_id = data.get('partyTypeId')
        self.key = data.get('key')
        self.app_id = data.get('appId')
        self.build_id = data.get('buildId')

        if self.build_id is not None and self.build_id.startswith('1:1:'):
            self.net_cl = self.build_id[4:]
        else:
            self.net_cl = None

        self.party_flags = data.get('partyFlags')
        self.not_accepting_reason = data.get('notAcceptingReason')

        self.playercount = data.get('pc')
        if self.playercount is not None:
            self.playercount = int(self.playercount)

    def __repr__(self) -> str:
        return ('<PresenceParty private={0.private} id={0.id!r} '
                'playercount={0.playercount}>'.format(self))

    async def join(self) -> 'ClientParty':
        """|coro|

        Joins the friends' party.

        Raises
        ------
        PartyError
            You are already a member of this party.
        Forbidden
            The party is private.
        HTTPException
            Something else went wrong when trying to join this party.

        Returns
        -------
        :class:`ClientParty`
            The party that was just joined.
        """
        if self.client.user.party.id == self.id:
            raise PartyError('You are already a member of this party.')

        if self.private:
            raise Forbidden('You cannot join a private party.')

        return await self.client.join_to_party(self.id)


class Presence:
    """Represents a presence received from a friend

    Attributes
    ----------
    client: :class:`Client`
        The client.
    available: :class:`bool`
        The availability of this presence. ``True`` if presence is available,
        ``False`` if user went unavailable.
    friend: :class:`Friend`
        The friend you received this presence from.
    platform: :class:`str`
        The platform this presence was sent from.
    received_at: :class:`datetime.datetime`
        The UTC time of when the client received this presence.
    status: :class:`str`
        The friend's status.
    playing: :class:`bool`
        Says if friend is playing.
    joinable: :class:`bool`
        Says if friend is joinable.
    session_id: :class:`str`
        The friend's current session id. Often referred to as
        server key or game key. Returns ``None`` if the friend is not currently
        in a game.
    has_properties: :class:`bool`
        ``True`` if the presence has properties else ``False``.

        .. warning::

            All attributes below this point will be ``None`` if
            :attr:`has_properties` is ``False``.
    party: :class:`PresenceParty`
        The friend's party.
    gameplay_stats: :class:`PresenceGameplayStats`
        The friend's gameplay stats.
    avatar: :class:`str`
        The avatar set in Kairos (Mobile app).
    avatar_colors: List[:class:`str`]
        List of colors in hex string format used in the avatar background.
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
    party_size: :class:`int`
        The size of the friend's party.
    max_party_size: :class:`int`
        The max size of the friend's party.
    game_session_join_key: :class:`str`
        The join key of the friend's session.
    server_player_count: :class:`str`
        The playercount of the friend's server.
    """

    __slots__ = ('client', 'raw', 'available', 'friend', 'platform',
                 'received_at', 'status', 'playing', 'joinable',
                 'has_voice_support', 'session_id', 'raw_properties',
                 'has_properties', 'avatar', 'avatar_colors',
                 'homebase_rating', 'lfg', 'sub_game', 'in_unjoinable_match',
                 'playlist', 'party_size', 'max_party_size',
                 'game_session_join_key', 'server_player_count',
                 'gameplay_stats', 'party')

    def __init__(self, client: 'Client',
                 from_id: str,
                 platform: str,
                 available: bool,
                 data: dict) -> None:
        self.client = client
        self.raw = data
        self.available = available
        self.friend = self.client.get_friend(from_id)
        self.platform = platform
        self.received_at = datetime.datetime.utcnow()

        self.status = data['Status']
        self.playing = data['bIsPlaying']
        self.joinable = data['bIsJoinable']
        self.has_voice_support = data['bHasVoiceSupport']
        self.session_id = (data['SessionId'] if
                           data['SessionId'] != "" else None)

        self.raw_properties = data['Properties']
        self.has_properties = self.raw_properties != {}

        # all values below will be "None" if properties is empty

        kairos_profile = self.raw_properties.get('KairosProfile_s', {})
        if kairos_profile != {}:
            kairos_profile = json.loads(kairos_profile)

        self.avatar = kairos_profile.get('avatar')
        self.avatar_colors = kairos_profile.get('avatarBackground')

        _basic_info = self.raw_properties.get('FortBasicInfo_j', {})
        self.homebase_rating = _basic_info.get('homeBaseRating')

        if self.raw_properties.get('FortLFG_I') is None:
            self.lfg = None
        else:
            self.lfg = int(self.raw_properties.get('FortLFG_I')) == 1

        self.sub_game = self.raw_properties.get('FortSubGame_i')

        self.in_unjoinable_match = self.raw_properties.get(
            'InUnjoinableMatch_b'
        )
        if self.in_unjoinable_match is not None:
            self.in_unjoinable_match = int(self.in_unjoinable_match)

        self.playlist = self.raw_properties.get('GamePlaylistName_s')

        players_alive = self.raw_properties.get('Event_PlayersAlive_s')
        if players_alive is not None:
            players_alive = int(players_alive)

        self.party_size = self.raw_properties.get('Event_PartySize_s')
        if self.party_size is not None:
            self.party_size = int(self.party_size)

        self.max_party_size = self.raw_properties.get('Event_PartyMaxSize_s')
        if self.max_party_size is not None:
            self.max_party_size = int(self.max_party_size)

        self.game_session_join_key = self.raw_properties.get(
            'GameSessionJoinKey_s'
        )

        self.server_player_count = self.raw_properties.get(
            'ServerPlayerCount_i'
        )
        if self.server_player_count is not None:
            self.server_player_count = int(self.server_player_count)

        if 'FortGameplayStats_j' in self.raw_properties.keys():
            self.gameplay_stats = PresenceGameplayStats(
                self.friend,
                self.raw_properties['FortGameplayStats_j'],
                players_alive
            )
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

    def __repr__(self):
        return ('<Presence friend={0.friend!r} available={0.available} '
                'received_at={0.received_at!r}>'.format(self))
