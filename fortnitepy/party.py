# -*- coding: utf-8 -*-

"""
MIT License

Copyright (c) 2019-2020 Terbau

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
import asyncio
import random
import aioxmpp
import re
import functools
import datetime

from typing import (TYPE_CHECKING, Optional, Any, List, Dict, Union, Tuple,
                    Awaitable)

from .errors import (FortniteException, PartyError, Forbidden, HTTPException,
                     NotFound)
from .user import User
from .enums import PartyPrivacy, DefaultCharactersChapter2, Region

if TYPE_CHECKING:
    from .client import Client


def get_random_default_character() -> str:
    return (random.choice(list(DefaultCharactersChapter2))).name


def get_random_hex_color() -> str:
    def r():
        return random.randint(0, 255)

    return '#{:02x}{:02x}{:02x}'.format(r(), r(), r())


class MaybeLock:
    def __init__(self, lock: asyncio.Lock,
                 loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self.lock = lock
        self.loop = loop or asyncio.get_event_loop()
        self._cleanup = False

    async def _acquire(self) -> None:
        await self.lock.acquire()
        self._cleanup = True

    async def __aenter__(self) -> 'MaybeLock':
        self._task = self.loop.create_task(self._acquire())
        return self

    async def __aexit__(self, *args: list) -> None:
        if not self._task.cancelled():
            self._task.cancel()

        if self._cleanup:
            self.lock.release()


class MetaBase:
    def __init__(self) -> None:
        self.schema = {}

    def set_prop(self, prop: str, value: Any, *,
                 raw: bool = False) -> Any:
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

    def get_prop(self, prop: str, *, raw: bool = False) -> Any:
        if raw:
            self.schema.get(prop)

        _t = prop[-1:]
        _v = self.schema.get(prop)
        if _t == 'b':
            return not (_v is None or (isinstance(_v, str)
                        and _v.lower() == 'false'))
        elif _t == 'j':
            return {} if _v is None else json.loads(_v)
        elif _t == 'U':
            return {} if _v is None else int(_v)
        else:
            return '' if _v is None else str(_v)

    def update(self, schema: Optional[dict] = None, *,
               raw: bool = False) -> None:
        if schema is None:
            return

        for prop, value in schema.items():
            self.set_prop(prop, value, raw=raw)

    def remove(self, schema: Union[List[str], Dict[str, Any]]):
        for prop in schema:
            try:
                del self.schema[prop]
            except KeyError:
                pass


class PartyMemberMeta(MetaBase):
    def __init__(self, member: 'PartyMemberBase',
                 meta: Optional[dict] = None) -> None:
        super().__init__()
        self.member = member
        self.meta_ready_event = asyncio.Event(loop=self.member.client.loop)

        self.def_character = get_random_default_character()
        self.schema = {
            'Location_s': 'PreLobby',
            'CampaignHero_j': json.dumps({
                'CampaignHero': {
                    'heroItemInstanceId': '',
                    'heroType': ("FortHeroType'/Game/Athena/Heroes/{0}.{0}'"
                                 "".format(self.def_character)),
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
                    'characterDef': ("AthenaCharacterItemDefinition'/Game/"
                                     "Athena/Items/Cosmetics/Characters/"
                                     "{0}.{0}'".format(self.def_character)),
                    'characterEKey': '',
                    'backpackDef': 'None',
                    'backpackEKey': '',
                    'pickaxeDef': ("AthenaPickaxeItemDefinition'/Game/Athena/"
                                   "Items/Cosmetics/Pickaxes/"
                                   "DefaultPickaxe.DefaultPickaxe'"),
                    'pickaxeEKey': '',
                    'contrailDef': 'None',
                    'contrailEKey': '',
                    'scratchpad': [],
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

        client = member.client
        if member.id == client.user.id and isinstance(member,
                                                      ClientPartyMember):
            fut = asyncio.ensure_future(
                member._edit(*client.default_party_member_config,
                             from_default=True),
                loop=client.loop
            )
            fut.add_done_callback(lambda *args: self.meta_ready_event.set())

    @property
    def ready(self) -> bool:
        return self.get_prop('GameReadiness_s')

    @property
    def input(self) -> str:
        return self.get_prop('CurrentInputType_s')

    @property
    def assisted_challenge(self) -> str:
        base = self.get_prop('AssistedChallengeInfo_j')
        return base['AssistedChallengeInfo']['questItemDef']

    @property
    def outfit(self) -> str:
        base = self.get_prop('AthenaCosmeticLoadout_j')
        return base['AthenaCosmeticLoadout']['characterDef']

    @property
    def backpack(self) -> str:
        base = self.get_prop('AthenaCosmeticLoadout_j')
        return base['AthenaCosmeticLoadout']['backpackDef']

    @property
    def pickaxe(self) -> str:
        base = self.get_prop('AthenaCosmeticLoadout_j')
        return base['AthenaCosmeticLoadout']['pickaxeDef']

    @property
    def contrail(self) -> str:
        base = self.get_prop('AthenaCosmeticLoadout_j')
        return base['AthenaCosmeticLoadout']['contrailDef']

    @property
    def variants(self) -> List[Dict[str, str]]:
        base = self.get_prop('AthenaCosmeticLoadout_j')
        return base['AthenaCosmeticLoadout']['variants']

    @property
    def outfit_variants(self) -> List[Dict[str, str]]:
        return [x for x in self.variants if x['item'] == 'AthenaCharacter']

    @property
    def backpack_variants(self) -> List[Dict[str, str]]:
        return [x for x in self.variants if x['item'] == 'AthenaBackpack']

    @property
    def pickaxe_variants(self) -> List[Dict[str, str]]:
        return [x for x in self.variants if x['item'] == 'AthenaPickaxe']

    @property
    def contrail_variants(self) -> List[Dict[str, str]]:
        return [x for x in self.variants if x['item'] == 'AthenaContrail']

    @property
    def scratchpad(self) -> list:
        base = self.get_prop('AthenaCosmeticLoadout_j')
        return base['AthenaCosmeticLoadout']['scratchpad']

    @property
    def emote(self) -> str:
        base = self.get_prop('FrontendEmote_j')
        return base['FrontendEmote']['emoteItemDef']

    @property
    def banner(self) -> Tuple[str, str, int]:
        base = self.get_prop('AthenaBannerInfo_j')
        banner_info = base['AthenaBannerInfo']

        return (banner_info['bannerIconId'],
                banner_info['bannerColorId'],
                banner_info['seasonLevel'])

    @property
    def battlepass_info(self) -> Tuple[bool, int, int, int]:
        base = self.get_prop('BattlePassInfo_j')
        bp_info = base['BattlePassInfo']

        return (bp_info['bHasPurchasedPass'],
                bp_info['passLevel'],
                bp_info['selfBoostXp'],
                bp_info['friendBoostXp'])

    @property
    def platform(self) -> str:
        base = self.get_prop('Platform_j')
        return base['Platform']['platformStr']

    def set_readiness(self, val: str) -> Dict[str, Any]:
        return {'GameReadiness_s': self.set_prop('GameReadiness_s', val)}

    def set_emote(self, emote: Optional[str] = None, *,
                  emote_ekey: Optional[str] = None,
                  section: Optional[int] = None) -> Dict[str, Any]:
        data = (self.get_prop('FrontendEmote_j'))['FrontendEmote']

        if emote is not None:
            data['emoteItemDef'] = emote
        if emote_ekey is not None:
            data['emoteItemDefEncryptionKey'] = emote_ekey
        if section is not None:
            data['emoteSection'] = section

        final = {'FrontendEmote': data}
        return {'FrontendEmote_j': self.set_prop('FrontendEmote_j', final)}

    def set_assisted_challenge(self, quest: Optional[str] = None, *,
                               completed: Optional[int] = None
                               ) -> Dict[str, Any]:
        prop = self.get_prop('AssistedChallengeInfo_j')
        data = prop['AssistedChallenge_j']

        if quest is not None:
            data['questItemDef'] = quest
        if completed is not None:
            data['objectivesCompleted'] = completed

        final = {'AssistedChallengeInfo': data}
        new_prop = self.set_prop('AssistedChallengeInfo_j', final)
        return {'AssistedChallengeInfo_j': new_prop}

    def set_banner(self, banner_icon: Optional[str] = None, *,
                   banner_color: Optional[str] = None,
                   season_level: Optional[int] = None) -> Dict[str, Any]:
        data = (self.get_prop('AthenaBannerInfo_j'))['AthenaBannerInfo']

        if banner_icon is not None:
            data['bannerIconId'] = banner_icon
        if banner_color is not None:
            data['bannerColorId'] = banner_color
        if season_level is not None:
            data['seasonLevel'] = season_level

        final = {'AthenaBannerInfo': data}
        new_prop = self.set_prop('AthenaBannerInfo_j', final)
        return {'AthenaBannerInfo_j': new_prop}

    def set_battlepass_info(self, has_purchased: Optional[bool] = None,
                            level: Optional[int] = None,
                            self_boost_xp: Optional[int] = None,
                            friend_boost_xp: Optional[int] = None
                            ) -> Dict[str, Any]:
        data = (self.get_prop('BattlePassInfo_j'))['BattlePassInfo']

        if has_purchased is not None:
            data['bHasPurchasedPass'] = has_purchased
        if level is not None:
            data['passLevel'] = level
        if self_boost_xp is not None:
            data['selfBoostXp'] = self_boost_xp
        if friend_boost_xp is not None:
            data['friendBoostXp'] = friend_boost_xp

        final = {'BattlePassInfo': data}
        return {'BattlePassInfo_j': self.set_prop('BattlePassInfo_j', final)}

    def set_cosmetic_loadout(self, *,
                             character: Optional[str] = None,
                             character_ekey: Optional[str] = None,
                             backpack: Optional[str] = None,
                             backpack_ekey: Optional[str] = None,
                             pickaxe: Optional[str] = None,
                             pickaxe_ekey: Optional[str] = None,
                             contrail: Optional[str] = None,
                             contrail_ekey: Optional[str] = None,
                             scratchpad: Optional[list] = None,
                             variants: Optional[List[Dict[str, str]]] = None
                             ) -> Dict[str, Any]:
        prop = self.get_prop('AthenaCosmeticLoadout_j')
        data = prop['AthenaCosmeticLoadout']

        if character is not None:
            data['characterDef'] = character
        if character_ekey is not None:
            data['characterEKey'] = character_ekey
        if backpack is not None:
            data['backpackDef'] = backpack
        if backpack_ekey is not None:
            data['backpackEKey'] = backpack_ekey
        if pickaxe is not None:
            data['pickaxeDef'] = pickaxe
        if pickaxe_ekey is not None:
            data['pickaxeEKey'] = pickaxe_ekey
        if contrail is not None:
            data['contrailDef'] = contrail
        if contrail_ekey is not None:
            data['contrailEKey'] = contrail_ekey
        if scratchpad is not None:
            data['scratchpad'] = scratchpad
        if variants is not None:
            data['variants'] = variants

        final = {'AthenaCosmeticLoadout': data}
        new_prop = self.set_prop('AthenaCosmeticLoadout_j', final)
        return {'AthenaCosmeticLoadout_j': new_prop}


class PartyMeta(MetaBase):
    def __init__(self, party: 'PartyBase',
                 meta: Optional[dict] = None) -> None:
        super().__init__()
        self.party = party

        privacy = self.party.config['privacy']
        privacy_settings = {
            'partyType': privacy['partyType'],
            'partyInviteRestriction': privacy['inviteRestriction'],
            'bOnlyLeaderFriendsCanJoin': privacy['onlyLeaderFriendsCanJoin'],
        }

        self.schema = {
            'PrimaryGameSessionId_s': '',
            'PartyState_s': 'BattleRoyaleView',
            'LobbyConnectionStarted_b': 'false',
            'MatchmakingResult_s': 'NoResults',
            'MatchmakingState_s': 'NotMatchmaking',
            'SessionIsCriticalMission_b': 'false',
            'ZoneTileIndex_U': '-1',
            'ZoneInstanceId_s': '',
            'SpectateAPartyMemberAvailable_b': False,
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
                'PrivacySettings': privacy_settings,
            }),
            'PlatformSessions_j': json.dumps({
                'PlatformSessions': [],
            }),
        }

        if meta is not None:
            self.update(meta, raw=True)

    @property
    def playlist_info(self) -> Tuple[str]:
        base = self.get_prop('PlaylistData_j')
        info = base['PlaylistData']

        return (info['playlistName'],
                info['tournamentId'],
                info['eventWindowId'],
                info['regionId'])

    @property
    def squad_fill(self) -> bool:
        return self.get_prop('AthenaSquadFill_b')

    @property
    def privacy(self) -> Optional[PartyPrivacy]:
        curr_priv = (self.get_prop('PrivacySettings_j'))['PrivacySettings']

        for privacy in PartyPrivacy:
            if curr_priv['partyType'] != privacy.value['partyType']:
                continue

            try:
                if (curr_priv['partyInviteRestriction']
                        != privacy.value['partyInviteRestriction']):
                    continue

                if (curr_priv['bOnlyLeaderFriendsCanJoin']
                        != privacy.value['bOnlyLeaderFriendsCanJoin']):
                    continue
            except KeyError:
                pass

            return privacy

    def set_playlist(self, playlist: Optional[str] = None, *,
                     tournament: Optional[str] = None,
                     event_window: Optional[str] = None,
                     region: Optional[Region] = None) -> Dict[str, Any]:
        data = (self.get_prop('PlaylistData_j'))['PlaylistData']

        if playlist is not None:
            data['playlistName'] = playlist
        if tournament is not None:
            data['tournamentId'] = tournament
        if event_window is not None:
            data['eventWindowId'] = event_window
        if region is not None:
            data['regionId'] = region

        final = {'PlaylistData': data}
        return {'PlaylistData_j': self.set_prop('PlaylistData_j', final)}

    def set_custom_key(self, key: str) -> Dict[str, Any]:
        return {'CustomMatchKey_s': self.set_prop('CustomMatchKey_s', key)}

    def set_fill(self, val: str) -> Dict[str, Any]:
        prop = self.set_prop('AthenaSquadFill_b', (str(val)).lower())
        return {'AthenaSquadFill_b': prop}

    def set_privacy(self, privacy: dict) -> Tuple[dict, list]:
        updated = {}
        deleted = []

        p = self.get_prop('PrivacySettings_j')
        if p:
            _priv = privacy
            new_privacy = {
                **p['PrivacySettings'],
                'partyType': _priv['partyType'],
                'bOnlyLeaderFriendsCanJoin': _priv['onlyLeaderFriendsCanJoin'],
                'partyInviteRestriction': _priv['inviteRestriction'],
            }

            updated['PrivacySettings_j'] = self.set_prop('PrivacySettings_j', {
                'PrivacySettings': new_privacy
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

    def refresh_squad_assignments(self) -> Dict[str, Any]:
        assignments = []

        i = 0
        for member in self.party.members.values():
            if member.leader:
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
    def __init__(self, client: 'Client',
                 party: 'PartyBase',
                 data: str) -> None:
        super().__init__(client=client, data=data)

        self._party = party

        self._joined_at = self.client.from_iso(data['joined_at'])
        self.meta = PartyMemberMeta(self, meta=data.get('meta'))
        self._update(data)

    @property
    def party(self) -> 'PartyBase':
        """Union[:class:`Party`, :class:`ClientParty`]: The party this member
        is a part of.
        """
        return self._party

    @property
    def joined_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: The UTC time of when this member joined
        its party.
        """
        return self._joined_at

    @property
    def leader(self) -> bool:
        """:class:`bool`: Returns ``True`` if member is the leader else
        ``False``.
        """
        return self.role is not None

    # TODO: Make check for sitting out
    @property
    def ready(self) -> bool:
        """:class:`bool`: ``True`` if this member is ready else ``False``."""
        return self.meta.ready == "Ready"

    @property
    def input(self) -> str:
        """:class:`str`: The input type this user is currently using."""
        return self.meta.input

    @property
    def assisted_challenge(self) -> str:
        """:class:`str`: The current assisted challenge chosen by this member.
        ``None`` if no assisted challenge is set.
        """
        asset = self.meta.assisted_challenge
        result = re.search(r".*\.([^\'\"]*)", asset.strip("'"))

        if result is not None and result[1] != 'None':
            return result.group(1)

    @property
    def outfit(self) -> str:
        """:class:`str`: The CID of the outfit this user currently has
        equipped.
        """
        asset = self.meta.outfit
        result = re.search(r".*\.([^\'\"]*)", asset.strip("'"))

        if result is not None and result.group(1) != 'None':
            return result.group(1)

    @property
    def backpack(self) -> str:
        """:class:`str`: The BID of the backpack this member currently has equipped.
        ``None`` if no backpack is equipped.
        """
        asset = self.meta.backpack
        if '/petcarriers/' not in asset.lower():
            result = re.search(r".*\.([^\'\"]*)", asset.strip("'"))

            if result is not None and result.group(1) != 'None':
                return result.group(1)

    @property
    def pet(self) -> str:
        """:class:`str`: The ID of the pet this member currently has equipped.
        ``None`` if no pet is equipped.
        """
        asset = self.meta.backpack
        if '/petcarriers/' in asset.lower():
            result = re.search(r".*\.([^\'\"]*)", asset.strip("'"))

            if result is not None and result.group(1) != 'None':
                return result.group(1)

    @property
    def pickaxe(self) -> str:
        """:class:`str`: The pickaxe id of the pickaxe this member currently
        has equipped.
        """
        asset = self.meta.pickaxe
        result = re.search(r".*\.([^\'\"]*)", asset.strip("'"))

        if result is not None and result.group(1) != 'None':
            return result.group(1)

    @property
    def contrail(self) -> str:
        """:class:`str`: The contrail id of the pickaxe this member currently
        has equipped.
        """
        asset = self.meta.contrail
        result = re.search(r".*\.([^\'\"]*)", asset.strip("'"))

        if result is not None and result[1] != 'None':
            return result.group(1)

    @property
    def outfit_variants(self) -> List[Dict[str, str]]:
        """:class:`list`: A list containing the raw variants data for the
        currently equipped outfit.

        .. warning::

            Variants doesn't seem to follow much logic. Therefore this returns
            the raw variants data received from fortnite's service. This can
            be directly passed with the ``variants`` keyword to
            :meth:`ClientPartyMember.set_outfit()`.
        """
        return self.meta.outfit_variants

    @property
    def backpack_variants(self) -> List[Dict[str, str]]:
        """:class:`list`: A list containing the raw variants data for the
        currently equipped backpack.

        .. warning::

            Variants doesn't seem to follow much logic. Therefore this returns
            the raw variants data received from fortnite's service. This can
            be directly passed with the ``variants`` keyword to
            :meth:`ClientPartyMember.set_backpack()`.
        """
        return self.meta.backpack_variants

    @property
    def pickaxe_variants(self) -> List[Dict[str, str]]:
        """:class:`list`: A list containing the raw variants data for the
        currently equipped pickaxe.

        .. warning::

            Variants doesn't seem to follow much logic. Therefore this returns
            the raw variants data received from fortnite's service. This can
            be directly passed with the ``variants`` keyword to
            :meth:`ClientPartyMember.set_pickaxe()`.
        """
        return self.meta.pickaxe_variants

    @property
    def contrail_variants(self) -> List[Dict[str, str]]:
        """:class:`list`: A list containing the raw variants data for the
        currently equipped contrail.

        .. warning::

            Variants doesn't seem to follow much logic. Therefore this returns
            the raw variants data received from fortnite's service. This can
            be directly passed with the ``variants`` keyword to
            :meth:`ClientPartyMember.set_contrail()`.
        """
        return self.meta.contrail_variants

    @property
    def emote(self) -> Optional[str]:
        """Optional[:class:`str`]: The EID of the emote this member is
        currently playing. ``None`` if no emote is currently playing.
        """
        asset = self.meta.emote
        if '/emoji/' not in asset.lower():
            result = re.search(r".*\.([^\'\"]*)", asset.strip("'"))

            if result is not None and result.group(1) != 'None':
                return result.group(1)

    @property
    def emoji(self) -> Optional[str]:
        """Optional[:class:`str`]: The ID of the emoji this member is
        currently playing. ``None`` if no emoji is currently playing.
        """
        asset = self.meta.emote
        if '/emoji/' in asset.lower():
            result = re.search(r".*\.([^\'\"]*)", asset.strip("'"))

            if result is not None and result.group(1) != 'None':
                return result.group(1)

    @property
    def banner(self) -> Tuple[str, str, int]:
        """:class:`tuple`: A tuple consisting of the icon id, color id and the
        season level.

        Example output: ::

            ('standardbanner15', 'defaultcolor15', 50)
        """
        return self.meta.banner

    @property
    def battlepass_info(self) -> Tuple[bool, int, int, int]:
        """:class:`tuple`: A tuple consisting of has purchased, battlepass
        level, self boost xp, friends boost xp.

        Example output: ::

            (True, 30, 80, 70)
        """
        return self.meta.battlepass_info

    @property
    def platform(self) -> str:
        """:class:`str`: The platform this user currently uses."""
        return self.meta.platform

    def is_chatbanned(self) -> bool:
        """:class:`bool`: Whether or not this member is chatbanned."""
        return self.id in getattr(self.party, '_chatbanned_members', {})

    def _update(self, data: dict) -> None:
        super()._update(data)
        self.role = data.get('role')
        self.revision = data.get('revision', 0)
        self.connections = data.get('connections', [])

    def update(self, data: dict) -> None:
        if data['revision'] > self.revision:
            self.revision = data['revision']
        self.meta.update(data['member_state_updated'], raw=True)
        self.meta.remove(data['member_state_removed'])

    def update_role(self, role: str) -> None:
        self.role = role

    @staticmethod
    def create_variants(item: str = "AthenaCharacter", *,
                        particle_config: str = 'Emissive',
                        **kwargs: Any) -> List[Dict[str, str]]:
        """Creates the variants list by the variants you set.

        .. warning::

            This function is built upon data received from only some of the
            available outfits with variants. There is little logic behind the
            variants function therefore there might be some unexpected issues
            with this function. Please report such issues by creating an issue
            on the issue tracker or by reporting it to me on discord.

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
            The jersey color you want to use. For soccer skins this is the
            country you want the jersey to represent.
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
        profile_banner: Optional[:class:`str`]
            The profile banner to use. The value should almost always be
            ``ProfileBanner``.

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
            'emissive': 'Emissive{}',
            'profile_banner': '{}',
        }

        variant = []
        for channel, value in kwargs.items():
            v = {
                'item': item,
                'channel': ''.join([x.capitalize()
                                    for x in channel.split('_')])
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

    def __init__(self, client: 'Client',
                 party: 'PartyBase',
                 data: dict) -> None:
        super().__init__(client, party, data)

    def __repr__(self) -> str:
        return ('<PartyMember id={0.id!r} party={0.party!r} '
                'display_name={0.display_name!r} '
                'joined_at={0.joined_at!r}>'.format(self))

    async def kick(self) -> None:
        """|coro|

        Kicks this member from the party.

        Raises
        ------
        Forbidden
            You are not the leader of the party.
        PartyError
            You attempted to kick yourself.
        HTTPException
            Something else went wrong when trying to kick this member.
        """
        if not self.party.me.leader:
            raise Forbidden('You must be the party leader to perform this '
                            'action')

        if self.client.user.id == self.id:
            raise PartyError('You can\'t kick yourself')

        try:
            await self.client.http.party_kick_member(self.party.id, self.id)
        except HTTPException as e:
            m = 'errors.com.epicgames.social.party.party_change_forbidden'
            if e.message_code == m:
                raise Forbidden(
                    'You dont have permission to kick this member.'
                )
            e.reraise()

    async def promote(self) -> None:
        """|coro|

        Promotes this user to partyleader.

        Raises
        ------
        Forbidden
            You are not the leader of the party.
        PartyError
            You are already partyleader.
        HTTPException
            Something else went wrong when trying to promote this member.
        """
        if not self.party.me.leader:
            raise Forbidden('You must be the party leader to perform this '
                            'action')

        if self.client.user.id == self.id:
            raise PartyError('You are already the leader')

        await self.client.http.party_promote_member(self.party.id, self.id)

    async def chatban(self, reason: Optional[str] = None) -> None:
        """|coro|

        Bans this member from the party chat. The member can then not send or
        receive messages but still is a part of the party.

        .. note::

            Chatbanned members are only banned for the current party. Whenever
            the client joins another party, the banlist will be empty.

        Parameters
        ----------
        reason: Optional[:class:`str`]
            The reason for the member being banned.

        Raises
        ------
        Forbidden
            You are not the leader of the party.
        ValueError
            This user is already banned.
        NotFound
            The user was not found.
        """
        await self.party.chatban_member(self.id, reason=reason)


class ClientPartyMember(PartyMemberBase):
    """Represents a the Clients party member object.

    Attributes
    ----------
    client: :class:`Client`
        The client.
    """

    def __init__(self, client: 'Client',
                 party: 'PartyBase',
                 data: dict) -> None:
        super().__init__(client, party, data)

        self.patch_lock = asyncio.Lock(loop=self.client.loop)
        self.edit_lock = asyncio.Lock(loop=self.client.loop)
        self.clear_emote_task = None

    def __repr__(self) -> str:
        return ('<ClientPartyMember id={0.id!r} party={0.party!r} '
                'display_name={0.display_name!r} '
                'joined_at={0.joined_at!r}>'.format(self))

    async def _patch(self, updated: Optional[dict] = None) -> None:
        meta = updated or self.meta.schema
        await self.client.http.party_update_member_meta(
            party_id=self.party.id,
            user_id=self.id,
            meta=meta,
            revision=self.revision
        )
        self.revision += 1

    async def patch(self, updated: Optional[dict] = None) -> Any:
        async with self.patch_lock:
            await self.meta.meta_ready_event.wait()
            while True:
                try:
                    await self._patch(updated=updated)
                    break
                except HTTPException as exc:
                    m = 'errors.com.epicgames.social.party.stale_revision'
                    if exc.message_code == m:
                        self.revision = int(exc.message_vars[1])
                        continue
                    exc.reraise()

    async def _edit(self, *coros: List[Union[Awaitable, functools.partial]],
                    from_default: bool = True) -> None:
        to_gather = {}
        for coro in reversed(coros):
            if isinstance(coro, functools.partial):
                result = getattr(coro.func, '__self__', None)
                if result is None:
                    coro = coro.func(self, *coro.args, **coro.keywords)
                else:
                    coro = coro()

            if coro.__qualname__ in to_gather:
                coro.close()
            else:
                to_gather[coro.__qualname__] = coro

        async with MaybeLock(self.edit_lock):
            await asyncio.gather(*list(to_gather.values()))

    async def edit(self,
                   *coros: List[Union[Awaitable, functools.partial]]
                   ) -> None:
        """|coro|

        Edits multiple meta parts at once.

        This example sets the clients outfit to galaxy and banner to the epic
        banner with level 100.: ::

            from functools import partial

            async def edit_client_member():
                member = client.user.party.me
                await member.edit(
                    member.set_outfit('CID_175_Athena_Commando_M_Celestial'), # usage with non-awaited coroutines
                    partial(member.set_banner, icon="OtherBanner28", season_level=100) # usage with functools.partial()
                )

        Parameters
        ----------
        *coros: Union[:class:`asyncio.coroutine`, :class:`functools.partial`]
            A list of coroutines that should be included in the edit.

        Raises
        ------
        HTTPException
            Something went wrong while editing.
        """  # noqa
        for coro in coros:
            if not (asyncio.iscoroutine(coro)
                    or isinstance(coro, functools.partial)):
                raise TypeError('All arguments must be coroutines or a '
                                'partials of coroutines')

        await self._edit(*coros)
        await self.patch()

    async def edit_and_keep(self,
                            *coros: List[Union[Awaitable, functools.partial]]
                            ) -> None:
        """|coro|

        Edits multiple meta parts at once and keeps the changes for when the
        bot joins other parties.

        This example sets the clients outfit to galaxy and banner to the epic
        banner with level 100. When the client joins another party, the outfit
        and banner will automatically be equipped.: ::

            from functools import partial

            async def edit_and_keep_client_member():
                member = client.user.party.me
                await member.edit_and_keep(
                    partial(member.set_outfit, 'CID_175_Athena_Commando_M_Celestial'),
                    partial(member.set_banner, icon="OtherBanner28", season_level=100)
                )

        Parameters
        ----------
        *coros: :class:`functools.partial`
            A list of coroutines that should be included in the edit. Unlike
            :meth:`ClientPartyMember.edit()`, this method only takes
            coroutines in the form of a :class:`functools.partial`.

        Raises
        ------
        HTTPException
            Something went wrong while editing.
        """  # noqa
        new = []
        for coro in coros:
            if not isinstance(coro, functools.partial):
                raise TypeError('All arguments partials of a coroutines')

            result = getattr(coro.func, '__self__', None)
            if result is not None:
                coro = functools.partial(
                    getattr(ClientPartyMember, coro.func.__name__),
                    *coro.args,
                    **coro.keywords
                )

            new.append(coro)

        self.client.update_default_party_member_config(new)
        default = self.client.default_party_member_config

        await self._edit(*default)
        await self.patch()

    async def leave(self) -> 'ClientParty':
        """|coro|

        Leaves the party.

        Raises
        ------
        HTTPException
            An error occured while requesting to leave the party.

        Returns
        -------
        :class:`ClientParty`
            The new party the client is connected to after leaving.
        """
        async with self.client._leave_lock:
            try:
                await self.client.http.party_leave(self.party.id)
            except HTTPException as e:
                m = 'errors.com.epicgames.social.party.party_not_found'
                if e.message_code != m:
                    e.reraise()

        await self.client.xmpp.leave_muc()
        p = await self.client._create_party()
        return p

    async def set_ready(self, value: Union[bool, None]) -> None:
        """|coro|

        Sets the readiness of the client.

        Parameters
        ----------
        value: :class:`bool`
            | ``True`` to set it to ready.
            | ``False`` to set it to unready.
            | ``None`` to set it to sitting out.
        """
        prop = self.meta.set_readiness(
            val='Ready' if value is True else ('NotReady' if value is False
                                               else 'SittingOut')
        )

        if not self.edit_lock.locked():
            tasks = [self.patch(updated=prop)]
            if value is None:
                tasks.append(
                    random.choice(list(self.party.members.values())).promote()
                )
            await asyncio.gather(*tasks)

        else:
            if value is None:
                asyncio.ensure_future(
                    random.choice(list(self.party.members.values())).promote(),
                    loop=self.client.loop
                )

    async def set_outfit(self, asset: Optional[str] = None, *,
                         key: Optional[str] = None,
                         variants: Optional[List[Dict[str, str]]] = None
                         ) -> None:
        """|coro|

        Sets the outfit of the client.

        Parameters
        ----------
        asset: Optional[:class:`str`]
            | The CID of the outfit.
            | Defaults to the last set outfit.

            .. note::

                You don't have to include the full path of the asset. The CID
                is enough.
        key: Optional[:class:`str`]
            The encyption key to use for this skin.
        variants: Optional[:class:`list`]
            The variants to use for this outfit. Defaults to ``None`` which
            resets variants.
        """
        if asset is not None:
            if '.' not in asset:
                asset = ("AthenaCharacterItemDefinition'/Game/Athena/Items/"
                         "Cosmetics/Characters/{0}.{0}'".format(asset))
        else:
            prop = self.meta.get_prop('AthenaCosmeticLoadout_j')
            asset = prop['AthenaCosmeticLoadout']['characterDef']

        variants = [x for x in self.meta.variants
                    if x['item'] != 'AthenaCharacter'] + (variants or [])
        prop = self.meta.set_cosmetic_loadout(
            character=asset,
            character_ekey=key,
            variants=variants
        )

        if not self.edit_lock.locked():
            await self.patch(updated=prop)

    async def set_backpack(self, asset: Optional[str] = None, *,
                           key: Optional[str] = None,
                           variants: Optional[List[Dict[str, str]]] = None
                           ) -> None:
        """|coro|

        Sets the backpack of the client.

        Parameters
        ----------
        asset: Optional[:class:`str`]
            | The BID of the backpack.
            | Defaults to the last set backpack.

            .. note::

                You don't have to include the full path of the asset. The CID
                is enough.
        key: Optional[:class:`str`]
            The encyption key to use for this backpack.
        variants: Optional[:class:`list`]
            The variants to use for this backpack. Defaults to ``None`` which
            resets variants.
        """
        if asset is not None:
            if '.' not in asset:
                asset = ("AthenaBackpackItemDefinition'/Game/Athena/Items/"
                         "Cosmetics/Backpacks/{0}.{0}'".format(asset))
        else:
            prop = self.meta.get_prop('AthenaCosmeticLoadout_j')
            asset = prop['AthenaCosmeticLoadout']['backpackDef']

        variants = [x for x in self.meta.variants
                    if x['item'] != 'AthenaBackpack'] + (variants or [])
        prop = self.meta.set_cosmetic_loadout(
            backpack=asset,
            backpack_ekey=key,
            variants=variants
        )

        if not self.edit_lock.locked():
            await self.patch(updated=prop)

    async def set_pet(self, asset: Optional[str] = None, *,
                      key: Optional[str] = None,
                      variants: Optional[List[Dict[str, str]]] = None
                      ) -> None:
        """|coro|

        Sets the pet of the client.

        Parameters
        ----------
        asset: Optional[:class:`str`]
            | The ID of the pet.
            | Defaults to the last set pet.

            .. note::

                You don't have to include the full path of the asset. The ID is
                enough.
        key: Optional[:class:`str`]
            The encyption key to use for this pet.
        variants: Optional[:class:`list`]
            The variants to use for this pet. Defaults to ``None`` which
            resets variants.
        """
        if asset is not None:
            if '.' not in asset:
                asset = ("AthenaPetItemDefinition'/Game/Athena/Items/"
                         "Cosmetics/PetCarriers/{0}.{0}'".format(asset))
        else:
            prop = self.meta.get_prop('AthenaCosmeticLoadout_j')
            asset = prop['AthenaCosmeticLoadout']['backpackDef']

        variants = [x for x in self.meta.variants
                    if x['item'] != 'AthenaBackpack'] + (variants or [])
        prop = self.meta.set_cosmetic_loadout(
            backpack=asset,
            backpack_ekey=key,
            variants=variants
        )

        if not self.edit_lock.locked():
            await self.patch(updated=prop)

    async def set_pickaxe(self, asset: Optional[str] = None, *,
                          key: Optional[str] = None,
                          variants: Optional[List[Dict[str, str]]] = None
                          ) -> None:
        """|coro|

        Sets the pickaxe of the client.

        Parameters
        ----------
        asset: Optional[:class:`str`]
            | The PID of the pickaxe.
            | Defaults to the last set pickaxe.

            .. note::

                You don't have to include the full path of the asset. The CID
                is enough.
        key: Optional[:class:`str`]
            The encyption key to use for this pickaxe.
        variants: Optional[:class:`list`]
            The variants to use for this pickaxe. Defaults to ``None`` which
            resets variants.
        """
        if asset is not None:
            if '.' not in asset:
                asset = ("AthenaPickaxeItemDefinition'/Game/Athena/Items/"
                         "Cosmetics/Pickaxes/{0}.{0}'".format(asset))
        else:
            prop = self.meta.get_prop('AthenaCosmeticLoadout_j')
            asset = prop['AthenaCosmeticLoadout']['pickaxeDef']

        variants = [x for x in self.meta.variants
                    if x['item'] != 'AthenaPickaxe'] + (variants or [])
        prop = self.meta.set_cosmetic_loadout(
            pickaxe=asset,
            pickaxe_ekey=key,
            variants=variants
        )

        if not self.edit_lock.locked():
            await self.patch(updated=prop)

    async def set_contrail(self, asset: Optional[str] = None, *,
                           key: Optional[str] = None,
                           variants: Optional[List[Dict[str, str]]] = None
                           ) -> None:
        """|coro|

        Sets the contrail of the client.

        Parameters
        ----------
        asset: Optional[:class:`str`]
            | The ID of the contrail.
            | Defaults to the last set contrail.

            .. note::

                You don't have to include the full path of the asset. The ID is
                enough.
        key: Optional[:class:`str`]
            The encyption key to use for this contrail.
        variants: Optional[:class:`list`]
            The variants to use for this contrail. Defaults to ``None`` which
            resets variants.
        """
        if asset is not None:
            if '.' not in asset:
                asset = ("AthenaContrailItemDefinition'/Game/Athena/Items/"
                         "Cosmetics/Contrails/{0}.{0}'".format(asset))
        else:
            prop = self.meta.get_prop('AthenaCosmeticLoadout_j')
            asset = prop['AthenaCosmeticLoadout']['contrailDef']

        variants = [x for x in self.meta.variants
                    if x['item'] != 'AthenaContrail'] + (variants or [])
        prop = self.meta.set_cosmetic_loadout(
            contrail=asset,
            contrail_ekey=key,
            variants=variants
        )

        if not self.edit_lock.locked():
            await self.patch(updated=prop)

    async def set_emote(self, asset: str, *,
                        run_for: Optional[int] = None,
                        key: Optional[str] = None,
                        section: Optional[int] = None) -> None:
        """|coro|

        Sets the emote of the client.

        Parameters
        ----------
        asset: :class:`str`
            The EID of the emote.

            .. note::

                You don't have to include the full path of the asset. The EID
                is enough.
        run_for: Optional[:class:`int`]
            Seconds this emote should run for before being cancelled. ``None``
            (default) means will run infinitely and you can then clear it with
            :meth:`PartyMember.clear_emote()`.
        key: Optional[:class:`str`]
            The encyption key to use for this emote.
        section: Optional[:class:`int`]
            The section.
        """
        if '.' not in asset:
            asset = ("AthenaDanceItemDefinition'/Game/Athena/Items/"
                     "Cosmetics/Dances/{0}.{0}'".format(asset))

        prop = self.meta.set_emote(
            emote=asset,
            emote_ekey=key,
            section=section
        )

        self._cancel_clear_emote()
        if run_for is not None:
            self.clear_emote_task = self.client.loop.create_task(
                self._schedule_clear_emote(run_for)
            )

        if not self.edit_lock.locked():
            await self.patch(updated=prop)

    async def set_emoji(self, asset: str, *,
                        key: Optional[str] = None,
                        section: Optional[int] = None) -> None:
        """|coro|

        Sets the emoji of the client.

        Parameters
        ----------
        asset: :class:`str`
            The ID of the emoji.

            .. note::

                You don't have to include the full path of the asset. The ID is
                enough.
        key: Optional[:class:`str`]
            The encyption key to use for this emoji.
        section: Optional[:class:`int`]
            The section.
        """
        if '.' not in asset:
            asset = ("AthenaDanceItemDefinition'/Game/Athena/Items/"
                     "Cosmetics/Dances/Emoji/{0}.{0}'".format(asset))

        prop = self.meta.set_emote(
            emote=asset,
            emote_ekey=key,
            section=section
        )

        self._cancel_clear_emote()
        self.clear_emote_task = self.client.loop.create_task(
            self._schedule_clear_emote(2)
        )

        if not self.edit_lock.locked():
            await self.patch(updated=prop)

    def _cancel_clear_emote(self) -> None:
        if (self.clear_emote_task is not None
                and not self.clear_emote_task.cancelled()):
            self.clear_emote_task.cancel()

    async def _schedule_clear_emote(self, seconds: Union[int, float]) -> None:
        await asyncio.sleep(seconds)
        self.clear_emote_task = None
        await self.clear_emote()

    async def clear_emote(self) -> None:
        """|coro|

        Clears/stops the emote currently playing.
        """

        prop = self.meta.set_emote(
            emote='None',
            emote_ekey='',
            section=-1
        )

        self._cancel_clear_emote()

        if not self.edit_lock.locked():
            await self.patch(updated=prop)

    async def set_banner(self, icon: Optional[str] = None,
                         color: Optional[str] = None,
                         season_level: Optional[int] = None) -> None:
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

        if not self.edit_lock.locked():
            await self.patch(updated=prop)

    async def set_battlepass_info(self, has_purchased: Optional[bool] = None,
                                  level: Optional[int] = None,
                                  self_boost_xp: Optional[int] = None,
                                  friend_boost_xp: Optional[int] = None
                                  ) -> None:
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

        if not self.edit_lock.locked():
            await self.patch(updated=prop)

    async def set_assisted_challenge(self, quest: Optional[str] = None, *,
                                     num_completed: Optional[int] = None
                                     ) -> None:
        """|coro|

        Sets the assisted challenge.

        Parameters
        ----------
        quest: Optional[:class:`str`]
            The quest to set.

            .. note::

                You don't have to include the full path of the quest. The
                quest id is enough.
        num_completed: Optional[:class:`int`]
            How many quests you have completed, I think (didn't test this).
        """
        if quest is not None:
            if '.' not in quest:
                quest = ("FortQuestItemDefinition'/Game/Athena/Items/"
                         "Quests/DailyQuests/Quests/{0}.{0}'".format(quest))
        else:
            prop = self.meta.get_prop('AssistedChallengeInfo_j')
            quest = prop['AssistedChallengeInfo']['questItemDef']

        prop = self.meta.set_assisted_challenge(
            quest=quest,
            completed=num_completed
        )

        if not self.edit_lock.locked():
            await self.patch(updated=prop)


class PartyBase:

    def __init__(self, client: 'Client', data: dict) -> None:
        self._client = client
        self._id = data.get('id')
        self._members = {}
        self._applicants = data.get('applicants', [])

        self._update_invites(data.get('invites', []))
        self._update_config(data.get('config'))
        self.meta = PartyMeta(self, data['meta'])

    def __str__(self) -> str:
        return self.id

    @property
    def client(self) -> 'Client':
        """:class:`Client`: The client."""
        return self._client

    @property
    def id(self) -> str:
        """:class:`str`: The party's id."""
        return self._id

    @property
    def members(self) -> Dict[str, PartyMember]:
        """:class:`dict`: Mapping of the party's members."""
        return self._members

    @property
    def member_count(self) -> int:
        """:class:`int`: The amount of member currently in this party."""
        return len(self._members)

    @property
    def applicants(self) -> list:
        """:class:`list`: The party's applicants."""
        return self._applicants

    @property
    def leader(self) -> PartyMember:
        """:class:`PartyMember`: The leader of the party."""
        for member in self.members.values():
            if member.leader:
                return member

    @property
    def playlist_info(self) -> Tuple[str]:
        """:class:`tuple`: A tuple containing the name, tournament, event
        window and region of the currently set playlist.

        Example output: ::

            # output for default duos
            (
                'Playlist_DefaultDuo',
                '',
                '',
                'EU'
            )

            # output for arena trios
            (
                'Playlist_ShowdownAlt_Trios',
                'epicgames_Arena_S10_Trios',
                'Arena_S10_Division1_Trios',
                'EU'
            )
        """
        return self.meta.playlist_info

    # TODO: Add SittingOut here too
    @property
    def squad_fill(self) -> bool:
        """:class:`bool`: ``True`` if squad fill is enabled else ``False``."""
        return self.meta.squad_fill

    @property
    def privacy(self) -> PartyPrivacy:
        """:class:`PartyPrivacy`: The currently set privacy of this party."""
        return self.meta.privacy

    def _add_member(self, member: PartyMember) -> None:
        self.members[member.id] = member

    def _remove_member(self, user_id: str) -> PartyMember:
        if not isinstance(user_id, str):
            user_id = user_id.id
        return self.members.pop(user_id)

    def _update(self, data: dict) -> None:
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
        c = privacy['PrivacySettings']
        found = False
        for d in PartyPrivacy:
            p = d.value
            if p['partyType'] != c['partyType']:
                continue
            if p['inviteRestriction'] != c['partyInviteRestriction']:
                continue
            if p['onlyLeaderFriendsCanJoin'] != c['bOnlyLeaderFriendsCanJoin']:
                continue
            found = p
            break

        if found:
            self.config['privacy'] = found

    def _update_invites(self, invites: list) -> None:
        self.invites = invites

    def _update_config(self, config: dict = {}) -> None:
        self.join_confirmation = config['join_confirmation']
        self.max_size = config['max_size']
        self.invite_ttl_seconds = config.get('invite_ttl_seconds',
                                             config['invite_ttl'])
        self.sub_type = config['sub_type']
        self.config = {**self.client.default_party_config, **config}

    async def _update_members(self, members: Optional[list] = None) -> None:
        if members is None:
            data = await self.client.http.party_lookup(self.id)
            members = data['members']

        def get_id(m):
            return m.get('account_id', m.get('accountId'))

        profiles = await self.client.fetch_profiles(
            [get_id(m) for m in members],
            cache=True
        )
        profiles = {p.id: p for p in profiles}

        for raw in members:
            user_id = get_id(raw)
            if user_id == self.client.user.id:
                user = self.client.user
            else:
                user = profiles[user_id]
            raw = {**raw, **(user.get_raw())}

            member = PartyMember(self.client, self, raw)
            self._add_member(member)

        ids = profiles.keys()
        to_remove = []
        for m in self.members.values():
            if m.id not in ids:
                to_remove.append(m.id)

        for id in to_remove:
            self._remove_member(id)


class Party(PartyBase):
    """Represent a party that the ClientUser is not yet a part of."""

    def __init__(self, client: 'Client', data: dict) -> None:
        super().__init__(client, data)

    def __repr__(self) -> str:
        return ('<Party id={0.id!r} leader={0.leader!r} '
                'member_count={0.member_count}>'.format(self))


class ClientParty(PartyBase):
    """Represents ClientUser's party."""

    def __init__(self, client: 'Client', data: dict) -> None:
        super().__init__(client, data)

        self.last_raw_status = None
        self._me = None
        self._chatbanned_members = {}

        self.patch_lock = asyncio.Lock(loop=self.client.loop)

        self._update_revision(data.get('revision', 0))
        self._update_invites(data.get('invites', []))
        self._update_config(data.get('config'))
        self.meta = PartyMeta(self, data['meta'])

    def __repr__(self) -> str:
        return ('<ClientParty id={0.id!r} me={0.me!r} leader={0.leader!r} '
                'member_count={0.member_count}>'.format(self))

    @property
    def me(self) -> 'ClientPartyMember':
        """:class:`ClientPartyMember`: The clients partymember object."""
        return self._me

    @property
    def muc_jid(self) -> aioxmpp.JID:
        """:class:`aioxmpp.JID`: The JID of the party MUC."""
        return aioxmpp.JID.fromstr(
            'Party-{}@muc.prod.ol.epicgames.com'.format(self.id)
        )

    @property
    def chatbanned_members(self) -> None:
        """Dict[:class:`str`, :class:`PartyMember`] A dict of all chatbanned
        members mapped to their user id.
        """
        return self._chatbanned_members

    def _add_clientmember(self, member: ClientPartyMember) -> None:
        self._me = member

    def _create_member(self, data: dict) -> PartyMember:
        member = PartyMember(self.client, self, data)
        self._add_member(member)
        return member

    def _create_clientmember(self, data: dict) -> ClientPartyMember:
        member = ClientPartyMember(self.client, self, data)
        self._add_clientmember(member)
        return member

    def _remove_member(self, user_id: str) -> PartyMember:
        if not isinstance(user_id, str):
            user_id = user_id.id
        self.update_presence()
        return self.members.pop(user_id)

    def update_presence(self, text: Optional[str] = None,
                        conf: dict = {}) -> None:
        perm = self.config['privacy']['presencePermission']
        if perm == 'Noone' or (perm == 'Leader' and (self.me is not None
                                                     and not self.me.leader)):
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
                'pc': self.member_count,
            }

        status = text or self.client.status
        _default_status = {
            'Status': status.format(party_size=self.member_count,
                                    party_max_size=self.max_size),
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

        if self.client.status is not False:
            self.last_raw_status = {**_default_status, **conf}
            self.client.xmpp.set_presence(status=self.last_raw_status)

    def _update(self, data: dict) -> None:
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
        c = privacy['PrivacySettings']
        found = False
        for d in PartyPrivacy:
            p = d.value
            if p['partyType'] != c['partyType']:
                continue
            if p['inviteRestriction'] != c['partyInviteRestriction']:
                continue
            if p['onlyLeaderFriendsCanJoin'] != c['bOnlyLeaderFriendsCanJoin']:
                continue
            found = p
            break

        if found:
            self.config['privacy'] = found

        if self.client.status is not False:
            self.update_presence()

    def _update_revision(self, revision: int) -> None:
        self.revision = revision

    def _update_config(self, config: dict = {}) -> None:
        self.join_confirmation = config['join_confirmation']
        self.max_size = config['max_size']
        self.invite_ttl_seconds = config.get('invite_ttl_seconds',
                                             config['invite_ttl'])
        self.sub_type = config['sub_type']
        self.config = {**self.client.default_party_config, **config}

    async def _update_members(self, members: Optional[list] = None) -> None:
        if members is None:
            data = await self.client.http.party_lookup(self.id)
            members = data['members']

        def get_id(m):
            return m.get('account_id', m.get('accountId'))

        profiles = await self.client.fetch_profiles(
            [get_id(m) for m in members],
            cache=True
        )
        profiles = {p.id: p for p in profiles}

        for raw in members:
            user_id = get_id(raw)
            if user_id == self.client.user.id:
                user = self.client.user
            else:
                user = profiles[user_id]
            raw = {**raw, **(user.get_raw())}

            member = PartyMember(self.client, self, raw)
            self._add_member(member)

            if member.id == self.client.user.id:
                clientmember = ClientPartyMember(self.client, self, raw)
                self._add_clientmember(clientmember)

        ids = profiles.keys()
        to_remove = []
        for m in self.members.values():
            if m.id not in ids:
                to_remove.append(m.id)

        for id in to_remove:
            self._remove_member(id)

    async def join_chat(self) -> None:
        await self.client.xmpp.join_muc(self.id)

    async def chatban_member(self, user_id: str, *,
                             reason: Optional[str] = None) -> None:
        if not self.me.leader:
            raise Forbidden('Only leaders can ban members from the chat.')

        if user_id in self._chatbanned_members:
            raise ValueError('This member is already banned')

        room = self.client.xmpp.muc_room
        for occupant in room.members:
            if occupant.direct_jid.localpart == user_id:
                self._chatbanned_members[user_id] = self.members[user_id]
                await room.ban(occupant, reason=reason)
                break
        else:
            raise NotFound('This member is not a part of the party.')

    async def send(self, content: str) -> None:
        """|coro|

        Sends a message to this party's chat.

        Parameters
        ----------
        content: :class:`str`
            The content of the message.
        """
        await self.client.xmpp.send_party_message(content)

    async def _patch(self, updated: Optional[dict] = None,
                     deleted: Optional[list] = None) -> None:
        await self.client.http.party_update_meta(
            party_id=self.id,
            updated_meta=updated or self.meta.schema,
            deleted_meta=deleted or [],
            config=self.config,
            revision=self.revision
        )
        self.revision += 1

    async def patch(self, updated: Optional[dict] = None,
                    deleted: Optional[list] = None) -> None:
        async with self.patch_lock:
            while True:
                try:
                    await self._patch(updated=updated, deleted=deleted)
                    break
                except HTTPException as exc:
                    m = 'errors.com.epicgames.social.party.stale_revision'
                    if exc.message_code == m:
                        self.revision = int(exc.message_vars[1])
                        continue
                    exc.reraise()

    async def invite(self, user_id: str) -> None:
        """|coro|

        Invites a user to the party.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the user to invite.

        Raises
        ------
        PartyError
            User is already in your party.
        PartyError
            The party is full.
        Forbidden
            The invited user is not friends with the client.
        HTTPException
            Something else went wrong when trying to invite the user.
        """
        if user_id in self.members:
            raise PartyError('User is already in you party.')

        if len(self.members) == self.max_size:
            raise PartyError('Party is full')

        try:
            await self.client.http.party_send_invite(self.id, user_id)
        except HTTPException as e:
            m = 'errors.com.epicgames.social.party.ping_forbidden'
            if e.message_code == m:
                raise Forbidden('You can only invite friends to your party.')
            e.reraise()

    async def _leave(self, ignore_not_found: bool = True) -> None:
        await self.client.xmpp.leave_muc()

        async with self.client._leave_lock:
            try:
                await self.client.http.party_leave(self.id)
            except HTTPException as e:
                m = 'errors.com.epicgames.social.party.party_not_found'
                if ignore_not_found and e.message_code == m:
                    return
                e.reraise()

    async def set_privacy(self, privacy: PartyPrivacy) -> None:
        """|coro|

        Sets the privacy of the party.

        Parameters
        ----------
        privacy: :class:`PartyPrivacy`

        Raises
        ------
        Forbidden
            The client is not the leader of the party.
        """
        if not self.me.leader:
            raise Forbidden('You have to be leader for this action to work.')

        if not isinstance(privacy, dict):
            privacy = privacy.value

        updated, deleted = self.meta.set_privacy(privacy)
        await self.patch(updated=updated, deleted=deleted)

    async def set_playlist(self, playlist: Optional[str] = None,
                           tournament: Optional[str] = None,
                           event_window: Optional[str] = None,
                           region: Optional[Region] = None) -> None:
        """|coro|

        Sets the current playlist of the party.

        Sets the playlist to Duos EU: ::

            await party.set_playlist(
                playlist='Playlist_DefaultDuo',
                region='EU'
            )

        Sets the playlist to Arena Trios EU (Replace ``Trios`` with ``Solo``
        for arena solo): ::

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
        Forbidden
            The client is not the leader of the party.
        """
        if not self.me.leader:
            raise Forbidden('You have to be leader for this action to work.')

        if region is not None:
            region = region.value

        prop = self.meta.set_playlist(
            playlist=playlist,
            tournament=tournament,
            event_window=event_window,
            region=region
        )
        await self.patch(updated=prop)

    async def set_custom_key(self, key: str) -> None:
        """|coro|

        Sets the custom key of the party.

        Parameters
        ----------
        key: :class:`str`
            The key to set.

        Raises
        ------
        Forbidden
            The client is not the leader of the party.
        """
        if not self.me.leader:
            raise Forbidden('You have to be leader for this action to work.')

        prop = self.meta.set_custom_key(
            key=key
        )
        await self.patch(updated=prop)

    async def set_fill(self, value: bool) -> None:
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
        Forbidden
            The client is not the leader of the party.
        """
        if not self.me.leader:
            raise Forbidden('You have to be leader for this action to work.')

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
    sender: :class:`Friend`
        The friend that invited you to the party.
    created_at: :class:`datetime.datetime`
        The UTC time this invite was created at.
    """
    def __init__(self, client: 'Client',
                 party: Party,
                 net_cl: str,
                 data: dict) -> None:
        self.client = client
        self.party = party
        self.net_cl = net_cl

        self.sender = self.client.get_friend(data['sent_by'])
        self.created_at = self.client.from_iso(data['sent_at'])

    def __repr__(self) -> str:
        return ('<PartyInvitation party={0.party!r} sender={0.sender!r} '
                'created_at={0.created_at!r}>'.format(self))

    async def accept(self) -> None:
        """|coro|

        Accepts the invitation and joins the party.

        .. warning::

            A bug within the fortnite services makes it not possible to join a
            private party you have already been a part of before.

        Raises
        ------
        Forbidden
            You attempted to join a private party you've already been a part
            of before.
        HTTPException
            Something went wrong when accepting the invitation.
        """
        if self.net_cl != self.client.net_cl and self.client.net_cl != '':
            raise PartyError('Incompatible net_cl')

        await self.client.join_to_party(self.party.id, check_private=False)
        asyncio.ensure_future(
            self.client.http.party_delete_ping(self.sender.id),
            loop=self.client.loop
        )

    async def decline(self) -> None:
        """|coro|

        Declines the invitation.

        Raises
        ------
        PartyError
            The clients net_cl is not compatible with the received net_cl.
        HTTPException
            Something went wrong when declining the invitation.
        """
        await self.client.http.party_delete_ping(self.sender.id)


class PartyJoinConfirmation:
    """Represents a join confirmation.

    Attributes
    ----------
    client: :class:`Client`
        The client.
    party: :class:`ClientParty`
        The party the user wants to join.
    user: :class:`User`
        The user who requested to join the party.
    created_at: :class:`datetime.datetime`
        The UTC time of when the join confirmation was received.
    """
    def __init__(self, client: 'Client',
                 party: ClientParty,
                 user: User,
                 data: dict) -> None:
        self.client = client
        self.party = party
        self.user = user
        self.created_at = self.client.from_iso(data['sent'])

    def __repr__(self) -> str:
        return ('<PartyJoinConfirmation party={0.party!r} user={0.user!r} '
                'created_at={0.created_at!r}>'.format(self))

    async def confirm(self) -> None:
        """|coro|

        Confirms this user.

        Raises
        ------
        HTTPException
            Something went wrong when confirming this user.
        """
        await self.client.http.party_member_confirm(self.party.id,
                                                    self.user.id)

    async def reject(self) -> None:
        """|coro|

        Rejects this user.

        Raises
        ------
        HTTPException
            Something went wrong when rejecting this user.
        """
        await self.client.http.party_member_reject(self.party.id, self.user.id)
