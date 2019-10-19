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
from .errors import PartyError, Forbidden


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
        self._favorite = bool(data['favorite'])
        self._created_at = self.client.from_iso(data['created'])

    @property
    def display_name(self):
        """:class:`str`: The friends' displayname"""
        return self._display_name
    
    @property
    def id(self):
        """:class:`str`: The friends' id"""
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
        await self.client.http.block_user(self.id)

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

    __slots__ = FriendBase.__slots__

    def __init__(self, client, data):
        super().__init__(client, data)

    @property
    def display_name(self):
        """:class:`str`: The friends displayname"""
        return self._display_name
    
    @property
    def id(self):
        """:class:`str`: The friends id"""
        return self._id
    
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
    def is_online(self):
        """:class:`bool`: ``True`` if this friend is currently online on 
        Fortnite else ``False``.
        """
        pres = self.client.get_presence(self.id)
        if pres is None:
            return False
        return pres.is_available

    async def remove(self):
        """|coro|
        
        Removes the friend from your friendlist.

        Raises
        ------
        HTTPException
            Something went wrong when trying to remove this friend.
        """
        await self.client.http.remove_friend(self.id)

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
        
        if _pre.party.is_private:
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
        """
        await self.client.http.add_friend(self.id)

    async def decline(self):
        """|coro|
        
        Declines this users' friend request.

        Raises
        ------
        HTTPException
            Something went wrong when trying to decline this request.
        """
        await self.client.http.remove_friend(self.id)


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
#         await self.client.http.unblock_user(self.id)

    