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

import json
import asyncio
import aioxmpp
import re
import functools
import datetime

from typing import (TYPE_CHECKING, Optional, Any, List, Dict, Union, Tuple,
                    Awaitable, Type)
from collections import OrderedDict

from .enums import Enum
from .errors import PartyError, Forbidden, HTTPException, NotFound
from .user import User
from .friend import Friend
from .enums import (PartyPrivacy, PartyDiscoverability, PartyJoinability,
                    DefaultCharactersChapter2, Region, ReadyState, Platform)
from .utils import MaybeLock

if TYPE_CHECKING:
    from .client import Client


class SquadAssignment:
    """Represents a party members squad assignment. A squad assignment
    is basically a piece of information about which position a member
    has in the party, which is directly related to party teams.

    Parameters
    ----------
    position: Optional[:class:`int`]
        The position a member should have in the party. If no position
        is passed, a position will be automatically given according to
        the position priorities set.
    hidden: :class:`bool`
        Whether or not the member should be hidden in the party.

        .. warning::

            Being hidden is not a native fortnite feature so be careful
            when using this. It might lead to undesirable results.
    """

    __slots__ = ('position', 'hidden')

    def __init__(self, *,
                 position: Optional[int] = None,
                 hidden: bool = False) -> None:
        self.position = position
        self.hidden = hidden

    def __repr__(self):
        return ('<SquadAssignment position={0.position!r} '
                'hidden={0.hidden!r}>'.format(self))

    @classmethod
    def copy(cls, assignment):
        self = cls.__new__(cls)

        self.position = assignment.position
        self.hidden = assignment.hidden

        return self


class DefaultPartyConfig:
    """Data class for the default party configuration used when a new party
    is created.

    Parameters
    ----------
    privacy: Optional[:class:`PartyPrivacy`]
        | The party privacy that should be used.
        | Defaults to: :attr:`PartyPrivacy.PUBLIC`
    max_size: Optional[:class:`int`]
        | The maximun party size. Valid party sizes must use a value
        between 1 and 16.
        | Defaults to ``16``
    chat_enabled: Optional[:class:`bool`]
        | Wether or not the party chat should be enabled for the party.
        | Defaults to ``True``.
    team_change_allowed: :class:`bool`
        | Whether or not players should be able to manually swap party team
        with another player. This setting only works if the client is the
        leader of the party.
        | Defaults to ``True``
    default_squad_assignment: :class:`SquadAssignment`
        | The default squad assignment to use for new members. Squad assignments
        holds information about a party member's current position and visibility.
        Please note that setting a position in the default squad assignment
        doesnt actually do anything and it will just be overridden.
        | Defaults to ``SquadAssignment(hidden=False)``.
    position_priorities: List[int]
        | A list of exactly 16 ints all ranging from 0-15. When a new member
        joins the party or a member is not defined in a squad assignment
        request, it will automatically give the first available position
        in this list.
        | Defaults to a list of 0-15 in order.
    reassign_positions_on_size_change: :class:`bool`
        | Whether or not positions should be automatically reassigned if the party
        size changes. Set this to ``False`` if you want members to keep their
        positions unless manually changed. The reassignment is done according
        to the position priorities.
        | Defaults to ``True``.
    joinability: Optional[:class:`PartyJoinability`]
        | The joinability configuration that should be used.
        | Defaults to :attr:`PartyJoinability.OPEN`
    discoverability: Optional[:class:`PartyDiscoverability`]
        | The discoverability configuration that should be used.
        | Defaults to :attr:`PartyDiscoverability.ALL`
    invite_ttl: Optional[:class:`int`]
        | How many seconds the invite should be valid for before
        automatically becoming invalid.
        | Defaults to ``14400``
    sub_type: Optional[:class:`str`]
        | The sub type the party should use.
        | Defaults to ``'default'``
    party_type: Optional[:class:`str`]
        | The type of the party.
        | Defaults to ``'DEFAULT'``
    cls: Type[:class:`ClientParty`]
        | The default party object to use for the client's party. Here you can
        specify all class objects that inherits from :class:`ClientParty`.
    meta: List[:class:`functools.partial`]
        A list of coroutines in the form of partials. This config will be
        automatically equipped by the party when a new party is created by the
        client.

        .. code-block:: python3

            from fortnitepy import ClientParty
            from functools import partial

            [
                partial(ClientParty.set_custom_key, 'myawesomekey'),
                partial(ClientParty.set_playlist, 'Playlist_PlaygroundV2')
            ]

    Attributes
    ----------
    team_change_allowed: :class:`bool`
        Whether or not players are able to manually swap party team
        with another player. This setting only works if the client is the
        leader of the party.
    default_squad_assignment: :class:`SquadAssignment`
        The default squad assignment to use for new members and members
        not specified in manual squad assignments requests.
    position_priorities: List[:class:`int`]
        A list containing exactly 16 integers ranging from 0-16 with no
        duplicates. This is used for position assignments.
    reassign_positions_on_size_change: :class:`bool`
        Whether or not positions will be automatically reassigned when the
        party size changes.
    cls: Type[:class:`ClientParty`]
        The default party object used to represent the client's party.
    """  # noqa
    def __init__(self, **kwargs: Any) -> None:
        self.cls = kwargs.pop('cls', ClientParty)
        self._client = None
        self.team_change_allowed = kwargs.pop('team_change_allowed', True)
        self.default_squad_assignment = kwargs.pop(
            'default_squad_assignment',
            SquadAssignment(hidden=False),
        )

        value = kwargs.pop('position_priorities', None)
        if value is None:
            self._position_priorities = list(range(16))
        else:
            self.position_priorities = value

        self.reassign_positions_on_size_change = kwargs.pop(
            'reassign_positions_on_size_change',
            True
        )
        self.meta = kwargs.pop('meta', [])

        self._config = {}
        self.update(kwargs)

    @property
    def position_priorities(self):
        return self._position_priorities

    @position_priorities.setter
    def position_priorities(self, value):
        def error():
            raise ValueError(
                'position priorities must include exactly 16 integers '
                'ranging from 0-16.'
            )

        if len(value) != 16:
            error()

        for i in range(16):
            if i not in value:
                error()

        self._position_priorities = value

    def _inject_client(self, client: 'Client') -> None:
        self._client = client

    @property
    def config(self) -> Dict[str, Any]:
        self._client._check_party_confirmation()
        return self._config

    def update(self, config: Dict[str, Any]) -> None:
        default = {
            'privacy': PartyPrivacy.PUBLIC.value,
            'joinability': PartyJoinability.OPEN.value,
            'discoverability': PartyDiscoverability.ALL.value,
            'max_size': 16,
            'invite_ttl_seconds': 14400,
            'chat_enabled': True,
            'join_confirmation': False,
            'sub_type': 'default',
            'type': 'DEFAULT',
        }

        to_update = {}
        for key, value in config.items():
            if isinstance(value, Enum):
                to_update[key] = value.value

        default_config = {**default, **self._config}
        self._config = {**default_config, **config, **to_update}

    def _update_privacy(self, args: list) -> None:
        for arg in args:
            if isinstance(arg, PartyPrivacy):
                if arg.value['partyType'] == 'Private':
                    include = {
                        'discoverability': PartyDiscoverability.INVITED_ONLY.value,  # noqa
                        'joinability': PartyJoinability.INVITE_AND_FORMER.value,  # noqa
                    }
                else:
                    include = {
                        'discoverability': PartyDiscoverability.ALL.value,
                        'joinability': PartyJoinability.OPEN.value,
                    }

                self.update({'privacy': arg, **include})
                break

    def update_meta(self, meta: List[functools.partial]) -> None:
        names = []
        results = []

        unfiltered = [*meta[::-1], *self.meta[::-1]]
        for elem in unfiltered:
            coro = elem.func

            if coro.__qualname__ not in names:
                # Very hacky solution but its needed to update the privacy
                # in .config since updating privacy doesnt work as expected
                # when updating with an "all patch" strategy like other props.
                if coro.__qualname__ == 'ClientParty.set_privacy':
                    self._update_privacy(elem.args)

                names.append(coro.__qualname__)
                results.append(elem)

            if not (asyncio.iscoroutine(coro)
                    or asyncio.iscoroutinefunction(coro)):
                raise TypeError('meta must be list containing partials '
                                'of coroutines')

        self.meta = results


class DefaultPartyMemberConfig:
    """Data class for the default party member configuration used when the
    client joins a party.

    Parameters
    ----------
    cls: Type[:class:`ClientPartyMember`]
        The default party member object to use to represent the client as a
        party member. Here you can specify all classes that inherits from
        :class:`ClientPartyMember`.
        The library has two out of the box objects that you can use:
        - :class:`ClientPartyMember` *(Default)*
        - :class:`JustChattingClientPartyMember`
    yield_leadership: :class:`bool`:
        Wether or not the client should promote another member automatically
        whenever there is a chance to.
        Defaults to ``False``
    offline_ttl: :class:`int`
        How long the client should stay in the party disconnected state before
        expiring when the xmpp connection is lost. Defaults to ``30``.
    meta: List[:class:`functools.partial`]
        A list of coroutines in the form of partials. This config will be
        automatically equipped by the bot when joining new parties.

        .. code-block:: python3

            from fortnitepy import ClientPartyMember
            from functools import partial

            [
                partial(ClientPartyMember.set_outfit, 'CID_175_Athena_Commando_M_Celestial'),
                partial(ClientPartyMember.set_banner, icon="OtherBanner28", season_level=100)
            ]

    Attributes
    ----------
    cls: Type[:class:`ClientPartyMember`]
        The default party member object used when representing the client as a
        party member.
    yield_leadership: :class:`bool`
        Wether or not the client promotes another member automatically
        whenever there is a chance to.
    offline_ttl: :class:`int`
        How long the client will stay in the party disconnected state before
        expiring when the xmpp connection is lost.
    """  # noqa
    def __init__(self, **kwargs: Any) -> None:
        self.cls = kwargs.get('cls', ClientPartyMember)
        self.yield_leadership = kwargs.get('yield_leadership', False)
        self.offline_ttl = kwargs.get('offline_ttl', 30)
        self.meta = kwargs.get('meta', [])

    def update_meta(self, meta: List[functools.partial]) -> None:
        names = []
        results = []

        unfiltered = [*meta[::-1], *self.meta[::-1]]
        for elem in unfiltered:
            coro = elem.func
            if coro.__qualname__ not in names:
                names.append(coro.__qualname__)
                results.append(elem)

            if not (asyncio.iscoroutine(coro)
                    or asyncio.iscoroutinefunction(coro)):
                raise TypeError('meta must be list containing partials '
                                'of coroutines')

        self.meta = results


class Patchable:
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def update_meta_config(self, data: dict, **kwargs) -> None:
        raise NotImplementedError

    async def do_patch(self, updated: Optional[dict] = None,
                       deleted: Optional[list] = None,
                       overridden: Optional[dict] = None,
                       **kwargs) -> None:
        raise NotImplementedError

    async def patch(self, updated: Optional[dict] = None,
                    deleted: Optional[list] = None,
                    overridden: Optional[dict] = None,
                    **kwargs) -> Any:
        async with self.patch_lock:
            try:
                await self.meta.meta_ready_event.wait()
                while True:
                    try:
                        # If no updated is passed then just select the first
                        # value to "update" as fortnite returns an error if
                        # the update meta is empty.
                        max_ = kwargs.pop('max', 1)
                        _updated = updated or self.meta.get_schema(max=max_)
                        _deleted = deleted or []
                        _overridden = overridden or {}

                        for val in _deleted:
                            try:
                                del _updated[val]
                            except KeyError:
                                pass

                        await self.do_patch(
                            updated=_updated,
                            deleted=_deleted,
                            overridden=_overridden,
                            **kwargs
                        )
                        self.revision += 1
                        return updated, deleted, overridden
                    except HTTPException as exc:
                        m = 'errors.com.epicgames.social.party.stale_revision'
                        if exc.message_code == m:
                            self.revision = int(exc.message_vars[1])
                            continue

                        raise
            finally:
                self._config_cache = {}

    async def _edit(self,
                    *coros: List[Union[Awaitable, functools.partial]]) -> None:
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

        before = self.meta.schema.copy()

        async with MaybeLock(self.edit_lock):
            await asyncio.gather(*list(to_gather.values()))

        updated = {}
        deleted = []
        for prop, value in before.items():
            try:
                new_value = self.meta.schema[prop]
            except KeyError:
                deleted.append(prop)
                continue

            if value != new_value:
                updated[prop] = new_value

        return updated, deleted, self._config_cache

    async def edit(self,
                   *coros: List[Union[Awaitable, functools.partial]]
                   ) -> None:
        for coro in coros:
            if not (asyncio.iscoroutine(coro)
                    or isinstance(coro, functools.partial)):
                raise TypeError('All arguments must be coroutines or a '
                                'partials of coroutines')

        updated, deleted, config = await self._edit(*coros)
        return await self.patch(
            updated=updated,
            deleted=deleted,
            config=config,
        )

    async def edit_and_keep(self,
                            *coros: List[Union[Awaitable, functools.partial]]
                            ) -> None:
        new = []
        for coro in coros:
            if not isinstance(coro, functools.partial):
                raise TypeError('All arguments must partials of a coroutines')

            result = getattr(coro.func, '__self__', None)
            if result is not None:
                coro = functools.partial(
                    getattr(self.__class__, coro.func.__name__),
                    *coro.args,
                    **coro.keywords
                )

            new.append(coro)

        updated, deleted, config = await self._edit(*new)
        self.update_meta_config(new, config=config)

        return await self.patch(
            updated=updated,
            deleted=deleted,
            config=config,
        )


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
            return self.schema.get(prop)

        _t = prop[-1:]
        _v = self.schema.get(prop)
        if _t == 'b':
            return not (_v is None or (isinstance(_v, str)
                        and _v.lower() == 'false'))
        elif _t == 'j':
            return {} if _v is None else json.loads(_v)
        elif _t == 'U':
            return 0 if _v is None else int(_v)
        else:
            return '' if _v is None else str(_v)

    def delete_prop(self, prop: str) -> str:
        try:
            del self.schema[prop]
        except KeyError:
            pass

        return prop

    def update(self, schema: Optional[dict] = None, *,
               raw: bool = False) -> None:
        if schema is None:
            return

        for prop, value in schema.items():
            self.set_prop(prop, value, raw=raw)

    def remove(self, schema: Union[List[str], Dict[str, Any]]) -> None:
        for prop in schema:
            try:
                del self.schema[prop]
            except KeyError:
                pass

    def get_schema(self, max: Optional[int] = None) -> dict:
        return dict(list(self.schema.items())[:max])


class PartyMemberMeta(MetaBase):
    def __init__(self, member: 'PartyMemberBase',
                 meta: Optional[dict] = None) -> None:
        super().__init__()
        self.member = member

        self.meta_ready_event = asyncio.Event()
        self.has_been_updated = True

        self.def_character = DefaultCharactersChapter2.get_random_name()
        self.schema = {
            'Default:Location_s': 'PreLobby',
            'Default:CampaignHero_j': json.dumps({
                'CampaignHero': {
                    'heroItemInstanceId': '',
                    'heroType': ("FortHeroType'/Game/Athena/Heroes/{0}.{0}'"
                                 "".format(self.def_character)),
                },
            }),
            'Default:CampaignInfo_j': json.dumps({
                'CampaignInfo': {
                    'matchmakingLevel': 0,
                    'zoneInstanceId': '',
                    'homeBaseVersion': 1,
                },
            }),
            'Default:MatchmakingLevel_U': '0',
            'Default:ZoneInstanceId_s': '',
            'Default:HomeBaseVersion_U': '1',
            'Default:FrontendEmote_j': json.dumps({
                'FrontendEmote': {
                    'emoteItemDef': 'None',
                    'emoteItemDefEncryptionKey': '',
                    'emoteSection': -1,
                },
            }),
            'Default:NumAthenaPlayersLeft_U': '0',
            'Default:UtcTimeStartedMatchAthena_s': '0001-01-01T00:00:00.000Z',
            'Default:LobbyState_j': json.dumps({
                'LobbyState': {
                    'inGameReadyCheckStatus': None,
                    'gameReadiness': 'NotReady',
                    'readyInputType': 'MouseAndKeyboard',
                    'currentInputType': 'MouseAndKeyboard',
                    'hiddenMatchmakingDelayMax': 0,
                    'hasPreloadedAthena': False,
                },
            }),
            'Default:FrontEndMapMarker_j': json.dumps({
                'FrontEndMapMarker': {
                    'markerLocation': {
                        'x': 0,
                        'y': 0,
                    },
                    'bIsSet': False,
                }
            }),
            'Default:AssistedChallengeInfo_j': json.dumps({
                'AssistedChallengeInfo': {
                    'questItemDef': 'None',
                    'objectivesCompleted': 0,
                },
            }),
            'Default:MemberSquadAssignmentRequest_j': json.dumps({
                'MemberSquadAssignmentRequest': {
                    'startingAbsoluteIdx': -1,
                    'targetAbsoluteIdx': -1,
                    'swapTargetMemberId': 'INVALID',
                    'version': 0,
                },
            }),
            'Default:AthenaCosmeticLoadout_j': json.dumps({
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
                },
            }),
            'Default:AthenaCosmeticLoadoutVariants_j': json.dumps({
                'AthenaCosmeticLoadoutVariants': {
                    'vL': {}
                }
            }),
            'Default:ArbitraryCustomDataStore_j': json.dumps({
                'ArbitraryCustomDataStore': []
            }),
            'Default:AthenaBannerInfo_j': json.dumps({
                'AthenaBannerInfo': {
                    'bannerIconId': 'standardbanner15',
                    'bannerColorId': 'defaultcolor15',
                    'seasonLevel': 1,
                },
            }),
            'Default:BattlePassInfo_j': json.dumps({
                'BattlePassInfo': {
                    'bHasPurchasedPass': False,
                    'passLevel': 1,
                    'selfBoostXp': 0,
                    'friendBoostXp': 0,
                },
            }),
            'Default:PlatformData_j': json.dumps({
                'PlatformData': {
                    'platform': {
                        'platformDescription': {
                            'name': self.member.client.platform.value,
                            'platformType': 'DESKTOP',
                            'onlineSubsystem': 'None',
                            'sessionType': '',
                            'externalAccountType': '',
                            'crossplayPool': 'DESKTOP'
                        },
                    },
                    'uniqueId': 'INVALID',
                    'sessionId': ''
                },
            }),
            'Default:CrossplayPreference_s': 'OptedIn',
            'Default:VoiceChatEnabled_b': 'true',
            'Default:VoiceConnectionId_s': '',
            'Default:SpectateAPartyMemberAvailable_b': 'false',
            'Default:FeatDefinition_s': 'None',
            'Default:SidekickStatus_s': 'None',
            'Default:VoiceChatStatus_s': 'Disabled',
        }

        if meta is not None:
            self.update(meta, raw=True)

        client = member.client
        if member.id == client.user.id and isinstance(member,
                                                      ClientPartyMember):
            fut = asyncio.ensure_future(
                member._edit(*member._default_config.meta)
            )
            fut.add_done_callback(lambda *args: self.meta_ready_event.set())

    @property
    def ready(self) -> bool:
        base = self.get_prop('Default:LobbyState_j')
        return base['LobbyState'].get('gameReadiness', 'NotReady')

    @property
    def input(self) -> str:
        return self.get_prop('Default:CurrentInputType_s')

    @property
    def assisted_challenge(self) -> str:
        base = self.get_prop('Default:AssistedChallengeInfo_j')
        return base['AssistedChallengeInfo'].get('questItemDef', 'None')

    @property
    def outfit(self) -> str:
        base = self.get_prop('Default:AthenaCosmeticLoadout_j')
        return base['AthenaCosmeticLoadout'].get('characterDef', 'None')

    @property
    def backpack(self) -> str:
        base = self.get_prop('Default:AthenaCosmeticLoadout_j')
        return base['AthenaCosmeticLoadout'].get('backpackDef', 'None')

    @property
    def pickaxe(self) -> str:
        base = self.get_prop('Default:AthenaCosmeticLoadout_j')
        return base['AthenaCosmeticLoadout'].get('pickaxeDef', 'None')

    @property
    def contrail(self) -> str:
        base = self.get_prop('Default:AthenaCosmeticLoadout_j')
        return base['AthenaCosmeticLoadout'].get('contrailDef', 'None')

    @property
    def variants(self) -> List[Dict[str, str]]:
        base = self.get_prop('Default:AthenaCosmeticLoadoutVariants_j')
        return base['AthenaCosmeticLoadoutVariants'].get('vL', {})

    @property
    def outfit_variants(self) -> List[Dict[str, str]]:
        return self.variants.get('AthenaCharacter', {}).get('i', [])

    @property
    def backpack_variants(self) -> List[Dict[str, str]]:
        return self.variants.get('AthenaBackpack', {}).get('i', [])

    @property
    def pickaxe_variants(self) -> List[Dict[str, str]]:
        return self.variants.get('AthenaPickaxe', {}).get('i', [])

    @property
    def contrail_variants(self) -> List[Dict[str, str]]:
        return self.variants.get('AthenaContrail', {}).get('i', [])

    @property
    def scratchpad(self) -> list:
        base = self.get_prop('Default:AthenaCosmeticLoadout_j')
        return base['AthenaCosmeticLoadout'].get('scratchpad', [])

    @property
    def custom_data_store(self) -> list:
        base = self.get_prop('Default:ArbitraryCustomDataStore_j')
        return base['ArbitraryCustomDataStore']

    @property
    def emote(self) -> str:
        base = self.get_prop('Default:FrontendEmote_j')
        return base['FrontendEmote'].get('emoteItemDef', 'None')

    @property
    def banner(self) -> Tuple[str, str, int]:
        base = self.get_prop('Default:AthenaBannerInfo_j')
        banner_info = base['AthenaBannerInfo']

        return (banner_info['bannerIconId'],
                banner_info['bannerColorId'],
                banner_info['seasonLevel'])

    @property
    def battlepass_info(self) -> Tuple[bool, int, int, int]:
        base = self.get_prop('Default:BattlePassInfo_j')
        bp_info = base['BattlePassInfo']

        return (bp_info['bHasPurchasedPass'],
                bp_info['passLevel'],
                bp_info['selfBoostXp'],
                bp_info['friendBoostXp'])

    @property
    def platform(self) -> str:
        base = self.get_prop('Default:PlatformData_j')
        return base['PlatformData']['platform']['platformDescription']['name']

    @property
    def location(self) -> str:
        return self.get_prop('Default:Location_s')

    @property
    def has_preloaded(self) -> bool:
        return self.get_prop('Default:HasPreloadedAthena_b')

    @property
    def spectate_party_member_available(self) -> bool:
        return self.get_prop('Default:SpectateAPartyMemberAvailable_b')

    @property
    def players_left(self) -> int:
        return self.get_prop('Default:NumAthenaPlayersLeft_U')

    @property
    def match_started_at(self) -> str:
        return self.get_prop('Default:UtcTimeStartedMatchAthena_s')

    @property
    def member_squad_assignment_request(self) -> str:
        prop = self.get_prop('Default:MemberSquadAssignmentRequest_j')
        return prop['MemberSquadAssignmentRequest']

    @property
    def frontend_marker_set(self) -> bool:
        prop = self.get_prop('Default:FrontEndMapMarker_j')
        return prop['FrontEndMapMarker'].get('bIsSet', False)

    @property
    def frontend_marker_location(self) -> Tuple[float, float]:
        prop = self.get_prop('Default:FrontEndMapMarker_j')
        location = prop['FrontEndMapMarker'].get('markerLocation')
        if location is None:
            return (0.0, 0.0)

        # Swap y and x because epic uses y for horizontal and x for vertical
        # which messes with my brain.
        return (location['y'], location['x'])

    def maybesub(self, def_: Any) -> Any:
        return def_ if def_ else 'None'

    def set_frontend_marker(self, *,
                            x: Optional[float] = None,
                            y: Optional[float] = None,
                            is_set: Optional[bool] = None
                            ) -> Dict[str, Any]:
        prop = self.get_prop('Default:FrontEndMapMarker_j')
        data = prop['FrontEndMapMarker']

        # Swap y and x because epic uses y for horizontal and x for vertical
        # which messes with my brain.
        if x is not None:
            data['markerLocation']['y'] = x
        if y is not None:
            data['markerLocation']['x'] = y
        if is_set is not None:
            data['bIsSet'] = is_set

        final = {'FrontEndMapMarker': data}
        key = 'Default:FrontEndMapMarker_j'
        return {key: self.set_prop(key, final)}

    def set_member_squad_assignment_request(self, current_pos: int,
                                            target_pos: int,
                                            version: int,
                                            target_id: Optional[str] = None
                                            ) -> Dict[str, Any]:
        data = {
            'startingAbsoluteIdx': current_pos,
            'targetAbsoluteIdx': target_pos,
            'swapTargetMemberId': target_id or 'INVALID',
            'version': version,
        }
        final = {'MemberSquadAssignmentRequest': data}
        key = 'Default:MemberSquadAssignmentRequest_j'
        return {key: self.set_prop(key, final)}

    def set_lobby_state(self, *,
                        in_game_ready_check_status: Optional[Any] = None,
                        game_readiness: Optional[str] = None,
                        ready_input_type: Optional[str] = None,
                        current_input_type: Optional[str] = None,
                        hidden_matchmaking_delay_max: Optional[int] = None,
                        has_pre_loaded_athena: Optional[bool] = None,
                        ) -> Dict[str, Any]:
        data = (self.get_prop('Default:LobbyState_j'))['LobbyState']

        if in_game_ready_check_status is not None:
            data['inGameReadyCheckStatus'] = in_game_ready_check_status
        if game_readiness is not None:
            data['gameReadiness'] = game_readiness
        if ready_input_type is not None:
            data['readyInputType'] = ready_input_type
        if current_input_type is not None:
            data['currentInputType'] = current_input_type
        if hidden_matchmaking_delay_max is not None:
            data['hiddenMatchmakingDelayMax'] = hidden_matchmaking_delay_max
        if has_pre_loaded_athena is not None:
            data['hasPreloadedAthena'] = has_pre_loaded_athena

        final = {'LobbyState': data}
        key = 'Default:LobbyState_j'
        return {key: self.set_prop(key, final)}

    def set_emote(self, emote: Optional[str] = None, *,
                  emote_ekey: Optional[str] = None,
                  section: Optional[int] = None) -> Dict[str, Any]:
        data = (self.get_prop('Default:FrontendEmote_j'))['FrontendEmote']

        if emote is not None:
            data['emoteItemDef'] = self.maybesub(emote)
        if emote_ekey is not None:
            data['emoteItemDefEncryptionKey'] = emote_ekey
        if section is not None:
            data['emoteSection'] = section

        final = {'FrontendEmote': data}
        key = 'Default:FrontendEmote_j'
        return {key: self.set_prop(key, final)}

    def set_assisted_challenge(self, quest: Optional[str] = None, *,
                               completed: Optional[int] = None
                               ) -> Dict[str, Any]:
        prop = self.get_prop('Default:AssistedChallengeInfo_j')
        data = prop['AssistedChallenge_j']

        if quest is not None:
            data['questItemDef'] = self.maybesub(quest)
        if completed is not None:
            data['objectivesCompleted'] = completed

        final = {'AssistedChallengeInfo': data}
        key = 'Default:AssistedChallengeInfo_j'
        return {key: self.set_prop(key, final)}

    def set_banner(self, banner_icon: Optional[str] = None, *,
                   banner_color: Optional[str] = None,
                   season_level: Optional[int] = None) -> Dict[str, Any]:
        key = 'Default:AthenaBannerInfo_j'
        data = (self.get_prop(key))['AthenaBannerInfo']

        if banner_icon is not None:
            data['bannerIconId'] = banner_icon
        if banner_color is not None:
            data['bannerColorId'] = banner_color
        if season_level is not None:
            data['seasonLevel'] = season_level

        final = {'AthenaBannerInfo': data}
        return {key: self.set_prop(key, final)}

    def set_battlepass_info(self, has_purchased: Optional[bool] = None,
                            level: Optional[int] = None,
                            self_boost_xp: Optional[int] = None,
                            friend_boost_xp: Optional[int] = None
                            ) -> Dict[str, Any]:
        data = (self.get_prop('Default:BattlePassInfo_j'))['BattlePassInfo']

        if has_purchased is not None:
            data['bHasPurchasedPass'] = has_purchased
        if level is not None:
            data['passLevel'] = level
        if self_boost_xp is not None:
            data['selfBoostXp'] = self_boost_xp
        if friend_boost_xp is not None:
            data['friendBoostXp'] = friend_boost_xp

        final = {'BattlePassInfo': data}
        key = 'Default:BattlePassInfo_j'
        return {key: self.set_prop(key, final)}

    def set_cosmetic_loadout(self, *,
                             character: Optional[str] = None,
                             character_ekey: Optional[str] = None,
                             backpack: Optional[str] = None,
                             backpack_ekey: Optional[str] = None,
                             pickaxe: Optional[str] = None,
                             pickaxe_ekey: Optional[str] = None,
                             contrail: Optional[str] = None,
                             contrail_ekey: Optional[str] = None,
                             scratchpad: Optional[list] = None
                             ) -> Dict[str, Any]:
        prop = self.get_prop('Default:AthenaCosmeticLoadout_j')
        data = prop['AthenaCosmeticLoadout']

        if character is not None:
            data['characterDef'] = character
        if character_ekey is not None:
            data['characterEKey'] = character_ekey
        if backpack is not None:
            data['backpackDef'] = self.maybesub(backpack)
        if backpack_ekey is not None:
            data['backpackEKey'] = backpack_ekey
        if pickaxe is not None:
            data['pickaxeDef'] = pickaxe
        if pickaxe_ekey is not None:
            data['pickaxeEKey'] = pickaxe_ekey
        if contrail is not None:
            data['contrailDef'] = self.maybesub(contrail)
        if contrail_ekey is not None:
            data['contrailEKey'] = contrail_ekey
        if scratchpad is not None:
            data['scratchpad'] = scratchpad

        final = {'AthenaCosmeticLoadout': data}
        key = 'Default:AthenaCosmeticLoadout_j'
        return {key: self.set_prop(key, final)}

    def set_variants(self, variants: List[dict]) -> Dict[str, Any]:
        final = {
            'AthenaCosmeticLoadoutVariants': {
                'vL': variants
            }
        }
        key = 'Default:AthenaCosmeticLoadoutVariants_j'
        return {key: self.set_prop(key, final)}

    def set_custom_data_store(self, value: list) -> Dict[str, Any]:
        final = {
            'ArbitraryCustomDataStore': value
        }
        key = 'Default:ArbitraryCustomDataStore_j'
        return {key: self.set_prop(key, final)}

    def set_match_state(self, *,
                        location: str = None,
                        has_preloaded: bool = None,
                        spectate_party_member_available: bool = None,
                        players_left: bool = None,
                        started_at: datetime.datetime = None
                        ) -> Dict[str, Any]:
        result = {}

        if location is not None:
            key = 'Default:Location_s'
            result[key] = self.set_prop(key, location)
        if has_preloaded is not None:
            key = 'Default:HasPreloadedAthena_b'
            result[key] = self.set_prop(key, has_preloaded)
        if spectate_party_member_available is not None:
            key = 'Default:SpectateAPartyMemberAvailable_b'
            result[key] = self.set_prop(key, spectate_party_member_available)
        if players_left is not None:
            key = 'Default:NumAthenaPlayersLeft_U'
            result[key] = self.set_prop(key, players_left)
        if started_at is not None:
            key = 'Default:UtcTimeStartedMatchAthena_s'
            timestamp = self.member.client.to_iso(started_at)
            result[key] = self.set_prop(key, timestamp)

        return result


class PartyMeta(MetaBase):
    def __init__(self, party: 'PartyBase',
                 meta: Optional[dict] = None) -> None:
        super().__init__()
        self.party = party

        self.meta_ready_event = asyncio.Event()

        privacy = self.party.config['privacy']
        privacy_settings = {
            'partyType': privacy['partyType'],
            'partyInviteRestriction': privacy['inviteRestriction'],
            'bOnlyLeaderFriendsCanJoin': privacy['onlyLeaderFriendsCanJoin'],
        }

        self.schema = {
            'Default:PrimaryGameSessionId_s': '',
            'Default:PartyState_s': 'BattleRoyaleView',
            'Default:LobbyConnectionStarted_b': 'false',
            'Default:MatchmakingResult_s': 'NoResults',
            'Default:MatchmakingState_s': 'NotMatchmaking',
            'Default:SessionIsCriticalMission_b': 'false',
            'Default:ZoneTileIndex_U': '-1',
            'Default:ZoneInstanceId_s': '',
            'Default:SpectateAPartyMemberAvailable_b': 'false',
            'Default:TheaterId_s': '',
            'Default:TileStates_j': json.dumps({
                'TileStates': [],
            }),
            'Default:MatchmakingInfoString_s': '',
            'Default:CustomMatchKey_s': '',
            'Default:PlaylistData_j': json.dumps({
                'PlaylistData': {
                    'playlistName': 'Playlist_DefaultDuo',
                    'tournamentId': '',
                    'eventWindowId': '',
                },
            }),
            'Default:RegionId_s': 'EU',
            'Default:AthenaSquadFill_b': 'true',
            'Default:AllowJoinInProgress_b': 'false',
            'Default:LFGTime_s': '0001-01-01T00:00:00.000Z',
            'Default:PartyIsJoinedInProgress_b': 'false',
            'Default:GameSessionKey_s': '',
            'Default:RawSquadAssignments_j': json.dumps({
                'RawSquadAssignments': []
            }),
            'Default:PrivacySettings_j': json.dumps({
                'PrivacySettings': privacy_settings,
            }),
            'Default:PlatformSessions_j': json.dumps({
                'PlatformSessions': [],
            }),
            'Default:PartyMatchmakingInfo_j': json.dumps({
                'PartyMatchmakingInfo': {
                    'buildId': -1,
                    'hotfixVersion': -1,
                    'regionId': '',
                    'playlistName': 'None',
                    'tournamentId': '',
                    'eventWindowId': '',
                    'linkCode': '',
                }
            }),
        }

        if meta is not None:
            self.update(meta, raw=True)

        self.meta_ready_event.set()

    @property
    def playlist_info(self) -> Tuple[str]:
        base = self.get_prop('Default:PlaylistData_j')
        info = base['PlaylistData']

        return (info['playlistName'],
                info['tournamentId'],
                info['eventWindowId'])

    @property
    def squad_fill(self) -> bool:
        return self.get_prop('Default:AthenaSquadFill_b')

    @property
    def region(self) -> Region:
        return Region(self.get_prop('Default:RegionId_s'))

    @property
    def privacy(self) -> Optional[PartyPrivacy]:
        raw = self.get_prop('Default:PrivacySettings_j')
        curr_priv = raw['PrivacySettings']

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

    @property
    def squad_assignments(self) -> List[dict]:
        raw = self.get_prop('Default:RawSquadAssignments_j')
        return raw['RawSquadAssignments']

    def set_squad_assignments(self, data: List[dict]) -> Dict[str, Any]:
        final = {'RawSquadAssignments': data}
        key = 'Default:RawSquadAssignments_j'
        return {key: self.set_prop(key, final)}

    def set_playlist(self, playlist: Optional[str] = None, *,
                     tournament: Optional[str] = None,
                     event_window: Optional[str] = None) -> Dict[str, Any]:
        data = (self.get_prop('Default:PlaylistData_j'))['PlaylistData']

        if playlist is not None:
            data['playlistName'] = playlist
        if tournament is not None:
            data['tournamentId'] = tournament
        if event_window is not None:
            data['eventWindowId'] = event_window

        final = {'PlaylistData': data}
        key = 'Default:PlaylistData_j'
        return {key: self.set_prop(key, final)}

    def set_region(self, region: Region) -> Dict[str, Any]:
        key = 'Default:RegionId_s'
        return {key: self.set_prop(key, region.value)}

    def set_custom_key(self, key: str) -> Dict[str, Any]:
        _key = 'Default:CustomMatchKey_s'
        return {_key: self.set_prop(_key, key)}

    def set_fill(self, val: str) -> Dict[str, Any]:
        key = 'Default:AthenaSquadFill_b'
        return {key: self.set_prop(key, (str(val)).lower())}

    def set_privacy(self, privacy: dict) -> Tuple[dict, list]:
        updated = {}
        deleted = []
        config = {}

        p = self.get_prop('Default:PrivacySettings_j')
        if p:
            _priv = privacy
            new_privacy = {
                **p['PrivacySettings'],
                'partyType': _priv['partyType'],
                'bOnlyLeaderFriendsCanJoin': _priv['onlyLeaderFriendsCanJoin'],
                'partyInviteRestriction': _priv['inviteRestriction'],
            }

            key = 'Default:PrivacySettings_j'
            updated[key] = self.set_prop(key, {
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
            deleted.append(
                self.delete_prop('urn:epic:cfg:not-accepting-members')
            )

        if privacy['partyType'] == 'Private':
            updated['urn:epic:cfg:not-accepting-members-reason_i'] = 7
            config['discoverability'] = PartyDiscoverability.INVITED_ONLY.value
            config['joinability'] = PartyJoinability.INVITE_AND_FORMER.value
        else:
            deleted.append(
                self.delete_prop('urn:epic:cfg:not-accepting-members-reason_i')
            )
            config['discoverability'] = PartyDiscoverability.ALL.value
            config['joinability'] = PartyJoinability.OPEN.value

        if self.party.edit_lock.locked():
            self.party._config_cache.update(config)

        return updated, deleted, config

    def set_voicechat_implementation(self, value: str) -> Dict[str, str]:
        key = 'VoiceChat:implementation_s'
        return {key: self.set_prop(key, value)}


class PartyMemberBase(User):
    def __init__(self, client: 'Client',
                 party: 'PartyBase',
                 data: str) -> None:
        super().__init__(client=client, data=data)

        self._party = party
        self._assignment_version = 0

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
        return self.role == 'CAPTAIN'

    @property
    def position(self) -> int:
        """:class:`int`: Returns this members position in the party. This
        position is what defines which team you're apart of in the party.
        The position can be any number from 0-15 (16 in total).

        | 0-3 = Team 1
        | 4-7 = Team 2
        | 8-11 = Team 3
        | 12-15 = Team 4
        """
        member = self.party.get_member(self.id)
        return self.party.squad_assignments[member].position

    @property
    def hidden(self) -> bool:
        """:class:`bool`: Whether or not the member is currently hidden in the
        party. A member can only be hidden if a bot is the leader, therefore
        this attribute rarely is used."""
        member = self.party.get_member(self.id)
        return self.party.squad_assignments[member].hidden

    @property
    def platform(self) -> Platform:
        """:class:`Platform`: The platform this user currently uses."""
        val = self.connection['meta'].get(
            'urn:epic:conn:platform_s',
            self.meta.platform
        )
        return Platform(val)

    @property
    def will_yield_leadership(self) -> bool:
        """:class:`bool`: Whether or not this member will promote another
        member as soon as there is a chance for it. This is usually only True
        for Just Chattin' members.
        """
        return self.connection.get('yield_leadership', False)

    @property
    def offline_ttl(self) -> int:
        """:class:`int`: The amount of time this member will stay in a zombie
        mode before expiring.
        """
        return self.connection.get('offline_ttl', 30)

    def is_zombie(self) -> bool:
        """:class:`bool`: Whether or not this member is in a zombie mode meaning
        their xmpp connection is disconnected and not responding.
        """
        return 'disconnected_at' in self.connection

    @property
    def zombie_since(self) -> Optional[datetime.datetime]:
        """Optional[:class:`datetime.datetime`]: The utc datetime this member
        went into a zombie state. ``None`` if this user is currently not a
        zombie.
        """
        disconnected_at = self.connection.get('disconnected_at')
        if disconnected_at is not None:
            return self.client.from_iso(disconnected_at)

    def is_just_chatting(self) -> bool:
        """:class:`bool`: Whether or not the member is Just Chattin' through
        the mobile app.

        .. warning::

            All attributes below will most likely have default values if this
            is True.
        """
        val = self.connection['meta'].get('urn:epic:conn:type_s') == 'embedded'
        return val

    @property
    def ready(self) -> ReadyState:
        """:class:`ReadyState`: The members ready state."""
        return ReadyState(self.meta.ready)

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
    def enlightenments(self) -> List[Tuple[int, int]]:
        """List[:class:`tuple`]: A list of tuples containing the
        enlightenments of this member.
        """
        return [tuple(d.values()) for d in self.meta.scratchpad]

    @property
    def corruption(self) -> Optional[float]:
        """Optional[float]: The corruption value this member is using. ``None``
        if no corruption value is set.
        """
        data = self.meta.custom_data_store
        if data:
            for variants in self.meta.variants.values():
                inner = variants.get('i', [])
                for variant in inner:
                    if variant['c'] == 'Corruption':
                        for stored in data:
                            try:
                                return float(stored)
                            except ValueError:
                                pass

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

    def in_match(self) -> bool:
        """Whether or not this member is currently in a match.

        Returns
        -------
        :class:`bool`
            ``True`` if this member is in a match else ``False``.
        """
        return self.meta.location == 'InGame'

    @property
    def match_started_at(self) -> Optional[datetime.datetime]:
        """Optional[:class:`datetime.datetime`]: The time in UTC that
        the members match started. ``None`` if not in a match.
        """
        if not self.in_match:
            return None

        return self.client.from_iso(self.meta.match_started_at)

    @property
    def match_players_left(self) -> int:
        """How many players there are left in this players match.

        Returns
        -------
        :class:`int`
            How many players there are left in this members current match.
            Defaults to ``0`` if not in a match.
        """
        return self.meta.players_left

    def lobby_map_marker_is_visible(self) -> bool:
        """Whether or not this members lobby map marker is currently visible.

        Returns
        -------
        :class:`bool`
            ``True`` if this members lobby map marker is currently visible else
            ``False``.
        """
        return self.meta.frontend_marker_set

    @property
    def lobby_map_marker_coordinates(self) -> Tuple[float, float]:
        """Tuple[:class:`float`, :class:`float`]: A tuple containing the x and y
        coordinates of this members current lobby map marker.

        .. note::

            Check if the marker is currently visible with
            :meth:`PartyMember.lobby_map_marker_is_visible()`.

        .. note::

            The coordinates range is roughly ``-135000.0 <= coordinate <= 135000``
        """  # noqa
        return self.meta.frontend_marker_location

    def is_ready(self) -> bool:
        """Whether or not this member is ready.

        Returns
        -------
        :class:`bool`
            ``True`` if this member is ready else ``False``.
        """
        return self.ready is ReadyState.READY

    def is_chatbanned(self) -> bool:
        """:class:`bool`: Whether or not this member is chatbanned."""
        return self.id in getattr(self.party, '_chatbanned_members', {})

    def _update_connection(self, data: Optional[Union[list, dict]]) -> None:
        if data:
            if isinstance(data, list):
                for connection in data:
                    if 'disconnected_at' not in connection:
                        data = connection
                        break
                else:
                    data = data[0]

        self.connection = data or {}

    def _update(self, data: dict) -> None:
        super()._update(data)
        self.update_role(data.get('role'))
        self.revision = data.get('revision', 0)

        connections = data.get('connections', data.get('connection'))
        self._update_connection(connections)

    def update(self, data: dict) -> None:
        if data['revision'] > self.revision:
            self.revision = data['revision']
        self.meta.update(data['member_state_updated'], raw=True)
        self.meta.remove(data['member_state_removed'])

    def update_role(self, role: str) -> None:
        self.role = role
        self._role_updated_at = datetime.datetime.utcnow()

    @staticmethod
    def create_variant(*, config_overrides: Dict[str, str] = {},
                       **kwargs: Any) -> List[Dict[str, Union[str, int]]]:
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
                me = client.party.me

                variants = me.create_variant(
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
        config_overrides: Dict[:class:`str`, :class:`str`]
            A config that overrides the default config for the variant
            backend names. Example: ::

                # NOTE: Keys refer to the kwarg name.
                # NOTE: Values must include exactly one empty format bracket.
                {
                    'particle': 'Mat{}'
                }
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
        default_config = {
            'pattern': 'Mat{}',
            'numeric': 'Numeric.{}',
            'clothing_color': 'Mat{}',
            'jersey_color': 'Color.{}',
            'parts': 'Stage{}',
            'progressive': 'Stage{}',
            'particle': 'Emissive{}',
            'material': 'Mat{}',
            'emissive': 'Emissive{}',
            'profile_banner': '{}',
        }
        config = {**default_config, **config_overrides}

        data = []
        for channel, value in kwargs.items():
            v = {
                'c': ''.join(x.capitalize() for x in channel.split('_')),
                'dE': 0,
            }

            if channel == 'JerseyColor':
                v['v'] = config[channel].format(value.upper())
            else:
                v['v'] = config[channel].format(value)

            data.append(v)

        return data

    create_variants = create_variant


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
        if self.client.is_creating_party():
            return

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
            raise

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
        if self.client.is_creating_party():
            return

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

    async def swap_position(self) -> None:
        """|coro|

        Swaps the clients party position with this member.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        me = self.party.me
        version = me._assignment_version + 1
        prop = me.meta.set_member_squad_assignment_request(
            me.position,
            self.position,
            version,
            target_id=self.id,
        )

        if not me.edit_lock.locked():
            return await me.patch(updated=prop)


class ClientPartyMember(PartyMemberBase, Patchable):
    """Represents the clients party member.

    Attributes
    ----------
    client: :class:`Client`
        The client.
    """

    CONN_TYPE = 'game'

    def __init__(self, client: 'Client',
                 party: 'PartyBase',
                 data: dict) -> None:
        self._default_config = client.default_party_member_config
        self.clear_emote_task = None
        self.clear_in_match_task = None

        self._config_cache = {}
        self.patch_lock = asyncio.Lock()
        self.edit_lock = asyncio.Lock()
        self._dummy = False

        super().__init__(client, party, data)

    def __repr__(self) -> str:
        return ('<ClientPartyMember id={0.id!r} '
                'display_name={0.display_name!r} '
                'joined_at={0.joined_at!r}>'.format(self))

    async def do_patch(self, updated: Optional[dict] = None,
                       deleted: Optional[list] = None,
                       overridden: Optional[dict] = None,
                       **kwargs) -> None:
        if self._dummy:
            return

        await self.client.http.party_update_member_meta(
            party_id=self.party.id,
            user_id=self.id,
            updated_meta=updated,
            deleted_meta=deleted,
            overridden_meta=overridden,
            revision=self.revision,
            **kwargs
        )

    def update_meta_config(self, data: dict, **kwargs) -> None:
        # Incase the default party member config has been overridden, the
        # config used to make this obj should also be updated. This is
        # so you can still do hacky checks to see the default meta
        # properties.
        if self._default_config is not self.client.default_party_member_config:
            self._default_config.update_meta(data)

        self.client.default_party_member_config.update_meta(data)
        return self.client.default_party_member_config.meta

    async def edit(self,
                   *coros: List[Union[Awaitable, functools.partial]]
                   ) -> None:
        """|coro|

        Edits multiple meta parts at once.

        This example sets the clients outfit to galaxy and banner to the epic
        banner with level 100: ::

            from functools import partial

            async def edit_client_member():
                member = client.party.me
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
        await super().edit(*coros)

    async def edit_and_keep(self,
                            *coros: List[Union[Awaitable, functools.partial]]
                            ) -> None:
        """|coro|

        Edits multiple meta parts at once and keeps the changes for when the
        bot joins other parties.

        This example sets the clients outfit to galaxy and banner to the epic
        banner with level 100. When the client joins another party, the outfit
        and banner will automatically be equipped: ::

            from functools import partial

            async def edit_and_keep_client_member():
                member = client.party.me
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
        await super().edit_and_keep(*coros)

    def do_on_member_join_patch(self) -> None:
        async def patcher():
            try:
                # max=30 because 30 is the maximum amount of props that
                # can be updated at once.
                await self.patch(max=30)
            except HTTPException as exc:
                m = 'errors.com.epicgames.social.party.party_not_found'
                if exc.message_code != m:
                    raise

        asyncio.ensure_future(patcher())

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
        self._cancel_clear_emote()

        async with self.client._join_party_lock:
            try:
                await self.client.http.party_leave(self.party.id)
            except HTTPException as e:
                m = 'errors.com.epicgames.social.party.party_not_found'
                if e.message_code != m:
                    raise

            await self.client.xmpp.leave_muc()
            p = await self.client._create_party(acquire=False)
            return p

    async def set_ready(self, state: ReadyState) -> None:
        """|coro|

        Sets the readiness of the client.

        Parameters
        ----------
        state: :class:`ReadyState`
            The ready state you wish to set.
        """
        prop = self.meta.set_lobby_state(
            game_readiness=state.value
        )

        if not self.edit_lock.locked():
            return await self.patch(updated=prop)

    async def set_outfit(self, asset: Optional[str] = None, *,
                         key: Optional[str] = None,
                         variants: Optional[List[Dict[str, str]]] = None,
                         enlightenment: Optional[Union[List, Tuple]] = None,
                         corruption: Optional[float] = None
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
        enlightenment: Optional[Union[:class:`list`, :class:`Tuple`]]
            A list/tuple containing exactly two integer values describing the
            season and the level you want to enlighten the current loadout
            with.

            .. note::

                Using enlightenments often requires you to set a specific
                variant for the skin.

            Example.: ::

                # First value is the season in Fortnite Chapter 2
                # Second value is the level for the season
                (1, 300)
        corruption: Optional[float]
            The corruption value to use for the loadout.

            .. note::

                Unlike enlightenment you do not need to set any variants
                yourself as that is handled by the library.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        if asset is not None:
            if asset != '' and '.' not in asset:
                asset = ("AthenaCharacterItemDefinition'/Game/Athena/Items/"
                         "Cosmetics/Characters/{0}.{0}'".format(asset))
        else:
            prop = self.meta.get_prop('Default:AthenaCosmeticLoadout_j')
            asset = prop['AthenaCosmeticLoadout']['characterDef']

        if enlightenment is not None:
            if len(enlightenment) != 2:
                raise ValueError('enlightenment has to be a list/tuple with '
                                 'exactly two int/float values.')
            else:
                enlightenment = [
                    {
                        't': enlightenment[0],
                        'v': enlightenment[1]
                    }
                ]

        if corruption is not None:
            corruption = ['{:.4f}'.format(corruption)]
            variants = [
                {'c': "Corruption", 'v': 'FloatSlider', 'dE': 1}
            ] + (variants or [])
        else:
            corruption = self.meta.custom_data_store

        current = self.meta.variants
        if variants is not None:
            current['AthenaCharacter'] = {'i': variants}
        else:
            try:
                del current['AthenaCharacter']
            except KeyError:
                pass

        prop = self.meta.set_cosmetic_loadout(
            character=asset,
            character_ekey=key,
            scratchpad=enlightenment
        )
        prop2 = self.meta.set_variants(
            variants=current
        )
        prop3 = self.meta.set_custom_data_store(
            value=corruption
        )

        if not self.edit_lock.locked():
            return await self.patch(updated={**prop, **prop2, **prop3})

    async def set_backpack(self, asset: Optional[str] = None, *,
                           key: Optional[str] = None,
                           variants: Optional[List[Dict[str, str]]] = None,
                           enlightenment: Optional[Union[List, Tuple]] = None,
                           corruption: Optional[float] = None
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
        enlightenment: Optional[Union[:class:`list`, :class:`Tuple`]]
            A list/tuple containing exactly two integer values describing the
            season and the level you want to enlighten the current loadout
            with.

            .. note::

                Using enlightenments often requires you to set a specific
                variant for the skin.

            Example.: ::

                # First value is the season in Fortnite Chapter 2
                # Second value is the level for the season
                (1, 300)
        corruption: Optional[float]
            The corruption value to use for the loadout.

            .. note::

                Unlike enlightenment you do not need to set any variants
                yourself as that is handled by the library.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        if asset is not None:
            if asset != '' and '.' not in asset:
                asset = ("AthenaBackpackItemDefinition'/Game/Athena/Items/"
                         "Cosmetics/Backpacks/{0}.{0}'".format(asset))
        else:
            prop = self.meta.get_prop('Default:AthenaCosmeticLoadout_j')
            asset = prop['AthenaCosmeticLoadout']['backpackDef']

        if enlightenment is not None:
            if len(enlightenment) != 2:
                raise ValueError('enlightenment has to be a list/tuple with '
                                 'exactly two int/float values.')
            else:
                enlightenment = [
                    {
                        't': enlightenment[0],
                        'v': enlightenment[1]
                    }
                ]

        if corruption is not None:
            corruption = ['{:.4f}'.format(corruption)]
            variants = [
                {'c': "Corruption", 'v': 'FloatSlider', 'dE': 1}
            ] + (variants or [])
        else:
            corruption = self.meta.custom_data_store

        current = self.meta.variants
        if variants is not None:
            current['AthenaBackpack'] = {'i': variants}
        else:
            try:
                del current['AthenaBackpack']
            except KeyError:
                pass

        prop = self.meta.set_cosmetic_loadout(
            backpack=asset,
            backpack_ekey=key,
            scratchpad=enlightenment
        )
        prop2 = self.meta.set_variants(
            variants=current
        )
        prop3 = self.meta.set_custom_data_store(
            value=corruption
        )

        if not self.edit_lock.locked():
            return await self.patch(updated={**prop, **prop2, **prop3})

    async def clear_backpack(self) -> None:
        """|coro|

        Clears the currently set backpack.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        await self.set_backpack(asset="")

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

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        if asset is not None:
            if asset != '' and '.' not in asset:
                asset = ("AthenaPetItemDefinition'/Game/Athena/Items/"
                         "Cosmetics/PetCarriers/{0}.{0}'".format(asset))
        else:
            prop = self.meta.get_prop('Default:AthenaCosmeticLoadout_j')
            asset = prop['AthenaCosmeticLoadout']['backpackDef']

        new = self.meta.variants
        if variants is not None:
            new['AthenaBackpack'] = {'i': variants}
        else:
            try:
                del new['AthenaBackpack']
            except KeyError:
                pass

        prop = self.meta.set_cosmetic_loadout(
            backpack=asset,
            backpack_ekey=key,
        )
        prop2 = self.meta.set_variants(
            variants=new
        )

        if not self.edit_lock.locked():
            return await self.patch(updated={**prop, **prop2})

    async def clear_pet(self) -> None:
        """|coro|

        Clears the currently set pet.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        await self.set_backpack(asset="")

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

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        if asset is not None:
            if asset != '' and '.' not in asset:
                asset = ("AthenaPickaxeItemDefinition'/Game/Athena/Items/"
                         "Cosmetics/Pickaxes/{0}.{0}'".format(asset))
        else:
            prop = self.meta.get_prop('Default:AthenaCosmeticLoadout_j')
            asset = prop['AthenaCosmeticLoadout']['pickaxeDef']

        new = self.meta.variants
        if variants is not None:
            new['AthenaPickaxe'] = {'i': variants}
        else:
            try:
                del new['AthenaPickaxe']
            except KeyError:
                pass

        prop = self.meta.set_cosmetic_loadout(
            pickaxe=asset,
            pickaxe_ekey=key,
        )
        prop2 = self.meta.set_variants(
            variants=new
        )

        if not self.edit_lock.locked():
            return await self.patch(updated={**prop, **prop2})

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

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        if asset is not None:
            if asset != '' and '.' not in asset:
                asset = ("AthenaContrailItemDefinition'/Game/Athena/Items/"
                         "Cosmetics/Contrails/{0}.{0}'".format(asset))
        else:
            prop = self.meta.get_prop('Default:AthenaCosmeticLoadout_j')
            asset = prop['AthenaCosmeticLoadout']['contrailDef']

        new = self.meta.variants
        if variants is not None:
            new['AthenaContrail'] = {'i': variants}
        else:
            try:
                del new['AthenaContrail']
            except KeyError:
                pass

        prop = self.meta.set_cosmetic_loadout(
            contrail=asset,
            contrail_ekey=key,
        )
        prop2 = self.meta.set_variants(
            variants=new
        )

        if not self.edit_lock.locked():
            return await self.patch(updated={**prop, **prop2})

    async def clear_contrail(self) -> None:
        """|coro|

        Clears the currently set contrail.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        await self.set_contrail(asset="")

    async def set_emote(self, asset: str, *,
                        run_for: Optional[float] = None,
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
        run_for: Optional[:class:`float`]
            Seconds the emote should run for before being cancelled. ``None``
            (default) means it will run indefinitely and you can then clear it
            with :meth:`PartyMember.clear_emote()`.
        key: Optional[:class:`str`]
            The encyption key to use for this emote.
        section: Optional[:class:`int`]
            The section.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        if asset != '' and '.' not in asset:
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
            return await self.patch(updated=prop)

    async def set_emoji(self, asset: str, *,
                        run_for: Optional[float] = 2,
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
        run_for: Optional[:class:`float`]
            Seconds the emoji should run for before being cancelled. ``None``
            means it will run indefinitely and you can then clear it with
            :meth:`PartyMember.clear_emote()`. Defaults to ``2`` seconds which
            is roughly the time an emoji naturally plays for. Note that an
            emoji is only cleared visually and audibly when the emoji
            naturally ends, not when :meth:`PartyMember.clear_emote()` is
            called.
        key: Optional[:class:`str`]
            The encyption key to use for this emoji.
        section: Optional[:class:`int`]
            The section.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        if asset != '' and '.' not in asset:
            asset = ("AthenaDanceItemDefinition'/Game/Athena/Items/"
                     "Cosmetics/Dances/Emoji/{0}.{0}'".format(asset))

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
            return await self.patch(updated=prop)

    def _cancel_clear_emote(self) -> None:
        if (self.clear_emote_task is not None
                and not self.clear_emote_task.cancelled()):
            self.clear_emote_task.cancel()

    async def _schedule_clear_emote(self, seconds: Union[int, float]) -> None:
        await asyncio.sleep(seconds)
        self.clear_emote_task = None

        try:
            await self.clear_emote()
        except HTTPException as exc:
            m = 'errors.com.epicgames.social.party.member_not_found'
            if m != exc.message_code:
                raise

    async def clear_emote(self) -> None:
        """|coro|

        Clears/stops the emote currently playing.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """

        prop = self.meta.set_emote(
            emote='None',
            emote_ekey='',
            section=-1
        )

        self._cancel_clear_emote()

        if not self.edit_lock.locked():
            return await self.patch(updated=prop)

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

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        prop = self.meta.set_banner(
            banner_icon=icon,
            banner_color=color,
            season_level=season_level
        )

        if not self.edit_lock.locked():
            return await self.patch(updated=prop)

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

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        prop = self.meta.set_battlepass_info(
            has_purchased=has_purchased,
            level=level,
            self_boost_xp=self_boost_xp,
            friend_boost_xp=friend_boost_xp
        )

        if not self.edit_lock.locked():
            return await self.patch(updated=prop)

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

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        if quest is not None:
            if quest != '' and '.' not in quest:
                quest = ("FortQuestItemDefinition'/Game/Athena/Items/"
                         "Quests/DailyQuests/Quests/{0}.{0}'".format(quest))
        else:
            prop = self.meta.get_prop('Default:AssistedChallengeInfo_j')
            quest = prop['AssistedChallengeInfo']['questItemDef']

        prop = self.meta.set_assisted_challenge(
            quest=quest,
            completed=num_completed
        )

        if not self.edit_lock.locked():
            return await self.patch(updated=prop)

    async def clear_assisted_challenge(self) -> None:
        """|coro|

        Clears the currently set assisted challenge.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        await self.set_assisted_challenge(quest="")

    async def set_position(self, position: int) -> None:
        """|coro|

        The the clients party position.

        Parameters
        ----------
        position: :class:`int`
            An integer ranging from 0-15. If a position is already held by
            someone else, then the client and the existing holder will swap
            positions.

        Raises
        ------
        ValueError
            The passed position is out of bounds.
        HTTPException
            An error occured while requesting.
        """
        if position < 0 or position > 15:
            raise ValueError('The passed position is out of bounds.')

        target_id = None
        for member, assignment in self.party.squad_assignments.items():
            if assignment.position == position:
                if member.id == self.id:
                    return

                target_id = member.id
                break

        version = self._assignment_version + 1
        prop = self.meta.set_member_squad_assignment_request(
            self.position,
            position,
            version,
            target_id=target_id,
        )

        if not self.edit_lock.locked():
            return await self.patch(updated=prop)

    async def set_in_match(self, *, players_left: int = 100,
                           started_at: datetime.timedelta = None) -> None:
        """|coro|

        Sets the clients party member in a visible match state.

        .. note::

            This is only visual in the party and is not a method for
            joining a match.

        Parameters
        ----------
        players_left: :class:`int`
            How many players that should be displayed left in your game.
            Defaults to 100.
        started_at: :class:`datetime.datetime`
            The match start time in UTC. A timer is visually displayed showing
            how long the match has lasted. Defaults to the current time (utcnow).

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """  # noqa
        if not 0 <= players_left <= 255:
            raise ValueError('players_left must be an integer between 0 '
                             'and 255')

        if started_at is not None:
            if not isinstance(started_at, datetime.datetime):
                raise TypeError('started_at must be None or datetime.datetime')
        else:
            started_at = datetime.datetime.utcnow()

        prop = self.meta.set_match_state(
            location='InGame',
            has_preloaded=True,
            spectate_party_member_available=True,
            players_left=players_left,
            started_at=started_at
        )

        if not self.edit_lock.locked():
            return await self.patch(updated=prop)

    async def clear_in_match(self) -> None:
        """|coro|

        Clears the clients "in match" state.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        prop = self.meta.set_match_state(
            location='PreLobby',
            has_preloaded=False,
            spectate_party_member_available=False,
            players_left=0,
            started_at=datetime.datetime(1, 1, 1)
        )

        if not self.edit_lock.locked():
            return await self.patch(updated=prop)

    async def set_lobby_map_marker(self, x: float, y: float) -> None:
        """|coro|

        Sets the clients lobby map marker.

        Parameters
        ----------
        x: :class:`float`
            The horizontal x coordinate.  The x range is roughly
            ``-135000.0 <= x <= 135000``.
        y: :class:`float`
            The vertical y coordinate. The y range is roughly
            ``-135000.0 <= y <= 135000``.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        prop = self.meta.set_frontend_marker(
            x=x,
            y=y,
            is_set=True,
        )

        if not self.edit_lock.locked():
            return await self.patch(updated=prop)

    async def clear_lobby_map_marker(self):
        """|coro|

        Clears and hides the clients current lobby map marker.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        prop = self.meta.set_frontend_marker(
            x=0.0,
            y=0.0,
            is_set=False,
        )

        if not self.edit_lock.locked():
            return await self.patch(updated=prop)


class JustChattingClientPartyMember(ClientPartyMember):
    """Represents the clients party member in a just chattin state
    from kairos.

    .. warning::

        The actions you can do with this party member type is very limited.
        For example if you were to change the clients outfit, it would override
        the just chattin state with no way of getting back to the state in the
        current party.

    .. container::

        You can read about all attributes and methods here:
        :class:`ClientPartyMember`
    """

    CONN_TYPE = 'embedded'

    def __init__(self, client: 'Client',
                 party: 'PartyBase',
                 data: dict) -> None:
        super().__init__(client, party, data)

        self._edited = False

    async def patch(self, *args, **kwargs) -> None:
        self._edited = True
        return await super().patch(*args, **kwargs)

    def do_on_member_join_patch(self) -> None:
        if self._edited:
            return super().do_on_member_join_patch()


class PartyBase:
    def __init__(self, client: 'Client', data: dict) -> None:
        self._client = client
        self._id = data.get('id')
        self._members = {}
        self._applicants = data.get('applicants', [])
        self._squad_assignments = OrderedDict()

        self._update_invites(data.get('invites', []))
        self._update_config(data.get('config'))
        self.meta = PartyMeta(self, data['meta'])

    def __str__(self) -> str:
        return self.id

    def __eq__(self, other):
        return isinstance(other, PartyBase) and other._id == self._id

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def client(self) -> 'Client':
        """:class:`Client`: The client."""
        return self._client

    @property
    def id(self) -> str:
        """:class:`str`: The party's id."""
        return self._id

    @property
    def members(self) -> List[PartyMember]:
        """List[:class:`PartyMember`]: A copied list of the members
        currently in this party."""
        return list(self._members.values())

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
        for member in self._members.values():
            if member.leader:
                return member

    @property
    def playlist_info(self) -> Tuple[str]:
        """:class:`tuple`: A tuple containing the name, tournament and
        event window of the currently set playlist.

        Example output: ::

            # output for default duos
            (
                'Playlist_DefaultDuo',
                '',
                '',
            )

            # output for arena trios
            (
                'Playlist_ShowdownAlt_Trios',
                'epicgames_Arena_S10_Trios',
                'Arena_S10_Division1_Trios',
            )
        """
        return self.meta.playlist_info

    @property
    def squad_fill(self) -> bool:
        """:class:`bool`: ``True`` if squad fill is enabled else ``False``."""
        return self.meta.squad_fill

    @property
    def region(self) -> Region:
        """Optional[:class:`Region`]: The region of the party."""
        return self.meta.region

    @property
    def privacy(self) -> PartyPrivacy:
        """:class:`PartyPrivacy`: The currently set privacy of this party."""
        return self.meta.privacy

    @property
    def squad_assignments(self) -> Dict[PartyMember, SquadAssignment]:
        """Dict[:class:`PartyMember`, :class:`SquadAssignment`]: The squad assignments
        for this party. This includes information about a members position and
        visibility."""
        return self._squad_assignments

    def _add_member(self, member: PartyMember) -> None:
        self._members[member.id] = member

    def _create_member(self, data: dict) -> PartyMember:
        member = PartyMember(self.client, self, data)
        self._add_member(member)
        return member

    def _remove_member(self, user_id: str) -> PartyMember:
        if not isinstance(user_id, str):
            user_id = user_id.id
        return self._members.pop(user_id)

    def get_member(self, user_id: str) -> Optional[PartyMember]:
        """Optional[:class:`PartyMember`]: Attempts to get a party member
        from the member cache. Returns ``None`` if no user was found by the
        user id.
        """
        return self._members.get(user_id)

    def _update_squad_assignments(self, raw):
        results = OrderedDict()
        for data in sorted(raw, key=lambda o: o['absoluteMemberIdx']):
            member = self.get_member(data['memberId'])
            if member is None:
                continue

            assignment = SquadAssignment(position=data['absoluteMemberIdx'])
            results[member] = assignment

        self._squad_assignments = results

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

        _update_squad_assignments = False
        
        if 'party_state_updated' in data:
            key = 'Default:RawSquadAssignments_j'
            _assignments = data['party_state_updated'].get(key)
            if _assignments:
                if _assignments != self.meta.schema.get(key, ''):
                    _update_squad_assignments = True

            self.meta.update(data['party_state_updated'], raw=True)

        if 'party_state_removed' in data:
            self.meta.remove(data['party_state_removed'])

        privacy = self.meta.get_prop('Default:PrivacySettings_j')
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

        # Only update role if the client is not in the party. This is because
        # we don't want the role being potentially updated before
        # MEMBER_NEW_CAPTAIN is received which could cause the promote
        # event to pass two of the same member objects. This piece of code
        # is essentially just here to update roles of parties that the client
        # doesn't receive events for.
        if self.client.user.id not in self._members:
            captain_id = data.get('captain_id')
            if captain_id is not None:
                leader = self.leader
                if leader is not None and captain_id != leader.id:
                    delt = datetime.datetime.utcnow() - leader._role_updated_at
                    if delt.total_seconds() > 3:
                        member = self.get_member(captain_id)
                        if member is not None:
                            self._update_roles(member)

        if _update_squad_assignments:
            if self.leader.id != self.client.user.id:
                _assignments = json.loads(_assignments)['RawSquadAssignments']
                self._update_squad_assignments(_assignments)

    def _update_roles(self, new_leader):
        for member in self._members.values():
            member.update_role(None)

        new_leader.update_role('CAPTAIN')

    def _update_invites(self, invites: list) -> None:
        self.invites = invites

    def _update_config(self, config: dict = {}) -> None:
        self.join_confirmation = config['join_confirmation']
        self.max_size = config['max_size']
        self.invite_ttl_seconds = config.get('invite_ttl_seconds',
                                             config['invite_ttl'])
        self.sub_type = config['sub_type']
        self.config = {**self.client.default_party_config.config, **config}

    async def _update_members(self, members: Optional[list] = None,
                              remove_missing: bool = True,
                              fetch_user_data: bool = True,
                              priority: int = 0) -> None:
        client = self.client
        if members is None:
            data = await client.http.party_lookup(
                self.id,
                priority=priority
            )
            members = data['members']

        def get_id(m):
            return m.get('account_id', m.get('accountId'))

        raw_users = {}
        user_ids = [get_id(m) for m in members]
        for user_id in user_ids:
            if user_id == client.user.id:
                user = client.user
            else:
                user = client.get_user(user_id)

            if user is not None:
                raw_users[user.id] = user.get_raw()
            else:
                if not fetch_user_data:
                    raw_users[user_id] = {'id': user_id}

        user_ids = [uid for uid in user_ids if uid not in raw_users]

        if user_ids:
            data = await client.http.account_get_multiple_by_user_id(
                user_ids,
                priority=priority
            )
            for account_data in data:
                raw_users[account_data['id']] = account_data

        result = []
        for raw in members:
            user_id = get_id(raw)

            account_data = raw_users[user_id]
            raw = {**raw, **account_data}

            member = self._create_member(raw)
            result.append(member)

            if member.id == client.user.id:
                try:
                    self._create_clientmember(raw)
                except AttributeError:
                    pass

        if remove_missing:
            to_remove = []
            for m in self._members.values():
                if m.id not in raw_users:
                    to_remove.append(m.id)

            for user_id in to_remove:
                self._remove_member(user_id)

        return result


class Party(PartyBase):
    """Represent a party that the ClientUser is not yet a part of."""

    def __init__(self, client: 'Client', data: dict) -> None:
        super().__init__(client, data)

    def __repr__(self) -> str:
        return ('<Party id={0.id!r} leader={0.leader.id!r} '
                'member_count={0.member_count}>'.format(self))

    async def join(self) -> 'ClientParty':
        """|coro|

        Joins the party.

        Raises
        ------
        .. warning::

            Because the client has to leave its current party before joining
            a new one, a new party is created if some of these errors are
            raised. Most of the time though this is not the case and the client
            will remain in its current party.
        PartyError
            You are already a member of this party.
        NotFound
            The party was not found.
        Forbidden
            You are not allowed to join this party because it's private
            and you have not been a part of it before.

            .. note::

                If you have been a part of the party before but got
                kicked, you are ineligible to join this party and this
                error is raised.
        HTTPException
            An error occurred when requesting to join the party.

        Returns
        -------
        :class:`ClientParty`
            The party that was just joined.
        """
        if self.client.party.id == self.id:
            raise PartyError('You are already a member of this party.')

        return await self.client.join_party(self.id)


class ClientParty(PartyBase, Patchable):
    """Represents ClientUser's party."""

    def __init__(self, client: 'Client', data: dict) -> None:
        self.last_raw_status = None
        self._me = None
        self._chatbanned_members = {}

        self.patch_lock = asyncio.Lock()
        self.edit_lock = asyncio.Lock()

        self._config_cache = {}
        self._default_config = client.default_party_config
        self._update_revision(data.get('revision', 0))

        super().__init__(client, data)

    def __repr__(self) -> str:
        return ('<ClientParty id={0.id!r} '
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

    def _add_clientmember(self, member: Type[ClientPartyMember]) -> None:
        self._me = member

    def _create_clientmember(self, data: dict) -> Type[ClientPartyMember]:
        cls = self.client.default_party_member_config.cls
        member = cls(self.client, self, data)
        self._add_clientmember(member)
        return member

    def _remove_member(self, user_id: str) -> PartyMember:
        if not isinstance(user_id, str):
            user_id = user_id.id
        self.update_presence()
        return self._members.pop(user_id)

    def construct_presence(self, text: Optional[str] = None) -> dict:
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
        kairos_profile = self.client.avatar.to_dict()

        _default_status = {
            'Status': status.format(party_size=self.member_count,
                                    party_max_size=self.max_size),
            'bIsPlaying': True,
            'bIsJoinable': False,
            'bHasVoiceSupport': False,
            'SessionId': '',
            'ProductName': 'Fortnite',
            'Properties': {
                'KairosProfile_j': kairos_profile,
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
                'Event_PartySize_s': str(len(self._members)),
                'Event_PartyMaxSize_s': str(self.max_size),
            },
        }
        return _default_status

    def update_presence(self, text: Optional[str] = None) -> None:
        data = self.construct_presence(text=text)

        if self.client.status is not False:
            self.last_raw_status = data
            self.client.xmpp.set_presence(
                status=self.last_raw_status,
                show=self.client.away.value,
            )

    def _update(self, data: dict) -> None:
        super()._update(data)
        if self.revision < data['revision']:
            self.revision = data['revision']

        if self.client.status is not False:
            self.update_presence()

    def _update_revision(self, revision: int) -> None:
        self.revision = revision

    def _update_roles(self, new_leader):
        super()._update_roles(new_leader)

        if new_leader.id == self.client.user.id:
            self.client.party.me.update_role('CAPTAIN')
        else:
            self.client.party.me.update_role(None)

    async def _update_members(self, members: Optional[list] = None,
                              remove_missing: bool = True,
                              fetch_user_data: bool = True,
                              priority: int = 0) -> None:
        result = await super()._update_members(
            members=members,
            remove_missing=remove_missing,
            fetch_user_data=fetch_user_data,
            priority=priority
        )

        if not remove_missing:
            return result

        for member in result:
            if member.id == self.client.user.id:
                break
        else:
            # There should always be a ClientPartyMember in a ClientParty,
            # therefore we have to create a dummy until the actual
            # ClientPartyMember is added at a later stage. We do this to avoid
            # ClientParty.me being None.
            default_config = self.client.default_party_member_config
            now = self.client.to_iso(datetime.datetime.utcnow())
            platform_s = self.client.platform.value
            conn_type = default_config.cls.CONN_TYPE
            external_auths = [
                x.get_raw() for x in self.client.user.external_auths
            ]

            data = {
                'account_id': self.client.user.id,
                'meta': {},
                'connections': [
                    {
                        'id': str(self.client.xmpp.xmpp_client.local_jid),
                        'connected_at': now,
                        'updated_at': now,
                        'offline_ttl': default_config.offline_ttl,
                        'yield_leadership': default_config.yield_leadership,
                        'meta': {
                            'urn:epic:conn:platform_s': platform_s,
                            'urn:epic:conn:type_s': conn_type,
                        }
                    }
                ],
                'revision': 0,
                'updated_at': now,
                'joined_at': now,
                'role': 'MEMBER',
                'displayName': self.client.user.display_name,
                'id': self.client.user.id,
                'externaAuths': external_auths,
            }

            member = self._create_clientmember(data)
            member._dummy = True

        return result

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
                self._chatbanned_members[user_id] = self._members[user_id]
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

    async def do_patch(self, updated: Optional[dict] = None,
                       deleted: Optional[list] = None,
                       overridden: Optional[dict] = None,
                       **kwargs) -> None:
        await self.client.http.party_update_meta(
            party_id=self.id,
            updated_meta=updated,
            deleted_meta=deleted,
            overridden_meta=overridden,
            revision=self.revision,
            **kwargs
        )

    def update_meta_config(self, data: dict, config: dict = {}) -> None:
        # Incase the default party member config has been overridden, the
        # config used to make this obj should also be updated. This is
        # so you can still do hacky checks to see the default meta
        # properties.
        if self._default_config is not self.client.default_party_config:
            self._default_config.update_meta(data)
            if config:
                self._default_config.update(config)

        self.client.default_party_config.update_meta(data)
        if config:
            self._default_config.update(config)

        return self.client.default_party_config.meta

    async def edit(self,
                   *coros: List[Union[Awaitable, functools.partial]]
                   ) -> None:
        """|coro|

        Edits multiple meta parts at once.

        Example: ::

            from functools import partial

            async def edit_party():
                party = client.party
                await party.edit(
                    party.set_privacy(fortnitepy.PartyPrivacy.PRIVATE), # usage with non-awaited coroutines
                    partial(party.set_custom_key, 'myawesomekey') # usage with functools.partial()
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
        await super().edit(*coros)

    async def edit_and_keep(self,
                            *coros: List[Union[Awaitable, functools.partial]]
                            ) -> None:
        """|coro|

        Edits multiple meta parts at once and keeps the changes for when new
        parties are created.

        This example sets the custom key to ``myawesomekey`` and the playlist to Creative.: ::

            from functools import partial

            async def edit_and_keep_party():
                party = client.party
                await party.edit_and_keep(
                    partial(party.set_custom_key, 'myawesomekey'),
                    partial(party.set_playlist, 'Playlist_PlaygroundV2')
                )

        Parameters
        ----------
        *coros: :class:`functools.partial`
            A list of coroutines that should be included in the edit. Unlike
            :meth:`ClientParty.edit()`, this method only takes
            coroutines in the form of a :class:`functools.partial`.

        Raises
        ------
        HTTPException
            Something went wrong while editing.
        """  # noqa
        await super().edit_and_keep(*coros)

    def construct_squad_assignments(self,
                                    assignments: Optional[Dict[PartyMember, SquadAssignment]] = None,  # noqa
                                    new_positions: Optional[Dict[str, int]] = None  # noqa
                                    ) -> Dict[PartyMember, SquadAssignment]:
        existing = self._squad_assignments

        results = {}
        already_assigned = set()

        positions = self._default_config.position_priorities.copy()
        reassign = self._default_config.reassign_positions_on_size_change
        default_assignment = self._default_config.default_squad_assignment

        def assign(member, assignment=None, position=True):
            if assignment is None:
                assignment = SquadAssignment.copy(default_assignment)
                position = True

            if str(position) not in ('True', 'False'):
                assignment.position = position
                positions.remove(position)
            elif position:
                assignment.position = positions.pop(0)
            else:
                try:
                    positions.remove(assignment.position)
                except ValueError:
                    pass

            results[member] = assignment
            already_assigned.add(member.id)

        if new_positions is not None:
            for user_id, position in new_positions.items():
                member = self.get_member(user_id)
                if member is None:
                    continue

                assignment = existing.get(member)
                assign(member, assignment, position=position)

        if assignments is not None:
            for m, assignment in assignments.items():
                if assignment.position is not None:
                    try:
                        positions.remove(assignment.position)
                    except ValueError:
                        raise ValueError('Duplicate positions set.')
                    else:
                        assign(m, assignment, position=False)
                else:
                    assign(m, assignment)

        for member in self._members.values():
            if member.id in already_assigned:
                continue

            assignment = existing.get(member)
            should_reassign = reassign
            if assignment and assignment.position not in positions:
                should_reassign = True

            assign(member, assignment, position=should_reassign)

        results = OrderedDict(
            sorted(results.items(), key=lambda o: o[1].position)
        )

        self._squad_assignments = results
        return results

    def _convert_squad_assignments(self, assignments):
        results = []
        for member, assignment in assignments.items():
            if assignment.hidden:
                continue

            results.append({
                'memberId': member.id,
                'absoluteMemberIdx': assignment.position,
            })

        return results

    def _construct_raw_squad_assignments(self,
                                         assignments: Dict[PartyMember, SquadAssignment] = None,  # noqa
                                         new_positions: Dict[str, int] = None,
                                         ) -> Dict[str, Any]:
        ret = self.construct_squad_assignments(
            assignments=assignments,
            new_positions=new_positions,
        )
        raw = self._convert_squad_assignments(ret)
        prop = self.meta.set_squad_assignments(raw)
        return prop

    async def refresh_squad_assignments(self,
                                        assignments: Dict[PartyMember, SquadAssignment] = None,  # noqa
                                        new_positions: Dict[str, int] = None,
                                        could_be_edit: bool = False) -> None:
        prop = self._construct_raw_squad_assignments(
            assignments=assignments,
            new_positions=new_positions,
        )

        check = not self.edit_lock.locked() if could_be_edit else True
        if check:
            return await self.patch(updated=prop)

    async def set_squad_assignments(self, assignments: Dict[PartyMember, SquadAssignment]) -> None:  # noqa
        """|coro|

        Sets squad assignments for members of the party.

        Parameters
        ----------
        assignments: Dict[:class:`PartyMember`, :class:`SquadAssignment`]
            Pre-defined assignments to set. If a member is missing from this
            dict, they will be automatically added to the final request.

            Example: ::

                {
                    member1: fortnitepy.SquadAssignment(position=5),
                    member2: fortnitepy.SquadAssignment(hidden=True)
                }

        Raises
        ------
        ValueError
            Duplicate positions were set in the assignments.
        Forbidden
            You are not the leader of the party.
        HTTPException
            An error occured while requesting.
        """
        if self.me is not None and not self.me.leader:
            raise Forbidden('You have to be leader for this action to work.')

        return await self.refresh_squad_assignments(assignments=assignments)

    async def _invite(self, friend: Friend) -> None:
        if friend.id in self._members:
            raise PartyError('User is already in you party.')

        if len(self._members) == self.max_size:
            raise PartyError('Party is full')

        await self.client.http.party_send_invite(self.id, friend.id)

        invite = SentPartyInvitation(
            self.client,
            self,
            self.me,
            self.client.store_user(friend.get_raw()),
            {'sent_at': datetime.datetime.utcnow()}
        )
        return invite

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

        Returns
        -------
        :class:`SentPartyInvitation`
            Object representing the sent party invitation.
        """
        if self.client.is_creating_party():
            return

        friend = self.client.get_friend(user_id)
        if friend is None:
            raise Forbidden('Invited user is not friends with the client')

        return await self._invite(friend)

    async def fetch_invites(self) -> List['SentPartyInvitation']:
        """|coro|

        Fetches all active invitations sent from the party.

        .. warning::

            Because of an error on fortnite's end, this method only returns
            invites sent from other party members if the party is private.
            However it will always return invites sent from the client
            regardless of party privacy.

        Raises
        ------
        HTTPException
            An error occured while requesting from fortnite's services.

        Returns
        -------
        List[:class:`SentPartyInvitation`]
            A list of all sent invites from the party.
        """
        if self.client.is_creating_party():
            return []

        data = await self.client.http.party_lookup(self.id)

        user_ids = [r['sent_to'] for r in data['invites']]
        users = await self.client.fetch_users(user_ids, cache=True)

        invites = []
        for i, raw in enumerate(data['invites']):
            invites.append(SentPartyInvitation(
                self.client,
                self,
                self._members[raw['sent_by']],
                users[i],
                raw
            ))

        return invites

    async def _leave(self, *,
                     ignore_not_found: bool = True,
                     priority: int = 0) -> None:
        me = self.me
        if me is not None:
            me._cancel_clear_emote()

        await self.client.xmpp.leave_muc()

        try:
            await self.client.http.party_leave(
                self.id,
                priority=priority
            )
        except HTTPException as e:
            m = 'errors.com.epicgames.social.party.party_not_found'
            if ignore_not_found and e.message_code == m:
                return
            raise

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
        if self.me is not None and not self.me.leader:
            raise Forbidden('You have to be leader for this action to work.')

        if not isinstance(privacy, dict):
            privacy = privacy.value

        updated, deleted, config = self.meta.set_privacy(privacy)
        if not self.edit_lock.locked():
            return await self.patch(
                updated=updated,
                deleted=deleted,
                config=config,
            )

    async def set_playlist(self, playlist: Optional[str] = None,
                           tournament: Optional[str] = None,
                           event_window: Optional[str] = None) -> None:
        """|coro|

        Sets the current playlist of the party.

        Sets the playlist to Duos: ::

            await party.set_playlist(
                playlist='Playlist_DefaultDuo'
            )

        Sets the playlist to Arena Trios (Replace ``Trios`` with ``Solo``
        for arena solo): ::

            await party.set_playlist(
                playlist='Playlist_ShowdownAlt_Trios',
                tournament='epicgames_Arena_S13_Trios',
                event_window='Arena_S13_Division1_Trios'
            )

        Parameters
        ----------
        playlist: Optional[:class:`str`]
            The name of the playlist.
        tournament: Optional[:class:`str`]
            The tournament id.
        event_window: Optional[:class:`str`]
            The event window id.

        Raises
        ------
        Forbidden
            The client is not the leader of the party.
        """
        if self.me is not None and not self.me.leader:
            raise Forbidden('You have to be leader for this action to work.')

        prop = self.meta.set_playlist(
            playlist=playlist,
            tournament=tournament,
            event_window=event_window
        )
        if not self.edit_lock.locked():
            return await self.patch(updated=prop)

    async def set_region(self, region: Region) -> None:
        """|coro|

        Sets the region of the party.

        Parameters
        ----------
        region: :class:`Region`
            The region to set.

        Raises
        ------
        Forbidden
            The client is not the leader of the party.
        """

        if self.me is not None and not self.me.leader:
            raise Forbidden('You have to be leader for this action to work.')

        prop = self.meta.set_region(
            region=region
        )
        if not self.edit_lock.locked():
            return await self.patch(updated=prop)

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
        if self.me is not None and not self.me.leader:
            raise Forbidden('You have to be leader for this action to work.')

        prop = self.meta.set_custom_key(
            key=key
        )
        if not self.edit_lock.locked():
            return await self.patch(updated=prop)

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
        if self.me is not None and not self.me.leader:
            raise Forbidden('You have to be leader for this action to work.')

        prop = self.meta.set_fill(val=value)
        if not self.edit_lock.locked():
            return await self.patch(updated=prop)

    async def set_max_size(self, size: int) -> None:
        """|coro|

        Sets a new max size of the party.

        Parameters
        ----------
        size: :class:`int`
            The size to set. Must be more than the current member count,
            more than or equal to 1 or less than or equal to 16.

        Raises
        ------
        Forbidden
            The client is not the leader of the party.
        PartyError
            The new size was lower than the current member count.
        PartyError
            The new size was not <= 1 and <= 16.
        """
        if self.me is not None and not self.me.leader:
            raise Forbidden('You have to be leader for this action to work.')

        if size < self.member_count:
            raise PartyError('New size is lower than current member count.')

        if not 1 <= size <= 16:
            raise PartyError('The new party size must be 1 <= size <= 16.')

        config = {
            'max_size': size
        }

        if not self.edit_lock.locked():
            return await self.patch(config=config)
        else:
            self._config_cache.update(config)


class ReceivedPartyInvitation:
    """Represents a received party invitation.

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

    __slots__ = ('client', 'party', 'net_cl', 'sender', 'created_at')

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
        return ('<ReceivedPartyInvitation party={0.party!r} '
                'sender={0.sender!r} '
                'created_at={0.created_at!r}>'.format(self))

    def __eq__(self, other):
        return (isinstance(other, ReceivedPartyInvitation)
                and other.sender == self.sender.id)

    def __ne__(self, other):
        return not self.__eq__(other)

    async def accept(self) -> ClientParty:
        """|coro|

        Accepts the invitation and joins the party.

        .. warning::

            A bug within the fortnite services makes it not possible to join a
            private party you have been kicked from.

        Raises
        ------
        Forbidden
            You attempted to join a private party you've been kicked from.
        HTTPException
            Something went wrong when accepting the invitation.

        Returns
        -------
        :class:`ClientParty`
            The party the client joined by accepting the invitation.
        """
        if self.net_cl != self.client.net_cl and self.client.net_cl != '':
            raise PartyError('Incompatible net_cl')

        party = await self.client.join_party(self.party.id)
        asyncio.ensure_future(
            self.client.http.party_delete_ping(self.sender.id)
        )
        return party

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


class SentPartyInvitation:
    """Represents a sent party invitation.

    Attributes
    ----------
    client: :class:`Client`
        The client.
    party: :class:`Party`
        The party the invitation belongs to.
    sender: :class:`PartyMember`
        The party member that sent the invite.
    receiver: :class:`User`
        The user that the invite was sent to.
    created_at: :class:`datetime.datetime`
        The UTC time this invite was created at.
    """

    __slots__ = ('client', 'party', 'sender', 'receiver', 'created_at')

    def __init__(self, client: 'Client',
                 party: Party,
                 sender: PartyMember,
                 receiver: User,
                 data: dict) -> None:
        self.client = client
        self.party = party

        self.sender = sender
        self.receiver = receiver
        self.created_at = self.client.from_iso(data['sent_at'])

    def __repr__(self) -> str:
        return ('<SentPartyInvitation party={0.party!r} sender={0.sender!r} '
                'created_at={0.created_at!r}>'.format(self))

    def __eq__(self, other):
        return (isinstance(other, SentPartyInvitation)
                and other.sender.id == self.sender.id)

    def __ne__(self, other):
        return not self.__eq__(other)

    async def cancel(self) -> None:
        """|coro|

        Cancels the invite. The user will see an error message saying something
        like ``<users>'s party is private.``

        Raises
        ------
        Forbidden
            Attempted to cancel an invite not sent by the client.
        HTTPException
            Something went wrong while requesting to cancel the invite.
        """
        if self.client.is_creating_party():
            return

        if self.sender.id != self.party.me.id:
            raise Forbidden('You can only cancel invites sent by the client.')

        await self.client.http.party_delete_invite(
            self.party.id,
            self.receiver.id
        )

    async def resend(self) -> None:
        """|coro|

        Resends an invite with a new notification popping up for the receiving
        user.

        Raises
        ------
        Forbidden
            Attempted to resend an invite not sent by the client.
        HTTPException
            Something went wrong while requesting to resend the invite.
        """
        if self.client.is_creating_party():
            return

        if self.sender.id == self.party.me.id:
            raise Forbidden('You can only resend invites sent by the client.')

        await self.client.http.party_send_ping(
            self.receiver.id
        )


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

    def __eq__(self, other):
        return (isinstance(other, PartyJoinConfirmation)
                and other.user.id == self.user.id)

    def __ne__(self, other):
        return not self.__eq__(other)

    async def confirm(self) -> None:
        """|coro|

        Confirms this user.

        .. note::

            This call does not guarantee that the player will end up in the
            clients party. Please always listen to
            :func:`event_party_member_join()` to ensure that the player in fact
            joined.

        Raises
        ------
        HTTPException
            Something went wrong when confirming this user.
        """
        if self.client.is_creating_party():
            return

        try:
            await self.client.http.party_member_confirm(
                self.party.id,
                self.user.id,
            )
        except HTTPException as exc:
            m = 'errors.com.epicgames.social.party.applicant_not_found'
            if exc.message_code == m:
                return

            raise

    async def reject(self) -> None:
        """|coro|

        Rejects this user.

        Raises
        ------
        HTTPException
            Something went wrong when rejecting this user.
        """
        if self.client.is_creating_party():
            return

        try:
            await self.client.http.party_member_reject(
                self.party.id,
                self.user.id,
            )
        except HTTPException as exc:
            m = 'errors.com.epicgames.social.party.applicant_not_found'
            if exc.message_code == m:
                return

            raise


class PartyJoinRequest:
    """Represents a party join request. These requests are in most cases
    only received when the bots party privacy is set to private.

    .. info::

        There is currently no way to reject a join request. The official
        fortnite client does this by simply ignoring the request and waiting
        for it to expire.

    Attributes
    ----------
    client: :class:`Client`
        The client.
    party: :class:`ClientParty`
        The party the user wants to join.
    friend: :class:`Friend`
        The friend who requested to join the party.
    created_at: :class:`datetime.datetime`
        The UTC timestamp of when this join request was created.
    expires_at: :class:`datetime.datetime`
        The UTC timestamp of when this join request will expire. This
        should always be one minute after its creation.
    """

    __slots__ = ('client', 'party', 'friend', 'created_at', 'expires_at')

    def __init__(self, client: 'Client',
                 party: ClientParty,
                 friend: User,
                 data: dict) -> None:
        self.client = client
        self.party = party
        self.friend = friend
        self.created_at = self.client.from_iso(data['sent_at'])
        self.expires_at = self.client.from_iso(data['expires_at'])

    async def accept(self):
        """|coro|

        Accepts a party join request. Accepting this before the request
        has expired forces the sender to join the party. If not then the
        sender will receive a regular party invite.

        Raises
        ------
        PartyError
            User is already in your party.
        PartyError
            The party is full.
        HTTPException
            An error occured while requesting.
        """
        return await self.party.invite(self.friend.id)
