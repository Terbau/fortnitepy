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

from .user import UserBase
from .errors import PartyError, Forbidden, HTTPException


class FriendBase(UserBase):

    __slots__ = UserBase.__slots__ + \
                ('_status', '_direction', '_favorite', '_created_at')

    def __init__(self, client, data):
        super().__init__(client, data)
        self._update(data)
        
    def _update(self, data):
        super()._update(data)
        self._status = data['status']
        self._direction = data['direction']
        self._favorite = str(data['favorite']).lower() == 'true'
        self._created_at = self.client.from_iso(data['created'])

    @property
    def display_name(self):
        """:class:`str`: The friend's displayname"""
        return self._display_name
    
    @property
    def id(self):
        """:class:`str`: The friend's id"""
        return self._id
    
    @property
    def external_auths(self):
        """:class:`list`: List containing information about external auths.
        Might be empty if the friend does not have any external auths"""
        return self._external_auths

    @property
    def jid(self):
        """:class:`aioxmpp.JID`: The jid of the friend."""
        return super().jid

    @property
    def status(self):
        """:class:`str`: The friends status to the client. E.g. if the friend
        is friends with the bot it will be ``ACCEPTED``.
        
        .. warning::
        
            This is not the same as status from presence!
        
        """
        return self._status
    
    @property
    def direction(self):
        """:class:`str`: The direction of the friendship. ``INBOUND`` if the friend 
        added :class:`ClientUser` else ``OUTGOING``.
        """
        return self._direction

    @property
    def inbound(self):
        """:class:`bool`: ``True`` if this friend was the one to send the friend request else ``False``."""
        return self._direction == 'INBOUND'

    @property
    def outgoing(self):
        """:class:`bool`: ``True`` if the bot was the one to send the friend request else ``False``."""
        return self._direction == 'OUTGOING'

    @property
    def favorite(self):
        """:class:`bool`: ``True`` if the friend is favorited by :class:`ClientUser`
        else ``False``.
        """
        return self._favorite

    @property
    def created_at(self):
        """:class:`datetime.datetime`: The UTC time of when the friendship was created."""
        return self._created_at

    async def block(self):
        """|coro|
        
        Blocks this friend.

        Raises
        ------
        HTTPException
            Something went wrong when trying to block this user.
        """
        await self.client.http.friends_block(self.id)

    def get_raw(self):
        return {
            **(super().get_raw()),
            'status': self.status,
            'direction': self.direction,
            'favorite': self.favorite,
            'created': self.created_at
        }


class Friend(FriendBase):
    """Represents a friend on Fortnite"""

    __slots__ = FriendBase.__slots__ + ('_nickname', '_note', '_last_logout')

    def __init__(self, client, data):
        super().__init__(client, data)
        self._last_logout = None

    def _update(self, data):
        super()._update(data)
        self._nickname = data.get('alias')
        self._note = data.get('note')
        self._favorite = data.get('favorite')

    def _update_last_logout(self, dt):
        self._last_logout = dt

    @property
    def display_name(self):
        """:class:`str`: The friends displayname"""
        return self._display_name
    
    @property
    def id(self):
        """:class:`str`: The friends id"""
        return self._id
    
    @property
    def nickname(self):
        """:class:`str`: The friend's nickname. ``None`` if no nickname is set for this friend."""
        return self._nickname

    @property
    def note(self):
        """:class:`str`: The friend's note. ``None`` if no note is set."""
        return self._note
    
    @property
    def external_auths(self):
        """:class:`list`: List containing information about external auths.
        Might be empty if the friend does not have any external auths
        """
        return self._external_auths

    @property
    def last_presence(self):
        """:class:`Presence`: The last presence retrieved by the
        friend. Might be ``None`` if no presence has been 
        received by this friend yet.
        """
        return self.client.get_presence(self.id)

    @property
    def last_logout(self):
        """:class:`datetime.datetime`: The UTC time of the last time this friend logged off."""
        return self._last_logout

    def is_online(self):
        """Method to check if a user is currently online.
        
        Returns
        -------
        :class:`bool`
            ``True`` if the friend is currently online else ``False``.
        """
        pres = self.client.get_presence(self.id)
        if pres is None:
            return False
        return pres.available

    async def fetch_mutual_friends_count(self):
        """|coro|
        
        Gets how many mutual friends the client and this friend have in common.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        data = await self.client.http.friends_get_summary()
        for friend in data['friends']:
            if friend['accountId'] == self.id:
                return friend['mutual']

    async def set_nickname(self, nickname):
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
            if e.message_code in ('errors.com.epicgames.common.unsupported_media_type',
                                  'errors.com.epicgames.validation.validation_failed'):
                raise ValueError('Invalid nickname')
            e.reraise()
        self._nickname = nickname

    async def remove_nickname(self):
        """|coro|
        
        Removes the friend's nickname.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        await self.client.http.friends_remove_nickname(self.id)
        self._nickname = None

    async def set_note(self, note):
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
            if e.message_code in ('errors.com.epicgames.common.unsupported_media_type',
                                  'errors.com.epicgames.validation.validation_failed'):
                raise ValueError('Invalid note')
            e.reraise()
        self._note = note

    async def remove_note(self):
        """|coro|
        
        Removes the friend's note.

        Raises
        ------
        HTTPException
            An error occured while requesting.
        """
        await self.client.http.friends_remove_note(self.id)
        self._note = None

    async def remove(self):
        """|coro|
        
        Removes the friend from your friendlist.

        Raises
        ------
        HTTPException
            Something went wrong when trying to remove this friend.
        """
        await self.client.friends_remove_or_decline(self.id)

    async def send(self, content):
        """|coro|
        
        Sends a :class:`FriendMessage` to this friend.

        Parameters
        ----------
        content: :class:`str`
            The content of the message.
        """
        await self.client.xmpp.send_friend_message(self.jid, content)

    async def join_party(self):
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
        """
        _pre = self.last_presence
        if _pre is None:
            raise PartyError('Could not join party. Reason: Party not found')
        
        if _pre.party.private:
            raise Forbidden('Could not join party. Reason: Party is private')
        
        await _pre.party.join()

    async def invite(self):
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
        """
        await self.client.user.party.invite(self.id)


class PendingFriend(FriendBase):
    """Represents a pending friend from Fortnite."""

    __slots__ = FriendBase.__slots__

    def __init__(self, client, data):
        super().__init__(client, data)

    @property
    def created_at(self):
        """:class:`datetime.datetime`: The UTC time of when the request was created"""
        return self._created_at

    async def accept(self):
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

    async def decline(self):
        """|coro|
        
        Declines this users' friend request.

        Raises
        ------
        HTTPException
            Something went wrong when trying to decline this request.
        """
        await self.client.remove_or_decline_friend(self.id)


# NOT IMPLEMENTED
# class BlockedFriend(FriendBase):
#     """Represents a blocked friend from Fortnite"""
#     def __init__(self, client, data):
#         super().__init__(client, data)

#     @property
#     def created_at(self):
#         """:class:`datetime.datetime`: The time of when the user was blocked"""
#         return self.created_at

#     async def unblock(self):
#         """|coro|
        
#         Unblocks this friend."""
#         await self.client.http.friends_unblock(self.id)

    
