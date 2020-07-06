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

import datetime
import asyncio
import sys
import signal
import logging

from bs4 import BeautifulSoup
from OpenSSL.SSL import SysCallError
from aioxmpp import JID
from typing import Union, Optional, Any, Awaitable, Callable, Dict, List

from .errors import (PartyError, HTTPException, PurchaseException,
                     NotFound, Forbidden, DuplicateFriendship,
                     FriendshipRequestAlreadySent)
from .xmpp import XMPPClient
from .http import HTTPClient
from .user import (ClientUser, User, BlockedUser, SacSearchEntryUser,
                   ProfileSearchEntryUser)
from .friend import Friend, PendingFriend
from .enums import (Platform, Region, ProfileSearchPlatform,
                    SeasonStartTimestamp, SeasonEndTimestamp)
from .cache import Cache
from .party import (DefaultPartyConfig, DefaultPartyMemberConfig, ClientParty)
from .stats import StatsV2
from .store import Store
from .news import BattleRoyaleNewsPost
from .playlist import Playlist
from .presence import Presence
from .auth import RefreshTokenAuth
from .kairos import Avatar, get_random_default_avatar
from .typedefs import MaybeCoro, DatetimeOrTimestamp, StrOrInt

log = logging.getLogger(__name__)


# all credit for this function goes to discord.py.
def _cancel_tasks(loop: asyncio.AbstractEventLoop) -> None:
    task_retriever = asyncio.Task.all_tasks
    tasks = {t for t in task_retriever(loop=loop) if not t.done()}

    if not tasks:
        return

    log.info('Cleaning up after %d tasks.', len(tasks))
    for task in tasks:
        task.cancel()

    loop.run_until_complete(
        asyncio.gather(*tasks, loop=loop, return_exceptions=True)
    )
    log.info('All tasks finished cancelling.')

    for task in tasks:
        if task.cancelled():
            continue
        if task.exception() is not None:
            loop.call_exception_handler({
                'message': 'Unhandled exception during run shutdown.',
                'exception': task.exception(),
                'task': task
            })


def _cleanup_loop(loop: asyncio.AbstractEventLoop) -> None:
    try:
        _cancel_tasks(loop)
        if sys.version_info >= (3, 6):
            loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        log.info('Closing the event loop.')
        loop.close()


async def _start_client(client: 'Client', *,
                        shutdown_on_error: bool = True,
                        after: Optional[MaybeCoro] = None
                        ) -> None:
    loop = asyncio.get_event_loop()

    if not isinstance(client, Client):
        raise TypeError('client must be an instance of fortnitepy.Client')

    async def starter():
        try:
            await client.start()
        except Exception as e:
            return e

    tasks = (
        loop.create_task(starter()),
        loop.create_task(client.wait_until_ready())
    )
    try:
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED
        )
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
    else:
        done_task = done.pop()
        e = done_task.result()
        if e is not None:
            identifier = client.auth.identifier

            if shutdown_on_error:
                if e.args:
                    e.args = ('{0} - {1}'.format(identifier, e.args[0]),)
                else:
                    e.args = (identifier,)

                raise e
            else:
                message = ('An exception occured while running client '
                           '{0}'.format(identifier))
                return loop.call_exception_handler({
                    'message': message,
                    'exception': e,
                    'task': done_task
                })

        if after:
            if asyncio.iscoroutinefunction(after):
                asyncio.ensure_future(after(client), loop=loop)
            else:
                after(client)

        await pending.pop()


async def start_multiple(clients: List['Client'], *,
                         gap_timeout: float = 0.2,
                         shutdown_on_error: bool = True,
                         ready_callback: Optional[MaybeCoro] = None,
                         all_ready_callback: Optional[MaybeCoro] = None
                         ) -> None:
    """|coro|

    Starts multiple clients at the same time.

    .. warning::

        This function is blocking and should be the last function to run.

    .. info::

        Due to throttling by epicgames on login, the clients are started
        with a 0.2 second gap. You can change this value with the gap_timeout
        keyword argument.

    Parameters
    ----------
    clients: List[:class:`Client`]
        A list of the clients you wish to start.
    gap_timeout: :class:`float`
        The time to sleep between starting clients. Defaults to ``0.2``.
    shutdown_on_error: :class:`bool`
        If the function should cancel all other start tasks if one of the
        tasks fails.
    ready_callback: Optional[Union[Callable[:class:`Client`], Awaitable[:class:`Client`]]]
        A callable/async callback taking a single parameter ``client``. 
        The callback is called whenever a client is ready.
    all_ready_callback: Optional[Union[Callable, Awaitable]]
        A callback/async callback that is called whenever all clients are ready.

    Raises
    ------
    AuthException
        Raised if invalid credentials in any form was passed or some
        other misc failure.
    HTTPException
        A request error occured while logging in.
    """  # noqa
    loop = asyncio.get_event_loop()

    async def all_ready_callback_runner():
        tasks = [loop.create_task(client.wait_until_ready())
                 for client in clients]
        await asyncio.gather(*tasks)

        log.info('All clients started.')

        if all_ready_callback:
            if asyncio.iscoroutinefunction(all_ready_callback):
                asyncio.ensure_future(all_ready_callback(), loop=loop)
            else:
                all_ready_callback()

    asyncio.ensure_future(all_ready_callback_runner())

    tasks = {}
    for i, client in enumerate(clients, 1):
        tasks[client] = loop.create_task(_start_client(
            client,
            shutdown_on_error=shutdown_on_error,
            after=ready_callback
        ))

        # sleeping between starting to avoid throttling
        if i < len(clients):
            await asyncio.sleep(gap_timeout)

    log.debug('Starting all clients')
    return_when = (asyncio.FIRST_EXCEPTION
                   if shutdown_on_error
                   else asyncio.ALL_COMPLETED)
    done, pending = await asyncio.wait(
        list(tasks.values()),
        return_when=return_when
    )

    done_task = done.pop()
    if pending and done_task.exception() is not None:
        raise done_task.exception()


async def close_multiple(clients: List['Client']) -> None:
    """|coro|

    Closes multiple clients at the same time by calling :meth:`Client.close()`
    on all of them.

    Parameters
    ----------
    clients: List[:class:`Client`]
        A list of the clients you wish to close.
    """
    loop = asyncio.get_event_loop()

    tasks = [loop.create_task(client.close())
             for client in clients if not client._closing]
    await asyncio.gather(*tasks)


def run_multiple(clients: List['Client'], *,
                 gap_timeout: float = 0.2,
                 shutdown_on_error: bool = True,
                 ready_callback: Optional[MaybeCoro] = None,
                 all_ready_callback: Optional[MaybeCoro] = None) -> None:
    """This function sets up a loop and then calls :func:`start_multiple()`
    for you. If you already have a running event loop, you should start
    the clients with :func:`start_multiple()`. On shutdown, all clients
    will be closed gracefully.

    .. warning::

        This function is blocking and should be the last function to run.

    .. info::

        Due to throttling by epicgames on login, the clients are started
        with a 0.2 second gap. You can change this value with the gap_timeout
        keyword argument.

    Parameters
    ----------
    clients: List[:class:`Client`]
        A list of the clients you wish to start.
    gap_timeout: :class:`float`
        The time to sleep between starting clients. Defaults to ``0.2``.
    shutdown_on_error: :class:`bool`
        If the function should shut down all other start tasks gracefully if
        one of the tasks fails.
    ready_callback: Optional[Union[Callable[:class:`Client`], Awaitable[:class:`Client`]]]
        A callable/async callback taking a single parameter ``client``. 
        The callback is called whenever a client is ready.
    all_ready_callback: Optional[Union[Callable, Awaitable]]
        A callback/async callback that is called whenever all clients are
        ready.

    Raises
    ------
    AuthException
        Raised if invalid credentials in any form was passed or some
        other misc failure.
    HTTPException
        A request error occured while logging in.
    """  # noqa
    loop = asyncio.get_event_loop()
    _closing = False
    _stopped = False

    def close(*args):
        nonlocal _closing

        def stopper(*argss):
            nonlocal _stopped
            if not _stopped:
                loop.stop()
                _stopped = True

        if not _closing:
            _closing = True
            fut = asyncio.ensure_future(close_multiple(clients))
            fut.add_done_callback(stopper)

    try:
        loop.add_signal_handler(signal.SIGINT, close)
        loop.add_signal_handler(signal.SIGTERM, close)
    except NotImplementedError:
        pass

    async def runner():
        await start_multiple(
            clients,
            gap_timeout=gap_timeout,
            shutdown_on_error=shutdown_on_error,
            ready_callback=ready_callback,
            all_ready_callback=all_ready_callback,
        )

    future = asyncio.ensure_future(runner(), loop=loop)
    future.add_done_callback(close)

    try:
        loop.run_forever()
    except KeyboardInterrupt:

        if not _stopped:
            loop.run_until_complete(close_multiple(clients))
    finally:
        future.remove_done_callback(close)

        log.info('Cleaning up loop')
        _cleanup_loop(loop)

    if not future.cancelled():
        return future.result()


class LockEvent(asyncio.Lock):
    def __init__(self, loop=None):
        super().__init__(loop=loop)

        self._event = asyncio.Event()
        self.wait = self._event.wait

    async def acquire(self):
        self._event.clear()
        await super().acquire()

    def release(self):
        self._event.set()
        super().release()


class Client:
    """Represents the client connected to Fortnite and EpicGames' services.

    Parameters
    ----------
    auth: :class:`Auth`
        The authentication method to use. You can read more about available authentication methods
        :ref:`here <authentication>`.
    loop: Optional[:class:`asyncio.AbstractEventLoop`]
        The event loop to use for asynchronous operations.
    status: :class:`str`
        The status you want the client to send with its presence to friends.
        Defaults to: ``Battle Royale Lobby - {party playercount} / {party max playercount}``
    platform: :class:`.Platform`
        The platform you want the client to display as its source.
        Defaults to :attr:`Platform.WINDOWS`.
    net_cl: :class:`str`
        The current net cl used by the current Fortnite build. Named **netCL**
        in official logs. Defaults to an empty string which is the recommended
        usage as of ``v0.9.0`` since you then
        won't need to update it when a new update is pushed by Fortnite.
    default_party_config: :class:`DefaultPartyConfig`
        The party configuration used when creating parties. If not specified,
        the client will use the default values specified in the data class.
    default_party_member_config: :class:`DefaultPartyMemberConfig`
        The party member configuration used when creating parties. If not specified,
        the client will use the default values specified in the data class.
    build: :class:`str`
        The build used by Fortnite.
        Defaults to a valid but maybe outdated value.
    os: :class:`str`
        The os version string to use in the user agent.
        Defaults to ``Windows/10.0.17134.1.768.64bit`` which is valid no
        matter which platform you have set.
    service_host: :class:`str`
        The host used by Fortnite's XMPP services.
    service_domain: :class:`str`
        The domain used by Fortnite's XMPP services.
    serivce_port: :class:`int`
        The port used by Fortnite's XMPP services.

    Attributes
    ----------
    loop: :class:`asyncio.AbstractEventLoop`
        The event loop that client implements.
    user: :class:`ClientUser`
        The user the client is logged in as.
    party: :class:`ClientParty`
        The party the client is currently connected to.
    """  # noqa

    def __init__(self, auth, *,
                 loop: Optional[asyncio.AbstractEventLoop] = None,
                 cache_users: bool = True,
                 **kwargs: Any) -> None:

        self.loop = loop or asyncio.get_event_loop()
        self.cache_users = cache_users

        self.status = kwargs.get('status', 'Battle Royale Lobby - {party_size} / {party_max_size}')  # noqa
        self.avatar = kwargs.get('avatar', get_random_default_avatar())  # noqa
        self.platform = kwargs.get('platform', Platform.WINDOWS)
        self.net_cl = kwargs.get('net_cl', '')
        self.party_build_id = '1:1:{0.net_cl}'.format(self)
        self.default_party_config = kwargs.get('default_party_config', DefaultPartyConfig())  # noqa
        self.default_party_member_config = kwargs.get('default_party_member_config', DefaultPartyMemberConfig())  # noqa
        self.build = kwargs.get('build', '++Fortnite+Release-12.50-CL-13193885')  # noqa
        self.os = kwargs.get('os', 'Windows/10.0.17134.1.768.64bit')

        self.service_host = kwargs.get('xmpp_host', 'prod.ol.epicgames.com')
        self.service_domain = kwargs.get('xmpp_domain', 'xmpp-service-prod.ol.epicgames.com')  # noqa
        self.service_port = kwargs.get('xmpp_port', 5222)

        self.kill_other_sessions = True
        self.accept_eula = True
        self.event_prefix = 'event_'

        self.auth = auth
        self.auth.initialize(self)
        self.http = HTTPClient(self, connector=kwargs.get('connector'))
        self.http.add_header('Accept-Language', 'en-EN')
        self.xmpp = None
        self.party = None

        self._listeners = {}
        self._events = {}
        self._friends = Cache()
        self._pending_friends = Cache()
        self._users = Cache()
        self._blocked_users = Cache()
        self._presences = Cache()
        self._ready = asyncio.Event(loop=self.loop)
        self._leave_lock = asyncio.Lock(loop=self.loop)
        self._join_party_lock = LockEvent(loop=self.loop)
        self._refresh_task = None
        self._start_runner_task = None
        self._closed = False
        self._closing = False
        self._restarting = False
        self._first_start = True

        self._join_confirmation = False

        self.setup_internal()

    @staticmethod
    def from_iso(iso: str) -> datetime.datetime:
        """:class:`str`: Converts an iso formatted string to a
        :class:`datetime.datetime` object

        Returns
        -------
        :class:`datetime.datetime`
        """
        if isinstance(iso, datetime.datetime):
            return iso

        try:
            return datetime.datetime.strptime(iso, '%Y-%m-%dT%H:%M:%S.%fZ')
        except ValueError:
            return datetime.datetime.strptime(iso, '%Y-%m-%dT%H:%M:%SZ')

    @staticmethod
    def to_iso(dt: str) -> datetime.datetime:
        """:class:`datetime.datetime`: Converts a :class:`datetime.datetime`
        object to an iso formatted string

        Returns
        -------
        :class:`str`
        """
        iso = dt.strftime('%Y-%m-%dT%H:%M:%S.%f')

        # fortnite's services expect three digit precision on millis
        return iso[:23] + 'Z'

    @property
    def default_party_config(self) -> DefaultPartyConfig:
        return self._default_party_config

    @default_party_config.setter
    def default_party_config(self, obj: DefaultPartyConfig) -> None:
        obj._inject_client(self)
        self._default_party_config = obj

    @property
    def default_party_member_config(self) -> DefaultPartyMemberConfig:
        return self._default_party_member_config

    @default_party_member_config.setter
    def default_party_member_config(self, o: DefaultPartyMemberConfig) -> None:
        self._default_party_member_config = o

    @property
    def friends(self) -> Dict[str, Friend]:
        """Dict[:class:`str`, :class:`Friends`]: Mapping of current friends."""
        return self._friends._cache

    @property
    def pending_friends(self) -> Dict[str, PendingFriend]:
        """Dict[:class:`str`, :class:`PendingFriend`]: Mapping of currently
        pending friends.

        .. note::

            Pending friends can be both inbound (pending friend sent the
            request to the bot) or outgoing (the bot sent the request to the
            pending friend).
        """
        return self._pending_friends._cache

    @property
    def blocked_users(self) -> Dict[str, BlockedUser]:
        """Dict[:class:`str`, :class:`BlockedUser`]: Mapping of currently
        blocked users.
        """
        return self._blocked_users._cache

    @property
    def presences(self) -> Dict[str, Presence]:
        """Dict[:class:`str`, :class:`Presence`]: Mapping of the last presence
        received from friends.
        """
        return self._presences._cache

    def _check_party_confirmation(self) -> None:
        k = 'party_member_confirm'
        val = k in self._events and len(self._events[k]) > 0
        if val != self._join_confirmation:
            self._join_confirmation = val
            self.default_party_config.update({'join_confirmation': val})

    def exc_handler(self, loop: asyncio.AbstractEventLoop, ctx: dict) -> None:
        exc = ctx.get('exception')
        message = 'Fatal read error on STARTTLS transport'
        if not (isinstance(exc, SysCallError) and ctx['message'] == message):
            loop.default_exception_handler(ctx)

    def setup_internal(self) -> None:
        logger = logging.getLogger('aioxmpp')
        if logger.getEffectiveLevel() == 30:
            logger.setLevel(level=logging.ERROR)

    def register_methods(self) -> None:
        methods = [func for func in dir(self) if callable(getattr(self, func))]
        for method_name in methods:
            if method_name.startswith(self.event_prefix):
                event = method_name[len(self.event_prefix):]
                func = getattr(self, method_name)
                self.add_event_handler(event, func)

    def run(self) -> None:
        """This function starts the loop and then calls :meth:`start` for you.
        If you have passed an already running event loop to the client, you
        should start the client with :meth:`start`.

        .. warning::

            This function is blocking and should be the last function to run.

        Raises
        ------
        AuthException
            Raised if invalid credentials in any form was passed or some
            other misc failure.
        HTTPException
            A request error occured while logging in.
        """
        loop = self.loop
        _stopped = False

        def stopper(*args):
            nonlocal _stopped

            if not _stopped or not self._closing:
                loop.stop()
                _stopped = True

        async def runner():
            nonlocal _stopped

            try:
                await self.start()
            finally:
                if not self._closing and self.is_ready():
                    await self.close()

        try:
            loop.add_signal_handler(signal.SIGINT, stopper)
            loop.add_signal_handler(signal.SIGTERM, stopper)
        except NotImplementedError:
            pass

        future = asyncio.ensure_future(runner(), loop=loop)
        future.add_done_callback(stopper)

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            log.info('Terminating event loop.')
            _stopped = True
        finally:
            future.remove_done_callback(stopper)
            if not self._closing and self.is_ready():
                log.info('Client not logged out when terminating loop. '
                         'Logging out now.')
                loop.run_until_complete(self.close())

            log.info('Cleaning up loop')
            _cleanup_loop(loop)

        if not future.cancelled():
            return future.result()

    async def start(self, dispatch_ready: bool = True) -> None:
        """|coro|

        Starts the client and logs into the specified user.

        .. warning::

            This functions is blocking and everything after the line calling
            this function will never run! If you are using this function
            instead of :meth:`run` you should always call it after everything
            else. When the client is ready it will dispatch
            :meth:`event_ready`.

        Parameters
        ----------
        dispatch_ready: :class:`bool`
            Whether or not the client should dispatch the ready event when
            ready.

        Raises
        ------
        AuthException
            Raised if invalid credentials in any form was passed or some
            other misc failure.
        HTTPException
            A request error occured while logging in.
        """
        _started_while_restarting = self._restarting

        if self._first_start:
            self.register_methods()
            self._first_start = False

        self._check_party_confirmation()

        self.loop.set_exception_handler(self.exc_handler)
        if self._closed:
            self.http.create_connection()
            self._closed = False

        ret = await self._login()
        if ret is False:
            return

        self._set_ready()
        if dispatch_ready:
            self.dispatch_event('ready')

        self._refresh_task = self.loop.create_task(
            self.auth.run_refresh_loop()
        )
        try:
            await self._refresh_task
        except asyncio.CancelledError:
            pass

        if not _started_while_restarting and self._restarting:
            async def runner():
                while True:
                    await asyncio.sleep(1)

            self._start_runner_task = self.loop.create_task(runner())
            try:
                await self._start_runner_task
            except asyncio.CancelledError:
                pass

    async def account_owns_fortnite(self) -> None:
        entitlements = await self.http.entitlement_get_all()

        for ent in entitlements:
            if (ent['entitlementName'] == 'Fortnite_Free'
                    and ent['active'] is True):
                return True
        return False

    # deprecated as of lately
    async def quick_purchase_fortnite(self) -> None:
        data = await self.http.orderprocessor_quickpurchase()
        status = data.get('quickPurchaseStatus', False)

        if status == 'SUCCESS':
            pass

        elif status == 'CHECKOUT':
            data = await self.http.launcher_website_purchase(
                'fn',
                '09176f4ff7564bbbb499bbe20bd6348f'
            )
            soup = BeautifulSoup(data, 'html.parser')

            token = soup.find(id='purchaseToken')['value']
            data = await self.http.payment_website_order_preview(
                token,
                'fn',
                '09176f4ff7564bbbb499bbe20bd6348f'
            )
            if 'syncToken' not in data:
                pass

            await self.http.payment_website_confirm_order(token, data)

        else:
            raise PurchaseException(
                'Could not purchase Fortnite. Reason: '
                'Unknown status {0}'.format(status)
            )

        log.debug('Purchase of Fortnite successfully processed.')

    async def _login(self) -> None:
        log.debug('Running authenticating')
        ret = await self.auth._authenticate()
        if ret is False:
            return False

        tasks = [
            self.http.account_get_by_user_id(self.auth.account_id),
            self.http.account_graphql_get_clients_external_auths(),
            self.http.account_get_external_auths_by_id(self.auth.account_id),
        ]

        data, ext_data, extra_ext_data, *_ = await asyncio.gather(*tasks)
        data['externalAuths'] = ext_data['myAccount']['externalAuths'] or []
        data['extraExternalAuths'] = extra_ext_data
        self.user = ClientUser(self, data)

        state_fut = asyncio.ensure_future(self.initialize_states(),
                                          loop=self.loop)

        if self.accept_eula:
            await self.auth.accept_eula()
            log.debug('EULA accepted')

        await state_fut

        self.xmpp = XMPPClient(self)
        await self.xmpp.run()
        log.debug('Connected to XMPP')

        await self.initialize_party()
        log.debug('Party created')

    async def _close(self, *,
                     close_http: bool = True,
                     dispatch_close: bool = True) -> None:
        self._closing = True

        try:
            if self.party is not None:
                await self.party._leave()
        except Exception:
            pass

        try:
            await self.xmpp.close()
        except Exception:
            pass

        async def killer(token):
            if token is None:
                return

            try:
                await self.http.account_sessions_kill_token(token)
            except HTTPException:
                # All exchanged sessions should be killed when the original
                # session is killed, but this doesn't seem to be consistant.
                # The solution is to attempt to kill each token and then just
                # catch 401.
                pass

        if not self._restarting:
            tasks = (
                killer(getattr(self.auth, 'ios_access_token', None)),
                killer(getattr(self.auth, 'launcher_access_token', None)),
                killer(getattr(self.auth, 'access_token', None)),
            )
            await asyncio.gather(*tasks)

        self._friends.clear()
        self._pending_friends.clear()
        self._users.clear()
        self._blocked_users.clear()
        self._presences.clear()
        self._ready.clear()

        if close_http:
            await self.http.close()
            self._closed = True

        if (self._refresh_task is not None
                and not self._refresh_task.cancelled()):
            self._refresh_task.cancel()

        if not self._restarting:
            if (self._start_runner_task is not None
                    and not self._start_runner_task.cancelled()):
                self._start_runner_task.cancel()

        self._closing = False
        log.debug('Successfully logged out')

    async def close(self, *,
                    close_http: bool = True,
                    dispatch_close: bool = True) -> None:
        """|coro|

        Logs the user out and closes running services.

        Parameters
        ----------
        close_http: :class:`bool`
            Whether or not to close the clients :class:`aiohttp.ClientSession`
            when logged out.
        dispatch_close: :class:`bool`
            Whether or not to dispatch the close event.

        Raises
        ------
        HTTPException
            An error occured while logging out.
        """
        if dispatch_close:
            await self.dispatch_and_wait_event('close')

        await self._close(
            close_http=close_http,
            dispatch_close=dispatch_close
        )

    def is_closed(self) -> bool:
        """:class:`bool`: Whether the client is running or not."""
        return self._closed

    async def restart(self) -> None:
        """|coro|

        Restarts the client completely. All events received while this method
        runs are dispatched when it has finished.

        Raises
        ------
        AuthException
            Raised if invalid credentials in any form was passed or some
            other misc failure.
        HTTPException
            A request error occured while logging in.
        """
        self._restarting = True
        ios_refresh_token = self.auth.ios_refresh_token

        asyncio.ensure_future(self.recover_events(), loop=self.loop)
        await self.close(close_http=False, dispatch_close=False)

        auth = RefreshTokenAuth(
            refresh_token=ios_refresh_token
        )
        auth.initialize(self)
        self.auth = auth

        async def runner():
            try:
                await self.start(dispatch_ready=False)
            except Exception as e:
                return e

        tasks = (
            self.loop.create_task(runner()),
            self.loop.create_task(self.wait_until_ready()),
        )
        d, p = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        done_task = d.pop()
        if done_task.result() is not None:
            p.pop().cancel()
            raise done_task.result()

        self.dispatch_event('restart')
        self._restarting = False

    async def recover_events(self) -> None:
        await self.wait_for('xmpp_session_close')
        pre_friends = self.friends
        pre_pending = self.pending_friends
        await self.wait_for('xmpp_session_establish')

        for friend in pre_friends.values():
            if friend.id not in self.friends:
                self.dispatch_event('friend_remove', friend)

        added_friends = []
        for friend in self.friends.values():
            if friend.id not in pre_friends:
                added_friends.append(friend.id)
                self.dispatch_event('friend_add', friend)

        for pending in pre_pending.values():
            if (pending.id not in self.pending_friends
                    and pending.id not in added_friends):
                self.dispatch_event('friend_request_abort', pending)

        for pending in self.pending_friends.values():
            if pending.id not in pre_pending:
                self.dispatch_event('friend_request', pending)

    def _set_ready(self) -> None:
        self._ready.set()

    def is_ready(self) -> bool:
        """Specifies if the internal state of the client is ready.

        Returns
        -------
        :class:`bool`
            ``True`` if the internal state is ready else ``False``
        """
        return self._ready.is_set()

    async def wait_until_ready(self) -> None:
        """|coro|

        Waits until the internal state of the client is ready.
        """
        await self._ready.wait()

    def construct_party(self, data, *, cls=None):
        clazz = cls or self.default_party_config.cls
        return clazz(self, data)

    async def initialize_party(self) -> None:
        data = await self.http.party_lookup_user(self.user.id)
        if len(data['current']) > 0:
            party = self.construct_party(data['current'][0])
            await party._leave()
            log.debug('Left old party')

        await self._create_party()

    async def fetch_profile_by_display_name(self, display_name, *,
                                            cache: bool = False,
                                            raw: bool = False
                                            ) -> Optional[User]:
        """|coro|

        Fetches a profile from the passed display name

        Parameters
        ----------
        display_name: :class:`str`
            The display name of the user you want to fetch the profile for.
        cache: :class:`bool`
            If set to True it will try to get the profile from the friends or
            user cache.

            .. note::

                Setting this parameter to False will make it an api call.

        raw: :class:`bool`
            If set to True it will return the data as you would get it from
            the api request.

            .. note::

                Setting raw to True does not work with cache set to True.

        Raises
        ------
        HTTPException
            An error occured while requesting the user.

        Returns
        -------
        Optional[:class:`User`]
            The user requested. If not found it will return ``None``.
        """
        if cache:
            for u in self._users._cache.values():
                try:
                    if u.display_name.casefold() == display_name.casefold():
                        return u
                except AttributeError:
                    pass

        res = await self.http.account_graphql_get_by_display_name(display_name)
        accounts = res['account']
        if len(accounts) == 0:
            return None

        epic_accounts = [d for d in accounts if d['displayName'] is not None]
        if epic_accounts:
            account = max(epic_accounts, key=lambda d: len(d['externalAuths']))
        else:
            account = accounts[0]

        if raw:
            return account
        return self.store_user(account, try_cache=cache)

    async def fetch_profiles_by_display_name(self, display_name, *,
                                             raw: bool = False
                                             ) -> Optional[User]:
        """|coro|

        Fetches all users including external users (accounts from other
        platforms) that matches the given the display name.

        .. warning::

            This function is not for requesting multiple profiles by multiple
            display names. Use :meth:`Client.fetch_profile()` for that.

        Parameters
        ----------
        display_name: :class:`str`
            The display name of the profiles you want to get.

        raw: :class:`bool`
            If set to True it will return the data as you would get it from
            the api request. *Defaults to ``False``*

        Raises
        ------
        HTTPException
            An error occured while requesting the user.

        Returns
        -------
        List[:class:`User`]
            A list containing all payloads found for this user.
        """
        res = await self.http.account_graphql_get_by_display_name(display_name)
        return [User(self, account) for account in res['account']]

    async def fetch_profile(self, user, *,
                            cache: bool = False,
                            raw: bool = False
                            ) -> Optional[User]:
        """|coro|

        Fetches a single profile by the given id/displayname

        Parameters
        ----------
        user: :class:`str`
            Id or display name
        cache: :class:`bool`
            If set to True it will try to get the profile from the friends or
            user cache and fall back to an api request if not found.

            .. note::

                Setting this parameter to False will make it an api call.

        raw: :class:`bool`
            If set to True it will return the data as you would get it from
            the api request.

            .. note::

                Setting raw to True does not work with cache set to True.

        Raises
        ------
        HTTPException
            An error occured while requesting the user.

        Returns
        -------
        Optional[:class:`User`]
            The user requested. If not found it will return ``None``
        """
        try:
            data = await self.fetch_profiles((user,), cache=cache, raw=raw)
            return data[0]
        except IndexError:
            return None

    async def fetch_profiles(self, users, *,
                             cache: bool = False,
                             raw: bool = False) -> List[User]:
        """|coro|

        Fetches multiple profiles at once by the given ids/displaynames

        Parameters
        ----------
        users: List[:class:`str`]
            A list/tuple containing ids/displaynames.
        cache: :class:`bool`
            If set to True it will try to get the profiles from the friends or
            user cache and fall back to an api request if not found.

            .. note::

                Setting this parameter to False will make it an api call.

        raw: :class:`bool`
            If set to True it will return the data as you would get it from
            the api request.

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

        def find_by_display_name(dn):
            if cache:
                for u in self._users._cache.values():
                    try:
                        if u.display_name.casefold() == dn.casefold():
                            profiles.append(u)
                            return
                    except AttributeError:
                        pass

            task = self.http.account_graphql_get_by_display_name(elem)
            tasks.append(task)

        for elem in users:
            if self.is_display_name(elem):
                find_by_display_name(elem)
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
            pfs = await asyncio.gather(*tasks)
            for p_data in pfs:
                accounts = p_data['account']
                for account_data in accounts:
                    if account_data['displayName'] is not None:
                        new.append(account_data['id'])
                        break
                else:
                    for account_data in accounts:
                        if account_data['displayName'] is None:
                            new.append(account_data['id'])
                            break

        chunk_tasks = []
        chunks = [new[i:i + 100] for i in range(0, len(new), 100)]
        for chunk in chunks:
            task = self.http.account_graphql_get_multiple_by_user_id(chunk)
            chunk_tasks.append(task)

        if len(chunks) > 0:
            d = await asyncio.gather(*chunk_tasks)
            for results in d:
                for result in results['accounts']:
                    if raw:
                        profiles.append(result)
                    else:
                        u = self.store_user(result, try_cache=cache)
                        profiles.append(u)
        return profiles

    async def fetch_profile_by_email(self, email, *,
                                     cache: bool = False,
                                     raw: bool = False) -> Optional[User]:
        """|coro|

        Fetches a single profile by the email.

        .. warning::

            Because of epicgames throttling policy, you can only do this
            request three times in a timespan of 600 seconds. If you were
            to do more than three requests in that timespan, a
            :exc:`HTTPException` would be raised.

        Parameters
        ----------
        email: :class:`str`
            The email of the account you are requesting.
        cache: :class:`bool`
            If set to True it will try to get the profile from the friends or
            user cache and fall back to an api request if not found.

            .. note::

                This method does two api requests but with this set to False
                only one request will be done as long as the user is found in
                one of the caches.

        raw: :class:`bool`
            If set to True it will return the data as you would get it from
            the api request.

            .. note::

                Setting raw to True does not work with cache set to True.

        Raises
        ------
        HTTPException
            An error occured while requesting the user.

        Returns
        -------
        Optional[:class:`User`]
            The user requested. If not found it will return ``None``
        """
        try:
            res = await self.http.account_get_by_email(email)
        except HTTPException as e:
            m = 'errors.com.epicgames.account.account_not_found'
            if e.message_code == m:
                return None
            raise

        # Request the account data through graphql since the one above returns
        # empty external auths payload.
        account_id = res['id']
        return await self.fetch_profile(account_id, cache=cache, raw=raw)

    async def search_profiles(self, prefix: str,
                              platform: ProfileSearchPlatform
                              ) -> List[ProfileSearchEntryUser]:
        """|coro|

        Searches after profiles by a prefix and returns up to 100 matches.

        Parameters
        ----------
        prefix: :class:`str`
            | The prefix you want to search by. The prefix is case insensitive.
            | Example: ``Tfue`` will return Tfue's profile + up to 99 other
            profiles which have display names that start with or match exactly
            to ``Tfue`` like ``Tfue_Faze dequan``.
        platform: :class:`ProfileSearchPlatform`
            The platform you wish to search by.

            ..note::

                The platform is only important for prefix matches. All exact
                matches are returned regardless of which platform is
                specified.

        Raises
        ------
        HTTPException
            An error occured while requesting.

        Returns
        -------
        List[:class:`ProfileSearchEntryUser`]
            An ordered list of users that matched the prefix.
        """
        if not isinstance(platform, ProfileSearchPlatform):
            raise TypeError(
                'The platform passed must be a constant from '
                'fortnitepy.ProfileSearchPlatform'
            )

        res = await self.http.user_search_by_prefix(
            prefix,
            platform.value
        )

        user_ids = [d['accountId'] for d in res]
        profiles = await self.fetch_profiles(user_ids, raw=True)
        lookup = {p['id']: p for p in profiles}

        entries = []
        for data in res:
            profile_data = lookup.get(data['accountId'])
            if profile_data is None:
                continue

            obj = ProfileSearchEntryUser(self, profile_data, data)
            entries.append(obj)

        return entries

    async def search_sac_by_slug(self, slug: str) -> List[SacSearchEntryUser]:
        """|coro|

        Searches for an owner of slug + retrieves owners of similar slugs.

        Parameters
        ----------
        slug: :class:`str`
            The slug (support a creator code) you wish to search for.

        Raises
        ------
        HTTPException
            An error occured while requesting fortnite's services.

        Returns
        -------
        List[:class:`SacSearchEntryUser`]
            An ordered list of users who matched the exact or slightly
            modified slug.
        """
        res = await self.http.payment_website_search_sac_by_slug(slug)

        user_ids = [e['id'] for e in res]
        profiles = await self.fetch_profiles(
            list(user_ids),
            raw=True
        )
        lookup = {p['id']: p for p in profiles}

        entries = []
        for data in res:
            profile_data = lookup.get(data['id'])
            if profile_data is None:
                continue

            obj = SacSearchEntryUser(self, profile_data, data)
            entries.append(obj)

        return entries

    async def initialize_states(self) -> None:
        tasks = (
            self.http.friends_get_all(include_pending=True),
            self.http.friends_get_summary(),
            self.http.presence_get_last_online(),
        )
        raw_friends, raw_summary, raw_presences = await asyncio.gather(*tasks)

        ids = [r['accountId'] for r in raw_friends + raw_summary['blocklist']]
        profiles = await self.fetch_profiles(ids, raw=True)

        profiles = {profile['id']: profile for profile in profiles}

        for friend in raw_friends:
            if friend['status'] == 'ACCEPTED':
                try:
                    data = profiles[friend['accountId']]
                    self.store_friend({**friend, **data})
                except KeyError:
                    continue

            elif friend['status'] == 'PENDING':
                try:
                    data = profiles[friend['accountId']]
                    self.store_pending_friend({**friend, **data})
                except KeyError:
                    continue

        for data in raw_summary['friends']:
            friend = self.get_friend(data['accountId'])
            if friend is not None:
                friend._update_summary(data)

        for user_id, data in raw_presences.items():
            friend = self.get_friend(user_id)
            if friend is not None:
                try:
                    value = data[0]['last_online']
                except (IndexError, KeyError):
                    value = None

                friend._update_last_logout(
                    self.from_iso(value) if value is not None else None
                )

        for data in raw_summary['blocklist']:
            user = profiles.get(data['accountId'])
            if user is not None:
                self.store_blocked_user(user)

    def store_user(self, data: dict, *, try_cache: bool = True) -> User:
        try:
            user_id = data.get(
                'accountId',
                data.get('id', data.get('account_id'))
            )

            if try_cache:
                return self._users.get(user_id, silent=False)
        except KeyError:
            pass

        u = User(self, data)
        if self.cache_users:
            self._users.set(u.id, u)
        return u

    def get_user(self, user_id: str) -> Optional[User]:
        """Tries to get a user from the user cache by the given user id.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the user.

        Returns
        -------
        Optional[:class:`User`]
            The user if found, else ``None``
        """
        user = self._users.get(user_id)
        if user is None:
            friend = self.get_friend(user_id)
            if friend is not None:
                user = User(self, friend.get_raw())
                if self.cache_users:
                    self._users.set(user.id, user)
        return user

    def store_friend(self, data: dict, *,
                     summary: Optional[dict] = None,
                     try_cache: bool = True) -> Friend:
        try:
            user_id = data.get(
                'accountId',
                data.get('id', data.get('account_id'))
            )
            if try_cache:
                return self._friends.get(user_id, silent=False)
        except KeyError:
            pass

        f = Friend(self, data)
        if summary is not None:
            f._update_summary(summary)
        self._friends.set(f.id, f)
        return f

    def get_friend(self, user_id: str) -> Optional[Friend]:
        """Tries to get a friend from the friend cache by the given user id.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the friend.

        Returns
        -------
        Optional[:class:`Friend`]
            The friend if found, else ``None``
        """
        return self._friends.get(user_id)

    def store_pending_friend(self, data: dict, *,
                             try_cache: bool = True) -> PendingFriend:
        try:
            user_id = data.get(
                'accountId',
                data.get('id', data.get('account_id'))
            )
            if try_cache:
                return self._pending_friends.get(user_id, silent=False)
        except KeyError:
            pass

        pf = PendingFriend(self, data)
        self._pending_friends.set(pf.id, pf)
        return pf

    def get_pending_friend(self, user_id: str) -> Optional[PendingFriend]:
        """Tries to get a pending friend from the pending friend cache by the
        given user id.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the pending friend.

        Returns
        -------
        Optional[:class:`PendingFriend`]
            The pending friend if found, else ``None``
        """
        return self._pending_friends.get(user_id)

    def store_blocked_user(self, data: dict, *,
                           try_cache: bool = True) -> BlockedUser:
        try:
            user_id = data.get(
                'accountId',
                data.get('id', data.get('account_id'))
            )
            if try_cache:
                return self._blocked_users.get(user_id, silent=False)
        except KeyError:
            pass

        bu = BlockedUser(self, data)
        self._blocked_users.set(bu.id, bu)
        return bu

    def get_blocked_user(self, user_id: str) -> Optional[BlockedUser]:
        """Tries to get a blocked user from the blocked users cache by the
        given user id.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the blocked user.

        Returns
        -------
        Optional[:class:`BlockedUser`]
            The blocked user if found, else ``None``
        """
        return self._blocked_users.get(user_id)

    def get_presence(self, user_id: str) -> Optional[Presence]:
        """Tries to get the latest received presence from the presence cache.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the friend you want the last presence of.

        Returns
        -------
        Optional[:class:`Presence`]
            The presence if found, else ``None``
        """
        return self._presences.get(user_id)

    def has_friend(self, user_id: str) -> bool:
        """Checks if the client is friends with the given user id.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the user you want to check.

        Returns
        -------
        :class:`bool`
            ``True`` if user is friends with the client else ``False``
        """
        return self.get_friend(user_id) is not None

    def is_pending(self, user_id: str) -> bool:
        """Checks if the given user id is a pending friend of the client.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the user you want to check.

        Returns
        -------
        :class:`bool`
            ``True`` if user is a pending friend else ``False``
        """
        return self.get_pending_friend(user_id) is not None

    def is_blocked(self, user_id: str) -> bool:
        """Checks if the given user id is blocked by the client.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the user you want to check.

        Returns
        -------
        :class:`bool`
            ``True`` if user is blocked else ``False``
        """
        return self.get_blocked_user(user_id) is not None

    async def fetch_blocklist(self) -> List[str]:
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
        return await self.http.friends_get_blocklist()

    async def block_user(self, user_id: str) -> None:
        """|coro|

        Blocks a user by a given user id.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the user you want to block.

        Raises
        ------
        HTTPException
            Something went wrong when trying to block this user.
        """
        await self.http.friends_block(user_id)

    async def unblock_user(self, user_id: str) -> None:
        """|coro|

        Unblocks a user by a given user id.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the user you want to unblock

        Raises
        ------
        HTTPException
            Something went wrong when trying to unblock this user.
        """
        await self.http.friends_unblock(user_id)

    def is_id(self, value: str) -> bool:
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

    def is_display_name(self, val: str) -> bool:
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

    async def add_friend(self, user_id: str) -> None:
        """|coro|

        Sends a friend request to the specified user id.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the user you want to add.

        Raises
        ------
        NotFound
            The specified user does not exist.
        DuplicateFriendship
            The client is already friends with this user.
        FriendshipRequestAlreadySent
            The client has already sent a friendship request that has not been
            handled yet by the user.
        Forbidden
            The client is not allowed to send friendship requests to the user
            because of the users settings.
        HTTPException
            An error occured while requesting to add this friend.
        """
        try:
            await self.http.friends_add_or_accept(user_id)
        except HTTPException as exc:
            m = 'errors.com.epicgames.friends.account_not_found'
            if exc.message_code == m:
                raise NotFound('The specified account does not exist.')

            m = 'errors.com.epicgames.friends.duplicate_friendship'
            if exc.message_code == m:
                raise DuplicateFriendship('This friendship already exists.')

            m = 'errors.com.epicgames.friends.friend_request_already_sent'
            if exc.message_code == m:
                raise FriendshipRequestAlreadySent(
                    'A friendship request already exists for this user.'
                )

            m = ('errors.com.epicgames.friends.'
                 'cannot_friend_due_to_target_settings')
            if exc.message_code == m:
                raise Forbidden('You cannot send friendship requests to '
                                'this user.')

            raise

    async def accept_friend(self, user_id: str) -> Friend:
        """|coro|

        .. warning::

            Do not use this method to send a friend request. It will then not
            return until the friend request has been accepted by the user.

        Accepts a request.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the user you want to accept.

        Raises
        ------
        NotFound
            The specified user does not exist.
        DuplicateFriendship
            The client is already friends with this user.
        FriendshipRequestAlreadySent
            The client has already sent a friendship request that has not been
            handled yet by the user.
        Forbidden
            The client is not allowed to send friendship requests to the user
            because of the users settings.
        HTTPException
            An error occured while requesting to accept this friend.

        Returns
        -------
        :class:`Friend`
            Object of the friend you just added.
        """
        await self.add_friend(user_id)
        friend = await self.wait_for('friend_add',
                                     check=lambda f: f.id == user_id)
        return friend

    async def remove_or_decline_friend(self, user_id: str) -> None:
        """|coro|

        Removes a friend by the given id.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the friend you want to remove.

        Raises
        ------
        HTTPException
            Something went wrong when trying to remove this friend.
        """
        await self.http.friends_remove_or_decline(user_id)

    # NOTE: Not tested
    async def remove_all_friends(self) -> None:
        """|coro|

        Removes all friends of the client.

        Raises
        ------
        HTTPException
            Something went wrong when requesting fortnite's services.
        """
        await self.http.friends_remove_all()

    async def dispatch_and_wait_event(self, event: str,
                                      *args: Any,
                                      **kwargs: Any) -> None:
        coros = self._events.get(event, [])
        tasks = [coro() for coro in coros]
        if len(tasks) > 0:
            await asyncio.gather(*tasks)

    def _dispatcher(self, coro: Awaitable,
                    *args: Any,
                    **kwargs: Any) -> asyncio.Future:
        return asyncio.ensure_future(coro(*args, **kwargs), loop=self.loop)

    def dispatch_event(self, event: str,
                       *args: Any,
                       **kwargs: Any) -> List[asyncio.Future]:
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

        tasks = []
        if event in self._events:
            for coro in self._events[event]:
                task = self._dispatcher(coro, *args, **kwargs)
                tasks.append(task)

        return tasks

    def wait_for(self, event: str, *,
                 check: Callable = None,
                 timeout: Optional[int] = None) -> Any:
        """|coro|

        Waits for an event to be dispatch.

        In case the event returns more than one arguments, a tuple is passed
        containing the arguments.

        Examples
        --------
        This example waits for the author of a :class:`FriendMessage` to say
        hello.: ::

            @client.event
            async def event_friend_message(message):
                await message.reply('Say hello!')

                def check_function(m):
                    return m.author.id == message.author.id

                msg = await client.wait_for('message', check=check_function, timeout=60)
                await msg.reply('Hello {0.author.display_name}!'.format(msg))

        This example waits for the the leader of a party to promote the bot
        after joining and then sets a new custom key: ::

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

                | The name of the event must be **without** the ``event_``
                prefix.
                |
                | Wrong = ``event_friend_message``.
                | Correct = ``friend_message``.

        check: Optional[Callable]
            A predicate to check what to wait for.
            Defaults to a predicate that always returns ``True``. This means
            it will return the first result unless you pass another predicate.

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
            Returns arguments based on the event you are waiting for. An event
            might return no arguments, one argument or a tuple of arguments.
            Check the :ref:`event reference <fortnitepy-events-api> for more
            information about the returning arguments.`
        """  # noqa
        future = self.loop.create_future()
        if check is None:
            def _check(*args):
                return True
            check = _check

        ev = (event.lower()).replace(self.event_prefix, '')
        try:
            listeners = self._listeners[ev]
        except KeyError:
            listeners = []
            self._listeners[ev] = listeners

        listeners.append((future, check))
        return asyncio.wait_for(future, timeout, loop=self.loop)

    def _event_has_handlers(self, event: str) -> bool:
        handlers = self._events.get(event.lower())
        return handlers is not None and len(handlers) > 0

    def add_event_handler(self, event: str, coro: Awaitable[Any]) -> None:
        """Registers a coroutine as an event handler. You can register as many
        coroutines as you want to a single event.

        Parameters
        ----------
        event: :class:`str`
            The name of the event you want to register this coro for.
        coro: :ref:`coroutine <coroutine>`
            The coroutine to function as the handler for the specified event.

        Raises
        ------
        TypeError
            The function passed to coro is not a coroutine.
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('event registered must be a coroutine function')

        if event.startswith(self.event_prefix):
            event = event[len(self.event_prefix):]

        if event not in self._events:
            self._events[event] = []
        self._events[event].append(coro)

    def remove_event_handler(self, event: str, coro: Awaitable) -> None:
        """Removes a coroutine as an event handler.

        Parameters
        ----------
        event: :class:`str`
            The name of the event you want to remove this coro for.
        coro: :ref:`coroutine <coroutine>`
            The coroutine that already functions as a handler for the
            specified event.
        """
        if event not in self._events:
            return

        self._events[event] = [c for c in self._events[event] if c != coro]

    def event(self,
              event_or_coro: Union[str, Awaitable[Any]] = None) -> Awaitable:
        """A decorator to register an event.

        .. note::

            You do not need to decorate events in a subclass of :class:`Client`
            but the function names of event handlers must follow this format
            ``event_<event>``.

        Usage: ::

            @client.event
            async def event_friend_message(message):
                await message.reply('Thanks for your message!')

            @client.event('friend_message')
            async def my_message_handler(message):
                await message.reply('Thanks for your message!')

        Raises
        ------
        TypeError
            The decorated function is not a coroutine.
        TypeError
            Event is not specified as argument or function name with event
            prefix.
        """
        is_coro = callable(event_or_coro)

        def pred(coro):
            if isinstance(coro, staticmethod):
                coro = coro.__func__

            if not asyncio.iscoroutinefunction(coro):
                raise TypeError('the decorated function must be a coroutine')

            if is_coro or event_or_coro is None:
                if not coro.__name__.startswith(self.event_prefix):
                    raise TypeError('non specified events must follow '
                                    'this function name format: '
                                    '"{}<event>"'.format(self.event_prefix))

                name = coro.__name__[len(self.event_prefix):]
            else:
                name = event_or_coro

            self.add_event_handler(name, coro)
            log.debug('{} has been registered as a handler for the '
                      'event {}'.format(coro.__name__, name))
            return coro
        return pred(event_or_coro) if is_coro else pred

    async def fetch_br_stats(self, user_id: str, *,
                             start_time: Optional[DatetimeOrTimestamp] = None,
                             end_time: Optional[DatetimeOrTimestamp] = None
                             ) -> StatsV2:
        """|coro|

        Gets Battle Royale stats the specified user.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the user you want to fetch stats for.
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
            | The user has chosen to be hidden from public stats by disabling
            the fortnite setting below.
            |  ``Settings`` -> ``Account and Privacy`` -> ``Show on career
            leaderboard``
        HTTPException
            An error occured while requesting.

        Returns
        -------
        :class:`StatsV2`
            An object representing the stats for this user. If the user was
            not found ``None`` is returned.
        """  # noqa
        epoch = datetime.datetime.utcfromtimestamp(0)
        if isinstance(start_time, datetime.datetime):
            start_time = int((start_time - epoch).total_seconds())
        elif isinstance(start_time, SeasonStartTimestamp):
            start_time = start_time.value

        if isinstance(end_time, datetime.datetime):
            end_time = int((end_time - epoch).total_seconds())
        elif isinstance(end_time, SeasonEndTimestamp):
            end_time = end_time.value

        tasks = [
            self.fetch_profile(user_id, cache=True),
            self.http.stats_get_v2(
                user_id,
                start_time=start_time,
                end_time=end_time
            )
        ]
        results = await asyncio.gather(*tasks)
        if results[1] == '':
            raise Forbidden('This user has chosen to be hidden '
                            'from public stats.')

        return StatsV2(*results) if results[0] is not None else None

    async def _multiple_stats_chunk_requester(self, user_ids: List[str],
                                              stats: List[str],
                                              start_time: Optional[DatetimeOrTimestamp] = None,  # noqa
                                              end_time: Optional[DatetimeOrTimestamp] = None  # noqa
                                              ) -> List[dict]:
        chunks = [user_ids[i:i+51] for i in range(0, len(user_ids), 51)]

        tasks = []
        for chunk in chunks:
            tasks.append(self.http.stats_get_mutliple_v2(
                chunk,
                stats,
                start_time=start_time,
                end_time=end_time
            ))

        results = await asyncio.gather(*tasks)
        return [item for sub in results for item in sub]

    async def fetch_multiple_br_stats(self, user_ids: List[str],
                                      stats: List[str],
                                      *,
                                      start_time: Optional[DatetimeOrTimestamp] = None,  # noqa
                                      end_time: Optional[DatetimeOrTimestamp] = None  # noqa
                                      ) -> Dict[str, StatsV2]:
        """|coro|

        Gets Battle Royale stats for multiple users at the same time.

        .. note::

            This function is not the same as doing :meth:`fetch_br_stats` for
            multiple users. The expected return for this function would not be
            all the stats for the specified users but rather the stats you
            specify.

        Example usage: ::

            async def stat_function():
                stats = [
                    fortnitepy.StatsV2.create_stat('placetop1', fortnitepy.V2Input.KEYBOARDANDMOUSE, 'defaultsolo'),
                    fortnitepy.StatsV2.create_stat('kills', fortnitepy.V2Input.KEYBOARDANDMOUSE, 'defaultsolo'),
                    fortnitepy.StatsV2.create_stat('matchesplayed', fortnitepy.V2Input.KEYBOARDANDMOUSE, 'defaultsolo')
                ]

                # get the profiles and create a list of their ids.
                profiles = await self.fetch_profiles(['Ninja', 'Dark', 'DrLupo'])
                user_ids = [u.id for u in profiles] + ['NonValidUserIdForTesting']

                data = await self.fetch_multiple_br_stats(user_ids=user_ids, stats=stats)
                for id, res in data.items():
                    if res is not None:
                        print('ID: {0} | Stats: {1}'.format(id, res.get_stats()))
                    else:
                        print('ID: {0} not found.'.format(id))

            # Example output:
            # ID: 463ca9d604524ce38071f512baa9cd70 | Stats: {'keyboardmouse': {'defaultsolo': {'wins': 759, 'kills': 28093, 'matchesplayed': 6438}}}
            # ID: 3900c5958e4b4553907b2b32e86e03f8 | Stats: {'keyboardmouse': {'defaultsolo': {'wins': 1763, 'kills': 41375, 'matchesplayed': 7944}}}
            # ID: 4735ce9132924caf8a5b17789b40f79c | Stats: {'keyboardmouse': {'defaultsolo': {'wins': 1888, 'kills': 40784, 'matchesplayed': 5775}}}
            # ID: NonValidUserIdForTesting not found.

        Parameters
        ----------
        user_ids: List[:class:`str`]
            A list of ids you are requesting the stats for.
        stats: List[:class:`str`]
            A list of stats to get for the users. Use
            :meth:`StatsV2.create_stat` to create the stats.

            Example: ::

                [
                    fortnitepy.StatsV2.create_stat('placetop1', fortnitepy.V2Input.KEYBOARDANDMOUSE, 'defaultsolo'),
                    fortnitepy.StatsV2.create_stat('kills', fortnitepy.V2Input.KEYBOARDANDMOUSE, 'defaultsolo'),
                    fortnitepy.StatsV2.create_stat('matchesplayed', fortnitepy.V2Input.KEYBOARDANDMOUSE, 'defaultsolo')
                ]

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
        HTTPException
            An error occured while requesting.

        Returns
        -------
        Dict[:class:`str`, :class:`StatsV2`]
            A mapping where :class:`StatsV2` is bound to its owners id. If a
            userid was not found then the value bound to that userid will be
            ``None``.
        """  # noqa
        epoch = datetime.datetime.utcfromtimestamp(0)
        if isinstance(start_time, datetime.datetime):
            start_time = int((start_time - epoch).total_seconds())
        elif isinstance(start_time, SeasonStartTimestamp):
            start_time = start_time.value

        if isinstance(end_time, datetime.datetime):
            end_time = int((end_time - epoch).total_seconds())
        elif isinstance(end_time, SeasonEndTimestamp):
            end_time = end_time.value

        tasks = [
            self.fetch_profiles(user_ids, cache=True),
            self._multiple_stats_chunk_requester(
                user_ids,
                stats,
                start_time=start_time,
                end_time=end_time
            )
        ]
        results = await asyncio.gather(*tasks)
        if len(results[0]) > 0 and isinstance(results[0][0], dict):
            results = results[::-1]

        res = {}
        for udata in results[1]:
            r = [x for x in results[0] if x.id == udata['accountId']]
            user = r[0] if len(r) != 0 else None
            res[udata['accountId']] = (StatsV2(user, udata)
                                       if user is not None else None)
        return res

    async def fetch_multiple_battlepass_levels(self,
                                               users: List[str],
                                               *,
                                               start_time: Optional[DatetimeOrTimestamp] = None,  # noqa
                                               end_time: Optional[DatetimeOrTimestamp] = None  # noqa
                                               ) -> Dict[str, float]:
        """|coro|

        Fetches multiple users battlepass level.

        Parameters
        ----------
        users: List[:class:`str`]
            List of user ids.
        start_time: Optional[Union[:class:`int`, :class:`datetime.datetime`, :class:`SeasonStartTimestamp`]]
            The UTC start time of the window to get the battlepass level from.
            *Must be seconds since epoch, :class:`datetime.datetime` or a constant from SeasonEndTimestamp*
            *Defaults to None*
        end_time: Optional[Union[:class:`int`, :class:`datetime.datetime`, :class:`SeasonEndTimestamp`]]
            The UTC end time of the window to get the battlepass level from.
            *Must be seconds since epoch, :class:`datetime.datetime` or a constant from SeasonEndTimestamp*
            *Defaults to None*

        .. note::

            If neither start_time nor end_time is ``None`` (default), then
            the battlepass level from the current season is fetched.

        Raises
        ------
        HTTPException
            An error occured while requesting.

        Returns
        -------
        Dict[:class:`str`, :class:`float`]
            Users battlepass level mapped to their account id. Returns ``None``
            if no battlepass level was found. If a user has career board set
            to private, he/she will not appear in the result. Therefore you
            should never expect a user to be included.
        """  # noqa
        epoch = datetime.datetime.utcfromtimestamp(0)
        if isinstance(start_time, datetime.datetime):
            start_time = int((start_time - epoch).total_seconds())
        elif isinstance(start_time, SeasonStartTimestamp):
            start_time = start_time.value

        if isinstance(end_time, datetime.datetime):
            end_time = int((end_time - epoch).total_seconds())
        elif isinstance(end_time, SeasonEndTimestamp):
            end_time = end_time.value

        data = await self._multiple_stats_chunk_requester(
            users,
            ('s11_social_bp_level',),
            start_time=start_time,
            end_time=end_time
        )

        return {e['accountId']: e['stats'].get('s11_social_bp_level', None)
                for e in data}

    async def fetch_battlepass_level(self, user_id: str, *,
                                     start_time: Optional[DatetimeOrTimestamp] = None,  # noqa
                                     end_time: Optional[DatetimeOrTimestamp] = None  # noqa
                                     ) -> float:
        """|coro|

        Fetches a users battlepass level.

        Parameters
        ----------
        user_id: :class:`str`
            The user id to fetch the battlepass level for.
        start_time: Optional[Union[:class:`int`, :class:`datetime.datetime`, :class:`SeasonStartTimestamp`]]
            The UTC start time of the window to get the battlepass level from.
            *Must be seconds since epoch, :class:`datetime.datetime` or a constant from SeasonEndTimestamp*
            *Defaults to None*
        end_time: Optional[Union[:class:`int`, :class:`datetime.datetime`, :class:`SeasonEndTimestamp`]]
            The UTC end time of the window to get the battlepass level from.
            *Must be seconds since epoch, :class:`datetime.datetime` or a constant from SeasonEndTimestamp*
            *Defaults to None*

        .. note::

            If neither start_time nor end_time is ``None`` (default), then
            the battlepass level from the current season is fetched.

        Raises
        ------
        Forbidden
            User has private career board.
        HTTPException
            An error occured while requesting.

        Returns
        -------
        :class:`float`
            The users battlepass level.
        """  # noqa
        data = await self.fetch_multiple_battlepass_levels(
            (user_id,),
            start_time=start_time,
            end_time=end_time
        )
        if user_id not in data:
            raise Forbidden('User has private career board.')

        return data[user_id]

    async def fetch_leaderboard(self, stat: str) -> List[Dict[str, StrOrInt]]:
        """|coro|

        Fetches the leaderboard for a stat.

        .. warning::

            For some weird reason, the only valid stat you can pass is
            one with ``placetop1`` (``wins`` is also accepted).

        Example usage: ::

            async def get_leaderboard():
                stat = fortnitepy.StatsV2.create_stat(
                    'wins',
                    fortnitepy.V2Input.KEYBOARDANDMOUSE,
                    'defaultsquad'
                )

                data = await client.fetch_leaderboard(stat)

                for placement, entry in enumerate(data):
                    print('[{0}] Id: {1} | Wins: {2}'.format(
                        placement, entry['account'], entry['value']))

        Parameters
        ----------
        stat: :class:`str`
            The stat you are requesting the leaderboard entries for. You can
            use :meth:`StatsV2.create_stat` to create this string.

        Raises
        ------
        ValueError
            You passed an invalid/non-accepted stat argument.
        HTTPException
            An error occured when requesting.

        Returns
        -------
        List[Dict[:class:`str`, Union[:class:`str`, :class:`int`]]]
            List of dictionaries containing entry data. Example return: ::

                {
                    'account': '4480a7397f824fe4b407077fb9397fbb',
                    'value': 5082
                }
        """
        data = await self.http.stats_get_leaderboard_v2(stat)

        if len(data['entries']) == 0:
            raise ValueError('{0} is not a valid stat'.format(stat))

        return data['entries']

    async def _create_party(self,
                            config: Optional[dict] = None) -> ClientParty:
        aquiring = not self.auth._refresh_lock.locked()
        try:
            if aquiring:
                await self._join_party_lock.acquire()

            if isinstance(config, dict):
                cf = {**self.default_party_config.config, **config}
            else:
                cf = self.default_party_config.config

            while True:
                try:
                    data = await self.http.party_create(cf)
                    break
                except HTTPException as exc:
                    if exc.message_code != ('errors.com.epicgames.social.'
                                            'party.user_has_party'):
                        raise

                    data = await self.http.party_lookup_user(self.user.id)
                    async with self._leave_lock:
                        try:
                            await self.http.party_leave(
                                data['current'][0]['id']
                            )
                        except HTTPException as e:
                            m = ('errors.com.epicgames.social.'
                                 'party.party_not_found')
                            if e.message_code != m:
                                raise

                    await self.xmpp.leave_muc()

            config = {**cf, **data['config']}
            party = self.construct_party(data)
            await party._update_members(members=data['members'])
            self.party = party

            tasks = [
                self.loop.create_task(party.join_chat()),
            ]
            await party.meta.meta_ready_event.wait()

            updated, deleted = party.meta.set_privacy(config['privacy'])
            tasks.append(party.patch(
                updated={**updated, **party.construct_squad_assignments()},
                deleted=deleted
            ))
            await asyncio.gather(*tasks)

            return party

        finally:
            if aquiring:
                self._join_party_lock.release()

    def is_creating_party(self) -> bool:
        return self._join_party_lock.locked()

    async def join_to_party(self, party_id: str, *,
                            check_private: bool = True) -> ClientParty:
        """|coro|

        Joins a party by the party id.

        Parameters
        ----------
        party_id: :class:`str`
            The id of the party you wish to join.
        check_private: :class:`bool`
            | Whether or not to check if the party is private before joining.
            | Defaults to ``True``.

        Raises
        ------
        PartyError
            You are already a member of this party.
        NotFound
            The party was not found.
        Forbidden
            You attempted to join a private party with ``check_party`` set to
            ``True``.
        Forbidden
            You have no right to join this party. This exception is only
            raised if ``check_party`` is set to ``False``.

            .. warning::

                Since the client has to leave its current party before joining
                another one, a new party is automatically created if this
                error is raised. Use ``check_private`` with caution.

        Returns
        -------
        :class:`ClientParty`
            The party that was just joined.
        """
        async with self._join_party_lock:
            if party_id == self.party.id:
                raise PartyError('You are already a member of this party.')

            try:
                party_data = await self.http.party_lookup(party_id)
            except HTTPException as e:
                if e.message_code == ('errors.com.epicgames.social.'
                                      'party.party_not_found'):
                    raise NotFound(
                        'Could not find a party with the id {0}'.format(
                            party_id
                        )
                    )
                raise

            if check_private:
                if party_data['config']['joinability'] == 'INVITE_AND_FORMER':
                    raise Forbidden('You can\'t join a private party.')

            await self.party._leave()
            party = self.construct_party(party_data)
            self.party = party

            future = asyncio.ensure_future(self.wait_for(
                'party_member_join',
                check=lambda m: m.id == self.user.id and party.id == m.party.id
            ), loop=self.loop)

            try:
                await self.http.party_join_request(party_id)
            except HTTPException as e:
                if not future.cancelled():
                    future.cancel()

                await self._create_party()

                if e.message_code == ('errors.com.epicgames.social.'
                                      'party.party_join_forbidden'):
                    raise Forbidden('Client has no right to join this party.')
                raise

            party_data = await self.http.party_lookup(party_id)
            party = self.construct_party(party_data)
            self.party = party
            asyncio.ensure_future(party.join_chat(), loop=self.loop)
            await party._update_members(party_data['members'])

            try:
                await future
            except asyncio.TimeoutError:
                pass

            return party

    async def set_status(self, status: str) -> None:
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

    async def send_status(self, status: str, *,
                          to: Optional[JID] = None) -> None:
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

    def set_avatar(self, avatar: Avatar) -> None:
        """Sets the client's avatar and updates it for all friends.

        Parameters
        ----------
        avatar: :class:`Avatar`
            The avatar to set.
        """
        self.avatar = avatar
        self.party.update_presence()

    async def fetch_lightswitch_status(self,
                                       service_id: str = 'Fortnite') -> bool:
        """|coro|

        Fetches the lightswitch status of an epicgames service.

        Parameters
        ----------
        service_id: :class:`str`
            The service id to check status for.

        Raises
        ------
        ValueError
            The returned data was empty. Most likely because service_id is not
            valid.
        HTTPException
            An error occured when requesting.

        Returns
        -------
        :class:`bool`
            ``True`` if service is up else ``False``
        """
        status = await self.http.lightswitch_get_status(service_id=service_id)
        if len(status) == 0:
            raise ValueError('emtpy lightswitch response')
        return True if status[0].get('status') == 'UP' else False

    async def fetch_item_shop(self) -> Store:
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
        data = await self.http.fortnite_get_store_catalog()
        return Store(self, data)

    async def fetch_br_news(self) -> List[BattleRoyaleNewsPost]:
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
        data = await self.http.fortnitecontent_get()

        res = []
        msg = data['battleroyalenews']['news'].get('message')
        if msg is not None:
            res.append(BattleRoyaleNewsPost(msg))
        else:
            msgs = data['battleroyalenews']['news']['messages']
            for msg in msgs:
                res.append(BattleRoyaleNewsPost(msg))
        return res

    async def fetch_br_playlists(self) -> List[Playlist]:
        """|coro|

        Fetches all playlists registered on Fortnite. This includes all
        previous gamemodes that is no longer active.

        Raises
        ------
        HTTPException
            An error occured while requesting.

        Returns
        -------
        List[:class:`Playlist`]
            List containing all playlists registered on Fortnite.
        """
        data = await self.http.fortnitecontent_get()

        raw = data['playlistinformation']['playlist_info']['playlists']
        playlists = []
        for playlist in raw:
            try:
                p = Playlist(playlist)
                playlists.append(p)
            except KeyError:
                pass
        return playlists

    async def fetch_active_ltms(self, region: Region) -> List[str]:
        """|coro|

        Fetches active LTMs for a specific region.

        Parameters
        ----------
        region: :class:`Region`
            The region to request active LTMs for.

        Raises
        ------
        HTTPException
            An error occured while requesting.

        Returns
        -------
        List[:class:`str`]
            List of internal playlist names. Returns an empty list of none
            LTMs are for the specified region.
        """
        data = await self.http.fortnite_get_timeline()

        states = data['channels']['client-matchmaking']['states']
        region_data = states[len(states) - 1]['state']['region'].get(
            region.value, {})
        return region_data.get('eventFlagsForcedOn', [])
