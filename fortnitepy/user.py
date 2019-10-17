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
import logging
import aioxmpp

log = logging.getLogger(__name__)


class UserBase:
    __slots__ = ('client', '_display_name', '_id', '_external_auths')

    def __init__(self, client, data, **kwargs):
        self.client = client
        if data:
            self._update(data)

    @property
    def display_name(self):
        """:class:`str`: The users displayname"""
        return self._display_name
    
    @property
    def id(self):
        """:class:`str`: The users id"""
        return self._id
    
    @property
    def external_auths(self):
        """:class:`list`: List containing information about external auths.
        Might be empty if the user does not have any external auths"""
        return self._external_auths

    @property
    def jid(self):
        """:class:`aioxmpp.JID`: The JID of the user."""
        return aioxmpp.JID.fromstr('{0.id}@{0.client.service_host}'.format(self))

    async def fetch_br_stats(self, *, start_time=None, end_time=None):
        """|coro|
        
        Fetches this users stats.
        
        Parameters
        ----------
        start_time: Optional[Union[:class:`int`, :class:`datetime.datetime`]]
            The UTC start time of the time period to get stats from.
            *Must be seconds since epoch or :class:`datetime.datetime`*
            *Defaults to None*
        end_time: Optional[Union[:class:`int`, :class:`datetime.datetime`]]
            The UTC end time of the time period to get stats from.
            *Must be seconds since epoch or :class:`datetime.datetime`*
            *Defaults to None*

        Raises
        ------
        HTTPException
            An error occured while requesting.
        
        Returns
        -------
        :class:`StatsV2`
            An object representing the stats for this user.
        """
        return await self.client.fetch_br_stats(self.id, start_time=start_time, end_time=end_time)

    async def fetch_battlepass_level(self):
        """|coro|
        
        Fetches this users battlepass level.
        
        Raises
        ------
        HTTPException
            An error occured while requesting.

        Returns
        -------
        :class:`float`
            The users battlepass level. ``None`` is returned if the user has not played any
            real matches this season.
        """
        return await self.client.fetch_battlepass_level(self.id)

    def _update(self, data):
        self._display_name = data.get('displayName', data.get('account_dn'))
        self._external_auths = data.get('external_auths', [])

        try:
            self._id = data['id']
        except KeyError:
            self._id = data.get('accountId', data.get('account_id'))

    def _update_display_name(self, display_name):
        self._display_name = display_name

    def get_raw(self):
        return {
            'displayName': self.display_name,
            'id': self.id,
            'externalAuths': self.external_auths
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
    headless: :class:`str`
        COME BACK TO THIS
    last_login: :class:`datetime.datetime`
        UTC time of the last login of the user.
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
        ``True`` if the user has two-factor authentication enabled.
    """

    def __init__(self, client, data, **kwargs):
        super().__init__(client, data)
        self._party = None
        self._update(data)

    @property
    def first_name(self):
        return self.name

    @property
    def full_name(self):
        return '{} {}'.format(self.name, self.last_name)

    @property
    def party(self):
        """:class:`Party`: The users party."""
        return self._party

    @property
    def jid(self):
        """:class:`aioxmpp.JID`: The JID of the client. Includes the 
        resource part.
        """
        return self.client.xmpp.xmpp_client.local_jid

    def _update(self, data):
        super()._update(data)
        self.age_group = data['ageGroup']
        self.can_update_display_name = bool(data['canUpdateDisplayName'])
        self.country = data['country']
        self.email = data['email']
        self.failed_login_attempts = data['failedLoginAttempts']
        self.headless = data['headless']
        self.last_login = self.client.from_iso(data['lastLogin'])
        self.name = data['name']
        self.last_name = data['lastName']
        self.number_of_display_name_changes = int(data['numberOfDisplayNameChanges'])
        self.preferred_language = data['preferredLanguage']
        self.tfa_enabled = bool(data['tfaEnabled'])

    def set_party(self, party):
        self._party = party

    def remove_party(self):
        self._party = None


class User(UserBase):

    __slots__ = UserBase.__slots__
    
    def __init__(self, client, data, **kwargs):
        super().__init__(client, data)
