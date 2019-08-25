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
import aiohttp
import asyncio
import sys
import signal
import logging
import json

from .errors import EventError, PartyError, HTTPException
from .xmpp import XMPPClient
from .auth import Auth
from .http import HTTPClient
from .user import ClientUser, User
from .friend import Friend, PendingFriend
from .enums import PartyPrivacy
from .cache import Cache, WeakrefCache
from .party import ClientParty
from .stats import StatsV2
from .store import Store
from .news import BattleRoyaleNewsPost
from .playlist import Playlist

# logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__) 

# all credit for this function goes to discord.py. Great task cancelling.
def _cancel_tasks(loop):
    task_retriever = asyncio.Task.all_tasks
    tasks = {t for t in task_retriever(loop=loop) if not t.done()}

    if not tasks:
        return

    log.info('Cleaning up after %d tasks.', len(tasks))
    for task in tasks:
        task.cancel()

    loop.run_until_complete(asyncio.gather(*tasks, loop=loop, return_exceptions=True))
    log.info('All tasks finished cancelling.')

    for task in tasks:
        if task.cancelled():
            continue
        if task.exception() is not None:
            loop.call_exception_handler({
                'message': 'Unhandled exception during Client.run shutdown.',
                'exception': task.exception(),
                'task': task
            })


def _cleanup_loop(loop):
    try:
        _cancel_tasks(loop)
        if sys.version_info >= (3, 6):
            loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        log.info('Closing the event loop.')
        loop.close()


class Client:
    """Represents the client connected to Fortnite and EpicGames' services.

    Parameters
    ----------
    email: Required[:class:`str`]
        The email of the account you want the client to log in as.
    password: Required[:class:`str`]
        The password of the account you want the client to log in as.
    two_factor_code: Optional[:class:`int`]
        The two-factor code to use when authenticating. If no two factor code is set
        and the passed account has 2fa enabled, you will be asked to enter it through
        console.
    loop: Optional[:class:`asyncio.AbstractEventLoop`]
        The event loop to use for asynchronous operations.
    status: :class:`str`
        The status you want the client to send with its presence to friends.
        Defaults to: ``Battle Royale Lobby - {party playercount} / {party max playercount}``
    platform: Optional[:class:`str`]
        The platform you want the client to display as its source. 
        Defaults to ``WIN``.
    net_cl: :class:`str`
        The current buildid used by the current Fortnite build. Named *netCL* in official logs.
        Defaults to the current buildid but doesn't get updated automatically. 
        
        .. warning::

            When a new buildid is pushed by EpicGames you must either wait for the library to get updated
            and then download the updated version with the correct buildid or you can get it yourself from
            the official logs and initialize client with it.

    default_party_config: Optional[:class:`dict`]
        The party configuration used when creating parties.
        Defaults to:

        .. code-block:: python3

            {
                'privacy': PartyPrivacy.PUBLIC,
                'joinability': 'OPEN',
                'max_size': 16,
                'sub_type': 'default',
                'type': 'default',
                'invite_ttl_seconds': 14400,
                'chat_enabled': True,
            }

    build: :class:`str`
        The build used by Fortnite. 
        Defaults to ``++Fortnite+Release-9.21-CL-6922310``

        .. note::

            The build is updated with every major version but is not that important to
            update as netCL.
    
    engine_build: :class:`str`
        The engine build used by Fortnite.
        Defaults to ``4.23.0-6922310+++Fortnite+Release-9.21``

        .. note::

            The build is updated with every major version but is not that important to
            update as netCL.
    
    launcher_token: :class:`str`
        The token used by EpicGames Launcher.
    fortnite_token: :class:`str`
        The token used by Fortnite.
    service_host: :class:`str`
        The host used by Fortnite's XMPP services.
    service_domain: :class:`str`
        The domain used by Fortnite's XMPP services.
    serivce_port: :class:`int`
        The port used by Fortnite's XMPP services.
    device_id: :class:`str`
        The hardware address of your computer as a 32char hex string.

    Attributes
    ----------
    user: :class:`ClientUser`
        The user the client is logged in as.
    loop: :class:`asyncio.AbstractEventLoop`
        The event loop that client implements.
    """

    def __init__(self, email, password, two_factor_code=None, loop=None, **kwargs):
        self.email = email
        self.password = password
        self.two_factor_code = two_factor_code
        self.loop = loop or asyncio.get_event_loop()

        self.status = kwargs.get('status', None)
        self.platform = kwargs.get('platform', 'WIN')
        self.net_cl = kwargs.get('net_cl', '7605985')
        self.party_build_id = '1:1:{0.net_cl}'.format(self)
        self.default_party_config = kwargs.get('default_party_config', {})
        self.build = kwargs.get('build', '++Fortnite+Release-10.10-CL-7955722')
        self.engine_build = kwargs.get('engine_build', '4.23.0-7955722+++Fortnite+Release-10.10')
        self.launcher_token = kwargs.get('launcher_token',
            'MzQ0NmNkNzI2OTRjNGE0NDg1ZDgxYjc3YWRiYjIxNDE6OTIwOWQ0YTVlMjVhNDU3ZmI5YjA3NDg5ZDMxM2I0MWE='
        )
        self.fortnite_token = kwargs.get('fortnite_token',
            'ZWM2ODRiOGM2ODdmNDc5ZmFkZWEzY2IyYWQ4M2Y1YzY6ZTFmMzFjMjExZjI4NDEzMTg2MjYyZDM3YTEzZmM4NGQ='
        )
        self.service_host = kwargs.get('xmpp_host', 'prod.ol.epicgames.com')
        self.service_domain = kwargs.get('xmpp_domain', 'xmpp-service-prod.ol.epicgames.com')
        self.service_port = kwargs.get('xmpp_port', 5222)
        self.device_id = kwargs.get('device_id', None)

        self.kill_other_sessions = True
        self.accept_eula = True

        self.http = HTTPClient(self, connector=kwargs.get('connector'))
        self.http.add_header('Accept-Language', 'en-EN')
        self.xmpp = None

        self._listeners = {}
        self._events = {}
        self._friends = Cache()
        self._pending_friends = Cache()
        self._users = Cache()
        self._presences = Cache()
        self.event_prefix = 'event'
        self._ready = asyncio.Event(loop=self.loop)
        self._refresh_task = None
        self._closed = False
        self._closing = False

        self.refresh_i = 0

        self.update_default_party_config(
            kwargs.get('default_party_config')
        )
        self._check_party_confirmation()
        
    @staticmethod
    def from_iso(iso):
        """:class:`str`: Converts an iso formatted string to a :class:`datetime.datetime` object
        
        Returns
        -------
        :class:`datetime.datetime`
        """
        if isinstance(iso, datetime.datetime):
            return iso
        return datetime.datetime.strptime(iso, '%Y-%m-%dT%H:%M:%S.%fZ')
    
    @staticmethod
    def to_iso(dt):
        """:class:`datetime.datetime`: Converts a :class:`datetime.datetime` object to an iso 
        formatted string

        Returns
        -------
        :class:`str`
        """
        return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    @property
    def friends(self):
        """:class:`dict`: Mapping of current friends. {id (:class:`str`): :class:`Friend`}"""
        return self._friends._cache

    @property
    def pending_friends(self):
        """:class:`dict`: Mapping of currently pending friends. {id (:class:`str`): :class:`PendingFriend`}
        
        .. note::
        
            Pending friends can be both inbound (pending friend sent the request to the bot) or outgoing 
            (the bot sent the request to the pending friend).
        """
        return self._pending_friends._cache

    @property
    def presences(self):
        """:class:`dict`: Mapping of the last presence received from friends. {id (:class:`str`): :class:`Presence`}"""
        return self._presences._cache

    def update_default_party_config(self, config):
        if config is None:
            return

        if not isinstance(config, dict):
            raise PartyError('\'config\' must be a dictionary')

        _default_conf = {
            'privacy': PartyPrivacy.PUBLIC.value,
            'join_confirmation': False,
            'joinability': 'OPEN',
            'max_size': 16,
            'sub_type': 'default',
            'type': 'default',
            'invite_ttl_seconds': 14400,
            'chat_enabled': True,
        }

        try:
            self.default_party_config['privacy'] = self.default_party_config['privacy'].value
        except (KeyError, AttributeError):
            pass

        default_config = {**_default_conf, **self.default_party_config}
        self.default_party_config = {**default_config, **config}

    def _check_party_confirmation(self):
        try:
            getattr(self, '{0.event_prefix}_party_member_confirmation'.format(self))
            val = True
        except AttributeError:
            val = False

        self.update_default_party_config({'join_confirmation': val})

    def exc_handler(self, loop, ctx):
        log.debug('Exception was catched by asyncio exception handler: {}'.format(ctx['message']))

    def run(self):
        """This function starts the loop and then calls :meth:`start` for you.
        If you have passed an already running event loop to the client, you should start the client
        with :meth:`start`.

        .. warning::

            This function is blocking and should be the last function to run.

        Raises
        ------
        AuthException
            An error occured when attempting to log in.
        """
        loop = self.loop

        try:
            loop.add_signal_handler(signal.SIGINT, lambda: loop.stop())
            loop.add_signal_handler(signal.SIGTERM, lambda: loop.stop())
        except NotImplementedError:
            pass

        async def runner():
            try:
                await self.start()
            finally:
                if not self._closing:
                    await self.logout()

        asyncio.ensure_future(runner(), loop=loop)

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            log.info('Terminating event loop.')
        finally:
            if not self._closing:
                log.info('Client not logged out when terminating loop. Logging out now.')
                loop.run_until_complete(self.logout())

            log.info('Cleaning up loop')
            _cleanup_loop(loop)
        
    async def start(self):
        """|coro|
        
        Starts the client and logs into the specified user.
        
        .. warning::

            This functions is blocking and everything after the line calling this function will never run!
            If you are using this function instead of :meth:`run` you should always call it after everything
            else. When the client is ready it will dispatch :meth:`event_ready`. 

        Raises
        ------
        AuthException
            An error occured when attempting to log in.
        """
        if self._closed:
            self.http.create_connection()
            self._closed = False

        await self._login()

        self._set_ready()
        self.dispatch_event('ready')

        self._refresh_task = self.loop.create_task(self.auth.schedule_token_refresh())
        try:
            await self._refresh_task
        except asyncio.CancelledError:
            pass
        
    async def _login(self):
        self.auth = Auth(self)
        await self.auth.authenticate()

        data = await self.http.get_profile(self.auth.account_id)
        self.user = ClientUser(self, data)

        if self.kill_other_sessions:
            await self.auth.kill_other_sessions()
            log.debug('Other sessions killed')

        if self.accept_eula:
            await self.auth.accept_eula(self.auth.account_id)
            log.debug('EULA accepted')

        await self.initialize_friends()

        self.xmpp = XMPPClient(self)
        await self.xmpp.run()
        log.debug('Connected to XMPP')

        await self.initialize_party()
        log.debug('Party created')

    async def logout(self):
        """|coro|
        
        Logs the user out and closes running services.

        Raises
        ------
        HTTPException
            An error occured while logging out.
        """
        self._closing = True
        if self._refresh_task is not None and not self._refresh_task.cancelled():
            self._refresh_task.cancel()

        try:
            if self.user.party is not None:
                await self.user.party._leave()
        except:
            pass

        try:
            await self.xmpp.close()
        except:
            pass

        try:
            await self.auth.kill_token(self.auth.access_token)
        except:
            pass

        self._friends.clear()
        self._pending_friends.clear()
        self._users.clear()
        self._presences.clear()
        self._ready.clear()
        
        await self.http.close()
        self._closed = True
        self._closing = False
        log.debug('Successfully logged out')

    def _set_ready(self):
        self._ready.set()

    def is_ready(self):
        """Specifies if the internal state of the client is ready.
        
        Returns
        -------
        :class:`bool`
            ``True`` if the internal state is ready else ``False``
        """
        return self._ready.is_set()

    async def wait_until_ready(self):
        """|coro|
        
        Waits until the internal state of the client is ready.
        """
        await self._ready.wait()

    async def initialize_party(self):
        data = await self.http.party_lookup_user(self.user.id)
        if len(data['current']) > 0:
            party = ClientParty(self, data['current'][0])
            await party._leave()
            log.debug('Left old party')
        await self._create_party()

    async def fetch_profile_by_display_name(self, display_name, cache=True, raw=False):
        """|coro|
        
        Fetches a profile from the passed display name
        
        Parameters
        ----------
        display_name: :class:`str`
            The display name of the user you want to fetch the profile for.
        cache: Optional[:class:`bool`]
            If set to True it will try to get the profile from the friends or user cache.
            *Defaults to ``True``*

            .. note::

                Setting this parameter to False will make it an api call.

        raw: Optional[:class:`bool`]
            If set to True it will return the data as you would get it from the api request.
            *Defaults to ``False``*

            .. note::

                Setting raw to True does not work with cache set to True.

        Raises
        ------
        HTTPException
            An error occured while requesting the user.

        Returns
        -------
        :class:`User`
            The user requested. If not found it will return ``None``  
        """
        if cache:
            for u in self._users.values():
                if u.display_name.lower() == display_name.lower():
                    return u
        try:
            res = await self.http.get_profile_by_display_name(display_name)
        except HTTPException as exc:
            if exc.message_code != 'errors.com.epicgames.account.account_not_found':
                raise HTTPException(exc.response, exc.raw)
            return None

        if raw:
            return res
        return self.store_user(res)

    async def fetch_profile(self, user, cache=True, raw=False):
        """|coro|
        
        Fetches a single profile by the given id/displayname

        Parameters
        ----------
        user: :class:`str`
            Id or display name
        cache: Optional[:class:`bool`]
            If set to True it will try to get the profile from the friends or user cache
            and fall back to an api request if not found.
            *Defaults to ``True``*

            .. note::

                Setting this parameter to False will make it an api call.

        raw: Optional[:class:`bool`]
            If set to True it will return the data as you would get it from the api request.
            *Defaults to ``False``*

            .. note::

                Setting raw to True does not work with cache set to True.

        Raises
        ------
        HTTPException
            An error occured while requesting the user.

        Returns
        -------
        :class:`User`
            The user requested. If not found it will return ``None``
        """
        try:
            return (await self.fetch_profiles((user,), cache=cache, raw=raw))[0]
        except IndexError:
            return None

    async def fetch_profiles(self, users, cache=True, raw=False):
        """|coro|
        
        Fetches multiple profiles at once by the given ids/displaynames

        Parameters
        ----------
        users: List[:class:`str`]
            A list/tuple containing ids/displaynames.
        cache: Optional[:class:`bool`]
            If set to True it will try to get the profiles from the friends or user cache
            and fall back to an api request if not found.
            *Defaults to ``True``*

            .. note::

                Setting this parameter to False will make it an api call.

        raw: Optional[:class:`bool`]
            If set to True it will return the data as you would get it from the api request.
            *Defaults to ``False``*

            .. note::

                Setting raw to True does not work with cache set to True.

        Raises
        ------
        HTTPException
            An error occured while requesting user information.

        Returns
        -------
        List[:class:`User`]
            Users requested. Only users that are found gets returned.
        """
        if len(users) == 0:
            return []

        profiles = []
        new = []
        tasks = []
        for elem in users:
            if self.is_display_name(elem):
                for u in self._users.values():
                    if u.display_name.lower() == elem.lower():
                        profiles.append(u)
                        continue

                task = self.http.get_profile_by_display_name(elem)
                tasks.append(task)
            else:
                if cache:
                    p = self.get_user(elem)
                    if p:
                        if raw:
                            profiles.append(p.get_raw())
                        else:
                            profiles.append(p)
                        continue
                new.append(elem)

        if len(tasks) > 0:
            done, _ = await asyncio.wait(tasks)
            for f in done:
                id = (f.result())['id']
                new.append(id)

        chunk_tasks = []
        chunks = [new[i:i + 100] for i in range(0, len(new), 100)]
        for chunk in chunks:
            task = self.http.get_profiles(chunk)
            chunk_tasks.append(task)
        
        if len(chunks) > 0:
            d, _ = await asyncio.wait(chunk_tasks)
            for results in d:
                for result in results.result():
                    if raw:
                        profiles.append(result)
                    else:
                        u = self.store_user(result)
                        profiles.append(u)
        return profiles

    async def initialize_friends(self):
        raw_friends = await self.http.get_friends(include_pending=True)
        ids = [r['accountId'] for r in raw_friends]
        friends = await self.fetch_profiles(ids, raw=True)
        
        m = {}
        for friend in friends:
            m[friend['id']] = friend

        for friend in raw_friends:
            if friend['status'] == 'PENDING':
                try:
                    f = PendingFriend(self, {**friend, **m[friend['accountId']]})
                    self._pending_friends.set(f.id, f)
                except KeyError:
                    continue

            elif friend['status'] == 'ACCEPTED':
                try:
                    f = Friend(self, {**friend, **m[friend['accountId']]})
                    self._friends.set(f.id, f)
                except KeyError:
                    continue

    def store_user(self, data):
        try:
            return self._users.get(data['id'], silent=False)
        except KeyError:
            u = User(self, data)
            self._users.set(u.id, u)
            return u

    def get_user(self, id):
        """Tries to get a user from the user cache by the given id.

        Parameters
        ----------
        id: :class:`str`
            The id of the user.

        Returns
        -------
        :class:`User`
            :class:`User` if found, else ``None``
        """
        user = self._users.get(id)
        if user is None:
            friend = self.get_friend(id)
            if friend is not None:
                user = User(self, friend.get_raw())
                self._users.set(user.id, user)
        return user

    def store_friend(self, data):
        try:
            return self._friends.get(data['accountId'], silent=False)
        except KeyError:
            f = Friend(self, data)
            self._friends.set(f.id, f)
            return f

    def get_friend(self, id):
        """Tries to get a friend from the friend cache by the given id.

        Parameters
        ----------
        id: :class:`str`
            The id of the friend.

        Returns
        -------
        :class:`Friend`
            :class:`Friend` if found, else ``None``
        """
        return self._friends.get(id)

    def get_presence(self, id):
        """Tries to get the latest received presence from the presence cache.

        Parameters
        ----------
        id: :class:`str`
            The id of the friend you want the last presence of.

        Returns
        -------
        :class:`Presence`
            :class:`Presence` if found, else ``None``
        """
        return self._presences.get(id)
    
    def get_pending_friend(self, id):
        """Tries to get a pending friend from the pending friend cache by the given id.

        Parameters
        ----------
        id: :class:`str`
            The id of the pending friend.

        Returns
        -------
        :class:`PendingFriend`: 
            :class:`PendingFriend` if found, else ``None``
        """
        return self._pending_friends.get(id)

    def has_friend(self, id):
        """Checks if the client is friends with the given id.

        Parameters
        ----------
        id: :class:`str`
            The id of the user you want to check.

        Returns
        -------
        :class:`bool`
            ``True`` if user is friends with the client else ``False``
        """
        return self.get_friend(id) is not None
    
    def is_pending(self, id):
        """Checks if the given id is a pending friend of the client.

        Parameters
        ----------
        id: :class:`str`
            The id of the user you want to check.

        Returns
        -------
        :class:`bool`
            ``True`` if user is a pending friend else ``False``
        """
        return self.get_pending_friend(id)

    async def get_blocklist(self):
        """|coro|
        
        Retrieves the blocklist with an api call.

        Raises
        ------
        HTTPException
            An error occured while fetching blocklist.

        Returns
        -------
        List[:class:`str`]
            List of ids
        """
        return (await self.http.get_friends_blocklist())['blockedUsers']

    async def block_user(self, id):
        """|coro|
        
        Blocks a user by a given id.

        Parameters
        ----------
        id: :class:`str`
            The id of the user you want to block.

        Raises
        ------
        HTTPException
            Something went wrong when trying to block this user.
        """
        await self.http.block_user(id)

    async def unblock_user(self, id):
        """|coro|
        
        Unblocks a user by a given id.

        Parameters
        ----------
        id: :class:`str`
            The id of the user you want to unblock

        Raises
        ------
        HTTPException
            Something went wrong when trying to unblock this user.
        """
        await self.http.unblock_user(id)

    def is_id(self, value):
        """Simple function that finds out if a :class:`str` is a valid id

        Parameters
        ----------
        value: :class:`str`
            The string you want to check.

        Returns
        -------
        :class:`bool`
            ``True`` if string is valid else ``False``
        """
        return isinstance(value, str) and len(value) > 16

    def is_display_name(self, val):
        """Simple function that finds out if a :class:`str` is a valid displayname

        Parameters
        ----------
        value: :class:`str`
            The string you want to check.

        Returns
        -------
        :class:`bool`
            ``True`` if string is valid else ``False``
        """
        return isinstance(val, str) and 3 <= len(val) <= 16  

    async def add_friend(self, id):
        """|coro|
        
        Sends a friend request or accepts a request if found.

        Raises
        ------
        HTTPException
            An error occured while requesting to add this friend.

        Parameters
        ----------
        id: :class:`str`
            The id of the user you want to add/accept.
        """
        await self.http.add_friend(id)
    
    async def remove_friend(self, id):
        """|coro|
        
        Removes a friend by the given id.

        Parameters
        ----------
        id: :class:`str`
            The id of the friend you want to remove.

        Raises
        ------
        HTTPException
            Something went wrong when trying to remove this friend.
        """
        await self.http.remove_friend(id)

    def dispatch_event(self, event, *args, **kwargs):
        method = '{0.event_prefix}_{1}'.format(self, event)

        listeners = self._listeners.get(event)
        if listeners:
            removed = []
            for i, (future, check) in enumerate(listeners):
                if future.cancelled():
                    removed.append(i)
                    continue
                
                try:
                    result = check(*args)
                except Exception as e:
                    future.set_exception(e)
                    removed.append(i)
                else:
                    if result:
                        if len(args) == 0:
                            future.set_result(None)
                        elif len(args) == 1:
                            future.set_result(args[0])
                        else:
                            future.set_result(args)
                        removed.append(i)

            if len(removed) == len(listeners):
                self._listeners.pop(event)
            else:
                for idx in reversed(removed):
                    del listeners[idx]
        
        try:
            coro = getattr(self, method)
        except AttributeError as e:
            pass
        else:
            asyncio.ensure_future(coro(*args, **kwargs), loop=self.loop)

        if event in self._events.keys():
            for coro in self._events[event]:
                asyncio.ensure_future(coro(*args, **kwargs), loop=self.loop)

    def wait_for(self, event, *, check=None, timeout=None):
        """|coro|
        
        Waits for an event to be dispatch.
        
        In case the event returns more than one arguments, a tuple is passed containing 
        the arguments.
        
        Examples
        --------
        This example waits for the author of a :class:`FriendMessage` to say hello.: ::

            @client.event
            async def event_friend_message(message):
                await message.reply('Say hello!')

                def check_function(m):
                    return m.author.id == message.author.id
                
                msg = await client.wait_for('message', check=check_function, timeout=60)
                await msg.reply('Hello {0.author.display_name}!'.format(msg))

        This example waits for the the leader of a party to promote the bot after joining
        and then sets a new custom key: ::

            @client.event
            async def event_party_member_join(member):

                # checks if the member that joined is the UserClient
                if member.id != client.user.id:
                    return

                def check(m):
                    return m.id == client.user.id
                
                try:
                    await client.wait_for('party_member_promote', check=check, timeout=120)
                except asyncio.TimeoutError:
                    await member.party.send('You took too long to promote me!')
                
                await member.party.set_custom_key('my_custom_key_123')

        Parameters
        ----------
        event: :class:`str`
            The name of the event. 

            .. note::

                The name of the event must be **without** the ``event_`` prefix.

                Wrong = ``event_friend_message``.
                Correct = ``friend_message``.

        check: Optional[Callable function]
            A predicate to check what to wait for.
            *Defaults to a predicate that always returns ``True``. This means it will return the first
            result.*

        timeout: :class:`int`
            How many seconds to wait for before asyncio.TimeoutError is raised.
            *Defaults to ``None`` which means it will wait forever.*

        Raises
        ------
        asyncio.TimeoutError
            No event was retrieved in the time you specified.

        Returns
        -------
        Any
            Returns arguments based on the event you are waiting for. An event might return
            no arguments, one argument or a tuple of arguments. Check the
            :ref:`event reference <fortnitepy-events-api> for more information about the returning
            arguments.`
        """
        future = self.loop.create_future()
        if check is None:
            def _check(*args):
                return True
            check = _check
        
        ev = (event.lower()).replace('{0.event_prefix}_'.format(self), '')
        try:
            listeners = self._listeners[ev]
        except KeyError:
            listeners = []
            self._listeners[ev] = listeners
        
        listeners.append((future, check))
        return asyncio.wait_for(future, timeout, loop=self.loop)

    def add_event_handler(self, event, coro):
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('event registered must be a coroutine function')

        if event not in self._events.keys():
            self._events[event] = []
        self._events[event].append(coro)
    
    def remove_event_handler(self, event, coro):
        if event not in self._events.keys():
            return
        
        try:
            self._events[event].remove(coro)
        except ValueError:
            pass

    def event(self, coro):
        """A decorator to register an event.
        
        .. note::

            You do not need to decorate events in a subclass of :class:`Client`.

        Usage: ::

            @client.event
            async def event_friend_message(message):
                await message.reply('Thanks for your message!')

        Raises
        ------
        TypeError
            The name of the function does is not prefixed with ``event_``
        TypeError
            The decorated function is not a coroutine.
        """
        if not coro.__name__.startswith('event_'):
            raise TypeError('event function names must follow this syntax: "event_<event>"')
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('the decorated function must be a coroutine')

        name = '_'.join(coro.__name__.split('_')[1:])
        self.add_event_handler(name, coro)
        log.debug('{} has been registered as an event'.format(coro.__name__))
        return coro

    async def fetch_br_stats(self, user_id, start_time=None, end_time=None):
        """|coro|
        
        Gets Battle Royale stats the specified user.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the user you want to fetch stats for.
        start_time: Optional[Union[:class:`int`, :class:`datetime.datetime`]]
            The start time of the time period to get stats from.
            *Must be seconds since epoch or :class:`datetime.datetime`*
            *Defaults to None*
        end_time: Optional[Union[:class:`int`, :class:`datetime.datetime`]]
            The end time of the time period to get stats from.
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
        epoch = datetime.datetime.utcfromtimestamp(0)
        if isinstance(start_time, datetime.datetime):
            start_time = (start_time - epoch).total_seconds()

        if isinstance(end_time, datetime.datetime):
            end_time = (end_time - epoch).total_seconds()

        data = await self.http.get_br_stats_v2(user_id, start_time=start_time, end_time=end_time)
        return StatsV2(data)

    async def fetch_multiple_br_stats(self, user_ids, stats, start_time=None, end_time=None):
        """|coro|
        
        Gets Battle Royale stats for multiple users at the same time.
        
        .. note::
            
            This function is not the same as doing :meth:`fetch_br_stats` for multiple users.
            The expected return for this function would not be all the stats for the specified
            users but rather the stats you specified.

        Example usage: ::

            async def stat_function():
                stats = [
                    fortnitepy.StatsV2.create_stat('placetop1', fortnitepy.V2Inputs.KEYBOARDANDMOUSE, 'defaultsolo'),
                    fortnitepy.StatsV2.create_stat('kills', fortnitepy.V2Inputs.KEYBOARDANDMOUSE, 'defaultsolo'),
                    fortnitepy.StatsV2.create_stat('matchesplayed', fortnitepy.V2Inputs.KEYBOARDANDMOUSE, 'defaultsolo')
                ]

                # get the profiles and create a list of their ids.
                profiles = await self.fetch_profiles(['Ninja', 'Dark', 'DrLupo'])
                user_ids = [u.id for u in profiles]

                data = await self.fetch_multiple_br_stats(user_ids=user_ids, stats=stats)
                for id, res in data.items():
                    print('ID: {0} | Stats: {1}'.format(id, res.stats))
            
            # expected output (ofc the values would be updated):
            # ID: 463ca9d604524ce38071f512baa9cd70 | Stats: {'keyboardmouse': {'defaultsolo': {'wins': 759, 'kills': 28093, 'matchesplayed': 6438}}}
            # ID: 3900c5958e4b4553907b2b32e86e03f8 | Stats: {'keyboardmouse': {'defaultsolo': {'wins': 1763, 'kills': 41375, 'matchesplayed': 7944}}}
            # ID: 4735ce9132924caf8a5b17789b40f79c | Stats: {'keyboardmouse': {'defaultsolo': {'wins': 1888, 'kills': 40784, 'matchesplayed': 5775}}}

        Parameters
        ----------
        user_ids: List[:class:`str`]
            A list of ids you are requesting the stats for.
        stats: List[:class:`str`]
            A list of stats to get for the users. Use :meth:`StatsV2.create_stat` to create the stats.

            Example: ::

                [
                    fortnitepy.StatsV2.create_stat('placetop1', fortnitepy.V2Inputs.KEYBOARDANDMOUSE, 'defaultsolo'),
                    fortnitepy.StatsV2.create_stat('kills', fortnitepy.V2Inputs.KEYBOARDANDMOUSE, 'defaultsolo'),
                    fortnitepy.StatsV2.create_stat('matchesplayed', fortnitepy.V2Inputs.KEYBOARDANDMOUSE, 'defaultsolo')
                ]

        start_time: Optional[Union[:class:`int`, :class:`datetime.datetime`]]
            The start time of the time period to get stats from.
            *Must be seconds since epoch or :class:`datetime.datetime`*
            *Defaults to None*
        end_time: Optional[Union[:class:`int`, :class:`datetime.datetime`]]
            The end time of the time period to get stats from.
            *Must be seconds since epoch or :class:`datetime.datetime`*
            *Defaults to None*

        Raises
        ------
        HTTPException
            An error occured while requesting.

        Returns
        -------
        Dict[id: :class:`StatsV2`]
            A mapping where :class:`StatsV2` is bound to its owners id.
        """
        epoch = datetime.datetime.utcfromtimestamp(0)
        if isinstance(start_time, datetime.datetime):
            start_time = (start_time - epoch).total_seconds()

        if isinstance(end_time, datetime.datetime):
            end_time = (end_time - epoch).total_seconds()
        
        data = await self.http.get_multiple_br_stats_v2(user_ids, stats)

        res = {}
        for udata in data:
            res[udata['accountId']] = StatsV2(udata)
        return res

    async def fetch_leaderboard(self, stat):
        """|coro|
        
        Fetches the leaderboard for a stat.
        
        .. warning::
        
            For some weird reason, the only valid stat you can pass is
            one with ``placetop1`` (``wins`` is also accepted).
            
        Example usage: ::

            async def get_leaderboard():
                stat = fortnitepy.StatsV2.create_stat(
                    'wins',
                    fortnitepy.V2Inputs.KEYBOARDANDMOUSE,
                    'defaultsquad'
                )

                data = await client.fetch_leaderboard(stat)

                for placement, entry in enumerate(data):
                    print('[{0}] Id: {1} | Wins: {2}'.format(
                        placement, entry['account'], entry['value']))

        Parameters
        ----------
        stat: :class:`str`
            The stat you are requesting the leaderboard entries for. You can use 
            :meth:`StatsV2.create_stat` to create this string.
            
        Raises
        ------
        ValueError
            You passed an invalid/non-accepted stat argument. 
        HTTPException
            An error occured when requesting.

        Returns
        -------
        List[Dict['account': :class:`str`: id, 'value': :class:`int`: The stat value.]]
            List of dictionaries containing entry data. Example return: ::

                {
                    'account': '4480a7397f824fe4b407077fb9397fbb',
                    'value': 5082
                }
        """
        data = await self.http.get_br_leaderboard_v2(stat)

        if len(data['entries']) == 0:
            raise ValueError('{0} is not a valid stat'.format(stat))
        
        return data['entries']

    async def _create_party(self, config=None):
        if isinstance(config, dict):
            cf = {**self.default_party_config, **config}
        else:
            cf = self.default_party_config

        while True:
            try:
                data = await self.http.party_create(cf)
                break
            except HTTPException as exc:
                if exc.message_code != 'errors.com.epicgames.social.party.user_has_party':
                    raise HTTPException(exc.response, exc.raw)

                data = await self.http.party_lookup_user(self.user.id)
                await self.http.party_leave(data['current'][0]['id'])

        config = {**cf, **data['config']}
        party = ClientParty(self, data)
        await party._update_members(data['members'])
        asyncio.ensure_future(party.join_chat(), loop=self.loop)
        self.user.set_party(party)

        def check(m):
            return m.id == self.user.id

        try:
            await self.wait_for('party_member_join', check=check, timeout=3)
        except asyncio.TimeoutError:
            await party._leave()
            return await self._create_party()

        await party.set_privacy(config['privacy'])
        return party

    async def join_to_party(self, party_id, party=None):
        if party is None:
            party_data = await self.http.party_lookup(party_id)
            party = ClientParty(self, party_data)
            await party._update_members(party_data['members'])

        await self.user.party._leave()
        self.user.set_party(party)

        await self.http.party_join_request(party_id)
        await party._update_members_meta()
        asyncio.ensure_future(self.user.party.join_chat(), loop=self.loop)

    async def set_status(self, status):
        """|coro|
        
        Sends and sets the status. This status message will override all other
        presence statuses including party presence status.

        Parameters
        ----------
        status: :class:`str`
            The status you want to set.

        Raises
        ------
        TypeError
            The status you tried to set were not a str.
        """
        if not isinstance(status, str):
            raise TypeError('status must be a str')
        
        self.status = status
        await self.xmpp.send_presence(status=status)

    async def send_status(self, status, to=None):
        """|coro|
        
        Sends this status to all or one single friend.
        
        Parameters
        ----------
        status: Union[:class:`str`, :class:`dict`]
            The status message in :class:`str` or full status in :class:`dict`.
        to: Optional[:class:`aioxmpp.JID`]
            The JID of the user that should receive this status.
            *Defaults to None which means it will send to all friends.*

        Raises
        ------
        TypeError
            Status was an invalid type.
        """
        await self.xmpp.send_presence(status=status, to=to)

    async def fetch_lightswitch_status(self, service_id='Fortnite'):
        """|coro|
        
        Fetches the lightswitch status of an epicgames service.

        Parameters
        ----------
        service_id: Optional[:class:`str`]
            The service id to check status for.
            *Defaults to ``Fortnite``.

        Raises
        ------
        ValueError
            The returned data was empty. Most likely because service_id is not valid.
        HTTPException
            An error occured when requesting.

        Returns
        -------
        :class:`bool`
            ``True`` if service is up else ``False``
        """
        status = await self.http.get_lightswitch_status(service_id=service_id)
        if len(status) == 0:
            raise ValueError('emtpy lightswitch response')
        return True if status[0].get('status') == 'UP' else False

    async def fetch_item_shop(self):
        """|coro|
        
        Fetches the current item shop.

        Example: ::

            # fetches all CIDs (character ids) of of the current item shop.
            async def get_current_item_shop_cids():
                store = await client.fetch_item_shop()

                cids = []
                for item in store.featured_items + store.daily_items:
                    for grant in item.grants:
                        if grant['type'] == 'AthenaCharacter':
                            cids.append(grant['asset'])

                return cids

        Raises
        ------
        HTTPException
            An error occured when requesting.

        Returns
        -------
        :class:`Store`
            Object representing the data from the current item shop.
        """
        data = await self.http.get_store_catalog()
        return Store(self, data)

    async def fetch_br_news(self):
        """|coro|
        
        Fetches news for the Battle Royale gamemode.

        Raises
        ------
        HTTPException
            An error occured when requesting.

        Returns
        -------
        :class:`list`
            List[:class:`BattleRoyaleNewsPost`]
        """
        raw = await self.http.get_fortnite_news()
        data = json.loads(raw.encode('utf-8'))

        res = []
        msg = data['battleroyalenews']['news'].get('message')
        if msg is not None:
            res.append(BattleRoyaleNewsPost(msg))
        else:
            msgs = data['battleroyalenews']['news']['messages']
            for msg in msgs:
                res.append(BattleRoyaleNewsPost(msg))
        return res

    async def fetch_br_playlists(self):
        """|coro|
        
        Fetches all playlists registered on Fortnite. This includes all previous gamemodes
        that is no longer active.
        
        Raises
        ------
        HTTPException
            An error occured while requesting.
        
        Returns
        -------
        List[:class:`Playlist`]
            List containing all playlists registered on Fortnite.
        """
        data = await self.http.get_fortnite_content()

        raw = data['playlistinformation']['playlist_info']['playlists']
        playlists = []
        for playlist in raw:
            try:
                p = Playlist(playlist)
                playlists.append(p)
            except KeyError:
                pass
        return playlists

    async def fetch_active_ltms(self, region):
        """|coro|
        
        Fetches active LTMs for a specific region.
        
        Parameters
        ----------
        :class:`Regions`
            The region to request active LTMs for.
            
        Raises
        ------
        HTTPException
            An error occured while requesting.
            
        Returns
        -------
        List[:class:`str`]
            List of internal playlist names.
        """
        data = await self.http.get_fortnite_timeline()

        states = data['channels']['client-matchmaking']['states']
        region_data = states[len(states) - 1]['state']['region'][region.value]
        return region_data.get('eventFlagsForcedOn', [])
