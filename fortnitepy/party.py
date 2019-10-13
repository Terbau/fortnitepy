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
import json
import asyncio
import random
import aioxmpp
import re

from .errors import FortniteException, PartyError, PartyPermissionError, HTTPException
from .user import User
from .friend import Friend
from .enums import PartyPrivacy, DefaultCharacters


class MetaBase:
    def __init__(self):
        self.schema = {}

    def set_prop(self, prop, value, raw=False):
        if raw:
            self.schema[prop] = str(value)
            return self.schema[prop]
        
        _t = prop[-1:]
        if _t == 'j':
            self.schema[prop] = json.dumps(value)
        elif _t == 'U':
            self.schema[prop] = int(value)
        else:
            self.schema[prop] = str(value)
        return self.schema[prop]
    
    def get_prop(self, prop, raw=False):
        if raw:
            self.schema.get(prop)
        
        _t = prop[-1:]
        _v = self.schema.get(prop)
        if _t == 'b':
            return False if _v is None or (isinstance(_v, str) and _v.lower() == 'false') else True
        elif _t == 'j':
            return {} if _v is None else json.loads(_v)
        elif _t == 'U':
            return {} if _v is None else int(_v)
        else:
            return '' if _v is None else str(_v)

    def update(self, schema, raw=False):
        if schema is None: 
            return

        for prop, value in schema.items():
            self.set_prop(prop, value, raw=raw)
    
    def remove(self, schema):
        for prop in schema:
            try:
                del self.schema[prop]
            except KeyError:
                pass


class PartyMemberMeta(MetaBase):
    def __init__(self, member, meta=None):
        super().__init__()
        self.member = member

        character = (random.choice(list(DefaultCharacters))).name
        self.schema = {
            'Location_s': 'PreLobby',
            'CampaignHero_j': json.dumps({
                'CampaignHero': {
                    'heroItemInstanceId': '',
                    'heroType': "FortHeroType'/Game/Athena/Heroes/{0}.{0}'" \
                                "".format(character),
                },
            }),
            'MatchmakingLevel_U': '0',
            'ZoneInstanceId_s': '',
            'HomeBaseVersion_U': '1',
            'HasPreloadedAthena_b': False,
            'FrontendEmote_j': json.dumps({
                'FrontendEmote': {
                    'emoteItemDef': 'None',
                    'emoteItemDefEncryptionKey': '',
                    'emoteSection': -1,
                },
            }),
            'NumAthenaPlayersLeft_U': '0',
            'UtcTimeStartedMatchAthena_s': '0001-01-01T00:00:00.000Z',
            'GameReadiness_s': 'NotReady',
            'HiddenMatchmakingDelayMax_U': '0',
            'ReadyInputType_s': 'Count',
            'CurrentInputType_s': 'MouseAndKeyboard',
            'AssistedChallengeInfo_j': json.dumps({
                'AssistedChallengeInfo': {
                    'questItemDef': 'None',
                    'objectivesCompleted': 0,
                },
            }),
            'MemberSquadAssignmentRequest_j': json.dumps({
                'MemberSquadAssignmentRequest': {
                    'startingAbsoluteIdx': -1,
                    'targetAbsoluteIdx': -1,
                    'swapTargetMemberId': 'INVALID',
                    'version': 0,
                },
            }),
            'AthenaCosmeticLoadout_j': json.dumps({
                'AthenaCosmeticLoadout': {
                    'characterDef': "AthenaCharacterItemDefinition'/Game/Athena/Items/Cosmetics/Characters/{0}.{0}'" \
                                    "".format(character),
                    'characterEKey': '',
                    'backpackDef': 'None',
                    'backpackEKey': '',
                    'pickaxeDef': "AthenaPickaxeItemDefinition'/Game/Athena/Items/Cosmetics/" \
                                  "Pickaxes/DefaultPickaxe.DefaultPickaxe'",
                    'pickaxeEKey': '',
                    'variants': [],
                },
            }),
            'AthenaBannerInfo_j': json.dumps({
                'AthenaBannerInfo': {
                    'bannerIconId': 'standardbanner15',
                    'bannerColorId': 'defaultcolor15',
                    'seasonLevel': 1,
                },
            }),
            'BattlePassInfo_j': json.dumps({
                'BattlePassInfo': {
                    'bHasPurchasedPass': False,
                    'passLevel': 1,
                    'selfBoostXp': 0,
                    'friendBoostXp': 0,
                },
            }),
            'Platform_j': json.dumps({
                'Platform': {
                    'platformStr': self.member.client.platform.value,
                },
            }),
            'PlatformUniqueId_s': 'INVALID',
            'PlatformSessionId_s': '',
            'CrossplayPreference_s': 'OptedIn',
            'VoiceChatEnabled_b': 'true',
            'VoiceConnectionId_s': '',
        }

        if meta is not None:
            self.update(meta, raw=True)

    @property
    def ready(self):
        base = self.get_prop('GameReadiness_s')
        return True if base == "Ready" else False

    @property
    def input(self):
        return self.get_prop('CurrentInputType_s')

    @property
    def assisted_challenge(self):
        base = self.get_prop('AssistedChallengeInfo_j')
        result = result = re.search(r".*\.(.*)", base['AssistedChallengeInfo']['questItemDef'].strip("'"))

        if result is None or result[1] == 'None':
            return None
        return result[1]

    @property
    def outfit(self):
        base = self.get_prop('AthenaCosmeticLoadout_j')
        return re.search(r'.*(CID.*)\..*', base['AthenaCosmeticLoadout']['characterDef'])[1]

    @property
    def variants(self):
        base = self.get_prop('AthenaCosmeticLoadout_j')
        return base['AthenaCosmeticLoadout']['variants']

    @property
    def outfit_variants(self):
        return [x for x in self.variants if x['item'] == 'AthenaCharacter']

    @property
    def backpack_variants(self):
        return [x for x in self.variants if x['item'] == 'AthenaBackpack']

    @property
    def pickaxe_variants(self):
        return [x for x in self.variants if x['item'] == 'AthenaPickaxe']

    @property
    def backpack(self):
        base = self.get_prop('AthenaCosmeticLoadout_j')
        result = re.search(r".*\.(.*)", base['AthenaCosmeticLoadout']['backpackDef'].strip("'"))

        if result is None or result[1] == 'None':
            return None
        return result[1]

    @property
    def pickaxe(self):
        base = self.get_prop('AthenaCosmeticLoadout_j')
        result = re.search(r".*\.(.*)", base['AthenaCosmeticLoadout']['pickaxeDef'].strip("'"))

        if result is None or result[1] == 'None':
            return None
        return result[1]

    @property
    def emote(self):
        base = self.get_prop('FrontendEmote_j')
        result = re.search(r'.*(EID.*)\..*', base['FrontendEmote']['emoteItemDef'])

        if result is None or result[1] == 'None':
            return None
        return result[1]

    @property
    def banner(self):
        base = self.get_prop('AthenaBannerInfo_j')
        banner_info = base['AthenaBannerInfo']

        return (banner_info['bannerIconId'], banner_info['bannerColorId'], banner_info['seasonLevel'])

    @property
    def battlepass_info(self):
        base = self.get_prop('BattlePassInfo_j')
        bp_info = base['BattlePassInfo']

        return (bp_info['bHasPurchasedPass'], bp_info['passLevel'], bp_info['selfBoostXp'], bp_info['friendBoostXp'])
        
    @property
    def platform(self):
        base = self.get_prop('Platform_j')
        return base['Platform']['platformStr']

    def set_readiness(self, val):
        return {'GameReadiness_s': self.set_prop('GameReadiness_s', val)}

    def set_emote(self, emote=None, emote_ekey=None, section=None):
        data = (self.get_prop('FrontendEmote_j'))['FrontendEmote']
        
        if emote:
            data['emoteItemDef'] = emote
        if emote_ekey:
            data['emoteItemDefEncryptionKey'] = emote_ekey
        if section:
            data['emoteSection'] = section
        
        final = {'FrontendEmote': data}
        return {'FrontendEmote_j': self.set_prop('FrontendEmote_j', final)}

    def set_assisted_challenge(self, quest=None, completed=None):
        data = (self.get_prop('AssistedChallengeInfo_j'))['AssistedChallenge_j']

        if quest:
            data['questItemDef'] = quest
        if completed:
            data['objectivesCompleted'] = completed
        
        final = {'AssistedChallengeInfo': data}
        return {'AssistedChallengeInfo_j': self.set_prop('AssistedChallengeInfo_j', final)}

    def set_banner(self, banner_icon=None, banner_color=None, season_level=None):
        data = (self.get_prop('AthenaBannerInfo_j'))['AthenaBannerInfo']

        if banner_icon:
            data['bannerIconId'] = banner_icon
        if banner_color:
            data['bannerColorId'] = banner_color
        if season_level:
            data['seasonLevel'] = season_level
        
        final = {'AthenaBannerInfo': data}
        return {'AthenaBannerInfo_j': self.set_prop('AthenaBannerInfo_j', final)}

    def set_battlepass_info(self, has_purchased=None, level=None, self_boost_xp=None, 
                            friend_boost_xp=None):
        data = (self.get_prop('BattlePassInfo_j'))['BattlePassInfo']

        if has_purchased:
            data['bHasPurchasedPass'] = has_purchased
        if level:
            data['passLevel'] = level
        if self_boost_xp:
            data['selfBoostXp'] = self_boost_xp
        if friend_boost_xp:
            data['friendBoostXp'] = friend_boost_xp
        
        final = {'BattlePassInfo': data}
        return {'BattlePassInfo_j': self.set_prop('BattlePassInfo_j', final)}

    def set_cosmetic_loadout(self, character=None, character_ekey=None, backpack=None,
                             backpack_ekey=None, pickaxe=None, pickaxe_ekey=None, variants=None):
        data = (self.get_prop('AthenaCosmeticLoadout_j'))['AthenaCosmeticLoadout']

        if character:
            data['characterDef'] = character
        if character_ekey:
            data['characterEKey'] = character_ekey
        if backpack:
            data['backpackDef'] = backpack
        if backpack_ekey:
            data['backpackEKey'] = backpack_ekey
        if pickaxe:
            data['pickaxeDef'] = pickaxe
        if pickaxe_ekey:
            data['pickaxeEKey'] = pickaxe_ekey
        if variants:
            data['variants'] = variants
        
        final = {'AthenaCosmeticLoadout': data}
        return {'AthenaCosmeticLoadout_j': self.set_prop('AthenaCosmeticLoadout_j', final)}


class PartyMeta(MetaBase):
    def __init__(self, party, meta=None):
        super().__init__()
        self.party = party

        self.schema = {
            'PrimaryGameSessionId_s': '',
            'PartyState_s': 'BattleRoyaleView',
            'LobbyConnectionStarted_b': 'false',
            'MatchmakingResult_s': 'NoResults',
            'MatchmakingState_s': 'NotMatchmaking',
            'SessionIsCriticalMission_b': 'false',
            'ZoneTileIndex_U': '-1',
            'ZoneInstanceId_s': '',
            'TheaterId_s': '',
            'TileStates_j': json.dumps({
                'TileStates': [],
            }),
            'MatchmakingInfoString_s': '',
            'CustomMatchKey_s': '',
            'PlaylistData_j': json.dumps({
                'PlaylistData': {
                    'playlistName': 'Playlist_DefaultDuo',
                    'tournamentId': '',
                    'eventWindowId': '',
                    'regionId': 'EU',
                },
            }),
            'AthenaSquadFill_b': 'true',
            'AllowJoinInProgress_b': 'false',
            'LFGTime_s': '0001-01-01T00:00:00.000Z',
            'PartyIsJoinedInProgress_b': 'false',
            'GameSessionKey_s': '',
            'RawSquadAssignments_j': '',
            'PrivacySettings_j': json.dumps({
                'PrivacySettings': {
                    'partyType': self.party.config['privacy']['partyType'],
                    'partyInviteRestriction': self.party.config['privacy']['inviteRestriction'],
                    'bOnlyLeaderFriendsCanJoin': self.party.config['privacy']['onlyLeaderFriendsCanJoin'],
                },
            }),
            'PlatformSessions_j': json.dumps({
                'PlatformSessions': [],
            }),
        }

        if meta is not None:
            self.update(meta, raw=True)
    
    @property
    def playlist_info(self):
        base = self.get_prop('PlaylistData_j')
        info = base['PlaylistData']

        return (info['playlistName'], info['tournamentId'], info['eventWindowId'], info['regionId'])

    @property
    def squad_fill_enabled(self):
        return self.get_prop('AthenaSquadFill_b')

    @property
    def privacy(self):
        curr_priv = (self.get_prop('PrivacySettings_j'))['PrivacySettings']

        for privacy in PartyPrivacy:
            if curr_priv['partyType'] != privacy.value['partyType']:
                continue
            
            try:
                if curr_priv['partyInviteRestriction'] != privacy.value['partyInviteRestriction']:
                    continue

                if curr_priv['bOnlyLeaderFriendsCanJoin'] != privacy.value['bOnlyLeaderFriendsCanJoin']:
                    continue
            except KeyError:
                pass

            return privacy

    def set_playlist(self, playlist=None, tournament=None, event_window=None, region=None):
        data = (self.get_prop('PlaylistData_j'))['PlaylistData']

        if playlist:
            data['playlistName'] = playlist
        if tournament:
            data['tournamentId'] = tournament
        if event_window:
            data['eventWindowId'] = event_window
        if region:
            data['regionId'] = region
        
        final = {'PlaylistData': data}
        return {'PlaylistData_j': self.set_prop('PlaylistData_j', final)}

    def set_custom_key(self, key):
        return {'CustomMatchKey_s': self.set_prop('CustomMatchKey_s', key)}

    def set_fill(self, val):
        return {'AthenaSquadFill_b': self.set_prop('AthenaSquadFill_b', (str(val)).lower())}

    def set_privacy(self, privacy):
        updated = {}
        deleted = []

        p = self.get_prop('PrivacySettings_j')
        if p:
            updated['PrivacySettings_j'] = self.set_prop('PrivacySettings_j', {
                'PrivacySettings': {
                    **p['PrivacySettings'],
                    'partyType': privacy['partyType'],
                    'bOnlyLeaderFriendsCanJoin': privacy['onlyLeaderFriendsCanJoin'],
                    'partyInviteRestriction': privacy['inviteRestriction'],
                }
            })
        
        updated['urn:epic:cfg:presence-perm_s'] = self.set_prop(
            'urn:epic:cfg:presence-perm_s', 
            privacy['presencePermission'],
        )

        updated['urn:epic:cfg:accepting-members_b'] = self.set_prop(
            'urn:epic:cfg:accepting-members_b',
            str(privacy['acceptingMembers']).lower(),
        )

        updated['urn:epic:cfg:invite-perm_s'] = self.set_prop(
            'urn:epic:cfg:invite-perm_s',
            privacy['invitePermission'],
        )

        if privacy['partyType'] not in ('Public', 'FriendsOnly'):
            deleted.append('urn:epic:cfg:not-accepting-members')

        if privacy['partyType'] == 'Private':
            updated['urn:epic:cfg:not-accepting-members-reason_i'] = 7
        else:
            deleted.append('urn:epic:cfg:not-accepting-members-reason_i')
        
        return (updated, deleted)
    
    def refresh_squad_assignments(self):
        assignments = []

        i = 0
        for member in self.party.members.values():
            if member.is_leader:
                assignments.append({
                    'memberId': member.id,
                    'absoluteMemberIdx': 0,
                })
            else:
                i += 1
                assignments.append({
                    'memberId': member.id,
                    'absoluteMemberIdx': i,
                })
        
        return self.set_prop('RawSquadAssignments_j', {
            'RawSquadAssignments': assignments
        })   


class PartyMemberBase(User):
    def __init__(self, client, party, data):
        super().__init__(client=client, data=data)

        self._party = party

        self._joined_at = self.client.from_iso(data['joined_at'])
        self.meta = PartyMemberMeta(self, meta=data.get('meta'))
        self._update(data)

    @property
    def party(self):
        """Union[:class:`Party`, :class:`ClientParty`]: The party this member is a part of."""
        return self._party
    
    @property
    def joined_at(self):
        """:class:`datetime.datetime`: The UTC time of when this member joined its party."""
        return self._joined_at

    @property
    def is_leader(self):
        """:class:`bool`: Returns ``True`` if member is the leader else ``False``."""
        return True if self.role else False

    @property
    def ready(self):
        """:class:`bool`: ``True`` if this member is ready else ``False``."""
        return self.meta.ready
    
    @property
    def input(self):
        """:class:`str`: The input type this user is currently using."""
        return self.meta.input

    @property
    def assisted_challenge(self):
        """:class:`str`: The current assisted challenge chosen by this member.
        ``None`` if no assisted challenge is set.
        """
        return self.meta.assisted_challenge

    @property
    def outfit(self):
        """:class:`str`: The CID of the outfit this user currently has equipped."""
        return self.meta.outfit

    @property
    def outfit_variants(self):
        """:class:`list`: A list containing the raw variants data for the currently equipped
        outfit.
        
        .. warning::
            
            Variants doesn't seem to follow much logic. Therefore this returns the raw
            variants data received from fortnite's service. This can be directly passed with the
            ``variants`` keyword to :meth:`PartyMember.set_outfit()`.
        """
        return self.meta.outfit_variants

    @property
    def backpack_variants(self):
        """:class:`list`: A list containing the raw variants data for the currently equipped
        backpack.
        
        .. warning::
            
            Variants doesn't seem to follow much logic. Therefore this returns the raw
            variants data received from fortnite's service. This can be directly passed with the
            ``variants`` keyword to :meth:`PartyMember.set_backpack()`.
        """
        return self.meta.backpack_variants

    @property
    def pickaxe_variants(self):
        """:class:`list`: A list containing the raw variants data for the currently equipped
        pickaxe.
        
        .. warning::
            
            Variants doesn't seem to follow much logic. Therefore this returns the raw
            variants data received from fortnite's service. This can be directly passed with the
            ``variants`` keyword to :meth:`PartyMember.set_pickaxe()`.
        """
        return self.meta.pickaxe_variants

    @property
    def backpack(self):
        """:class:`str`: The BID of the backpack this member currently has equipped. 
        ``None`` if no backpack is equipped.
        """
        return self.meta.backpack
    
    @property
    def pickaxe(self):
        """:class:`str`: The pickaxe id of the pickaxe this member currently has equipped."""
        return self.meta.pickaxe

    @property
    def emote(self):
        """:class:`str`: The EID of the emote this member is currenyly playing.
        ``None`` if no emote is currently playing.
        """
        return self.meta.emote

    @property
    def banner(self):
        """:class:`tuple`: A tuple consisting of the icon id, color id and the season level.
        
        Example output: ::

            ('standardbanner15', 'defaultcolor15', 50)
        """
        return self.meta.banner

    @property
    def battlepass_info(self):
        """:class:`tuple`: A tuple consisting of has purchased, battlepass level, self boost xp, friends boost xp.
        
        Example output: ::
        
            (True, 30, 80, 70)    
        """
        return self.meta.battlepass_info
    
    @property
    def platform(self):
        """:class:`str`: The platform this user currently uses."""
        return self.meta.platform

    def _update(self, data):
        super()._update(data)
        self.role = data.get('role')
        self.revision = data.get('revision', 0)
        self.connections = data.get('connections', [])

    def update(self, data):
        if data['revision'] > self.revision:
            self.revision = data['revision']
        self.meta.update(data['member_state_updated'], raw=True)
        self.meta.remove(data['member_state_removed'])

    def update_role(self, role):
        self.role = role

    def create_variants(self, item="AthenaCharacter", particle_config='Emissive', **kwargs):
        """Creates the variants list by the variants you set.

        .. warning::

            This function is built upon data received from only some of the available outfits
            with variants. There is little logic behind the variants function therefore there
            might be some unexpected issues with this function. Please report such issues by
            creating an issue on the issue tracker or by reporting it to me on discord.
        
        Example usage: ::
        
            # set the outfit to soccer skin with Norwegian jersey and
            # the jersey number set to 99 (max number).
            async def set_soccer_skin():
                me = client.user.party.me

                variants = me.create_variants(
                    pattern=0,
                    numeric=99,
                    jersey_color='Norway'
                )

                await me.set_outfit(
                    asset='CID_149_Athena_Commando_F_SoccerGirlB',
                    variants=variants
                )
        
        Parameters
        ----------
        item: :class:`str`
            The variant item type. This defaults to ``AthenaCharacter`` which
            is what you want to use if you are changing skin variants.
        particle_config: :class:`str`
            The type of particle you want to use. The available types 
            are ``Emissive`` (default), ``Mat`` and ``Particle``.
        pattern: Optional[:class:`int`]
            The pattern number you want to use.
        numeric: Optional[:class:`int`]
            The numeric number you want to use.
        clothing_color: Optional[:class:`int`]
            The clothing color you want to use.
        jersey_color: Optional[:class:`str`]
            The jersey color you want to use. For soccer skins this is the country
            you want the jersey to represent.
        parts: Optional[:class:`int`]
            The parts number you want to use.
        progressive: Optional[:class:`int`]
            The progressing number you want to use.
        particle: Optional[:class:`int`]
            The particle number you want to use.
        material: Optional[:class:`int`]
            The material number you want to use.
        emissive: Optional[:class:`int`]
            The emissive number you want to use.

        Returns
        -------
        List[:class:`dict`]
            List of dictionaries including all variants data.
        """
        config = {
            'pattern': 'Mat{}',
            'numeric': 'Numeric.{}',
            'clothing_color': 'Mat{}',
            'jersey_color': 'Color.{}',
            'parts': 'Stage{}',
            'progressive': 'Stage{}',
            'particle': '{}{}',
            'material': 'Mat{}',
            'emissive': 'Emissive{}'
        }

        variant = []
        for channel, value in kwargs.items():
            v = {
                'item': item,
                'channel': ''.join([x.capitalize() for x in channel.split('_')])
            }

            if channel == 'particle':
                v['variant'] = config[channel].format(particle_config, value)
            elif channel == 'JerseyColor':
                v['variant'] = config[channel].format(value.upper())
            else:
                v['variant'] = config[channel].format(value)
            variant.append(v)
        return variant


class PartyMember(PartyMemberBase):
    """Represents a party member.
    
    Attributes
    ----------
    client: :class:`Client`
        The client.
    """

    def __init__(self, client, party, data):
        super().__init__(client, party, data)

    async def kick(self):
        """|coro|
        
        Kicks this member from the party.

        Raises
        ------
        PartyPermissionError
            You are not the leader of the party.
        PartyError
            You attempted to kick yourself.
        HTTPException
            Something else went wrong when trying to kick this member.
        """
        if self.client.user.id != self.party.leader.id:
            raise PartyPermissionError(
                'You must be partyleader to perform this action')

        if self.client.user.id == self.id:
            raise PartyError('You can\'t kick yourself')

        await self.client.http.party_kick_member(self.party.id, self.id)
        self.party._remove_member(self.id)

    async def promote(self):
        """|coro|
        
        Promotes this user to partyleader.

        Raises
        ------
        PartyPermissionError
            You are not the leader of the party.
        PartyError
            You are already partyleader.
        HTTPException
            Something else went wrong when trying to promote this member.
        """
        if self.client.user.id != self.party.leader.id:
            raise PartyPermissionError(
                'You must be partyleader to perform this action')

        if self.client.user.id == self.id:
            raise PartyError('You are already partyleader')

        await self.client.http.party_promote_member(self.party.id, self.id)


class ClientPartyMember(PartyMemberBase):
    """Represents a the Clients party member object.
    
    Attributes
    ----------
    client: :class:`Client`
        The client.
    """

    def __init__(self, client, party, data):
        super().__init__(client, party, data)

        self.queue = asyncio.Queue(loop=self.client.loop)
        self.queue_active = False

    async def _patch(self, updated=None):
        meta = updated or self.meta.schema
        await self.client.http.party_update_member_meta(
            party_id=self.party.id,
            user_id=self.id,
            meta=meta,
            revision=self.revision
        )
        self.revision += 1
    
    async def patch(self, updated=None):
        future = self.client.loop.create_future()
        await self.queue.put((self._patch, future, {'updated': updated}))

        if not self.queue_active:
            asyncio.ensure_future(self._run_queue(), loop=self.client.loop)
        return await future

    async def _run_queue(self):
        self.queue_active = True
        try:
            while not self.queue.empty():
                func, future, kwargs = await self.queue.get()
                if func is None:
                    break

                while True:
                    try:
                        res = await func(**kwargs)
                        future.set_result(res)
                        break
                    except HTTPException as exc:
                        if exc.message_code == 'errors.com.epicgames.social.party.stale_revision':
                            self.revision = int(exc.message_vars[1])
                            continue
                        raise HTTPException(exc.response, exc.raw)
                    except FortniteException as exc:
                        future.set_exception(exc)
                        break

        except RuntimeError:
            pass
        self.queue_active = False

    async def leave(self):
        """|coro|
        
        Leaves the party.

        Raises
        ------
        HTTPException
            An error occured while requesting to leave the party.

        Returns
        -------
        :class:`Party`
            The new party the client is connected to after leaving.
        """
        await self.client.http.party_leave(self.party.id)
        self.client.xmpp.muc_room = None
        p = await self.client._create_party()
        self.client.user.set_party(p)
        return p

    async def set_ready(self, value):
        """|coro|
        
        Sets the readiness of the client.
        
        Parameters
        ----------
        value: :class:`bool`
            **True** to set it to ready.
            **False** to set it to unready.
            **None** to set it to sitting out.
        """
        prop = self.meta.set_readiness(
            val='Ready' if value is True else ('NotReady' if value is False else 'SittingOut')
        )
        await self.patch(updated=prop)

    async def set_outfit(self, asset, key=None, variants=None):
        """|coro|
        
        Sets the outfit of the client.

        Parameters
        ----------
        asset: Required[:class:`str`]
            The CID of the outfit.

            .. note::

                You don't have to include the full path of the asset. The CID is
                enough.
        key: Optional[:class:`str`]
            The encyption key to use for this skin.
        variants: Optional[:class:`list`]
            The variants to use for this outfit.
        """
        if '.' not in asset:
            asset = "AthenaCharacterItemDefinition'/Game/Athena/Items/Cosmetics/Characters/" \
                    "{0}.{0}'".format(asset)

        if variants is not None:
            variants = [x for x in self.meta.variants if x['item'] != 'AthenaCharacter'] + variants

        prop = self.meta.set_cosmetic_loadout(
            character=asset,
            character_ekey=key,
            variants=variants
        )
        await self.patch(updated=prop)
        
    async def set_backpack(self, asset, key=None, variants=None):
        """|coro|
        
        Sets the backpack of the client.

        Parameters
        ----------
        asset: Required[:class:`str`]
            The CID of the backpack.

            .. note::

                You don't have to include the full path of the asset. The CID is
                enough.
        key: Optional[:class:`str`]
            The encyption key to use for this backpack.
        variants: Optional[:class:`list`]
            The variants to use for this backpack.
        """
        if '.' not in asset:
            asset = "AthenaBackpackItemDefinition'/Game/Athena/Items/Cosmetics/Backpacks/" \
                    "{0}.{0}'".format(asset)

        if variants is not None:
            variants = [x for x in self.meta.variants if x['item'] != 'AthenaBackpack'] + variants

        prop = self.meta.set_cosmetic_loadout(
            backpack=asset,
            backpack_ekey=key,
            variants=variants
        )
        await self.patch(updated=prop)
    
    async def set_pickaxe(self, asset, key=None, variants=None):
        """|coro|
        
        Sets the pickaxe of the client.

        Parameters
        ----------
        asset: Required[:class:`str`]
            The CID of the pickaxe.

            .. note::

                You don't have to include the full path of the asset. The CID is
                enough.
        key: Optional[:class:`str`]
            The encyption key to use for this pickaxe.
        variants: Optional[:class:`list`]
            The variants to use for this pickaxe.
        """
        if '.' not in asset:
            asset = "AthenaPickaxeItemDefinition'/Game/Athena/Items/Cosmetics/Pickaxes/" \
                    "{0}.{0}'".format(asset)

        if variants is not None:
            variants = [x for x in self.meta.variants if x['item'] != 'AthenaPickaxe'] + variants

        prop = self.meta.set_cosmetic_loadout(
            pickaxe=asset,
            pickaxe_ekey=key,
            variants=variants
        )
        await self.patch(updated=prop)

    async def set_emote(self, asset, run_for=None, key=None, section=None):
        """|coro|
        
        Sets the emote of the client.

        Parameters
        ----------
        asset: Required[:class:`str`]
            The EID of the emote.

            .. note::

                You don't have to include the full path of the asset. The EID is
                enough.
        run_for: Optional[:class:`int`]
            Seconds this emote should run for before being cancelled. ``None`` (default) means 
            will run infinitely and you can then clear it with :meth:`PartyMember.clear_emote()`.
        key: Optional[:class:`str`]
            The encyption key to use for this emote.
        section: Optional[:class:`int`]
            The section.
        """
        if '.' not in asset:
            asset = "AthenaDanceItemDefinition'/Game/Athena/Items/Cosmetics/Dances/" \
                    "{0}.{0}'".format(asset)

        prop = self.meta.set_emote(
            emote=asset,
            emote_ekey=key,
            section=section
        )
        await self.patch(updated=prop)

        if run_for is not None:
            self.client.loop.create_task(self._schedule_clear_emote(run_for))

    async def _schedule_clear_emote(self, seconds):
        await asyncio.sleep(seconds)
        await self.clear_emote()
    
    async def clear_emote(self):
        """|coro|
        
        Clears/stops the emote currently playing.
        """
        prop = self.meta.set_emote(
            emote='None',
            emote_ekey='',
            section=-1
        )
        await self.patch(updated=prop)
    
    async def set_banner(self, icon=None, color=None, season_level=None):
        """|coro|
        
        Sets the banner of the client.

        Parameters
        ----------
        icon: Optional[:class:`str`]
            The icon to use.
            *Defaults to standardbanner15*
        color: Optional[:class:`str`]
            The color to use.
            *Defaults to defaultcolor15*
        season_level: Optional[:class:`int`]
            The season level.
            *Defaults to 1*
        """
        prop = self.meta.set_banner(
            banner_icon=icon,
            banner_color=color,
            season_level=season_level
        )
        await self.patch(updated=prop)
    
    async def set_battlepass_info(self, has_purchased=None, level=None, self_boost_xp=None,
                                  friend_boost_xp=None):
        """|coro|
        
        Sets the battlepass info of the client.

        .. note::

            This is simply just for showing off. It just shows visually so
            boostxp, level and stuff will not work, just show.

        Parameters
        ----------
        has_purchased: Optional[:class:`bool`]
            Shows visually that you have purchased the battlepass.
            *Defaults to False*
        level: Optional[:class:`int`]
            Sets the level and shows it visually.
            *Defaults to 1*
        self_boost_xp: Optional[:class:`int`]
            Sets the self boost xp and shows it visually.
        friend_boost_xp: Optional[:class:`int`]
            Set the friend boost xp and shows it visually.
        """
        prop = self.meta.set_battlepass_info(
            has_purchased=has_purchased,
            level=level,
            self_boost_xp=self_boost_xp,
            friend_boost_xp=friend_boost_xp
        )
        await self.patch(updated=prop)
    
    async def set_assisted_challenge(self, quest=None, num_completed=None):
        """|coro|
        
        Sets the assisted challenge.
        
        Parameters
        ----------
        quest: :class:`str`
            The quest to set.

            .. note::

                You don't have to include the full path of the quest. The quest id is
                enough.
        num_completed: :class:`int`
            How many quests you have completed, I think (didn't test this).
        """
        if '.' not in quest:
            quest = "FortQuestItemDefinition'/Game/Athena/Items/Quests/DailyQuests/Quests/" \
                    "{0}.{0}'".format(quest)

        prop = self.meta.set_assisted_challenge(
            quest=quest,
            completed=num_completed
        )
        await self.patch(updated=prop)    


class PartyBase:

    def __init__(self, client, data):
        self._client = client
        self._id = data.get('id')
        self._members = {}
        self._applicants = data.get('applicants', [])

        self._update_invites(data.get('invites', []))
        self._update_config(data.get('config'))
        self.meta = PartyMeta(self, data['meta'])

    @property
    def client(self):
        """:class:`Client`: The client."""
        return self._client

    @property
    def id(self):
        """:class:`str`: The party's id."""
        return self._id

    @property
    def members(self):
        """:class:`dict`: Mapping of the party's members. *Example: {memberid: :class:`PartyMember`}*"""
        return self._members

    @property
    def member_count(self):
        """:class:`int`: The amount of member currently in this party."""
        return len(self._members)

    @property
    def applicants(self):
        """:class:`list`: The party's applicants."""
        return self._applicants

    @property
    def leader(self):
        """:class:`PartyMember`: The leader of the party."""
        for member in self.members.values():
            if member.is_leader:
                return member

    @property
    def playlist_info(self):
        """:class:`tuple`: A tuple containing the name, tournament, event window and region
        of the currently set playlist.
        
        Example output: ::

            # output for default duos
            ('Playlist_DefaultDuo', '', '', 'EU')

            # output for arena trios
            ('Playlist_ShowdownAlt_Trios', 'epicgames_Arena_S10_Trios', 'Arena_S10_Division1_Trios', 'EU')
        """
        return self.meta.playlist_info

    @property
    def squad_fill_enabled(self):
        """:class:`bool`: ``True`` if squad fill is enabled else ``False``."""
        return self.meta.squad_fill_enabled

    @property
    def privacy(self):
        """:class:`PartyPrivacy`: The currently set privacy of this party."""
        return self.meta.privacy

    def _add_member(self, member):
        self.members[member.id] = member

    def _remove_member(self, id):
        if not isinstance(id, str):
            id = id.id
        del self.members[id]

    def _update(self, data):
        try:
            config = data['config']
        except KeyError:
            config = {
                'joinability': data['party_privacy_type'],
                'max_size': data['max_number_of_members'],
                'sub_type': data['party_sub_type'],
                'type': data['party_type'],
                'invite_ttl_seconds': data['invite_ttl_seconds']
            }

        self._update_config({**self.config, **config})

        self.meta.update(data['party_state_updated'], raw=True)
        self.meta.remove(data['party_state_removed'])

        privacy = self.meta.get_prop('PrivacySettings_j')
        _p = privacy['PrivacySettings']
        found = False
        for d in PartyPrivacy:
            p = d.value
            if p['partyType'] != _p['partyType']:
                continue
            if p['inviteRestriction'] != _p['partyInviteRestriction']:
                continue
            if p['onlyLeaderFriendsCanJoin'] != _p['bOnlyLeaderFriendsCanJoin']:
                continue
            found = p
            break

        if found:
            self.config['privacy'] = found

    def _update_invites(self, invites):
        self.invites = invites

    def _update_config(self, config=None):
        config = config if config is not None else {}

        self.join_confirmation = config['join_confirmation']
        self.max_size = config['max_size']
        self.invite_ttl_seconds = config.get('invite_ttl_seconds', config['invite_ttl'])
        self.sub_type = config['sub_type']
        self.config = {**self.client.default_party_config, **config}

    async def _update_members(self, raw_members):
        for raw in raw_members:
            user_id = raw.get('account_id', raw.get('accountId'))
            if user_id == self.client.user.id:
                user = self.client.user
            else:
                user = self.client.get_user(user_id)
                if user is None:
                    user = await self.client.fetch_profile(user_id)
            raw = {**raw, **(user.get_raw())}

            member = PartyMember(self.client, self, raw)
            self._add_member(member)

        ids = map(lambda r: raw.get('account_id', raw.get('accountId')), raw_members)
        to_remove = []
        for m in self.members.values():
            if m.id not in ids:
                to_remove.append(m.id)

        for id in to_remove:
            self._remove_member(id)


class Party(PartyBase):
    """Represent a party that the ClientUser is not yet a part of."""

    def __init__(self, client, data):
        super().__init__(client, data)


class ClientParty(PartyBase):
    """Represents ClientUser's party."""

    def __init__(self, client, data):
        super().__init__(client, data)

        self.last_raw_status = None
        self._me = None

        self.queue = asyncio.Queue(loop=self.client.loop)
        self.queue_active = False
        
        self._update_revision(data.get('revision', 0))
        self._update_invites(data.get('invites', []))
        self._update_config(data.get('config'))
        self.meta = PartyMeta(self, data['meta'])

    @property
    def me(self):
        """:class:`ClientPartyMember`: The clients partymember object."""
        return self._me

    @property
    def muc_jid(self):
        """:class:`aioxmpp.JID`: The JID of the party MUC."""
        return aioxmpp.JID.fromstr('Party-{}@muc.prod.ol.epicgames.com'.format(self.id))

    def _add_clientmember(self, member):
        self._me = member

    def _remove_member(self, id):
        if not isinstance(id, str):
            id = id.id
        del self.members[id]
        self.update_presence()

    def update_presence(self, text=None, conf={}):
        perm = self.config['privacy']['presencePermission']
        if perm == 'Noone' or (perm == 'Leader' and (self.me is not None and not self.me.is_leader)):
            join_data = {
                'bInPrivate': True
            }
        else:
            join_data = {
                'sourceId': self.client.user.id,
                'sourceDisplayName': self.client.user.display_name,
                'sourcePlatform': self.client.platform.value,
                'partyId': self.id,
                'partyTypeId': 286331153,
                'key': 'k',
                'appId': 'Fortnite',
                'buildId': self.client.party_build_id,
                'partyFlags': -2024557306,
                'notAcceptingReason': 0,
                'pc': len(self.members.keys()),
            }

        _default_status = {
            'Status': 'Battle Royale Lobby - {0} / {1}'.format(len(self.members.keys()), self.max_size),
            'bIsPlaying': True,
            'bIsJoinable': False,
            'bHasVoiceSupport': False,
            'SessionId': '',
            'Properties': {
                'party.joininfodata.286331153_j': join_data,
                'FortBasicInfo_j': {
                    'homeBaseRating': 1,
                },
                'FortLFG_I': '0',
                'FortPartySize_i': 1,
                'FortSubGame_i': 1,
                'InUnjoinableMatch_b': False,
                'FortGameplayStats_j': {
                    'state': '',
                    'playlist': 'None',
                    'numKills': 0,
                    'bFellToDeath': False,
                },
                'GamePlaylistName_s': self.meta.playlist_info[0],
                'Event_PlayersAlive_s': '0',
                'Event_PartySize_s': str(len(self.members)),
                'Event_PartyMaxSize_s': str(self.max_size),
            },
        }

        if text is None:
            if self.client.status is None:
                _text = {}
            else:
                _text = {'Status': str(self.client.status)}
        else:
            _text = {'Status': str(text)}
        
        if self.client.status is not False:
            self.last_raw_status = {**_default_status, **conf, **_text}
            self.client.xmpp.set_presence(status=self.last_raw_status)
        
    def _update(self, data):
        if self.revision < data['revision']:
            self.revision = data['revision']

        try:
            config = data['config']
        except KeyError:
            config = {
                'joinability': data['party_privacy_type'],
                'max_size': data['max_number_of_members'],
                'sub_type': data['party_sub_type'],
                'type': data['party_type'],
                'invite_ttl_seconds': data['invite_ttl_seconds']
            }
        
        self._update_config({**self.config, **config})

        self.meta.update(data['party_state_updated'], raw=True)
        self.meta.remove(data['party_state_removed'])

        privacy = self.meta.get_prop('PrivacySettings_j')
        _p = privacy['PrivacySettings']
        found = False
        for d in PartyPrivacy:
            p = d.value
            if p['partyType'] != _p['partyType']:
                continue
            if p['inviteRestriction'] != _p['partyInviteRestriction']:
                continue
            if p['onlyLeaderFriendsCanJoin'] != _p['bOnlyLeaderFriendsCanJoin']:
                continue
            found = p
            break
        
        if found:
            self.config['privacy'] = found
        
        if self.client.status is not False:
            self.update_presence()

    def _update_revision(self, revision):
        self.revision = revision

    def _update_config(self, config=None):
        config = config if config is not None else {} 
        
        self.join_confirmation = config['join_confirmation']
        self.max_size = config['max_size']
        self.invite_ttl_seconds = config.get('invite_ttl_seconds', config['invite_ttl'])
        self.sub_type = config['sub_type']
        self.config = {**self.client.default_party_config, **config}

    async def _update_members(self, raw_members):
        for raw in raw_members:
            user_id = raw.get('account_id', raw.get('accountId'))
            if user_id == self.client.user.id:
                user = self.client.user
            else:
                user = self.client.get_user(user_id)
                if user is None:
                    user = await self.client.fetch_profile(user_id)
            raw = {**raw, **(user.get_raw())}

            member = PartyMember(self.client, self, raw)
            self._add_member(member)
        
            if member.id == self.client.user.id:
                clientmember = ClientPartyMember(self.client, self, raw)
                self._add_clientmember(clientmember)

        ids = map(lambda r: raw.get('account_id', raw.get('accountId')), raw_members)
        to_remove = []
        for m in self.members.values():
            if m.id not in ids:
                to_remove.append(m.id)
            
        for id in to_remove:
            self._remove_member(id)

    async def _update_members_meta(self):
        data = await self.client.http.party_lookup(self.id)
        for m in data['members']:
            try:
                member = self.members[m['account_id']]
                member.meta.update(m['meta'], raw=True)
            except KeyError:
                pass

    async def join_chat(self):
        await self.client.xmpp.join_muc(self.id)
    
    async def send(self, content):
        """|coro|
        
        Sends a message to this party's chat.

        Parameters
        ----------
        content: :class:`str`
            The content of the message.
        """
        await self.client.xmpp.send_party_message(content)

    async def _patch(self, updated=None, deleted=None):
        await self.client.http.party_update_meta(
            party_id=self.id,
            updated_meta=updated or self.meta.schema,
            deleted_meta=deleted or [],
            config=self.config,
            revision=self.revision
        )
        self.revision += 1
    
    async def patch(self, updated=None, deleted=None):
        future = self.client.loop.create_future()
        await self.queue.put((self._patch, future, {'updated': updated, 'deleted': deleted}))

        if not self.queue_active:
            asyncio.ensure_future(self._run_queue(), loop=self.client.loop)
        return await future

    async def _run_queue(self):
        self.queue_active = True
        try:
            while not self.queue.empty():
                func, future, kwargs = await self.queue.get()
                if func is None:
                    break
                
                while True:
                    try:
                        res = await func(**kwargs)
                        future.set_result(res)
                        break
                    except HTTPException as exc:
                        if exc.message_code == 'errors.com.epicgames.social.party.stale_revision':
                            self.revision = int(exc.message_vars[1])
                            continue
                        raise HTTPException(exc.response, exc.raw)
                    except FortniteException as exc:
                        future.set_exception(exc)
                        break

        except RuntimeError:
            pass
        self.queue_active = False
    
    async def invite(self, user_id):
        """|coro|
        
        Invites a user to the party.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the user to invite.

        Raises
        ------
        PartyError
            The party is full.
        HTTPException
            Something else went wrong when trying to invite the user.
        """
        if len(self.members.keys()) == self.max_size:
            raise PartyError('Party is full')
        
        await self.client.http.party_send_invite(user_id)

    async def _leave(self):
        """|coro|
        
        Leaves the party.
        
        Raises
        ------
        HTTPException
            Something went wrong when trying to leave the party.
        """
        self.client.xmpp.muc_room = None
        await self.client.http.party_leave(self.id)

    async def set_privacy(self, privacy):
        """|coro|
        
        Sets the privacy of the party.
        
        Parameters
        ----------
        privacy: :class:`.PartyPrivacy`

        Raises
        ------
        PartyPermissionError
            The client is not the leader of the party.
        """
        if self.leader.id != self.client.user.id:
            raise PartyPermissionError('You have to be leader for this action to work.')

        if not isinstance(privacy, dict):
            privacy = privacy.value

        updated, deleted = self.meta.set_privacy(privacy)
        await self.patch(updated=updated, deleted=deleted)
    
    async def set_playlist(self, playlist=None, tournament=None, event_window=None, region=None):
        """|coro|
        
        Sets the current playlist of the party.

        Sets the playlist to Duos EU: ::

            await party.set_playlist(
                playlist='Playlist_DefaultDuo',
                region='EU'
            )
        
        Sets the playlist to Arena Trios EU (Replace ``Trios`` with ``Solo`` for arena solo): ::

            await party.set_playlist(
                playlist='Playlist_ShowdownAlt_Trios',
                tournament='epicgames_Arena_S10_Trios',
                event_window='Arena_S10_Division1_Trios',
                region='EU'
            )

        Parameters
        ----------
        playlist: Optional[:class:`str`]
            The name of the playlist.
            *Defaults to 'EU'*
        tournament: Optional[:class:`str`]
            The tournament id.
        event_window: Optional[:class:`str`]
            The event window id.
        region: Optional[:class:`Region`]
            The region to use.
            *Defaults to :attr:`Region.EUROPE`*

        Raises
        ------
        PartyPermissionError
            The client is not the leader of the party.
        """
        if self.leader.id != self.client.user.id:
            raise PartyPermissionError('You have to be leader for this action to work.')

        if region is not None:
            region = region.value

        prop = self.meta.set_playlist(
            playlist=playlist,
            tournament=tournament,
            event_window=event_window,
            region=region
        )
        await self.patch(updated=prop)
    
    async def set_custom_key(self, key):
        """|coro|
        
        Sets the custom key of the party.

        Parameters
        ----------
        key: :class:`str`
            The key to set.

        Raises
        ------
        PartyPermissionError
            The client is not the leader of the party.
        """
        if self.leader.id != self.client.user.id:
            raise PartyPermissionError('You have to be leader for this action to work.')

        prop = self.meta.set_custom_key(
            key=key
        )
        await self.patch(updated=prop)

    async def set_fill(self, value):
        """|coro|
        
        Sets the fill status of the party.

        Parameters
        ----------
        value: :class:`bool`
            What to set the fill status to.

            **True** sets it to 'Fill'
            **False** sets it to 'NoFill'

        Raises
        ------
        PartyPermissionError
            The client is not the leader of the party.
        """
        if self.leader.id != self.client.user.id:
            raise PartyPermissionError('You have to be leader for this action to work.')

        prop = self.meta.set_fill(val=value)
        await self.patch(updated=prop)


class PartyInvitation:
    """Represents a party invitation.
    
    Attributes
    ----------
    client: :class:`Client`
        The client.
    party: :class:`Party`
        The party the invitation belongs to.
    net_cl: :class:`str`
        The net_cl received by the sending client.
    author: :class:`Friend`
        The friend that invited you to the party.
    created_at: :class:`datetime.datetime`
        The UTC time this invite was created at.
    """
    def __init__(self, client, party, net_cl, data):
        self.client = client
        self.party = party
        self.net_cl = net_cl

        self.author = self.client.get_friend(data['sent_by'])
        self.created_at = self.client.from_iso(data['sent_at'])

    async def accept(self):
        """|coro|
        
        Accepts the invitation and joins the party.

        Raises
        ------
        HTTPException
            Something went wrong when accepting the invitation.
        """
        if self.net_cl != self.client.net_cl:
            raise PartyError('Incompatible net_cl')

        await self.client.join_to_party(self.party.id)

    async def decline(self):
        """|coro|
        
        Declines the invitation.

        Raises
        ------
        PartyError
            The clients net_cl is not compatible with the received net_cl.
        HTTPException
            Something went wrong when declining the invitation.
        """
        await self.client.http.party_decline_invite(self.party.id)


class PartyJoinConfirmation:
    """Represents a join confirmation.
    
    Attributes
    ----------
    client: :class:`Client`
        The client.
    party: :class:`Party`
        The party the user wants to join.
    user: :class:`User`
        The user who requested to join the party.
    created_at: :class:`datetime.datetime`
        The UTC time of when the join confirmation was received.
    """
    def __init__(self, client, party, data):
        self.client = client
        self.party = party
        self.user = User(self.client, data)
        self.created_at = self.client.from_iso(data['sent'])

    async def confirm(self):
        """|coro|
        
        Confirms this user.

        Raises
        ------
        HTTPException
            Something went wrong when confirming this user.
        """
        await self.client.http.party_member_confirm(self.party.id, self.user.id)

    async def reject(self):
        """|coro|
        
        Rejects this user.

        Raises
        ------
        HTTPException
            Something went wrong when rejecting this user.
        """
        await self.client.http.party_member_reject(self.party.id, self.user.id)
 
