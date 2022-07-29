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
import asyncio
import logging
import time

from aioxmpp import JID
from aiohttp import BaseConnector
from typing import (Iterable, Union, Optional, Any, Awaitable, Callable, Dict,
                    List, Tuple)

from .errors import (PartyError, HTTPException, NotFound, Forbidden,
                     DuplicateFriendship, FriendshipRequestAlreadySent,
                     MaxFriendshipsExceeded, InviteeMaxFriendshipsExceeded,
                     InviteeMaxFriendshipRequestsExceeded, PartyIsFull)
from .xmpp import XMPPClient
from .http import HTTPClient
from .user import (ClientUser, User, BlockedUser, SacSearchEntryUser,
                   UserSearchEntry)
from .friend import Friend, IncomingPendingFriend, OutgoingPendingFriend
from .enums import (Platform, Region, UserSearchPlatform, AwayStatus,
                    SeasonStartTimestamp, SeasonEndTimestamp,
                    BattlePassStat, StatsCollectionType)
from .party import (DefaultPartyConfig, DefaultPartyMemberConfig, ClientParty,
                    Party)
from .stats import StatsV2, StatsCollection, _StatsBase
from .store import Store
from .news import BattleRoyaleNewsPost
from .playlist import Playlist
from .presence import Presence
from .auth import Auth, RefreshTokenAuth
from .avatar import Avatar
from .typedefs import MaybeCoro, DatetimeOrTimestamp, StrOrInt
from .utils import LockEvent, MaybeLock, from_iso, is_display_name

log = logging.getLogger(__name__)


class StartContext:
    def __init__(self, client: 'Client', dispatch_ready: bool = True) -> None:
        self.client = client
        self.dispatch_ready = dispatch_ready

    async def start(self) -> asyncio.Task:
        await self.client.init()
        task = asyncio.create_task(
            self.client._start(dispatch_ready=self.dispatch_ready)
        )

        await self.client.wait_until_ready()
        return task

    async def __aenter__(self) -> asyncio.Task:
        return await self.start()

    async def __aexit__(self, *args) -> None:
        if not self.client._closing and not self.client._closed:
            await self.client.close()

    def __await__(self) -> None:
        async def awaiter():
            task = await self.start()
            return await task

        return awaiter().__await__()


async def _start_client(client: 'Client', *,
                        shutdown_on_error: bool = True,
                        after: Optional[MaybeCoro] = None,
                        error_after: Optional[MaybeCoro] = None,
                        ) -> None:
    loop = asyncio.get_running_loop()

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
            await client.close()

            identifier = client.auth.identifier

            if shutdown_on_error:
                if e.args:
                    e.args = ('{0} - {1}'.format(identifier, e.args[0]),)
                else:
                    e.args = (identifier,)

                raise e
            else:
                if error_after is not None:
                    if asyncio.iscoroutinefunction(after):
                        asyncio.ensure_future(error_after(client, e))
                    else:
                        error_after(client, e)
                    return

                message = ('An exception occured while running client '
                           '{0}'.format(identifier))
                return loop.call_exception_handler({
                    'message': message,
                    'exception': e,
                    'task': done_task
                })

        if after:
            if asyncio.iscoroutinefunction(after):
                asyncio.ensure_future(after(client))
            else:
                after(client)

        await pending.pop()


def _before_event(callback):
    event = asyncio.Event()
    is_processing = False

    async def processor():
        nonlocal is_processing

        if not is_processing:
            is_processing = True
            try:
                await callback()
            finally:
                event.set()
        else:
            await event.wait()

    return processor


async def start_multiple(clients: List['Client'], *,
                         gap_timeout: float = 0.2,
                         shutdown_on_error: bool = True,
                         ready_callback: Optional[MaybeCoro] = None,
                         error_callback: Optional[MaybeCoro] = None,
                         all_ready_callback: Optional[MaybeCoro] = None,
                         before_start: Optional[Awaitable] = None,
                         before_close: Optional[Awaitable] = None
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
        tasks fails. You can catch the error by try excepting.
    ready_callback: Optional[Union[Callable[:class:`Client`], Awaitable[:class:`Client`]]]
        A callable/async callback taking a single parameter ``client``. 
        The callback is called whenever a client is ready.
    error_callback: Optional[Union[Callable[:class:`Client`, Exception], Awaitable[:class:`Client`, Exception]]]
        A callable/async callback taking two parameters, :class:`Client`
        and an exception. The callback is called whenever a client fails
        logging in. The callback is not called if ``shutdown_on_error`` is
        ``True``.
    all_ready_callback: Optional[Union[Callable, Awaitable]]
        A callback/async callback that is called whenever all clients
        have finished logging in, regardless if one of the clients failed
        logging in. That means that the callback is always called when all
        clients are either logged in or raised an error.
    before_start: Optional[Awaitable]
        An async callback that is called when just before the clients are
        beginning to start. This must be a coroutine as all the clients
        wait to start until this callback is finished processing so you
        can do heavy start stuff like opening database connections, sessions
        etc.
    before_close: Optional[Awaitable]
        An async callback that is called when the clients are beginning to
        close. This must be a coroutine as all the clients wait to close until
        this callback is finished processing so you can do heavy close stuff
        like closing database connections, sessions etc.

    Raises
    ------
    AuthException
        Raised if invalid credentials in any form was passed or some
        other misc failure.
    ValueError
        Two or more clients with the same authentication identifier was
        passed. This means that you attemted to start two or more clients
        with the same credentials.
    HTTPException
        A request error occured while logging in.
    """  # noqa
    loop = asyncio.get_running_loop()

    async def waiter(client):
        _, pending = await asyncio.wait(
            (client.wait_until_ready(), client.wait_until_closed()),
            return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()

    async def all_ready_callback_runner():
        tasks = [loop.create_task(waiter(client))
                 for client in clients]
        await asyncio.gather(*tasks)

        if all(client.is_closed() for client in clients):
            return

        log.info('All clients started.')

        if all_ready_callback:
            if asyncio.iscoroutinefunction(all_ready_callback):
                asyncio.ensure_future(all_ready_callback())
            else:
                all_ready_callback()

    # Do a check to see if any duplicate clients have been passed
    identifiers = []
    for client in clients:
        identifier = client.auth.identifier
        if identifier in identifiers:
            raise ValueError(
                'Two or more clients with the same auth identifier was passed.'
                ' Identifier = {}'.format(repr(identifier))
            )

        identifiers.append(identifier)

    await asyncio.gather(*[client.init() for client in clients])

    asyncio.ensure_future(all_ready_callback_runner())

    _before_start = _before_event(before_start)
    _before_close = _before_event(before_close)

    tasks = {}
    for i, client in enumerate(clients, 1):
        tasks[client] = loop.create_task(_start_client(
            client,
            shutdown_on_error=shutdown_on_error,
            after=ready_callback,
            error_after=error_callback
        ))

        if before_start is not None:
            client.add_event_handler('before_start', _before_start)
        if before_close is not None:
            client.add_event_handler('before_close', _before_close)

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


async def close_multiple(clients: Iterable['Client']) -> None:
    """|coro|

    Closes multiple clients at the same time by calling :meth:`Client.close()`
    on all of them.

    Parameters
    ----------
    clients: Iterable[:class:`Client`]
        An iterable of the clients you wish to close. If a client is already
        closing or closed, it will get skipped without raising an error.
    """
    loop = asyncio.get_running_loop()

    tasks = [
        loop.create_task(client.close()) for client in clients
        if not client._closing and not client.is_closed()
    ]
    await asyncio.gather(*tasks)


def run_multiple(clients: List['Client'], *,
                 gap_timeout: float = 0.2,
                 shutdown_on_error: bool = True,
                 ready_callback: Optional[MaybeCoro] = None,
                 error_callback: Optional[MaybeCoro] = None,
                 all_ready_callback: Optional[MaybeCoro] = None,
                 before_start: Optional[Awaitable] = None,
                 before_close: Optional[Awaitable] = None
                 ) -> None:
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
        If the function should cancel all other start tasks if one of the
        tasks fails. You can catch the error by try excepting.
    ready_callback: Optional[Union[Callable[:class:`Client`], Awaitable[:class:`Client`]]]
        A callable/async callback taking a single parameter ``client``. 
        The callback is called whenever a client is ready.
    error_callback: Optional[Union[Callable[:class:`Client`, Exception], Awaitable[:class:`Client`, Exception]]]
        A callable/async callback taking two parameters, :class:`Client`
        and an exception. The callback is called whenever a client fails
        logging in. The callback is not called if ``shutdown_on_error`` is
        ``True``.
    all_ready_callback: Optional[Union[Callable, Awaitable]]
        A callback/async callback that is called whenever all clients
        have finished logging in, regardless if one of the clients failed
        logging in. That means that the callback is always called when all
        clients are either logged in or raised an error.
    before_start: Optional[Awaitable]
        An async callback that is called when just before the clients are
        beginning to start. This must be a coroutine as all the clients
        wait to start until this callback is finished processing so you
        can do heavy start stuff like opening database connections, sessions
        etc.
    before_close: Optional[Awaitable]
        An async callback that is called when the clients are beginning to
        close. This must be a coroutine as all the clients wait to close until
        this callback is finished processing so you can do heavy close stuff
        like closing database connections, sessions etc.

    Raises
    ------
    AuthException
        Raised if invalid credentials in any form was passed or some
        other misc failure.
    HTTPException
        A request error occured while logging in.
    """  # noqa
    async def runner():
        try:
            await start_multiple(
                clients,
                gap_timeout=gap_timeout,
                shutdown_on_error=shutdown_on_error,
                ready_callback=ready_callback,
                error_callback=error_callback,
                all_ready_callback=all_ready_callback,
                before_start=before_start,
                before_close=before_close,
            )
        finally:
            await close_multiple(clients)

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        pass


class BasicClient:
    """Represents a basic stripped down version of :class:`Client`. You
    might want to use this client if your only goal is to make simple
    requests like user or stats fetching.

    This client does **not** support the following:
      - Parties (except :meth:`Client.fetch_party()`)
      - Friends
      - Anything related to XMPP (Messaging and most events)

    Supported events by this client:
      - :meth:`event_ready()`
      - :meth:`event_before_start()`
      - :meth:`event_before_close()`
      - :meth:`event_restart()`
      - :meth:`event_device_auth_generate()`
      - :meth:`event_auth_refresh()`

    Parameters
    ----------
    auth: :class:`Auth`
        The authentication method to use. You can read more about available
        authentication methods :ref:`here <authentication>`.
    http_connector: :class:`aiohttp.BaseConnector`
        The connector to use for http connection pooling.
    http_retry_config: Optional[:class:`HTTPRetryConfig`]
        The config to use for http retries.
    build: :class:`str`
        The build used by Fortnite.
        Defaults to a valid but maybe outdated value.
    os: :class:`str`
        The os version string to use in the user agent.
        Defaults to ``Windows/10.0.17134.1.768.64bit`` which is valid no
        matter which platform you have set.
    cache_users: :class:`bool`
        Whether or not the library should cache :class:`User` objects. Disable
        this if you are running a program with lots of users as this could
        potentially take a big hit on the memory usage. Defaults to ``True``.

    Attributes
    ----------
    user: :class:`ClientUser`
        The user the client is logged in as.
    """  # noqa

    def __init__(self, auth: Auth,
                 **kwargs: Any) -> None:
        self.cache_users = kwargs.get('cache_users', True)
        self.build = kwargs.get('build', '++Fortnite+Release-14.10-CL-14288110')  # noqa
        self.os = kwargs.get('os', 'Windows/10.0.17134.1.768.64bit')

        self.kill_other_sessions = True
        self.accept_eula = True
        self.event_prefix = 'event_'

        self.auth = auth
        self.http = HTTPClient(
            self,
            connector=kwargs.get('http_connector'),
            retry_config=kwargs.get('http_retry_config')
        )
        self.http.add_header('Accept-Language', 'en-EN')

        self._listeners = {}
        self._events = {}
        self._users = {}
        self._refresh_times = []

        self._exception_future = None
        self._ready_event = None
        self._closed_event = None
        self._reauth_lock = None

        self._refresh_task = None
        self._start_runner_task = None
        self._closed = False
        self._closing = False
        self._restarting = False
        self._first_start = True
        self._has_async_init = False

        self.setup_internal()

    async def _async_init(self) -> None:
        # We must deal with loop stuff after a loop has been
        # created by asyncio.run(). This is called at the start
        # of start().

        self.loop = asyncio.get_running_loop()

        self._exception_future = self.loop.create_future()
        self._ready_event = asyncio.Event()
        self._closed_event = asyncio.Event()
        self._reauth_lock = LockEvent()
        self._reauth_lock.failed = False

        self.auth.initialize(self)

    def register_connectors(self,
                            http_connector: Optional[BaseConnector] = None
                            ) -> None:
        """This can be used to register a http connector after the client has
        already been initialized. It must however be called before
        :meth:`start()` has been called, or in :meth:`event_before_start()`.

        .. warning::

            Connectors passed will not be closed on shutdown. You must close
            them yourself if you want a graceful shutdown.

        Parameters
        ----------
        http_connector: :class:`aiohttp.BaseConnector`
            The connector to use for the http session.
        """
        if http_connector is not None:
            if self.http.connection_exists():
                raise RuntimeError(
                    'http_connector must be registered before startup.')

            self.http.connector = http_connector

    def setup_internal(self) -> None:
        logger = logging.getLogger('aioxmpp')
        if logger.getEffectiveLevel() == 30:
            logger.setLevel(level=logging.ERROR)

    def register_methods(self) -> None:
        methods = (func for func in dir(self) if callable(getattr(self, func)))
        for method_name in methods:
            if method_name.startswith(self.event_prefix):
                event = method_name[len(self.event_prefix):]
                func = getattr(self, method_name)
                self.add_event_handler(event, func)

    async def init(self) -> None:
        if not self._has_async_init:
            self._has_async_init = True
            await self._async_init()

    def run(self) -> None:
        """This function starts the loop and then calls :meth:`start` for you.
        If your program already has an asyncio loop setup, you should use
        :meth:`start()` instead.

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

        async def runner():
            async with self.start() as start_future:
                await start_future

        try:
            asyncio.run(runner())
        except KeyboardInterrupt:
            # StartContext automatically closes for us, so we just catch
            # the KeyboardInterrupt wihtout doing anything more here.
            pass

    def start(self, dispatch_ready: bool = True) -> StartContext:
        """|coro|

        Starts the client and logs into the specified user.

        This method can be used as a coroutine or an async context manager,
        depending on your needs.

        How to use as an async context manager: ::
            async with client.start():
                user = await client.fetch_user('Ninja')
                print(user.display_name)

        If you want to use it as an async context manager, but also keep the
        client running forever, you can await the return of start like this: ::
            async with client.start() as future:
                user = await client.fetch_user('Ninja')
                print(user.display_name)

                await future  # Nothing after this line will run.

        .. warning::

            This method is blocking if you await it as a coroutine or you
            await the return future. This means that no code coming after
            will run until the client is closed. When the client is ready
            it will dispatch :meth:`event_ready`.

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
        return StartContext(self, dispatch_ready=dispatch_ready)

    async def _start(self, dispatch_ready: bool = True) -> None:
        await self.init()

        if self._first_start:
            self.register_methods()

            if dispatch_ready:
                await self.dispatch_and_wait_event('before_start')

            # Do this after before_start() in case any connectors
            # are registered during the execution.
            self.http.create_connection()

            self._first_start = False

        _started_while_restarting = self._restarting
        pri = self._reauth_lock.priority if _started_while_restarting else 0

        self._closed_event.clear()

        if self._closed:
            self.http.create_connection()
            self._closed = False

        ret = await self._login(priority=pri)
        if ret is False:
            return

        self._set_ready()
        if dispatch_ready:
            self.dispatch_event('ready')

        async def waiter(task):
            done, _ = await asyncio.wait(
                (task, self._exception_future),
                return_when=asyncio.FIRST_COMPLETED
            )
            try:
                exc = done.pop().exception()
            except asyncio.CancelledError:
                pass
            else:
                raise exc

        self._refresh_task = self.loop.create_task(
            self.auth.run_refresh_loop()
        )
        await waiter(self._refresh_task)

        if not _started_while_restarting and self._restarting:
            async def runner():
                await self.loop.create_future()

            self._start_runner_task = self.loop.create_task(runner())
            await waiter(self._start_runner_task)

    async def _setup_client_user(self, priority: int = 0):
        tasks = [
            self.http.account_get_by_user_id(
                self.auth.account_id,
                priority=priority
            ),
            self.http.account_graphql_get_clients_external_auths(
                priority=priority
            ),
            self.http.account_get_external_auths_by_id(
                self.auth.account_id,
                priority=priority
            ),
        ]

        data, ext_data, extra_ext_data, *_ = await asyncio.gather(*tasks)
        data['externalAuths'] = ext_data['myAccount']['externalAuths'] or []
        data['extraExternalAuths'] = extra_ext_data
        self.user = ClientUser(self, data)

    async def _login(self, priority: int = 0) -> None:
        log.debug('Running authenticating')
        ret = await self.auth._authenticate(priority=priority)
        if ret is False:
            return False

        await self._setup_client_user(priority=priority)

        if self.auth.eula_check_needed() and self.accept_eula:
            await self.auth.accept_eula(
                priority=priority
            )
            log.debug('EULA accepted')

    async def _kill_tokens(self) -> None:
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
                killer(getattr(self.auth, 'access_token', None)),
            )
            await asyncio.gather(*tasks)

    def _clear_caches(self) -> None:
        self._users.clear()

    async def _close(self, *,
                     close_http: bool = True,
                     dispatch_close: bool = True,
                     priority: int = 0) -> None:
        self._closing = True

        await self._kill_tokens()
        self._clear_caches()

        if self._ready_event is not None:
            self._ready_event.clear()

        if close_http:
            self._closed = True
            await self.http.close()

        if self.auth.refresh_loop_running():
            self._refresh_task.cancel()

        if not self._restarting:
            if (self._start_runner_task is not None
                    and not self._start_runner_task.cancelled()):
                self._start_runner_task.cancel()

        self._closing = False

        if dispatch_close and self._closed_event is not None:
            self._set_closed()

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
            await asyncio.gather(
                self.dispatch_and_wait_event('before_close'),
                self.dispatch_and_wait_event('close'),
            )

        await self._close(
            close_http=close_http,
            dispatch_close=dispatch_close
        )

    def is_closed(self) -> bool:
        """:class:`bool`: Whether the client is running or not."""
        return self._closed

    def can_restart(self) -> bool:
        return hasattr(self.auth, 'ios_refresh_token')

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
        self._reauth_lock.priority += 1
        priority = self._reauth_lock.priority
        async with MaybeLock(self._reauth_lock):
            self._restarting = True

            self._refresh_times.append(time.time())
            ios_refresh_token = self.auth.ios_refresh_token

            self.recover_events()
            await self._close(
                close_http=False,
                dispatch_close=False,
                priority=priority
            )

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
            d, p = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )

            done_task = d.pop()
            if done_task.result() is not None:
                p.pop().cancel()
                raise done_task.result()

            self.dispatch_event('restart')
            self._restarting = False
            log.debug('Successully restarted the client.')

    def recover_events(self) -> None:
        pass

    def _set_ready(self) -> None:
        self._ready_event.set()

    def _set_closed(self) -> None:
        self._closed_event.set()

    def is_ready(self) -> bool:
        """Specifies if the internal state of the client is ready.

        Returns
        -------
        :class:`bool`
            ``True`` if the internal state is ready else ``False``
        """
        return self._ready_event.is_set()

    async def wait_until_ready(self) -> None:
        """|coro|

        Waits until the internal state of the client is ready.
        """
        if self._ready_event is not None:
            await self._ready_event.wait()
        else:
            raise RuntimeError(
                'The client has not been fully initialized. Make sure '
                'Client.init() has been called before using this method.'
            )

    async def wait_until_closed(self) -> None:
        """|coro|

        Waits until the client is fully closed.
        """
        if self._closed_event is not None:
            await self._closed_event.wait()
        else:
            raise RuntimeError(
                'The client has not been fully initialized. Make sure '
                'Client.init() has been called before using this method.'
            )

    async def fetch_user_by_display_name(self, display_name: str, *,
                                         cache: bool = False,
                                         raw: bool = False
                                         ) -> Optional[User]:
        """|coro|

        Fetches a user from the passed display name.

        Parameters
        ----------
        display_name: :class:`str`
            The display name of the user you want to fetch the user for.
        cache: :class:`bool`
            If set to True it will try to get the user from the friends or
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
            for u in self._users.values():
                try:
                    if u.display_name is not None:
                        if u.display_name.casefold() == display_name.casefold():  # noqa
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

    async def fetch_users_by_display_name(self, display_name: str, *,
                                          raw: bool = False
                                          ) -> Optional[User]:
        """|coro|

        Fetches all users including external users (accounts from other
        platforms) that matches the given the display name.

        .. warning::

            This function is not for requesting multiple users by multiple
            display names. Use :meth:`Client.fetch_user()` for that.

        Parameters
        ----------
        display_name: :class:`str`
            The display name of the users you want to get.

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
        if raw:
            return res['account']

        return [User(self, account) for account in res['account']]

    async def fetch_user(self, user, *,
                         cache: bool = False,
                         raw: bool = False
                         ) -> Optional[User]:
        """|coro|

        Fetches a single user by the given id/displayname.

        Parameters
        ----------
        user: :class:`str`
            Id or display name
        cache: :class:`bool`
            If set to True it will try to get the user from the friends or
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
            data = await self.fetch_users((user,), cache=cache, raw=raw)
            return data[0]
        except IndexError:
            return None

    async def fetch_users(self, users: Iterable[str], *,
                          cache: bool = False,
                          raw: bool = False) -> List[User]:
        """|coro|

        Fetches multiple users at once by the given ids/displaynames.

        Parameters
        ----------
        users: Iterable[:class:`str`]
            An iterable containing ids/displaynames.
        cache: :class:`bool`
            If set to True it will try to get the users from the friends or
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
        _users = []
        new = []
        tasks = []

        def find_by_display_name(dn):
            if cache:
                for u in self._users.values():
                    try:
                        if u.display_name is not None:
                            if u.display_name.casefold() == dn.casefold():
                                _users.append(u)
                                return
                    except AttributeError:
                        pass

            task = self.http.account_graphql_get_by_display_name(elem)
            tasks.append(task)

        for elem in users:
            if is_display_name(elem):
                find_by_display_name(elem)
            else:
                if cache:
                    p = self.get_user(elem)
                    if p:
                        if raw:
                            _users.append(p.get_raw())
                        else:
                            _users.append(p)
                        continue
                new.append(elem)

        if not _users and not new and not tasks:
            return []

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
        chunks = (new[i:i + 100] for i in range(0, len(new), 100))
        for chunk in chunks:
            task = self.http.account_graphql_get_multiple_by_user_id(chunk)
            chunk_tasks.append(task)

        if len(chunk_tasks) > 0:
            d = await asyncio.gather(*chunk_tasks)
            for results in d:
                for result in results['accounts']:
                    if raw:
                        _users.append(result)
                    else:
                        u = self.store_user(result, try_cache=cache)
                        _users.append(u)
        return _users

    async def fetch_user_by_email(self, email, *,
                                  cache: bool = False,
                                  raw: bool = False) -> Optional[User]:
        """|coro|

        Fetches a single user by the email.

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
            If set to True it will try to get the user from the friends or
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
        return await self.fetch_user(account_id, cache=cache, raw=raw)

    async def search_users(self, prefix: str,
                           platform: UserSearchPlatform
                           ) -> List[UserSearchEntry]:
        """|coro|

        Searches after users by a prefix and returns up to 100 matches.

        Parameters
        ----------
        prefix: :class:`str`
            | The prefix you want to search by. The prefix is case insensitive.
            | Example: ``Tfue`` will return Tfue's user + up to 99 other
            users which have display names that start with or match exactly
            to ``Tfue`` like ``Tfue_Faze dequan``.
        platform: :class:`UserSearchPlatform`
            The platform you wish to search by.

            .. note::

                The platform is only important for prefix matches. All exact
                matches are returned regardless of which platform is
                specified.

        Raises
        ------
        HTTPException
            An error occured while requesting.

        Returns
        -------
        List[:class:`UserSearchEntry`]
            An ordered list of users that matched the prefix.
        """
        if not isinstance(platform, UserSearchPlatform):
            raise TypeError(
                'The platform passed must be a constant from '
                'fortnitepy.UserSearchPlatform'
            )

        res = await self.http.user_search_by_prefix(
            self.user.id,
            prefix,
            platform.value
        )

        user_ids = (d['accountId'] for d in res)
        users = await self.fetch_users(user_ids, raw=True)
        lookup = {p['id']: p for p in users}

        entries = []
        for data in res:
            user_data = lookup.get(data['accountId'])
            if user_data is None:
                continue

            obj = UserSearchEntry(self, user_data, data)
            entries.append(obj)

        return entries

    async def fetch_avatars(self, users: List[str]) -> Dict[str, Avatar]:
        """|coro|

        Fetches the avatars of the provided user ids.

        .. warning::
            You can only fetch avatars of friends. That means that the bot has
            to be friends with the users you are requesting the avatars of.

        Parameters
        ----------
        users: List[:class:`str`]
            A list containing user ids.

        Raises
        ------
        HTTPException
            An error occured while requesting.

        Returns
        -------
        Dict[:class:`str`, :class:`Avatar`]
            A dict containing avatars mapped to their user id.
        """
        chunk_tasks = []
        chunks = (users[i:i + 100] for i in range(0, len(users), 100))
        for chunk in chunks:
            task = self.http.avatar_get_multiple_by_user_id(chunk)
            chunk_tasks.append(task)

        results = {}
        if len(chunk_tasks) > 0:
            d = await asyncio.gather(*chunk_tasks)
            for chunk_results in d:
                for avatar_data in chunk_results:
                    results[avatar_data['accountId']] = Avatar(avatar_data)

        return results

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

        user_ids = (e['id'] for e in res)
        users = await self.fetch_users(
            user_ids,
            raw=True
        )
        lookup = {p['id']: p for p in users}

        entries = []
        for data in res:
            user_data = lookup.get(data['id'])
            if user_data is None:
                continue

            obj = SacSearchEntryUser(self, user_data, data)
            entries.append(obj)

        return entries

    def store_user(self, data: dict, *, try_cache: bool = True) -> User:
        try:
            user_id = data.get(
                'accountId',
                data.get('id', data.get('account_id'))
            )

            if try_cache:
                return self._users[user_id]
        except KeyError:
            pass

        user = User(self, data)
        if self.cache_users:
            self._users[user.id] = user
        return user

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
        return self._users.get(user_id)

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

            m = 'errors.com.epicgames.friends.inviter_friendships_limit_exceeded'  # noqa
            if exc.message_code == m:
                raise MaxFriendshipsExceeded(
                    'The client has hit the friendships limit.'
                )

            m = 'errors.com.epicgames.friends.invitee_friendships_limit_exceeded'  # noqa
            if exc.message_code == m:
                raise InviteeMaxFriendshipsExceeded(
                    'The user has hit the friendships limit.'
                )

            m = 'errors.com.epicgames.friends.incoming_friendships_limit_exceeded'  # noqa
            if exc.message_code == m:
                raise InviteeMaxFriendshipRequestsExceeded(
                    'The user has hit the incoming friendship requests limit.'
                )

            m = ('errors.com.epicgames.friends.'
                 'cannot_friend_due_to_target_settings')
            if exc.message_code == m:
                raise Forbidden('You cannot send friendship requests to '
                                'this user.')

            raise

    async def accept_friend(self, user_id: str) -> None:
        """|coro|

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
        """
        await self.add_friend(user_id)

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

    async def dispatch_and_wait_event(self, event: str,
                                      *args: Any,
                                      **kwargs: Any) -> None:
        coros = self._events.get(event, [])
        tasks = [asyncio.create_task(coro()) for coro in coros]
        if tasks:
            await asyncio.wait(
                tasks,
                return_when=asyncio.ALL_COMPLETED
            )

    def _dispatcher(self, coro: Awaitable,
                    *args: Any,
                    **kwargs: Any) -> asyncio.Future:
        return asyncio.ensure_future(coro(*args, **kwargs))

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
        return asyncio.wait_for(future, timeout)

    def _event_has_handler(self, event: str) -> bool:
        handlers = self._events.get(event.lower())
        return handlers is not None and len(handlers) > 0

    def _event_has_destination(self, event: str) -> bool:
        if event in self._listeners:
            return True
        elif self._event_has_handler(event):
            return True
        return False

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

    def _process_stats_times(self, start_time: Optional[DatetimeOrTimestamp] = None,  # noqa
                             end_time: Optional[DatetimeOrTimestamp] = None
                             ) -> Tuple[Optional[int], Optional[int]]:
        epoch = datetime.datetime.utcfromtimestamp(0)
        if isinstance(start_time, datetime.datetime):
            start_time = int((start_time - epoch).total_seconds())
        elif isinstance(start_time, SeasonStartTimestamp):
            start_time = start_time.value

        if isinstance(end_time, datetime.datetime):
            end_time = int((end_time - epoch).total_seconds())
        elif isinstance(end_time, SeasonEndTimestamp):
            end_time = end_time.value

        return start_time, end_time

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
        start_time, end_time = self._process_stats_times(start_time, end_time)

        tasks = [
            self.fetch_user(user_id, cache=True),
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

    async def _multiple_stats_chunk_requester(self, user_ids: List[str], stats: List[str], *,  # noqa
                                              collection: Optional[str] = None,
                                              start_time: Optional[DatetimeOrTimestamp] = None,  # noqa
                                              end_time: Optional[DatetimeOrTimestamp] = None  # noqa
                                              ) -> List[dict]:
        chunks = [user_ids[i:i+51] for i in range(0, len(user_ids), 51)]
        stats_chunks = [stats[i:i+20] for i in range(0, len(stats), 20)]

        tasks = []
        for chunk in chunks:
            for stats_chunk in stats_chunks:
                tasks.append(self.http.stats_get_multiple_v2(
                    chunk,
                    stats_chunk,
                    category=collection,
                    start_time=start_time,
                    end_time=end_time
                ))

        results = await asyncio.gather(*tasks)
        return [item for sub in results for item in sub]

    async def _fetch_multiple_br_stats(self, cls: _StatsBase,
                                       user_ids: List[str],
                                       stats: List[str],
                                       *,
                                       collection: Optional[str] = None,  # noqa
                                       start_time: Optional[DatetimeOrTimestamp] = None,  # noqa
                                       end_time: Optional[DatetimeOrTimestamp] = None,  # noqa
                                       ) -> Dict[str, StatsV2]:
        start_time, end_time = self._process_stats_times(start_time, end_time)

        tasks = [
            self.fetch_users(user_ids, cache=True),
            self._multiple_stats_chunk_requester(
                user_ids,
                stats,
                collection=collection,
                start_time=start_time,
                end_time=end_time
            )
        ]
        results = await asyncio.gather(*tasks)
        if len(results[0]) > 0 and isinstance(results[0][0], dict):
            results = results[::-1]

        res = {}
        for udata in results[1]:
            if udata['accountId'] in res and res[udata['accountId']] is not None:  # noqa
                res[udata['accountId']].raw['stats'].update(udata['stats'])
                continue

            r = [x for x in results[0] if x.id == udata['accountId']]
            user = r[0] if len(r) != 0 else None
            res[udata['accountId']] = (cls(user, udata)
                                       if user is not None else None)
        return res

    async def fetch_multiple_br_stats(self, user_ids: List[str],
                                      stats: List[str],
                                      *,
                                      start_time: Optional[DatetimeOrTimestamp] = None,  # noqa
                                      end_time: Optional[DatetimeOrTimestamp] = None  # noqa
                                      ) -> Dict[str, Optional[StatsV2]]:
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

                # get the users and create a list of their ids.
                users = await self.fetch_users(['Ninja', 'DrLupo'])
                user_ids = [u.id for u in users] + ['NonValidUserIdForTesting']

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
        Dict[:class:`str`, Optional[:class:`StatsV2`]]
            A mapping where :class:`StatsV2` is bound to its owners id. If a
            userid was not found then the value bound to that userid will be
            ``None``.

            .. note::

                If a users stats is missing in the returned mapping it means
                that the user has opted out of public leaderboards and that
                the client therefore does not have permissions to requests
                their stats.
        """  # noqa
        res = await self._fetch_multiple_br_stats(
            cls=StatsV2,
            user_ids=user_ids,
            stats=stats,
            start_time=start_time,
            end_time=end_time,
        )
        return res

    async def fetch_multiple_br_stats_collections(self, user_ids: List[str],
                                                  collection: Optional[StatsCollectionType] = None,  # noqa
                                                  *,
                                                  start_time: Optional[DatetimeOrTimestamp] = None,  # noqa
                                                  end_time: Optional[DatetimeOrTimestamp] = None  # noqa
                                                  ) -> Dict[str, Optional[StatsCollection]]:  # noqa
        """|coro|

        Gets Battle Royale stats collections for multiple users at the same time.

        Parameters
        ----------
        user_ids: List[:class:`str`]
            A list of ids you are requesting the stats for.
        collection: :class:`StatsCollectionType`
            The collection to receive. Collections are predefined
            stats that it attempts to request. 
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
        Dict[:class:`str`, Optional[:class:`StatsCollection`]]
            A mapping where :class:`StatsCollection` is bound to its owners id. If a
            userid was not found then the value bound to that userid will be
            ``None``.

            .. note::

                If a users stats is missing in the returned mapping it means
                that the user has opted out of public leaderboards and that
                the client therefore does not have permissions to requests
                their stats.
        """  # noqa
        res = await self._fetch_multiple_br_stats(
            cls=StatsCollection,
            user_ids=user_ids,
            stats=[],
            collection=collection.value,
            start_time=start_time,
            end_time=end_time,
        )
        return res

    async def fetch_multiple_battlepass_levels(self,
                                               users: List[str],
                                               season: int,
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
        season: :class:`int`
            The season number to request the battlepass levels for.

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
            An error occured while requesting.

        Returns
        -------
        Dict[:class:`str`, Optional[:class:`float`]]
            Users battlepass level mapped to their account id. Returns ``None``
            if no battlepass level was found. If a user has career board set
            to private, he/she will not appear in the result. Therefore you
            should never expect a user to be included.

            .. note::

                The decimals are the percent progress to the next level.
                E.g. ``208.63`` -> ``Level 208 and 63% on the way to 209.``

            .. note::

                If a users battlepass level is missing in the returned mapping it means
                that the user has opted out of public leaderboards and that
                the client therefore does not have permissions to requests
                their stats.
        """  # noqa
        start_time, end_time = self._process_stats_times(start_time, end_time)

        if end_time is not None:
            e = getattr(SeasonStartTimestamp, 'SEASON_{}'.format(season), None)
            if e is not None and end_time < e.value:
                raise ValueError(
                    'end_time can\'t be lower than the seasons start timestamp'
                )

        e = getattr(BattlePassStat, 'SEASON_{}'.format(season), None)
        if e is not None:
            info = e.value
            stats = info[0] if isinstance(info[0], tuple) else (info[0],)
            end_time = end_time if end_time is not None else info[1]
        else:
            stats = ('s{0}_social_bp_level'.format(season),)

        data = await self._multiple_stats_chunk_requester(
            users,
            stats,
            start_time=start_time,
            end_time=end_time
        )

        def get_stat(user_data):
            for stat in stats:
                value = user_data.get(stat)
                if value is not None:
                    return value / 100

        return {e['accountId']: get_stat(e['stats']) for e in data}

    async def fetch_battlepass_level(self, user_id: str, *,
                                     season: int,
                                     start_time: Optional[DatetimeOrTimestamp] = None,  # noqa
                                     end_time: Optional[DatetimeOrTimestamp] = None  # noqa
                                     ) -> float:
        """|coro|

        Fetches a users battlepass level.

        Parameters
        ----------
        user_id: :class:`str`
            The user id to fetch the battlepass level for.
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
        Forbidden
            User has private career board.
        HTTPException
            An error occured while requesting.

        Returns
        -------
        Optional[:class:`float`]
            The users battlepass level. ``None`` is returned if the user has
            not played any real matches this season.

            .. note::

                The decimals are the percent progress to the next level.
                E.g. ``208.63`` -> ``Level 208 and 63% on the way to 209.``
        """  # noqa
        data = await self.fetch_multiple_battlepass_levels(
            (user_id,),
            season=season,
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

    async def fetch_party(self, party_id: str) -> Party:
        """|coro|

        Fetches a party by its id.

        Parameters
        ----------
        party_id: :class:`str`
            The id of the party.

        Raises
        ------
        Forbidden
            You are not allowed to look up this party.

        Returns
        -------
        Optional[:class:`Party`]
            The party that was fetched. ``None`` if not found.
        """
        try:
            data = await self.http.party_lookup(party_id)
        except HTTPException as exc:
            m = 'errors.com.epicgames.social.party.party_not_found'
            if exc.message_code == m:
                return None

            m = 'errors.com.epicgames.social.party.party_query_forbidden'
            if exc.message_code == m:
                raise Forbidden('You are not allowed to lookup this party.')

            raise

        party = Party(self, data)
        await party._update_members(members=data['members'])

        return party

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

    async def join_party(self, party_id: str) -> None:
        raise NotImplementedError(
            'BasicClient does not support party actions.'
        )


class Client(BasicClient):
    """Represents the client connected to Fortnite and EpicGames' services.

    Parameters
    ----------
    auth: :class:`Auth`
        The authentication method to use. You can read more about available authentication methods
        :ref:`here <authentication>`.
    http_connector: :class:`aiohttp.BaseConnector`
        The connector to use for http connection pooling.
    ws_connector: :class:`aiohttp.BaseConnector`
        The connector to use for websocket connection pooling. This could be
        the same as the above connector.
    status: :class:`str`
        The status you want the client to send with its presence to friends.
        Defaults to: ``Battle Royale Lobby - {party playercount} / {party max playercount}``
    away: :class:`AwayStatus`
        The away status the client should use for its presence. Defaults to
        :attr:`AwayStatus.ONLINE`.
    platform: :class:`.Platform`
        The platform you want the client to display as its source.
        Defaults to :attr:`Platform.WINDOWS`.
    net_cl: :class:`str`
        The current net cl used by the current Fortnite build. Named **netCL**
        in official logs. Defaults to an empty string which is the recommended
        usage as of ``v0.9.0`` since you then
        won't need to update it when a new update is pushed by Fortnite.
    party_version: :class:`int`
        The party version the client should use. This value determines which version
        should be able to join the party. If a user attempts to join the clients party
        with a different party version than the client, then an error will be visible
        saying something by the lines of "Their party of Fortnite is older/newer than
        yours". If you experience this error I recommend incrementing the default set
        value by one since the library in that case most likely has yet to be updated.
        Defaults to ``3`` (As of November 3rd 2020).
    default_party_config: :class:`DefaultPartyConfig`
        The party configuration used when creating parties. If not specified,
        the client will use the default values specified in the data class.
    default_party_member_config: :class:`DefaultPartyMemberConfig`
        The party member configuration used when creating parties. If not specified,
        the client will use the default values specified in the data class.
    http_retry_config: Optional[:class:`HTTPRetryConfig`]
        The config to use for http retries.
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
    service_port: :class:`int`
        The port used by Fortnite's XMPP services.
    cache_users: :class:`bool`
        Whether or not the library should cache :class:`User` objects. Disable
        this if you are running a program with lots of users as this could
        potentially take a big hit on the memory usage. Defaults to ``True``.
    fetch_user_data_in_events: :class:`bool`
        Whether or not user data should be fetched in event processing. Disabling
        this might be useful for larger applications that deals with
        possibly being rate limited on their ip. Defaults to ``True``.

        .. warning::

            Keep in mind that if this option is disabled, there is a big
            chance that display names, external auths and more might be missing
            or simply is ``None`` on objects deriving from :class:`User`. Keep in
            mind that :attr:`User.id` always will be available. You can use
            :meth:`User.fetch()` to update all missing attributes.
    wait_for_member_meta_in_events: :class:`bool`
        Whether or not the client should wait for party member meta (information
        about outfit, backpack etc.) before dispatching events like
        :func:`event_party_member_join()`. If this is disabled then member objects
        in the events won't have the correct meta. Defaults to ``True``.
    leave_party_at_shutdown: :class:`bool`
        Whether or not the client should leave its current party at shutdown. If this
        is set to false, then the client will attempt to reconnect to the party on a
        startup. If :attr:`DefaultPartyMemberConfig.offline_ttl` is exceeded before
        a reconnect is attempted, then the client will create a new party at startup.

    Attributes
    ----------
    user: :class:`ClientUser`
        The user the client is logged in as.
    party: :class:`ClientParty`
        The party the client is currently connected to.
    """  # noqa

    def __init__(self, auth: Auth,
                 **kwargs: Any) -> None:
        super().__init__(auth=auth, **kwargs)

        self.status = kwargs.get('status', 'Battle Royale Lobby - {party_size} / {party_max_size}')  # noqa
        self.away = kwargs.get('away', AwayStatus.ONLINE)
        self.platform = kwargs.get('platform', Platform.WINDOWS)
        self.net_cl = kwargs.get('net_cl', '')
        self.party_version = kwargs.get('party_version', 3)
        self.party_build_id = '1:{0.party_version}:{0.net_cl}'.format(self)
        self.default_party_config = kwargs.get('default_party_config', DefaultPartyConfig())  # noqa
        self.default_party_member_config = kwargs.get('default_party_member_config', DefaultPartyMemberConfig())  # noqa
        self.service_host = kwargs.get('xmpp_host', 'prod.ol.epicgames.com')
        self.service_domain = kwargs.get('xmpp_domain', 'xmpp-service-prod.ol.epicgames.com')  # noqa
        self.service_port = kwargs.get('xmpp_port', 5222)
        self.fetch_user_data_in_events = kwargs.get('fetch_user_data_in_events', True)  # noqa
        self.wait_for_member_meta_in_events = kwargs.get('wait_for_member_meta_in_events', True)  # noqa
        self.leave_party_at_shutdown = kwargs.get('leave_party_at_shutdown', True)  # noqa

        self.xmpp = XMPPClient(self, ws_connector=kwargs.get('ws_connector'))
        self.party = None

        self._listeners = {}
        self._events = {}
        self._friends = {}
        self._pending_friends = {}
        self._blocked_users = {}
        self._presences = {}

        self._join_party_lock = None
        self._internal_join_party_lock = None
        self._join_confirmation = False
        self._refresh_times = []

        self.setup_internal()

    async def _async_init(self) -> None:
        # We must deal with loop stuff after a loop has been
        # created by asyncio.run(). This is called at the start
        # of start().

        self.loop = asyncio.get_running_loop()

        self._exception_future = self.loop.create_future()
        self._ready_event = asyncio.Event()
        self._closed_event = asyncio.Event()
        self._join_party_lock = LockEvent()
        self._internal_join_party_lock = LockEvent()
        self._reauth_lock = LockEvent()
        self._reauth_lock.failed = False

        self.auth.initialize(self)

    def register_connectors(self,
                            http_connector: Optional[BaseConnector] = None,
                            ws_connector: Optional[BaseConnector] = None
                            ) -> None:
        """This can be used to register connectors after the client has
        already been initialized. It must however be called before
        :meth:`start()` has been called, or in :meth:`event_before_start()`.

        .. warning::

            Connectors passed will not be closed on shutdown. You must close
            them yourself if you want a graceful shutdown.

        Parameters
        ----------
        http_connector: :class:`aiohttp.BaseConnector`
            The connector to use for the http session.
        ws_connector: :class:`aiohttp.BaseConnector`
            The connector to use for the websocket xmpp connection.
        """
        super().register_connectors(http_connector=http_connector)

        if ws_connector is not None:
            if self.xmpp.xmpp_client is not None:
                raise RuntimeError(
                    'ws_connector must be registered before startup')

            self.xmpp.ws_connector = ws_connector

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
    def friends(self) -> List[Friend]:
        """List[:class:`Friend`]: A list of the clients friends."""
        return list(self._friends.values())

    @property
    def friend_count(self) -> int:
        """:class:`int`: The amount of friends the bot currently has."""
        return len(self._friends)

    @property
    def pending_friends(self) -> List[Union[IncomingPendingFriend,
                                            OutgoingPendingFriend]]:
        """List[Union[:class:`IncomingPendingFriend`,
        :class:`OutgoingPendingFriend`]]: A list of all of the clients
        pending friends.

        .. note::

            Pending friends can be both incoming (pending friend sent the
            request to the bot) or outgoing (the bot sent the request to the
            pending friend). You must check what kind of pending friend an
            object is by their attributes ``incoming`` or ``outgoing``.
        """  # noqa
        return list(self._pending_friends.values())

    @property
    def pending_friend_count(self) -> int:
        """:class:`int`: The amount of pending friends the bot currently has.
        """
        return len(self._pending_friends)

    @property
    def incoming_pending_friends(self) -> List[IncomingPendingFriend]:
        """List[:class:`IncomingPendingFriend`]: A list of the clients
        incoming pending friends.
        """
        return [pf for pf in self._pending_friends.values() if pf.incoming]

    @property
    def incoming_pending_friend_count(self) -> int:
        """:class:`int`: The amount of active incoming pending friends the bot
        currently has received."""
        return len(self.incoming_pending_friends)

    @property
    def outgoing_pending_friends(self) -> List[OutgoingPendingFriend]:
        """List[:class:`OutgoingPendingFriend`]: A list of the clients
        outgoing pending friends.
        """
        return [pf for pf in self._pending_friends.values() if pf.outgoing]

    @property
    def outgoing_pending_friend_count(self) -> int:
        """:class:`int`: The amount of active outgoing pending friends the bot
        has sent."""
        return len(self.outgoing_pending_friends)

    @property
    def blocked_users(self) -> List[BlockedUser]:
        """List[:class:`BlockedUser`]: A list of the users client has
        as blocked.
        """
        return list(self._blocked_users.values())

    @property
    def blocked_user_count(self) -> int:
        """:class:`int`: The amount of blocked users the bot currently has
        blocked."""
        return len(self._blocked_users)

    @property
    def presences(self) -> List[Presence]:
        """List[:class:`Presence`]: A list of the last presences from
        currently online friends.
        """
        return list(self._presences.values())

    def _check_party_confirmation(self) -> None:
        k = 'party_member_confirm'
        val = k in self._events and len(self._events[k]) > 0
        if val != self._join_confirmation:
            self._join_confirmation = val
            self.default_party_config.update({'join_confirmation': val})

    def register_methods(self) -> None:
        super().register_methods()

        self._check_party_confirmation()

    async def internal_auth_refresh_handler(self):
        try:
            log.debug('Refreshing xmpp session')
            await self.xmpp.close()
            await self.xmpp.run()

            await self._reconnect_to_party()
        except AttributeError:
            pass

    async def _start(self, dispatch_ready: bool = True) -> None:
        if self._first_start:
            self.add_event_handler(
                'internal_auth_refresh',
                self.internal_auth_refresh_handler
            )

        return await super()._start(dispatch_ready=dispatch_ready)

    async def _login(self, priority: int = 0) -> None:
        res = await super()._login(priority=priority)
        if res is not None:
            return res

        await self.refresh_caches(priority=priority)
        log.debug('Successfully set up caches')

        await self.xmpp.run()
        log.debug('Connected to XMPP')

        await self.initialize_party(priority=priority)
        log.debug('Party created')

    def _clear_caches(self) -> None:
        super()._clear_caches()

        self._friends.clear()
        self._pending_friends.clear()
        self._blocked_users.clear()
        self._presences.clear()

    async def _close(self, *,
                     close_http: bool = True,
                     dispatch_close: bool = True,
                     priority: int = 0) -> None:
        self._closing = True

        if self.leave_party_at_shutdown:
            try:
                if self.party is not None:
                    await self.party._leave(priority=priority)
            except Exception:
                pass

        try:
            await self.xmpp.close()
        except Exception:
            pass

        await super()._close(
            close_http=close_http,
            dispatch_close=dispatch_close,
            priority=priority,
        )

    def recover_events(self) -> asyncio.Task:
        return asyncio.create_task(self._recover_events())

    async def _recover_events(self, *,
                              refresh_caches: bool = False,
                              wait_for_close: bool = True) -> None:
        if wait_for_close:
            await self.wait_for('xmpp_session_close')

        pre_friends = self.friends
        pre_pending = self.pending_friends
        await self.wait_for('xmpp_session_establish')

        if refresh_caches:
            await self.refresh_caches()

        for friend in pre_friends:
            if friend not in self._friends.values():
                self.dispatch_event('friend_remove', friend)

        added_friends = []
        for friend in self._friends.values():
            if friend not in pre_friends:
                added_friends.append(friend)
                self.dispatch_event('friend_add', friend)

        for pending in pre_pending:
            if (pending not in self._pending_friends.values()
                    and pending not in added_friends):
                self.dispatch_event('friend_request_abort', pending)

        for pending in self._pending_friends.values():
            if pending not in pre_pending:
                self.dispatch_event('friend_request', pending)

    def construct_party(self, data: dict, *,
                        cls: Optional[ClientParty] = None) -> ClientParty:
        clazz = cls or self.default_party_config.cls
        return clazz(self, data)

    async def initialize_party(self, priority: int = 0) -> None:
        data = await self.http.party_lookup_user(
            self.user.id,
            priority=priority
        )
        if len(data['current']) > 0:
            if not self.leave_party_at_shutdown:
                current = data['current'][0]

                member_d = None
                for member_data in current['members']:
                    if member_data['account_id'] == self.auth.account_id:
                        member_d = member_data
                        break

                if member_d is not None:
                    newest_conn = max(
                        member_data['connections'],
                        key=lambda o: from_iso(o['connected_at']),
                    )

                    try:
                        disc_at = from_iso(newest_conn['disconnected_at'])
                    except KeyError:
                        pass
                    else:
                        now = datetime.datetime.utcnow()
                        total_seconds = (now - disc_at).total_seconds()
                        if total_seconds < newest_conn.get('offline_ttl', 30):
                            return await self._reconnect_to_party(data=data)

            party = self.construct_party(data['current'][0])
            await party._leave(priority=priority)
            log.debug('Left old party')

        await self._create_party(priority=priority)

    async def refresh_caches(self, priority: int = 0) -> None:
        self._friends.clear()
        self._pending_friends.clear()
        self._blocked_users.clear()

        tasks = (
            self.http.friends_get_all(
                include_pending=True,
                priority=priority
            ),
            self.http.friends_get_summary(priority=priority),
            self.http.presence_get_last_online(priority=priority),
        )
        raw_friends, raw_summary, raw_presences = await asyncio.gather(*tasks)

        ids = [r['accountId'] for r in raw_friends + raw_summary['blocklist']]
        chunks = (ids[i:i + 100] for i in range(0, len(ids), 100))

        users = {}
        tasks = [
            self.http.account_graphql_get_multiple_by_user_id(
                chunk,
                priority=priority
            )
            for chunk in chunks
        ]
        if tasks:
            done = await asyncio.gather(*tasks)
        else:
            done = []

        for results in done:
            for user in results['accounts']:
                users[user['id']] = user

        # TODO: Add method for fetching friends and other stuff

        for friend in raw_friends:
            try:
                data = users[friend['accountId']]
            except KeyError:
                continue

            if friend['status'] == 'ACCEPTED':
                self.store_friend({**friend, **data})

            elif friend['status'] == 'PENDING':
                if friend['direction'] == 'INBOUND':
                    self.store_incoming_pending_friend({**friend, **data})
                else:
                    self.store_outgoing_pending_friend({**friend, **data})

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
                    from_iso(value) if value is not None else None
                )

        for data in raw_summary['blocklist']:
            user = users.get(data['accountId'])
            if user is not None:
                self.store_blocked_user(user)

    def store_user(self, data: dict, *, try_cache: bool = True) -> User:
        try:
            user_id = data.get(
                'accountId',
                data.get('id', data.get('account_id'))
            )

            if try_cache:
                return self._users[user_id]
        except KeyError:
            pass

        user = User(self, data)
        if self.cache_users:
            self._users[user.id] = user
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        user = super().get_user(user_id)
        if user is None:
            friend = self.get_friend(user_id)
            if friend is not None:
                user = User(self, friend.get_raw())
                if self.cache_users:
                    self._users[user.id] = user
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
                return self._friends[user_id]
        except KeyError:
            pass

        friend = Friend(self, data)
        if summary is not None:
            friend._update_summary(summary)
        self._friends[friend.id] = friend
        return friend

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

    def store_incoming_pending_friend(self, data: dict, *,
                                      try_cache: bool = True
                                      ) -> IncomingPendingFriend:
        try:
            user_id = data.get(
                'accountId',
                data.get('id', data.get('account_id'))
            )
            if try_cache:
                return self._pending_friends[user_id]
        except KeyError:
            pass

        pending_friend = IncomingPendingFriend(self, data)
        self._pending_friends[pending_friend.id] = pending_friend
        return pending_friend

    def store_outgoing_pending_friend(self, data: dict, *,
                                      try_cache: bool = True
                                      ) -> OutgoingPendingFriend:
        try:
            user_id = data.get(
                'accountId',
                data.get('id', data.get('account_id'))
            )
            if try_cache:
                return self._pending_friends[user_id]
        except KeyError:
            pass

        pending_friend = OutgoingPendingFriend(self, data)
        self._pending_friends[pending_friend.id] = pending_friend
        return pending_friend

    def get_pending_friend(self,
                           user_id: str
                           ) -> Optional[Union[IncomingPendingFriend,
                                               OutgoingPendingFriend]]:
        """Tries to get a pending friend from the pending friend cache by the
        given user id.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the pending friend.

        Returns
        -------
        Optional[Union[:class:`IncomingPendingFriend`, 
        :class:`OutgoingPendingFriend`]]
            The pending friend if found, else ``None``
        """  # noqa
        return self._pending_friends.get(user_id)

    def get_incoming_pending_friend(self,
                                    user_id: str
                                    ) -> Optional[IncomingPendingFriend]:
        """Tries to get an incoming pending friend from the pending friends
        cache by the given user id.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the incoming pending friend.

        Returns
        -------
        Optional[:class:`IncomingPendingFriend`]
            The incoming pending friend if found, else ``None``.
        """
        pending_friend = self.get_pending_friend(user_id)
        if pending_friend and pending_friend.incoming:
            return pending_friend

    def get_outgoing_pending_friend(self,
                                    user_id: str
                                    ) -> Optional[OutgoingPendingFriend]:
        """Tries to get an outgoing pending friend from the pending friends
        cache by the given user id.

        Parameters
        ----------
        user_id: :class:`str`
            The id of the outgoing pending friend.

        Returns
        -------
        Optional[:class:`OutgoingPendingFriend`]
            The outgoing pending friend if found, else ``None``.
        """
        pending_friend = self.get_pending_friend(user_id)
        if pending_friend and pending_friend.outgoing:
            return pending_friend

    def store_blocked_user(self, data: dict, *,
                           try_cache: bool = True) -> BlockedUser:
        try:
            user_id = data.get(
                'accountId',
                data.get('id', data.get('account_id'))
            )
            if try_cache:
                return self._blocked_users[user_id]
        except KeyError:
            pass

        blocked_user = BlockedUser(self, data)
        self._blocked_users[blocked_user.id] = blocked_user
        return blocked_user

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
        await super().add_friend(user_id)
        friend = await self.wait_for('friend_add',
                                     check=lambda f: f.id == user_id)
        return friend

    async def _reconnect_to_party(self, data: Optional[dict] = None) -> None:
        if data is None:
            data = await self.http.party_lookup_user(
                self.user.id
            )

        if data['current']:
            party_data = data['current'][0]
            async with self._join_party_lock:
                try:
                    await self._join_party(
                        party_data,
                        event='party_member_reconnect'
                    )
                except Exception:
                    await self._create_party(acquire=False)
                    raise
        else:
            await self._create_party()

    async def _create_party(self,
                            config: Optional[dict] = None,
                            acquire: bool = True,
                            priority: int = 0) -> ClientParty:
        aquiring = not self.auth._refresh_lock.locked() and acquire
        try:
            if aquiring:
                await self._join_party_lock.acquire()

            if isinstance(config, dict):
                cf = {**self.default_party_config.config, **config}
            else:
                cf = self.default_party_config.config

            while True:
                try:
                    data = await self.http.party_create(
                        cf,
                        priority=priority
                    )
                    break
                except HTTPException as exc:
                    if exc.message_code != ('errors.com.epicgames.social.'
                                            'party.user_has_party'):
                        raise

                    data = await self.http.party_lookup_user(
                        self.user.id,
                        priority=priority
                    )

                    try:
                        await self.http.party_leave(
                            data['current'][0]['id'],
                            priority=priority
                        )
                    except HTTPException as e:
                        m = ('errors.com.epicgames.social.'
                             'party.party_not_found')
                        if e.message_code != m:
                            raise

                    await self.xmpp.leave_muc()

            config = {**cf, **data['config']}
            party = self.construct_party(data)
            await party._update_members(
                members=data['members'],
                priority=priority
            )
            self.party = party

            tasks = [
                self.loop.create_task(party.join_chat()),
            ]
            await party.meta.meta_ready_event.wait()

            updated, deleted, cfg1 = party.meta.set_privacy(config['privacy'])
            edit_updated, edit_deleted, cfg2 = await party._edit(
                *party._default_config.meta
            )

            # Filter out urn:epic:* properties that was set in party create
            # payload.
            default_schema = {
                k: v for k, v in party.meta.schema.items()
                if k.startswith('Default:')
            }

            tasks.append(party.patch(
                updated={
                    **default_schema,
                    **updated,
                    **edit_updated,
                    **party._construct_raw_squad_assignments(),
                    **party.meta.set_voicechat_implementation('EOSVoiceChat')
                },
                deleted=[*deleted, *edit_deleted],
                priority=priority,
                config={**cfg1, **cfg2},
            ))
            await asyncio.gather(*tasks)

            return party

        finally:
            if aquiring:
                self._join_party_lock.release()

    def is_creating_party(self) -> bool:
        return self._join_party_lock.locked()

    async def wait_until_party_ready(self) -> None:
        await self._join_party_lock.wait()

    async def _join_party(self, party_data: dict, *,
                          event: str = 'party_member_join') -> ClientParty:
        async with self._internal_join_party_lock:
            party = self.construct_party(party_data)
            await party._update_members(party_data['members'])
            self.party = party

            def check(m):
                if m.id != self.user.id:
                    return False
                if party.id != m.party.id:
                    return False
                return True

            future = asyncio.ensure_future(
                self.wait_for(event, check=check, timeout=5),
            )

            try:
                await self.http.party_join_request(party.id)
            except HTTPException as e:
                if not future.cancelled():
                    future.cancel()

                m = 'errors.com.epicgames.social.party.party_join_forbidden'  # noqa
                if e.message_code == m:
                    raise Forbidden(
                        'You are not allowed to join this party.'
                    )
                raise

            party_data = await self.http.party_lookup(party.id)
            party = self.construct_party(party_data)
            self.party = party
            asyncio.ensure_future(party.join_chat())
            await party._update_members(party_data['members'])

        try:
            await future
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError('Party join timed out.')

        return party

    async def join_party(self, party_id: str) -> ClientParty:
        """|coro|

        Joins a party by the party id.

        Parameters
        ----------
        party_id: :class:`str`
            The id of the party you wish to join.

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
        PartyIsFull
            The party you attempted to join is full.
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
        async with self._join_party_lock:
            if party_id == self.party.id:
                raise PartyError('You are already a member of this party.')

            try:
                party_data = await self.http.party_lookup(party_id)
            except HTTPException as e:
                m = 'errors.com.epicgames.social.party.party_not_found'
                if e.message_code == m:
                    raise NotFound(
                        'Could not find a party with the id {0}'.format(
                            party_id
                        )
                    )

                m = 'errors.com.epicgames.social.party.party_query_forbidden'  # noqa
                if e.message_code == m:
                    raise Forbidden(
                        'You are not allowed to join this party.'
                    )

                m = 'errors.com.epicgames.social.party.party_is_full'
                if e.message_code == m:
                    raise PartyIsFull(
                        'The party you attempted to join is full.'
                    )

                raise

            try:
                await self.party._leave()
                party = await self._join_party(party_data)
                return party
            except Exception:
                await self._create_party(acquire=False)
                raise

    def set_presence(self, status: str, *,
                     away: AwayStatus = AwayStatus.ONLINE) -> None:
        """|coro|

        Sends and sets the status. This status message will override all other
        presence statuses including party presence status.

        Parameters
        ----------
        status: :class:`str`
            The status you want to set.
        away: :class:`AwayStatus`
            The away status to use. Defaults to :attr:`AwayStatus.ONLINE`.

        Raises
        ------
        TypeError
            The status you tried to set were not a str.
        """
        if not isinstance(status, str):
            raise TypeError('status must be a str')

        self.status = status
        self.away = away
        self.party.update_presence()

    async def send_presence(self, status: Union[str, dict], *,
                            away: AwayStatus = AwayStatus.ONLINE,
                            to: Optional[JID] = None) -> None:
        """|coro|

        Sends this status to all or one single friend.

        Parameters
        ----------
        status: Union[:class:`str`, :class:`dict`]
            The status message in :class:`str` or full status in :class:`dict`.
        away: :class:`AwayStatus`
            The away status to use. Defaults to :attr:`AwayStatus.ONLINE`.
        to: Optional[:class:`aioxmpp.JID`]
            The JID of the user that should receive this status.
            *Defaults to None which means it will send to all friends.*

        Raises
        ------
        TypeError
            Status was an invalid type.
        """
        await self.xmpp.send_presence(
            status=status,
            show=away.value,
            to=to
        )

    async def set_platform(self, platform: Platform) -> None:
        """|coro|

        Sets and updates the clients platform. This method is slow (~2-3s) as
        changing platform requires a full authentication refresh.

        Parameters
        ----------
        platform: :class:`Platform`
            The platform to set.

        Raises
        ------
        HTTPException
            An error occurred when requesting.
        """
        self.platform = platform

        await asyncio.gather(
            self.auth.run_refresh(),
            self.wait_for('muc_enter'),
        )
