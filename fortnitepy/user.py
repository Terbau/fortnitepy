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

import logging

from aioxmpp import JID
from typing import TYPE_CHECKING, Any, List, Optional
from .enums import UserSearchPlatform, UserSearchMatchType, StatsCollectionType
from .typedefs import DatetimeOrTimestamp
from .errors import Forbidden

if TYPE_CHECKING:
    from .client import Client
    from .stats import StatsV2, StatsCollection

log = logging.getLogger(__name__)


class ExternalAuth:
    """Represents an external auth belonging to a user.

    Attributes
    ----------
    client: :class:`Client`
        The client.
    type: :class:`str`:
        The type/platform of the external auth.
    id: :class:`str`:
        The users universal fortnite id.
    external_id: Optional[:class:`str`]
        The id belonging to this user on the platform. This could in some
        cases be `None`.
    external_display_name: :class:`str`
        The display name belonging to this user on the platform. This could
        in some cases be `None`.
    extra_info: Dict[:class:`str`, Any]
        Extra info from the payload. Usually empty on accounts other
        than :class:`ClientUser`.
    """

    __slots__ = ('client', 'type', 'id', 'external_id',
                 'external_display_name', 'extra_info')

    def __init__(self, client: 'Client', data: dict) -> None:
        self.client = client
        self.type = data['type']
        self.id = data['accountId']

        if 'authIds' in data:
            self.external_id = data['authIds'][0]['id'] if data['authIds'] else None  # noqa
        else:
            self.external_id = data['externalAuthId']

        self.external_display_name = data.get('externalDisplayName')

    def _update_extra_info(self, data: dict) -> None:
        to_be_removed = ('type', 'accountId', 'externalAuthId',
                         'externalDisplayName')
        for field in to_be_removed:
            try:
                del data[field]
            except KeyError:
                pass

        self.extra_info = data

    def __str__(self) -> str:
        return self.external_display_name

    def __repr__(self) -> str:
        return ('<ExternalAuth type={0.type!r} id={0.id!r} '
                'external_display_name={0.external_display_name!r} '
                'external_id={0.external_id!r}>'.format(self))

    def __eq__(self, other):
        return isinstance(other, ExternalAuth) and other.id == self.id

    def __ne__(self, other):
        return not self.__eq__(other)

    def get_raw(self) -> dict:
        return {
            'type': self.type,
            'accountId': self.id,
            'externalAuthId': self.external_id,
            'externalDisplayName': self.external_display_name,
            **self.extra_info
        }


class UserBase:
    __slots__ = ('client', '_epicgames_display_name', '_external_display_name',
                 '_id', '_external_auths')

    def __init__(self, client: 'Client', data: dict, **kwargs: Any) -> None:
        self.client = client
        if data:
            self._update(data)

    def __hash__(self) -> int:
        return hash(self._id)

    def __str__(self) -> str:
        return self.display_name

    def __eq__(self, other):
        return isinstance(other, UserBase) and other._id == self._id

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def display_name(self) -> Optional[str]:
        """Optional[:class:`str`]: The users displayname

        .. warning::

            The display name will be the one registered to the epicgames
            account. If an epicgames account is not found it defaults
            to the display name of an external auth.

        .. warning::

            This property might be ``None`` if
            ``Client.fetch_user_data_in_events`` is set to ``False``.
        """
        return self._epicgames_display_name or self._external_display_name

    @property
    def id(self) -> str:
        """:class:`str`: The users id"""
        return self._id

    @property
    def external_auths(self) -> List[ExternalAuth]:
        """List[:class:`ExternalAuth`]: List containing information about
        external auths. Might be empty if the user does not have any external
        auths.
        """
        return self._external_auths

    @property
    def epicgames_account(self) -> bool:
        """:class:`bool`: Tells you if the user is an account registered to epicgames
        services. ``False`` if the user is from another platform without
        having linked their account to an epicgames account.

        .. warning::

            If this is True, the display name will be the one registered to
            the epicgames account, if not it defaults to the display name of
            an external auth.

        .. warning::

            This property might be ``False`` even though the account is a
            registered epic games account if
            ``Client.fetch_user_data_in_events`` is set to ``False``.
        """
        return self._epicgames_display_name is not None

    @property
    def jid(self) -> JID:
        """:class:`aioxmpp.JID`: The JID of the user."""
        return JID.fromstr('{0.id}@{0.client.service_host}'.format(self))

    async def fetch(self) -> None:
        """|coro|

        Fetches basic information about this user and sets the updated
        properties. This might be useful if you for example need to be
        sure the display name is updated or if you have
        ``Client.fetch_user_data_in_events`` set to ``False``.

        Raises
        ------
        HTTPException
            An error occurred while requesting.
        """
        result = await self.client.http.account_get_multiple_by_user_id(  # noqa
            (self.id,),
        )
        data = result[0]

        self._update(data)

    async def fetch_br_stats(self, *,
                             start_time: Optional[DatetimeOrTimestamp] = None,
                             end_time: Optional[DatetimeOrTimestamp] = None
                             ) -> 'StatsV2':
        """|coro|

        Fetches this users stats.

        Parameters
        ----------
        start_time: Optional[Union[:class:`int`, :class:`datetime.datetime`, :class:`SeasonStartTimestamp`]]
            The UTC start time of the time period to get stats from.
            *Must be seconds since epoch, :class:`datetime.datetime` or a constant from SeasonEndTimestamp*
            *Defaults to None*
        end_time: Optional[Union[:class:`int`, :class:`datetime.datetime`, :class:`SeasonEndTimestamp`]]
            The UTC end time of the time period to get stats from.
            *Must be seconds since epoch, :class:`datetime.datetime` or a constant from SeasonEndTimestamp*
            *Defaults to None*

        Raises
        ------
        Forbidden
            The user has chosen to be hidden from public stats by disabling
            the fortnite setting below.
            ``Settings`` -> ``Account and Privacy`` -> ``Show on career
            leaderboard``
        HTTPException
            An error occurred while requesting.

        Returns
        -------
        :class:`StatsV2`
            An object representing the stats for this user.
        """  # noqa
        return await self.client.fetch_br_stats(
            self.id,
            start_time=start_time,
            end_time=end_time
        )

    async def fetch_br_stats_collection(self, collection: StatsCollectionType,
                                        start_time: Optional[DatetimeOrTimestamp] = None,  # noqa
                                        end_time: Optional[DatetimeOrTimestamp] = None  # noqa)
                                        ) -> 'StatsCollection':
        """|coro|

        Fetches a stats collections for this user.

        Parameters
        ----------
        start_time: Optional[Union[:class:`int`, :class:`datetime.datetime`, :class:`SeasonStartTimestamp`]]
            The UTC start time of the time period to get stats from.
            *Must be seconds since epoch, :class:`datetime.datetime` or a constant from SeasonEndTimestamp*
            *Defaults to None*
        end_time: Optional[Union[:class:`int`, :class:`datetime.datetime`, :class:`SeasonEndTimestamp`]]
            The UTC end time of the time period to get stats from.
            *Must be seconds since epoch, :class:`datetime.datetime` or a constant from SeasonEndTimestamp*
            *Defaults to None*

        Raises
        ------
        Forbidden
            The user has chosen to be hidden from public stats by disabling
            the fortnite setting below.
            ``Settings`` -> ``Account and Privacy`` -> ``Show on career
            leaderboard``
        HTTPException
            An error occurred while requesting.

        Returns
        -------
        :class:`StatsCollection`
            An object representing the stats collection for this user.
        """  # noqa
        res = await self.client.fetch_multiple_br_stats_collections(
            user_ids=(self.id,),
            collection=collection,
            start_time=start_time,
            end_time=end_time,
        )

        if self.id not in res:
            raise Forbidden('User has opted out of public leaderboards.')

        return res[self.id]

    async def fetch_battlepass_level(self, *,
                                     season: int,
                                     start_time: Optional[DatetimeOrTimestamp] = None,  # noqa
                                     end_time: Optional[DatetimeOrTimestamp] = None  # noqa
                                     ) -> float:
        """|coro|

        Fetches this users battlepass level.

        Parameters
        ----------
        season: :class:`int`
            The season number to request the battlepass level for.
            
            .. warning::

                If you are requesting the previous season and the new season has not been
                added to the library yet (check :class:`SeasonStartTimestamp`), you have to
                manually include the previous seasons end timestamp in epoch seconds.
        start_time: Optional[Union[:class:`int`, :class:`datetime.datetime`, :class:`SeasonStartTimestamp`]]
            The UTC start time of the window to get the battlepass level from.
            *Must be seconds since epoch, :class:`datetime.datetime` or a constant from SeasonEndTimestamp*
            *Defaults to None*
        end_time: Optional[Union[:class:`int`, :class:`datetime.datetime`, :class:`SeasonEndTimestamp`]]
            The UTC end time of the window to get the battlepass level from.
            *Must be seconds since epoch, :class:`datetime.datetime` or a constant from SeasonEndTimestamp*
            *Defaults to None*

        Raises
        ------
        HTTPException
            An error occurred while requesting.

        Returns
        -------
        Optional[:class:`float`]
            The users battlepass level. ``None`` is returned if the user has
            not played any real matches this season.

            .. note::

                The decimals are the percent progress to the next level.
                E.g. ``208.63`` -> ``Level 208 and 63% on the way to 209.``
        """  # noqa
        return await self.client.fetch_battlepass_level(
            self.id,
            season=season,
            start_time=start_time,
            end_time=end_time
        )

    def _update(self, data: dict) -> None:
        self._epicgames_display_name = data.get('displayName',
                                                data.get('account_dn'))
        self._update_external_auths(
            data.get('externalAuths', data.get('external_auths', [])),
            extra_external_auths=data.get('extraExternalAuths', []),
        )

        self._id = data.get('id', data.get('accountId', data.get('account_id')))  # noqa

    def _update_external_auths(self, external_auths: List[dict], *,
                               extra_external_auths: Optional[List[dict]] = None  # noqa
                               ) -> None:
        extra_external_auths = extra_external_auths or []
        extra_ext = {v['authIds'][0]['type'].split('_')[0].lower(): v
                     for v in extra_external_auths}

        ext_list = []
        iterator = external_auths.values() if isinstance(external_auths, dict) else external_auths  # noqa
        for e in iterator:
            ext = ExternalAuth(self.client, e)
            ext._update_extra_info(extra_ext.get(ext.type, {}))
            ext_list.append(ext)

        self._external_display_name = None
        for ext_auth in reversed([x for x in ext_list
                                  if x.type.lower() not in ('twitch',)]):
            self._external_display_name = ext_auth.external_display_name
            break

        self._external_auths = ext_list

    def _update_epicgames_display_name(self, display_name: str) -> None:
        self._epicgames_display_name = display_name

    def get_raw(self) -> dict:
        return {
            'displayName': self.display_name,
            'id': self.id,
            'externalAuths': [ext.get_raw() for ext in self._external_auths]
        }


class ClientUser(UserBase):
    """Represents the user the client is connected to.

    Attributes
    ----------
    client: :class:`Client`
        The client.
    age_group: :class:`str`
        The age group of the user.
    can_update_display_name: :class:`bool`
        ``True`` if the user can update it's displayname else ``False``
    country: :class:`str`
        The country the user wasregistered in.
    email: :class:`str`
        The email of the user.
    failed_login_attempts: :class:`str`
        Failed login attempts
    headless: :class:`bool`
        ``True`` if the account has no display name due to no epicgames
        account being linked to the current account.
    last_login: :class:`datetime.datetime`
        UTC time of the last login of the user. ``None`` if no failed login
        attempt has been registered.
    name: :class:`str`
        First name of the user.
    first_name: :class:`str`
        First name of the user. Alias for name.
    last_name: :class:`str`
        Last name of the user.
    full_name: :class:`str`
        Full name of the user.
    number_of_display_name_changes: :class:`int`
        Amount of displayname changes.
    preferred_language: :class:`str`
        Users preferred language.
    tfa_enabled: :class:`bool`
        ``True`` if the user has two-factor authentication enabled else
        ``False``.
    email_verified: :class:`bool`
        ``True`` if the accounts email has been verified.
    minor_verified: :class:`bool`
        ``True`` if the account has been verified to be run by a minor.
    minor_expected: :class:`bool`
        ``True`` if the account is expected to be run by a minor.
    minor_status: :class:`str`
        The minor status of this account.
    """

    def __init__(self, client: 'Client', data: dict, **kwargs: Any) -> None:
        super().__init__(client, data)
        self._update(data)

    def __repr__(self) -> str:
        return ('<ClientUser id={0.id!r} display_name={0.display_name!r} '
                'jid={0.jid!r} email={0.email!r}>'.format(self))

    @property
    def first_name(self) -> str:
        return self.name

    @property
    def full_name(self) -> str:
        return '{} {}'.format(self.name, self.last_name)

    @property
    def jid(self) -> JID:
        """:class:`aioxmpp.JID`: The JID of the client. Includes the
        resource part.
        """
        return self.client.xmpp.xmpp_client.local_jid

    def _update(self, data: dict) -> None:
        super()._update(data)
        self.name = data['name']
        self.email = data['email']
        self.failed_login_attempts = data['failedLoginAttempts']
        self.last_failed_login = (self.client.from_iso(data['lastFailedLogin'])
                                  if 'lastFailedLogin' in data else None)
        self.last_login = (self.client.from_iso(data['lastLogin'])
                           if 'lastLogin' in data else None)

        n_changes = data['numberOfDisplayNameChanges']
        self.number_of_display_name_changes = n_changes
        self.age_group = data['ageGroup']
        self.headless = data['headless']
        self.country = data['country']
        self.last_name = data['lastName']
        self.preferred_language = data['preferredLanguage']
        self.can_update_display_name = data['canUpdateDisplayName']
        self.tfa_enabled = data['tfaEnabled']
        self.email_verified = data['emailVerified']
        self.minor_verified = data['minorVerified']
        self.minor_expected = data['minorExpected']
        self.minor_status = data['minorStatus']


class User(UserBase):
    """Represents a user from Fortnite"""

    __slots__ = UserBase.__slots__

    def __init__(self, client: 'Client', data: dict, **kwargs: Any) -> None:
        super().__init__(client, data)

    def __repr__(self) -> str:
        return ('<User id={0.id!r} display_name={0.display_name!r} '
                'epicgames_account={0.epicgames_account!r}>'.format(self))

    async def block(self) -> None:
        """|coro|

        Blocks this user.

        Raises
        ------
        HTTPException
            Something went wrong while blocking this user.
        """
        await self.client.block_user(self.id)

    async def add(self) -> None:
        """|coro|

        Sends a friendship request to this user or adds them if they
        have already sent one to the client.

        Raises
        ------
        NotFound
            The specified user does not exist.
        DuplicateFriendship
            The client is already friends with this user.
        FriendshipRequestAlreadySent
            The client has already sent a friendship request that has not been
            handled yet by the user.
        MaxFriendshipsExceeded
            The client has hit the max amount of friendships a user can
            have at a time. For most accounts this limit is set to ``1000``
            but it could be higher for others.
        InviteeMaxFriendshipsExceeded
            The user you attempted to add has hit the max amount of friendships
            a user can have at a time.
        InviteeMaxFriendshipRequestsExceeded
            The user you attempted to add has hit the max amount of friendship
            requests a user can have at a time. This is usually ``700`` total
            requests.
        Forbidden
            The client is not allowed to send friendship requests to the user
            because of the users settings.
        HTTPException
            An error occurred while requesting to add this friend.
        """
        await self.client.add_friend(self.id)


class BlockedUser(UserBase):
    """Represents a blocked user from Fortnite"""

    __slots__ = UserBase.__slots__

    def __init__(self, client: 'Client', data: dict) -> None:
        super().__init__(client, data)

    def __repr__(self) -> str:
        return ('<BlockedUser id={0.id!r} '
                'display_name={0.display_name!r} '
                'epicgames_account={0.epicgames_account!r}>'.format(self))

    async def unblock(self) -> None:
        """|coro|

        Unblocks this friend.
        """
        await self.client.unblock_user(self.id)


class UserSearchEntry(User):
    """Represents a user entry in a user search.

    Parameters
    ----------
    matches: List[Tuple[:class:`str`, :class:`UserSearchPlatform`]]
        | A list of tuples containing the display name the user matched
        and the platform the display name is from.
        | Example: ``[('Tfue', UserSearchPlatform.EPIC_GAMES)]``
    match_type: :class:`UserSearchMatchType`
        The type of match this user matched by.
    mutual_friend_count: :class:`int`
        The amount of **epic** mutual friends the client has with the user.
    """
    def __init__(self, client: 'Client',
                 user_data: dict,
                 search_data: dict) -> None:
        super().__init__(client, user_data)

        self.matches = [(d['value'], UserSearchPlatform(d['platform']))
                        for d in search_data['matches']]
        self.match_type = UserSearchMatchType(search_data['matchType'])
        self.mutual_friend_count = search_data['epicMutuals']

    def __str__(self) -> str:
        return self.matches[0][0]

    def __repr__(self) -> str:
        return ('<UserSearchEntry id={0.id!r} '
                'display_name={0.display_name!r} '
                'epicgames_account={0.epicgames_account!r}>'.format(self))


class SacSearchEntryUser(User):
    """Represents a user entry in a support a creator code search.

    Parameters
    ----------
    slug: :class:`str`
        The slug (creator code) that matched.
    active: :class:`bool`
        Whether or not the creator code is active or not.
    verified: :class:`bool`
        Whether or not the creator code is verified or not.
    """
    def __init__(self, client: 'Client',
                 user_data: dict,
                 search_data: dict) -> None:
        super().__init__(client, user_data)

        self.slug = search_data['slug']
        self.active = search_data['status'] == 'ACTIVE'
        self.verified = search_data['verified']

    def __repr__(self) -> str:
        return ('<SacSearchEntryUser slug={0.slug!r} '
                'id={0.id!r} '
                'display_name={0.display_name!r} '
                'epicgames_account={0.epicgames_account!r}>'.format(self))
