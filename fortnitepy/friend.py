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

from typing import TYPE_CHECKING, List, Optional
from aioxmpp import JID

from .user import UserBase, ExternalAuth
from .errors import FriendOffline, InvalidOffer, PartyError, Forbidden, HTTPException
from .presence import Presence
from .enums import Platform

if TYPE_CHECKING:
    from .client import Client
    from .party import ClientParty


class FriendBase(UserBase):

    __slots__ = UserBase.__slots__ + \
                ('_status', '_direction', '_favorite', '_created_at')

    def __init__(self, client: 'Client', data: dict) -> None:
        super().__init__(client, data)

    def _update(self, data: dict) -> None:
        super()._update(data)
        self._status = data['status']
        self._direction = data['direction']
        self._created_at = self.client.from_iso(data['created'])

    @property
    def status(self) -> str:
        """:class:`str`: The friends status to the client. E.g. if the friend
        is friends with the bot it will be ``ACCEPTED``.

        .. warning::

            This is not the same as status from presence!

        """
        return self._status

    @property
    def incoming(self) -> bool:
        """:class:`bool`: ``True`` if this friend was the one to send the
        friend request else ``False`. Aliased to ``inbound`` as well.
        """
        return self._direction == 'INBOUND'

    inbound = incoming

    @property
    def outgoing(self) -> bool:
        """:class:`bool`: ``True`` if the bot was the one to send the friend
        request else ``False``. Aliased to ``outbound`` as well.
        """
        return self._direction == 'OUTBOUND'

    outbound = outgoing

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: The UTC time of when the friendship was
        created.
        """
        return self._created_at

    async def block(self) -> None:
        """|coro|

        Blocks this friend.

        Raises
        ------
        HTTPException
            Something went wrong when trying to block this user.
        """
        await self.client.block_user(self.id)

    def get_raw(self) -> dict:
        return {
            **(super().get_raw()),
            'status': self._status,
            'direction': self._direction,
            'created': self._created_at
        }


class Friend(FriendBase):
    """Represents a friend on Fortnite"""

    __slots__ = FriendBase.__slots__ + ('_nickname', '_note', '_last_logout')

    def __init__(self, client: 'Client', data: dict) -> None:
        super().__init__(client, data)
        self._last_logout = None
        self._nickname = None
        self._note = None

    def __repr__(self) -> str:
        return ('<Friend id={0.id!r} display_name={0.display_name!r} '
                'epicgames_account={0.epicgames_account!r}>'.format(self))

    def _update(self, data: dict) -> None:
        super()._update(data)
        self._favorite = data.get('favorite')

    def _update_last_logout(self, dt: datetime.datetime) -> None:
        self._last_logout = dt

    def _update_summary(self, data: dict) -> None:
        _alias = data['alias']
        self._nickname = _alias if _alias != '' else None

        _note = data['note']
        self._note = _note if _note != '' else None

    @property
    def favorite(self) -> bool:
        """:class:`bool`: ``True`` if the friend is favorited by :class:`ClientUser`
        else ``False``.
        """
        return self._favorite

    @property
    def nickname(self) -> Optional[str]:
        """:class:`str`: The friend's nickname. ``None`` if no nickname is set
        for this friend.
        """
        return self._nickname

    @property
    def note(self) -> Optional[str]:
        """:class:`str`: The friend's note. ``None`` if no note is set."""
        return self._note

    @property
    def last_presence(self) -> Presence:
        """:class:`Presence`: The last presence retrieved by the
        friend. Might be ``None`` if no presence has been
        received by this friend yet.
        """
        return self.client.get_presence(self.id)

    @property
    def last_logout(self) -> Optional[datetime.datetime]:
        """:class:`datetime.datetime`: The UTC time of the last time this
        friend logged off.
        ``None`` if this friend has never logged into fortnite or because
        the friend was added after the client was started. If the latter is the
        case, you can fetch the friends last logout with
        :meth:`Friend.fetch_last_logout()`.
        """
        return self._last_logout

    @property
    def platform(self) -> Optional[Platform]:
        """:class:`Platform`: The platform the friend is currently online on.
        ``None`` if the friend is offline.
        """
        pres = self.last_presence
        if pres is not None:
            return pres.platform

    def is_online(self) -> bool:
        """Method to check if a user is currently online.

        .. warning::

            This method uses the last received presence from this user to
            determine if the friend is online or not. Therefore, this method
            will most likely not return True when calling it in
            :func:`event_friend_add()`. You could use :meth:`Client.wait_for()`
            to wait for the presence to be received but remember that if the
            friend is infact offline, no presence will be received. You can add
            a timeout the method to make sure it won't wait forever.

        Returns
        -------
        :class:`bool`
            ``True`` if the friend is currently online else ``False``.
        """
        pres = self.last_presence
        if pres is None:
            return False
        return pres.available

    def _online_check(self, available):
        def check(b, a):
            if a.friend.id != self.id:
                return False
            return a.available is available
        return check

    async def wait_until_online(self) -> None:
        """|coro|

        Waits until this friend comes online. Returns instantly if already
        online.
        """
        pres = self.last_presence
        if pres is None or pres.available is False:
            pres = await self.client.wait_for(
                'friend_presence',
                check=self._online_check(available=True)
            )

    async def wait_until_offline(self) -> None:
        """|coro|

        Waits until this friend goes offline. Returns instantly if already
        offline.
        """
        pres = self.last_presence
        if pres is not None and pres.available is not False:
            pres = await self.client.wait_for(
                'friend_presence',
                check=self._online_check(available=False)
            )

    async def fetch_last_logout(self) -> Optional[datetime.datetime]:
        """|coro|

        Fetches the last time this friend logged out.

        Raises
        ------
        HTTPException
            An error occured while requesting.

        Returns
        -------
        Optional[:class:`datetime.datetime`]
            The last UTC datetime of this friends last logout. Could be
            ``None`` if the friend has never logged into fortnite.
        """
        presences = await self.client.http.presence_get_last_online()
        presence = presences.get(self.id)
        if presence is not None:
            self._update_last_logout(
                self.client.from_iso(presence[0]['last_online'])
            )

        return self.last_logout

    async def fetch_mutual_friends(self) -> List['Friend']:
        """|coro|

        Fetches a list of friends you and this friend have in common.

        Raises
        ------
        HTTPException
            An error occured while requesting.

        Returns
        -------
        List[:class:`Friend`]
            A list of friends you and this friend have in common.
        """
        res = await self.client.http.friends_get_mutual(self.id)

        mutuals = []
        for user_id in res:
            friend = self.client.get_friend(user_id)
            if friend is not None:
                mutuals.append(friend)

        return mutuals

    async def set_nickname(self, nickname: str) -> None:
        """|coro|

        Sets the nickname of this friend.

        Parameters
        ----------
        nickname: :class:`str`
            | The nickname you want to set.
            | Min length: ``3``
            | Max length: ``16``

        Raises
        ------
        ValueError
            The nickname contains too few/many characters or contains invalid
            characters.
        HTTPException
            An error occured while requesting.
        """
        if not (3 <= len(nickname) <= 16):
            raise ValueError('Invalid nickname length')

        try:
            await self.client.http.friends_set_nickname(self.id, nickname)
        except HTTPException as e:
            ignored = ('errors.com.epicgames.common.unsupported_media_type',
                       'errors.com.epicgames.validation.validation_failed')
            if e.message_code in ignored:
                raise ValueError('Invalid nickname')
            raise
        self._nickname = nickname

    async def remove_nickname(self) -> None:
        """|coro|

        Removes the friend's nickname.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        await self.client.http.friends_remove_nickname(self.id)
        self._nickname = None

    async def set_note(self, note: str) -> None:
        """|coro|

        Pins a note to this friend.

        Parameters
        note: :class:`str`
            | The note you want to set.
            | Min length: ``3``
            | Max length: ``255``

        Raises
        ------
        ValueError
            The note contains too few/many characters or contains invalid
            characters.
        HTTPException
            An error occured while requesting.
        """
        if not (3 <= len(note) <= 255):
            raise ValueError('Invalid note length')

        try:
            await self.client.http.friends_set_note(self.id, note)
        except HTTPException as e:
            ignored = ('errors.com.epicgames.common.unsupported_media_type',
                       'errors.com.epicgames.validation.validation_failed')
            if e.message_code in ignored:
                raise ValueError('Invalid note')
            raise
        self._note = note

    async def remove_note(self) -> None:
        """|coro|

        Removes the friend's note.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        await self.client.http.friends_remove_note(self.id)
        self._note = None

    async def remove(self) -> None:
        """|coro|

        Removes the friend from your friendlist.

        Raises
        ------
        HTTPException
            Something went wrong when trying to remove this friend.
        """
        await self.client.remove_or_decline_friend(self.id)

    async def send(self, content: str) -> None:
        """|coro|

        Sends a :class:`FriendMessage` to this friend.

        Parameters
        ----------
        content: :class:`str`
            The content of the message.
        """
        await self.client.xmpp.send_friend_message(self.jid, content)

    async def join_party(self) -> 'ClientParty':
        """|coro|

        Attempts to join this friends' party.

        Raises
        ------
        PartyError
            Party was not found.
        Forbidden
            The party you attempted to join was private.
        HTTPException
            Something else went wrong when trying to join the party.

        Returns
        -------
        :class:`ClientParty`
            The clients new party.
        """
        _pre = self.last_presence
        if _pre is None:
            raise PartyError('Could not join party. Reason: Party not found')

        if _pre.party.private:
            raise Forbidden('Could not join party. Reason: Party is private')

        return await _pre.party.join()

    async def invite(self) -> None:
        """|coro|

        Invites this friend to your party.

        Raises
        ------
        PartyError
            Friend is already in your party.
        PartyError
            The party is full.
        HTTPException
            Something went wrong when trying to invite this friend.

        Returns
        -------
        :class:`SentPartyInvitation`
            Object representing the sent party invitation.
        """
        return await self.client.party.invite(self.id)

    async def request_to_join(self) -> None:
        """|coro|

        Sends a request to join a friends party. This is mainly used for
        requesting to join private parties specifically, but it can be used
        for all types of party privacies.

        Raises
        ------
        PartyError
            You are already a part of this friends party.
        FriendOffline
            The friend you requested to join is offline.
        HTTPException
            An error occured while requesting.
        """
        try:
            await self.client.http.party_send_intention(self.id)
        except HTTPException as exc:
            m = 'errors.com.epicgames.social.party.user_already_in_party'
            if exc.message_code == m:
                raise PartyError(
                    'The bot is already a part of this friends party.'
                )

            m = 'errors.com.epicgames.social.party.user_has_no_party'
            if exc.message_code == m:
                raise FriendOffline(
                    'The friend you requested to join is offline.'
                )

            raise

    async def owns_offer(self, offer_id: str) -> bool:
        """|coro|

        Checks if a friend owns a currently active offer in the item shop.

        Raises
        ------
        InvalidOffer
            An invalid/outdated offer_id was passed. Only offers currently in
            the item shop are valid.
        HTTPException
            An error occured while requesting.

        Returns
        -------
        :class:`bool`
            Whether or not the friend owns the offer.
        """
        try:
            data = await self.client.http.fortnite_check_gift_eligibility(
                self.id,
                offer_id,
            )
        except HTTPException as exc:
            m = 'errors.com.epicgames.modules.gamesubcatalog.purchase_not_allowed'  # noqa
            if exc.message_code == m:
                return True

            m = 'errors.com.epicgames.modules.gamesubcatalog.catalog_out_of_date'  # noqa
            if exc.message_code == m:
                raise InvalidOffer('The offer_id passed is not valid.')

            raise

        return False


class PendingFriendBase(FriendBase):
    """Represents a pending friend from Fortnite."""

    __slots__ = FriendBase.__slots__

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: The UTC time of when the request was
        created
        """
        return self._created_at


class IncomingPendingFriend(PendingFriendBase):
    """Represents an incoming pending friend. This means that the client
    received the friend request."""

    __slots__ = PendingFriendBase.__slots__

    def __repr__(self) -> str:
        return ('<IncomingPendingFriend id={0.id!r} '
                'display_name={0.display_name!r} '
                'epicgames_account={0.epicgames_account!r}>'.format(self))

    async def accept(self) -> Friend:
        """|coro|

        Accepts this users' friend request.

        Raises
        ------
        HTTPException
            Something went wrong when trying to accept this request.

        Returns
        -------
        :class:`Friend`
            Object of the friend you just added.
        """
        friend = await self.client.accept_friend(self.id)
        return friend

    async def decline(self) -> None:
        """|coro|

        Declines this users' friend request.

        Raises
        ------
        HTTPException
            Something went wrong when trying to decline this request.
        """
        await self.client.remove_or_decline_friend(self.id)


class OutgoingPendingFriend(PendingFriendBase):

    __slots__ = PendingFriendBase.__slots__

    def __repr__(self) -> str:
        return ('<OutgoingPendingFriend id={0.id!r} '
                'display_name={0.display_name!r} '
                'epicgames_account={0.epicgames_account!r}>'.format(self))

    async def cancel(self) -> None:
        """|coro|

        Cancel the friend request sent to this user. This method is also
        aliases to ``abort()``.

        Raises
        ------
        HTTPException
            Something went wrong when trying to cancel this request.
        """
        await self.client.remove_or_decline_friend(self.id)

    abort = cancel
