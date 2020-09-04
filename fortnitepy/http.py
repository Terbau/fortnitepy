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

import aiohttp
import asyncio
import logging
import json
import re
import time

from typing import TYPE_CHECKING, List, Optional, Any, Union, Tuple
from urllib.parse import quote
from .utils import MaybeLock

from .errors import HTTPException

if TYPE_CHECKING:
    from .client import Client

log = logging.getLogger(__name__)

GRAPHQL_HTML_ERROR_PATTERN = re.compile(
    r'<title>((\d+).*)<\/title>',
    re.MULTILINE
)


class HTTPRetryConfig:
    """Config for how HTTPClient should handle retries.

    .. warning::

        Messing with these values could potentially make retries spammy.
        Worst case scenario of this would be that either your ip or
        your account could be limited due to high traffic. Change these
        values with caution!

    Parameters
    ----------
    max_retry_attempts: :class:`int`
        The max amount of retry attempts for a request. Defaults to ``5``.

        .. note::

            This is ignored when handling capacity throttling.
    max_wait_time: Optional[:class:`float`]
        The max amount of seconds to wait for a request before
        raising the original exception. This works by keeping track of the
        total seconds that has been waited for the request regardless of
        number of attempts. If ``None`` this is ignored. Defaults to ``65``.
    handle_rate_limits: :class:`bool`
        Whether or not the client should handle rate limit errors and wait
        the received ``Retry-After`` before automatically retrying the request.
        Defaults to ``True``.

        .. note::

            This option is only for throttling errors with a Retry-After value.
    max_retry_after: :class:`float`
        The max amount of seconds the client should handle. If a throttled
        error with a higher Retry-After than this value is received, then
        the original :exc:`HTTPException` is raised instead. *Only matters
        when ``handle_rate_limits`` is ``True``*
    other_requests_wait: :class:`bool`
        Whether other requests to a rate limited endpoint should wait
        for the rate limit to disappear before requesting. Defaults to
        ``True``. *Only matters when ``handle_rate_limits`` is ``True``*
    handle_capacity_throttling: :class:`bool`
        Whether or not the client should automatically handle capacity
        throttling errors. These occur when the prod server you
        are requesting from has no available capacity to process a
        request and therefore returns with a throttle error
        without a Retry-After. Defaults to ``True``.
    backoff_start: :class:`float`
        The initial seconds to wait for the exponential backoff. Defaults
        to ``1``. *Only matters when ``handle_capacity_throttling`` is
        ``True``*
    backoff_factor: :class:`float`
        The multiplying factor used for the exponential backoff when a
        request fails. Defaults to ``1.5``. *Only matters when
        ``handle_capacity_throttling`` is ``True``*
    backoff_cap: :class:`float`
        The cap for the exponential backoff to avoid having
        unrealistically high wait times. Defaults to ``20``. *Only matters
        when ``handle_capacity_throttling`` is ``True``*
    """
    def __init__(self, **kwargs):
        self.max_retry_attempts = kwargs.get('max_retry_attempts', 5)
        self.max_wait_time = kwargs.get('max_wait_time', 65)

        self.handle_rate_limits = kwargs.get('handle_rate_limits', True)
        self.max_retry_after = kwargs.get('max_retry_after', 60)
        self.other_requests_wait = kwargs.get('other_requests_wait', True)

        self.handle_capacity_throttling = kwargs.get('handle_capacity_throttling', True)  # noqa
        self.backoff_start = kwargs.get('backoff_start', 1)
        self.backoff_factor = kwargs.get('backoff_factor', 1.5)
        self.backoff_cap = kwargs.get('backoff_cap', 20)


class GraphQLRequest:
    def __init__(self, query: str, *,
                 operation_name: str = None,
                 variables: dict = None
                 ) -> None:
        self.query = query
        self.operation_name = operation_name
        self.variables = variables

    def _to_camel_case(self, text: str) -> str:
        components = text.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])

    def __iter__(self) -> str:
        for key, value in self.__dict__.items():
            if value is None:
                continue

            yield (self._to_camel_case(key), value)

    def as_dict(self) -> dict:
        return dict(self)

    def as_multiple_payload(self) -> dict:
        return {
            'operationName': (self.operation_name
                              or self.get_operation_name_by_query()),
            'variables': self.variables,
            'query': self.query
        }

    def get_operation_name_by_query(self) -> str:
        return re.search(r'(?:mutation|query) (\w+)', self.query).group(1)


class Route:
    """Represents a route to use for a http request. This should
    be subclassed by new routes and the class attributes ``BASE`` and
    optionally ``AUTH`` should be overridden.

    .. warning::

        Usually there is no reason to subclass and implement routes
        yourself as most of them are already implemented. Take a look
        at http.py if you're interested in knowing all of the predefined
        routes.

    Available authentication placeholders:
    - `IOS_BASIC_TOKEN`
    - `FORTNITE_BASIC_TOKEN`
    - `IOS_ACCESS_TOKEN`
    - `FORTNITE_ACCESS_TOKEN`

    Example usage: ::

        class SocialBanPublicService(fortnitepy.Route):
            BASE = 'https://social-ban-public-service-prod.ol.epicgames.com'
            AUTH = 'FORTNITE_ACCESS_TOKEN'

        route = SocialBanPublicService(
            '/socialban/api/public/v1/{user_id}',
            user_id='c7af4984a77a498b83d8b16d475d76bc'
        )
        resp = await client.http.get(route)

        # resp would look something like this:
        # {
        #     "bans" : [],
        #     "warnings" : []
        # }

    Parameters
    ----------
    path: :class:`path`
        The path to used for the request.

        .. warning::

            You should always use name
            formatting for arguments and instead of using `.format()`on the
            path, you should pass the format kwargs as kwargs to the route.
            This might seem counterintuitive but it is important to ensure
            rate limit retry reliability.
    auth: Optional[:class:`str`]
        The authentication to use for the request. If ``None`` the default
        auth specified for the route is used.
    **params: Any
        The variables to format the path with passed alongside their name.

    Attributes
    ----------
    path: :class:`str`
        The requests path.
    params: Dict[:class:`str`, Any]
        A mapping of the params passed.
    base: :class:`str`
        The base of the request url.
    auth: Optional[:class:`str`]
        The auth placeholder.
    url: :class:`str`
        The formatted url.
    sanitized_url: :class:`str`
        The yet to be formatted url.
    """
    BASE = ''
    AUTH = None

    def __init__(self, path: str = '', *,
                 auth: str = None,
                 **params: Any) -> None:
        self.path = path
        self.params = {k: (quote(v) if isinstance(v, str) else v)
                       for k, v in params.items()}

        if self.BASE == '':
            raise ValueError('Route must have a base')

        self.sanitized_url = url = self.BASE + self.path
        self.url = url.format(**self.params) if self.params else url

        if auth:
            self.AUTH = auth

        self.base = self.BASE
        self.auth = self.AUTH


class EpicGamesGraphQL(Route):
    BASE = 'https://graphql.epicgames.com/graphql'
    AUTH = 'FORTNITE_ACCESS_TOKEN'


class EpicGames(Route):
    BASE = 'https://www.epicgames.com'
    AUTH = None


class PaymentWebsite(Route):
    BASE = 'https://payment-website-pci.ol.epicgames.com'
    AUTH = None


class LightswitchPublicService(Route):
    BASE = 'https://lightswitch-public-service-prod06.ol.epicgames.com'
    AUTH = 'IOS_ACCESS_TOKEN'


class UserSearchService(Route):
    BASE = 'https://user-search-service-prod.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'


class AccountPublicService(Route):
    BASE = 'https://account-public-service-prod.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'


class EulatrackingPublicService(Route):
    BASE = 'https://eulatracking-public-service-prod-m.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'


class AffiliatePublicService(Route):
    BASE = 'https://affiliate-public-service-prod.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'


class EventsPublicService(Route):
    BASE = 'https://events-public-service-live.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'


class FortniteContentWebsite(Route):
    BASE = 'https://fortnitecontent-website-prod07.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'


class FortnitePublicService(Route):
    BASE = 'https://fortnite-public-service-prod11.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'


class FriendsPublicService(Route):
    BASE = 'https://friends-public-service-prod.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'


class PartyService(Route):
    BASE = 'https://party-service-prod.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'


class PresencePublicService(Route):
    BASE = 'https://presence-public-service-prod.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'


class StatsproxyPublicService(Route):
    BASE = 'https://statsproxy-public-service-live.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'


class HTTPClient:
    def __init__(self, client: 'Client', *,
                 connector: aiohttp.BaseConnector = None,
                 retry_config: Optional[HTTPRetryConfig] = None) -> None:
        self.client = client
        self.connector = connector
        self.retry_config = retry_config or HTTPRetryConfig()

        self._jar = aiohttp.CookieJar()
        self.headers = {}
        self.device_id = self.client.auth.device_id
        self._endpoint_events = {}

        # How many refreshes (max_refresh_attempts) to attempt in
        # a time window (refresh_attempt_window) before closing.
        self.max_refresh_attempts = 3
        self.refresh_attempt_window = 20

        self.create_connection()

    @staticmethod
    async def json_or_text(response: aiohttp.ClientResponse) -> Union[str,
                                                                      dict]:
        text = await response.text(encoding='utf-8')
        if 'application/json' in response.headers.get('content-type', ''):
            return json.loads(text)
        return text

    @property
    def user_agent(self) -> str:
        return 'Fortnite/{0.client.build} {0.client.os}'.format(self)

    def get_auth(self, auth: str) -> str:
        u_auth = auth.upper()

        if u_auth == 'IOS_BASIC_TOKEN':
            return 'basic {0}'.format(self.client.auth.ios_token)
        elif u_auth == 'FORTNITE_BASIC_TOKEN':
            return 'basic {0}'.format(self.client.auth.fortnite_token)
        elif u_auth == 'IOS_ACCESS_TOKEN':
            return self.client.auth.ios_authorization
        elif u_auth == 'FORTNITE_ACCESS_TOKEN':
            return self.client.auth.authorization
        return auth

    def add_header(self, key: str, val: Any) -> None:
        self.headers[key] = val

    def remove_header(self, key: str) -> Any:
        return self.headers.pop(key)

    async def close(self) -> None:
        self._jar.clear()
        if self.__session:
            await self.__session.close()

    def create_connection(self) -> None:
        self.__session = aiohttp.ClientSession(
            connector=self.connector,
            connector_owner=self.connector is None,
            cookie_jar=self._jar
        )

    async def request(self, method: str, url: str,
                      **kwargs: Any
                      ) -> Tuple[aiohttp.ClientResponse, Union[str, dict]]:
        try:
            params = kwargs['params']
            if isinstance(params, dict):
                kwargs['params'] = {k: (str(v).lower() if isinstance(v, bool)
                                        else v) for k, v in params.items()}
            else:
                kwargs['params'] = [(k, (str(v).lower() if isinstance(v, bool)
                                         else v)) for k, v in params]
        except KeyError:
            pass

        pre_time = time.time()
        async with self.__session.request(method, url, **kwargs) as r:
            log.debug('{0} {1} has returned {2.status} in {3:.2f}s'.format(
                method,
                url,
                r,
                time.time() - pre_time
            ))

            data = await self.json_or_text(r)
            return r, data

    async def _fn_request(self, method: str,
                          route: Union[Route, str],
                          auth: Optional[str] = None,
                          graphql: Optional[Union[Route, List[Route]]] = None,
                          **kwargs: Any) -> Any:
        url = route.url if not isinstance(route, str) else route

        headers = {**kwargs.get('headers', {}), **self.headers}
        headers['User-Agent'] = self.user_agent

        auth = auth or route.AUTH
        if auth is not None:
            headers['Authorization'] = self.get_auth(auth)

        device_id = kwargs.pop('device_id', None)
        if device_id is not None:
            headers['X-Epic-Device-ID'] = (self.device_id if device_id is True
                                           else device_id)

        if graphql is not None:
            is_multiple = isinstance(graphql, (list, tuple))

            if not is_multiple:
                graphql = (graphql,)
            kwargs['json'] = [gql_query.as_multiple_payload()
                              for gql_query in graphql]

        kwargs['headers'] = headers

        try:
            del kwargs['config']
        except KeyError:
            pass

        raw = kwargs.pop('raw', False)
        r, data = await self.request(method, url, **kwargs)

        if raw:
            return r

        if graphql is not None:
            if isinstance(data, str):
                m = GRAPHQL_HTML_ERROR_PATTERN.search(data)
                error_data = ({
                    'serviceResponse': '',
                    'message': 'Unknown reason' if m is None else m.group(1)
                },)
                if m is not None:
                    error_data['serviceResponse'] = json.dumps({
                        'errorStatus': int(m.group(2))
                    })

            elif isinstance(data, dict):
                if data['status'] >= 400:
                    message = data['message']
                    error_data = ({
                        'serviceResponse': json.dumps({
                            'errorCode': message
                        }),
                        'message': message
                    },)
            else:
                error_data = None
                for child_data in data:
                    if 'errors' in child_data:
                        error_data = child_data['errors']
                        break

            if error_data is not None:
                selected = error_data[0]

                obj = {'errorMessage': selected['message']}
                service_response = selected['serviceResponse']
                if service_response == '':
                    error_payload = {}
                else:
                    error_payload = json.loads(service_response)

                if isinstance(error_payload, str):
                    m = GRAPHQL_HTML_ERROR_PATTERN.search(error_payload)
                    message = 'Unknown reason' if m is None else m.group(1)
                    error_payload = {
                        'errorMessage': message,
                    }

                    if m is not None:
                        error_payload['errorStatus'] = int(m.group(2))

                raise HTTPException(
                    r,
                    route,
                    {**obj, **error_payload},
                    headers
                )

            def get_payload(d):
                return next(iter(d['data'].values()))

            if len(data) == 1:
                return get_payload(data[0])
            return [get_payload(d) for d in data]

        if 'errorCode' in data or r.status >= 400:
            if isinstance(data, str):
                data = {
                    'errorMessage': data if data else 'Unknown {}'.format(
                        r.status
                    )
                }
            raise HTTPException(r, route, data, headers)

        return data

    def get_retry_after(self, exc):
        retry_after = exc.response.headers.get('Retry-After')
        if retry_after is not None:
            return int(retry_after)

        # For some reason graphql response headers doesn't contain
        # rate limit headers so we have to get retry after from
        # the message vars.
        try:
            return int(exc.message_vars[0])
        except (ValueError, IndexError):
            return None

    async def fn_request(self, method: str,
                         route: Union[Route, str],
                         auth: Optional[str] = None,
                         graphql: Union[Route, List[Route]] = None,
                         priority: int = 0,
                         **kwargs: Any) -> Any:
        if self.client.is_closed():
            raise RuntimeError('Client is closed.')

        cfg = self.retry_config
        if isinstance(route, Route):
            url = route.url
            url_key = (method, route.sanitized_url)
        else:
            url = route
            url_key = None

        tries = 0
        total_slept = 0
        backoff = cfg.backoff_start
        while True:
            sleep_time = 0
            tries += 1

            endpoint_event = self._endpoint_events.get(url_key)
            if endpoint_event is not None:
                log.debug('Waiting for {0:.2f}s before requesting {1} {2}.'.format(  # noqa
                    endpoint_event.ends_at - time.time(),
                    method,
                    url,
                ))
                await endpoint_event.wait()

            endpoint_event = None

            lock = self.client._reauth_lock
            if priority <= 0:
                await lock.wait()
                if lock.failed:
                    raise asyncio.CancelledError(
                        'Client is shutting down.'
                    )

            try:
                return await self._fn_request(
                    method,
                    route,
                    auth,
                    graphql,
                    **kwargs
                )
            except HTTPException as exc:
                if self.client._closing:
                    raise

                if tries >= cfg.max_retry_attempts:
                    raise

                code = exc.message_code

                if graphql:
                    gql_server_error = exc.raw.get('errorStatus') in {500, 502}
                else:
                    gql_server_error = False

                catch = (
                    'errors.com.epicgames.common.oauth.invalid_token',
                    'errors.com.epicgames.common.authentication.token_verification_failed',  # noqa
                    'error.graphql.401',
                )
                if code in catch:
                    _auth = auth or route.AUTH
                    if exc.request_headers['Authorization'] != self.get_auth(_auth):  # noqa
                        continue

                    force_attempts = self.max_refresh_attempts
                    retry = True

                    def should_force():
                        ts = self.client._refresh_times
                        if len(ts) > force_attempts:
                            self.client._refresh_times = ts[-force_attempts:]
                        try:
                            old = self.client._refresh_times[-force_attempts]
                        except IndexError:
                            return True
                        else:
                            cur = time.time()
                            return cur - old > self.refresh_attempt_window

                    if priority > lock.priority - 1:
                        async with MaybeLock(lock):
                            if should_force():
                                try:
                                    await self.client.auth.do_refresh()
                                except asyncio.CancelledError:
                                    lock.failed = True
                                    retry = False
                                except Exception:
                                    if self.client.can_restart():
                                        await self.client.restart()
                                    else:
                                        lock.failed = True
                                        retry = False
                            else:
                                retry = False
                    else:
                        if lock.locked():
                            await lock.wait()
                            if lock.failed:
                                raise asyncio.CancelledError(
                                    'Client is shutting down.'
                                )
                        else:
                            retry = False

                    if retry:
                        continue
                    else:
                        try:
                            e = RuntimeError('Oauth token invalid.')
                            e.__cause__ = exc
                            self.client._exception_future.set_exception(e)
                        except asyncio.InvalidStateError:
                            pass

                        raise asyncio.CancelledError(
                            'Client is shutting down.'
                        )

                elif code == 'errors.com.epicgames.common.throttled' or exc.status == 429:  # noqa
                    retry_after = self.get_retry_after(exc)
                    if retry_after is not None and cfg.handle_rate_limits:
                        if retry_after <= cfg.max_retry_after:
                            sleep_time = retry_after + 0.5
                            if cfg.other_requests_wait and url_key is not None:
                                if url_key not in self._endpoint_events:
                                    endpoint_event = asyncio.Event()
                                    endpoint_event.ends_at = time.time() + sleep_time  # noqa
                                    self._endpoint_events[url_key] = endpoint_event  # noqa
                    else:
                        tries -= 1  # backoff tries shouldn't count
                        if cfg.handle_capacity_throttling:
                            backoff *= cfg.backoff_factor
                            if backoff <= cfg.backoff_cap:
                                sleep_time = backoff

                elif (code == 'errors.com.epicgames.common.concurrent_modification_error'  # noqa
                        or code == 'errors.com.epicgames.common.server_error'
                        or gql_server_error):  # noqa
                    sleep_time = 0.5 + (tries - 1) * 2

                if sleep_time > 0:
                    total_slept += sleep_time
                    if cfg.max_wait_time and total_slept > cfg.max_wait_time:
                        raise

                    log.debug('Retrying {0} {1} in {2:.2f}s.'.format(
                        method,
                        url,
                        sleep_time
                    ))
                    await asyncio.sleep(sleep_time)
                    continue
                raise

            except aiohttp.ServerDisconnectedError:
                await asyncio.sleep(0.5 + (tries - 1) * 2)
                continue
            except OSError as exc:
                if exc.errno in (54, 10054):
                    continue
                raise

            finally:
                if endpoint_event is not None:
                    del self._endpoint_events[url_key]
                    endpoint_event.set()

    async def get(self, route: Union[Route, str],
                  auth: Optional[str] = None,
                  **kwargs: Any) -> Any:
        return await self.fn_request('GET', route, auth, **kwargs)

    async def post(self, route: Union[Route, str],
                   auth: Optional[str] = None,
                   **kwargs: Any) -> Any:
        return await self.fn_request('POST', route, auth, **kwargs)

    async def delete(self, route: Union[Route, str],
                     auth: Optional[str] = None,
                     **kwargs: Any) -> Any:
        return await self.fn_request('DELETE', route, auth, **kwargs)

    async def patch(self, route: Union[Route, str],
                    auth: Optional[str] = None,
                    **kwargs: Any) -> Any:
        return await self.fn_request('PATCH', route, auth, **kwargs)

    async def put(self, route: Union[Route, str],
                  auth: Optional[str] = None,
                  **kwargs: Any) -> Any:
        return await self.fn_request('PUT', route, auth, **kwargs)

    async def graphql_request(self, graphql: Union[GraphQLRequest,
                                                   List[GraphQLRequest]],
                              auth: Optional[str] = None,
                              **kwargs: Any) -> Any:
        return await self.fn_request('POST', EpicGamesGraphQL(), auth, graphql,
                                     **kwargs)

    ###################################
    #        Epicgames GraphQL        #
    ###################################

    async def graphql_friends_set_alias(self) -> Any:
        variables = {
            "friendId": "65db72079052463cb345d23ee27ae6a1",
            "alias": "Hallo1233"
        }

        query = """
        mutation FriendsMutation($friendId: String!, $alias: String!) {
            Friends {
                setAlias(friendId: $friendId, alias: $alias) {
                    success
                }
            }
        }"""

        return await self.graphql_request(
            GraphQLRequest(query, variables=variables))

    async def graphql_initialize_friends_request(self) -> List[dict]:
        queries = (
            GraphQLRequest(
                query="""
                query FriendsQuery($displayNames: Boolean!) {
                    Friends {
                        summary(displayNames: $displayNames) {
                            friends {
                                alias
                                note
                                favorite
                                ...friendFields
                            }
                            incoming {
                                ...friendFields
                            }
                            outgoing {
                                ...friendFields
                            }
                            blocklist {
                                ...friendFields
                            }
                        }
                    }
                }

                fragment friendFields on Friend {
                    accountId
                    displayName
                    account {
                        externalAuths {
                            type
                            accountId
                            externalAuthId
                            externalDisplayName
                        }
                    }
                }
                """,
                variables={
                    'displayNames': True
                }
            ),
            GraphQLRequest(
                query="""
                query PresenceV2Query($namespace: String!, $circle: String!) {
                    PresenceV2 {
                        getLastOnlineSummary(namespace: $namespace, circle: $circle) {
                            summary { #Type: [LastOnline]
                                friendId #Type: String
                                last_online #Type: String
                            }
                        }
                    }
                }
                """,  # noqa
                variables={
                    'namespace': 'Fortnite',
                    'circle': 'friends'
                }
            )
        )

        return await self.graphql_request(queries)

    ###################################
    #            Epicgames            #
    ###################################

    async def epicgames_get_csrf(self) -> aiohttp.ClientResponse:
        return await self.get(EpicGames('/id/api/csrf'), raw=True)

    async def epicgames_reputation(self, xsrf_token: str) -> Any:
        headers = {
            'x-xsrf-token': xsrf_token
        }

        return await self.get(EpicGames('/id/api/reputation'), headers=headers)

    async def epicgames_login(self, email: str,
                              password: str,
                              xsrf_token: str) -> Any:
        headers = {
            'x-xsrf-token': xsrf_token
        }

        payload = {
            'email': email,
            'password': password,
            'rememberMe': False,
            'captcha': ''
        }

        return await self.post(EpicGames('/id/api/login'),
                               headers=headers,
                               data=payload)

    async def epicgames_mfa_login(self, method: str,
                                  code: str,
                                  xsrf_token: str) -> Any:
        headers = {
            'x-xsrf-token': xsrf_token
        }

        payload = {
            'code': code,
            'method': method,
            'rememberDevice': False
        }

        return await self.post(EpicGames('/id/api/login/mfa'),
                               headers=headers,
                               data=payload)

    async def epicgames_redirect(self, xsrf_token: str) -> Any:
        headers = {
            'x-xsrf-token': xsrf_token
        }

        return await self.get(EpicGames('/id/api/redirect'), headers=headers)

    async def epicgames_get_exchange_data(self, xsrf_token: str) -> dict:
        headers = {
            'x-xsrf-token': xsrf_token
        }

        r = EpicGames('/id/api/exchange/generate')
        return await self.post(r, headers=headers)

    ###################################
    #        Payment Website          #
    ###################################

    async def payment_website_search_sac_by_slug(self, slug: str) -> Any:
        params = {
            'slug': slug
        }

        r = PaymentWebsite('/affiliate/search-by-slug', auth=None)
        return await self.get(r, params=params)

    ###################################
    #           Lightswitch           #
    ###################################

    async def lightswitch_get_status(self, *,
                                     service_id: Optional[str] = None) -> list:
        params = {'serviceId': service_id} if service_id else None

        r = LightswitchPublicService('/lightswitch/api/service/bulk/status')
        return await self.get(r, params=params)

    ###################################
    #           User Search           #
    ###################################

    async def user_search_by_prefix(self, prefix: str, platform: str) -> list:
        params = {
            'prefix': prefix,
            'platform': platform
        }

        r = UserSearchService('/api/v1/search')
        return await self.get(r, params=params)

    ###################################
    #            Account              #
    ###################################

    async def account_get_exchange_data(self, auth: str,
                                        **kwargs: Any) -> dict:
        r = AccountPublicService('/account/api/oauth/exchange')
        return await self.get(r, auth=auth, **kwargs)

    async def account_oauth_grant(self, **kwargs: Any) -> dict:
        r = AccountPublicService('/account/api/oauth/token')
        return await self.post(r, **kwargs)

    async def account_generate_device_auth(self, client_id: str) -> dict:
        r = AccountPublicService(
            '/account/api/public/account/{client_id}/deviceAuth',
            client_id=client_id
        )
        return await self.post(r, auth="IOS_ACCESS_TOKEN", json={})

    async def account_get_device_auths(self, client_id: str) -> list:
        r = AccountPublicService(
            '/account/api/public/account/{client_id}/deviceAuth',
            client_id=client_id,
            auth="IOS_ACCESS_TOKEN"
        )
        return await self.get(r)

    async def account_lookup_device_auth(self, client_id: str,
                                         device_id: str) -> dict:
        r = AccountPublicService(
            '/account/api/public/account/{client_id}/deviceAuth/{device_id}',
            client_id=client_id,
            device_id=device_id,
            auth="IOS_ACCESS_TOKEN"
        )
        return await self.get(r)

    async def account_delete_device_auth(self, client_id: str,
                                         device_id: str) -> None:
        r = AccountPublicService(
            '/account/api/public/account/{client_id}/deviceAuth/{device_id}',
            client_id=client_id,
            device_id=device_id,
            auth="IOS_ACCESS_TOKEN"
        )
        return await self.delete(r)

    async def account_sessions_kill_token(self, token: str, auth=None) -> Any:
        r = AccountPublicService(
            '/account/api/oauth/sessions/kill/{token}',
            token=token
        )
        return await self.delete(r, auth='bearer {0}'.format(token))

    async def account_sessions_kill(self, kill_type: str,
                                    auth='IOS_ACCESS_TOKEN',
                                    **kwargs: Any) -> Any:
        params = {
            'killType': kill_type
        }

        r = AccountPublicService('/account/api/oauth/sessions/kill')
        return await self.delete(r, params=params, auth=auth, **kwargs)

    async def account_get_by_display_name(self, display_name: str) -> dict:
        r = AccountPublicService(
            '/account/api/public/account/displayName/{display_name}',
            display_name=display_name
        )
        return await self.get(r)

    async def account_get_by_user_id(self, user_id: str, *,
                                     auth: Optional[str] = None,
                                     **kwargs: Any) -> dict:
        r = AccountPublicService(
            '/account/api/public/account/{user_id}',
            user_id=user_id
        )
        return await self.get(r, auth=auth, **kwargs)

    async def account_get_by_email(self, email: str) -> dict:
        r = AccountPublicService(
            '/account/api/public/account/email/{email}',
            email=email
        )
        return await self.get(r, auth='IOS_ACCESS_TOKEN')

    async def account_get_external_auths_by_id(self, user_id: str,
                                               **kwargs: Any) -> list:
        r = AccountPublicService(
            '/account/api/public/account/{user_id}/externalAuths',
            user_id=user_id
        )
        return await self.get(r, **kwargs)

    async def account_get_multiple_by_user_id(self,
                                              user_ids: List[str]) -> list:
        params = [('accountId', user_id) for user_id in user_ids]
        r = AccountPublicService('/account/api/public/account')
        return await self.get(r, params=params)

    async def account_graphql_get_multiple_by_user_id(self,
                                                      user_ids: List[str],
                                                      **kwargs: Any
                                                      ) -> dict:
        return await self.graphql_request(GraphQLRequest(
            query="""
            query AccountQuery($accountIds: [String]!) {
                Account {
                    # Get details about an account given an account ID
                    accounts(accountIds: $accountIds) { #Type: [Account]
                        # The AccountID for this account
                        id #Type: String
                        # The epic display name for this account
                        displayName #Type: String
                        # External auths associated with this account
                        externalAuths { #Type: [ExternalAuth]
                            type #Type: String
                            accountId #Type: String
                            externalAuthId #Type: String
                            externalDisplayName #Type: String
                        }
                    }
                }
            }
            """,
            variables={
                'accountIds': user_ids
            }
        ), **kwargs)

    async def account_graphql_get_by_display_name(self,
                                                  display_name: str) -> dict:
        return await self.graphql_request(GraphQLRequest(
            query="""
            query AccountQuery($displayName: String!) {
                Account {
                    account(displayName: $displayName) {
                        id
                        displayName
                        externalAuths {
                            type
                            accountId
                            externalAuthId
                            externalDisplayName
                        }
                    }
                }
            }
            """,
            variables={
                'displayName': display_name
            }
        ))

    async def account_graphql_get_clients_external_auths(self,
                                                         **kwargs: Any
                                                         ) -> dict:
        return await self.graphql_request(GraphQLRequest(
            query="""
            query AccountQuery {
                Account {
                    myAccount {
                        externalAuths {
                            type
                            accountId
                            externalAuthId
                            externalDisplayName
                        }
                    }
                }
            }
            """
        ), **kwargs)

    ###################################
    #          Eula Tracking          #
    ###################################

    async def eulatracking_get_data(self, **kwargs: Any) -> dict:
        r = EulatrackingPublicService(
            '/eulatracking/api/public/agreements/fn/account/{client_id}',
            client_id=self.client.user.id
        )
        return await self.get(r, **kwargs)

    async def eulatracking_accept(self, version: int, *,
                                  locale: str = 'en',
                                  **kwargs: Any) -> Any:
        params = {
            'locale': locale
        }

        r = EulatrackingPublicService(
            ('/eulatracking/api/public/agreements/fn/version/{version}'
             '/account/{client_id}/accept'),
            version=version,
            client_id=self.client.user.id
        )
        return await self.post(r, params=params, **kwargs)

    ###################################
    #         Fortnite Public         #
    ###################################

    async def fortnite_grant_access(self, **kwargs: Any) -> Any:
        r = FortnitePublicService(
            '/fortnite/api/game/v2/grant_access/{client_id}',
            client_id=self.client.user.id
        )
        return await self.post(r, json={}, **kwargs)

    async def fortnite_get_store_catalog(self) -> dict:
        r = FortnitePublicService('/fortnite/api/storefront/v2/catalog')
        return await self.get(r)

    async def fortnite_get_timeline(self) -> dict:
        r = FortnitePublicService('/fortnite/api/calendar/v1/timeline')
        return await self.get(r)

    ###################################
    #        Fortnite Content         #
    ###################################

    async def fortnitecontent_get(self) -> dict:
        r = FortniteContentWebsite('/content/api/pages/fortnite-game')
        return await self.get(r)

    ###################################
    #            Friends              #
    ###################################

    async def friends_get_all(self, *,
                              include_pending: bool = False,
                              **kwargs) -> list:
        params = {
            'includePending': include_pending
        }

        r = FriendsPublicService('/friends/api/public/friends/{client_id}',
                                 client_id=self.client.user.id)
        return await self.get(r, params=params, **kwargs)

    async def friends_add_or_accept(self, user_id: str) -> Any:
        r = FriendsPublicService(
            '/friends/api/v1/{client_id}/friends/{user_id}',
            client_id=self.client.user.id,
            user_id=user_id
        )
        return await self.post(r)

    async def friends_remove_or_decline(self, user_id: str) -> Any:
        r = FriendsPublicService(
            '/friends/api/v1/{client_id}/friends/{user_id}',
            client_id=self.client.user.id,
            user_id=user_id
        )
        return await self.delete(r)

    async def friends_get_blocklist(self) -> list:
        r = FriendsPublicService('/friends/api/v1/{client_id}/blocklist',
                                 client_id=self.client.user.id)
        return await self.get(r)

    async def friends_set_nickname(self, user_id: str, nickname: str) -> Any:
        r = FriendsPublicService(
            '/friends/api/v1/{client_id}/friends/{user_id}/alias',
            client_id=self.client.user.id,
            user_id=user_id
        )
        return await self.put(r, data=nickname)

    async def friends_remove_nickname(self, user_id: str) -> Any:
        r = FriendsPublicService(
            '/friends/api/v1/{client_id}/friends/{user_id}/alias',
            client_id=self.client.user.id,
            user_id=user_id
        )
        return await self.delete(r)

    async def friends_set_note(self, user_id: str, note: str) -> Any:
        r = FriendsPublicService(
            '/friends/api/v1/{client_id}/friends/{user_id}/note',
            client_id=self.client.user.id,
            user_id=user_id
        )
        return await self.put(r, data=note)

    async def friends_remove_note(self, user_id: str) -> Any:
        r = FriendsPublicService(
            '/friends/api/v1/{client_id}/friends/{user_id}/note',
            client_id=self.client.user.id,
            user_id=user_id
        )
        return await self.delete(r)

    async def friends_get_summary(self, **kwargs) -> dict:
        r = FriendsPublicService('/friends/api/v1/{client_id}/summary',
                                 client_id=self.client.user.id)
        return await self.get(r, **kwargs)

    async def friends_block(self, user_id: str) -> Any:
        r = FriendsPublicService(
            '/friends/api/v1/{client_id}/blocklist/{user_id}',
            client_id=self.client.user.id,
            user_id=user_id
        )
        return await self.post(r)

    async def friends_unblock(self, user_id: str) -> Any:
        r = FriendsPublicService(
            '/friends/api/v1/{client_id}/blocklist/{user_id}',
            client_id=self.client.user.id,
            user_id=user_id
        )
        return await self.delete(r)

    async def friends_get_mutual(self, user_id: str) -> Any:
        r = FriendsPublicService(
            '/friends/api/v1/{client_id}/friends/{user_id}/mutual',
            client_id=self.client.user.id,
            user_id=user_id
        )
        return await self.get(r)

    ###################################
    #            Presence             #
    ###################################

    async def presence_get_last_online(self, **kwargs) -> dict:
        r = PresencePublicService('/presence/api/v1/_/{client_id}/last-online',
                                  client_id=self.client.user.id)
        return await self.get(r, **kwargs)

    ###################################
    #              Stats              #
    ###################################

    async def stats_get_v2(self, user_id: str, *,
                           start_time: Optional[int] = None,
                           end_time: Optional[int] = None) -> dict:
        params = {}
        if start_time:
            params['startTime'] = start_time
        if end_time:
            params['endTime'] = end_time

        r = StatsproxyPublicService(
            '/statsproxy/api/statsv2/account/{user_id}',
            user_id=user_id
        )
        return await self.get(r, params=params)

    async def stats_get_multiple_v2(self, ids: List[str], stats: List[str], *,
                                    start_time: Optional[int] = None,
                                    end_time: Optional[int] = None) -> list:
        payload = {
            'appId': 'fortnite',
            'owners': ids,
            'stats': stats
        }
        if start_time:
            payload['startDate'] = start_time
        if end_time:
            payload['endDate'] = end_time

        r = StatsproxyPublicService('/statsproxy/api/statsv2/query')
        return await self.post(r, json=payload)

    async def stats_get_leaderboard_v2(self, stat: str) -> dict:
        r = StatsproxyPublicService(
            '/statsproxy/api/statsv2/leaderboards/{stat}',
            stat=stat
        )
        return await self.get(r)

    ###################################
    #             Party               #
    ###################################

    async def party_disconnect(self, party_id: str, user_id: str):
        r = PartyService(
            'party/api/v1/Fortnite/parties/{party_id}/members/{user_id}/disconnect',  # noqa
            party_id=party_id,
            user_id=user_id,
        )
        return await self.post(r)

    async def party_send_invite(self, party_id: str,
                                user_id: str,
                                send_ping: bool = True) -> Any:
        conn_type = self.client.default_party_member_config.cls.CONN_TYPE
        payload = {
            'urn:epic:cfg:build-id_s': self.client.party_build_id,
            'urn:epic:conn:platform_s': self.client.platform.value,
            'urn:epic:conn:type_s': conn_type,
            'urn:epic:invite:platformdata_s': '',
            'urn:epic:member:dn_s': self.client.user.display_name,
        }

        params = {
            'sendPing': send_ping
        }

        r = PartyService(
            '/party/api/v1/Fortnite/parties/{party_id}/invites/{user_id}',
            party_id=party_id,
            user_id=user_id
        )
        return await self.post(r, json=payload, params=params)

    async def party_delete_invite(self, party_id: str, user_id: str) -> Any:
        r = PartyService(
            '/party/api/v1/Fortnite/parties/{party_id}/invites/{user_id}',
            party_id=party_id,
            user_id=user_id
        )
        return await self.delete(r)

    # NOTE: Depracated since fortnite v11.30. Use param sendPing=True with
    #       send_invite
    # NOTE: Now used for sending invites from private parties
    async def party_send_ping(self, user_id: str) -> Any:
        r = PartyService(
            '/party/api/v1/Fortnite/user/{user_id}/pings/{client_id}',
            user_id=user_id,
            client_id=self.client.user.id
        )
        return await self.post(r, json={})

    async def party_delete_ping(self, user_id: str) -> Any:
        r = PartyService(
            '/party/api/v1/Fortnite/user/{client_id}/pings/{user_id}',
            client_id=self.client.user.id,
            user_id=user_id
        )
        return await self.delete(r)

    async def party_decline_invite(self, party_id: str) -> Any:
        r = PartyService(
            ('/party/api/v1/Fortnite/parties/{party_id}/invites/'
             '{client_id}/decline'),
            party_id=party_id,
            client_id=self.client.user.id
        )
        return await self.post(r, json={})

    async def party_member_confirm(self, party_id: str, user_id: str) -> Any:
        r = PartyService(
            ('/party/api/v1/Fortnite/parties/{party_id}/members/'
             '{user_id}/confirm'),
            party_id=party_id,
            user_id=user_id
        )
        return await self.post(r, json={})

    async def party_member_reject(self, party_id: str, user_id: str) -> Any:
        r = PartyService(
            ('/party/api/v1/Fortnite/parties/{party_id}/members/'
             '{user_id}/reject'),
            party_id=party_id,
            user_id=user_id
        )
        return await self.post(r, json={})

    async def party_promote_member(self, party_id: str, user_id: str) -> Any:
        r = PartyService(
            ('/party/api/v1/Fortnite/parties/{party_id}/members/'
             '{user_id}/promote'),
            party_id=party_id,
            user_id=user_id
        )
        return await self.post(r, json={})

    async def party_kick_member(self, party_id: str, user_id: str) -> Any:
        r = PartyService(
            '/party/api/v1/Fortnite/parties/{party_id}/members/{user_id}',
            party_id=party_id,
            user_id=user_id
        )
        return await self.delete(r)

    async def party_leave(self, party_id: str, **kwargs: Any) -> Any:
        conn_type = self.client.default_party_member_config.cls.CONN_TYPE
        payload = {
            'connection': {
                'id': self.client.user.jid,
                'meta': {
                    'urn:epic:conn:platform_s': self.client.platform.value,
                    'urn:epic:conn:type_s': conn_type,
                },
            },
            'meta': {
                'urn:epic:member:dn_s': self.client.user.display_name,
                'urn:epic:member:type_s': conn_type,
                'urn:epic:member:platform_s': self.client.platform.value,
                'urn:epic:member:joinrequest_j': json.dumps({
                    'CrossplayPreference_i': '1'
                }),
            }
        }

        r = PartyService(
            '/party/api/v1/Fortnite/parties/{party_id}/members/{client_id}',
            party_id=party_id,
            client_id=self.client.user.id
        )
        return await self.delete(r, json=payload, **kwargs)

    async def party_join_request(self, party_id: str) -> Any:
        conf = self.client.default_party_member_config
        conn_type = conf.cls.CONN_TYPE
        payload = {
            'connection': {
                'id': str(self.client.xmpp.xmpp_client.local_jid),
                'meta': {
                    'urn:epic:conn:platform_s': self.client.platform.value,
                    'urn:epic:conn:type_s': conn_type,
                },
                'yield_leadership': conf.yield_leadership,
                'offline_ttl': conf.offline_ttl,
            },
            'meta': {
                'urn:epic:member:dn_s': self.client.user.display_name,
                'urn:epic:member:joinrequestusers_j': json.dumps({
                    'users': [
                        {
                            'id': self.client.user.id,
                            'dn': self.client.user.display_name,
                            'plat': self.client.platform.value,
                            'data': json.dumps({
                                'CrossplayPreference': '1',
                                'SubGame_u': '1',
                            })
                        }
                    ]
                }),
            },
        }

        r = PartyService(
            ('/party/api/v1/Fortnite/parties/{party_id}/members/'
             '{client_id}/join'),
            party_id=party_id,
            client_id=self.client.user.id
        )
        return await self.post(r, json=payload)

    async def party_lookup(self, party_id: str, **kwargs: Any) -> dict:
        r = PartyService('/party/api/v1/Fortnite/parties/{party_id}',
                         party_id=party_id)
        return await self.get(r, **kwargs)

    async def party_lookup_user(self, user_id: str, **kwargs: Any) -> dict:
        r = PartyService('/party/api/v1/Fortnite/user/{user_id}',
                         user_id=user_id)
        return await self.get(r, **kwargs)

    async def party_lookup_ping(self, user_id: str) -> list:
        r = PartyService(
            ('/party/api/v1/Fortnite/user/{client_id}/pings/'
             '{user_id}/parties'),
            client_id=self.client.user.id,
            user_id=user_id
        )
        return await self.get(r)

    async def party_create(self, config: dict, **kwargs: Any) -> dict:
        conf = self.client.default_party_member_config
        conn_type = conf.cls.CONN_TYPE

        _chat_enabled = str(config['chat_enabled']).lower()
        payload = {
            'config': {
                'join_confirmation': config['join_confirmation'],
                'joinability': config['joinability'],
                'max_size': config['max_size']
            },
            'join_info': {
                'connection': {
                    'id': str(self.client.xmpp.xmpp_client.local_jid),
                    'meta': {
                        'urn:epic:conn:platform_s': self.client.platform.value,
                        'urn:epic:conn:type_s': conn_type
                    },
                    'yield_leadership': conf.yield_leadership,
                    'offline_ttl': conf.offline_ttl,
                },
            },
            'meta': {
                'urn:epic:cfg:accepting-members_b': False,
                'urn:epic:cfg:build-id_s': str(self.client.party_build_id),
                'urn:epic:cfg:can-join_b': True,
                'urn:epic:cfg:chat-enabled_b': _chat_enabled,
                'urn:epic:cfg:invite-perm_s': 'Noone',
                'urn:epic:cfg:join-request-action_s': 'Manual',
                'urn:epic:cfg:not-accepting-members-reason_i': 0,
                'urn:epic:cfg:party-type-id_s': 'default',
                'urn:epic:cfg:presence-perm_s': 'Noone',
            }
        }

        r = PartyService('/party/api/v1/Fortnite/parties')
        return await self.post(r, json=payload, **kwargs)

    async def party_update_member_meta(self, party_id: str,
                                       user_id: str,
                                       updated_meta: dict,
                                       deleted_meta: list,
                                       overridden_meta: dict,
                                       revision: int,
                                       override: dict = {},
                                       **kwargs: Any) -> Any:
        payload = {
            'delete': deleted_meta,
            'update': updated_meta,
            'override': overridden_meta,
            'revision': revision,
        }

        r = PartyService(
            ('/party/api/v1/Fortnite/parties/{party_id}/members/'
             '{user_id}/meta'),
            party_id=party_id,
            user_id=user_id
        )
        return await self.patch(r, json=payload, **kwargs)

    async def party_update_meta(self, party_id: str,
                                updated_meta: dict,
                                deleted_meta: list,
                                overridden_meta: dict,
                                revision: int,
                                config: dict = {},
                                **kwargs: Any) -> Any:
        payload = {
            'meta': {
                'delete': deleted_meta,
                'update': updated_meta,
                'override': overridden_meta
            },
            'revision': revision,
        }

        if config:
            payload['config'] = config

        r = PartyService('/party/api/v1/Fortnite/parties/{party_id}',
                         party_id=party_id)
        return await self.patch(r, json=payload, **kwargs)
