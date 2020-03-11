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
import logging
import uuid

from aioconsole import ainput
from typing import TYPE_CHECKING, Optional, Any, Callable, Awaitable, Union

from .errors import AuthException, HTTPException

if TYPE_CHECKING:
    from .client import Client

log = logging.getLogger(__name__)
_prompt_lock = asyncio.Lock()
AnyCallable = Union[Callable, Awaitable]


class Auth:
    def __init__(self, **kwargs: Any) -> None:
        self.launcher_token = kwargs.get('launcher_token', 'MzRhMDJjZjhmNDQxNGUyOWIxNTkyMTg3NmRhMzZmOWE6ZGFhZmJjY2M3Mzc3NDUwMzlkZmZlNTNkOTRmYzc2Y2Y=')  # noqa
        self.fortnite_token = kwargs.get('fortnite_token', 'ZWM2ODRiOGM2ODdmNDc5ZmFkZWEzY2IyYWQ4M2Y1YzY6ZTFmMzFjMjExZjI4NDEzMTg2MjYyZDM3YTEzZmM4NGQ=')  # noqa

    def initialize(self, client: 'Client') -> None:
        self.client = client
        self.device_id = getattr(self, 'device_id', None) or uuid.uuid4().hex
        self._refresh_event = asyncio.Event(loop=self.client.loop)
        self._refresh_lock = asyncio.Lock()
        self.refresh_i = 0

    @property
    def launcher_authorization(self) -> str:
        return 'bearer {0}'.format(self.launcher_access_token)

    @property
    def authorization(self) -> str:
        return 'bearer {0}'.format(self.access_token)

    @property
    def identifier(self) -> str:
        raise NotImplementedError

    async def authenticate(self) -> dict:
        raise NotImplementedError

    async def _authenticate(self) -> None:
        try:
            log.info('Running authentication.')
            data = await self.authenticate()
            self._update_data(data)
        except asyncio.CancelledError:
            pass

    async def get_eula_version(self) -> int:
        data = await self.client.http.eulatracking_get_data()
        return data['version'] if isinstance(data, dict) else 0

    async def accept_eula(self) -> None:
        version = await self.get_eula_version()
        if version != 0:
            await self.client.http.eulatracking_accept(version)

            try:
                await self.client.http.fortnite_grant_access()
            except HTTPException as e:
                if e.message_code != 'errors.com.epicgames.bad_request':
                    raise

    def _update_launcher_data(self, data: dict) -> None:
        self.launcher_access_token = data['access_token']
        self.launcher_expires_in = data['expires_in']
        self.launcher_expires_at = self.client.from_iso(data["expires_at"])
        self.launcher_token_type = data['token_type']
        self.launcher_refresh_token = data['refresh_token']
        self.launcher_refresh_expires = data['refresh_expires']
        self.launcher_refresh_expires_at = data['refresh_expires_at']
        self.launcher_account_id = data['account_id']
        self.launcher_client_id = data['client_id']
        self.launcher_internal_client = data['internal_client']
        self.launcher_client_service = data['client_service']
        self.launcher_app = data['app']
        self.launcher_in_app_id = data['in_app_id']

    def _update_data(self, data: dict) -> None:
        self.access_token = data['access_token']
        self.expires_in = data['expires_in']
        self.expires_at = self.client.from_iso(data["expires_at"])
        self.token_type = data['token_type']
        self.refresh_token = data['refresh_token']
        self.refresh_expires = data['refresh_expires']
        self.refresh_expires_at = data['refresh_expires_at']
        self.account_id = data['account_id']
        self.client_id = data['client_id']
        self.internal_client = data['internal_client']
        self.client_service = data['client_service']
        self.app = data['app']
        self.in_app_id = data['in_app_id']

    async def grant_refresh_token(self, refresh_token: str,
                                  auth_token: str) -> dict:
        payload = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }

        return await self.client.http.account_oauth_grant(
            auth='basic {0}'.format(auth_token),
            device_id=True,
            data=payload
        )

    async def get_exchange_code(self) -> str:
        data = await self.client.http.account_get_exchange_data(
            auth='LAUNCHER_ACCESS_TOKEN'
        )
        return data.get('code')

    async def exchange_launcher_code(self, code: str) -> dict:
        payload = {
            'grant_type': 'exchange_code',
            'exchange_code': code,
            'token_type': 'eg1',
        }

        return await self.client.http.account_oauth_grant(
            auth='basic {0}'.format(self.launcher_token),
            device_id=True,
            data=payload
        )

    async def exchange_fortnite_code(self) -> dict:
        code = await self.get_exchange_code()

        payload = {
            'grant_type': 'exchange_code',
            'token_type': 'eg1',
            'exchange_code': code
        }

        return await self.client.http.account_oauth_grant(
            auth='basic {0}'.format(self.fortnite_token),
            device_id=True,
            data=payload
        )

    async def kill_token(self, token: str) -> None:
        await self.client.http.account_sessions_kill_token(
            token,
            auth='bearer {0}'.format(token)
        )

    async def schedule_token_refresh(self) -> None:
        subtracted = self.launcher_expires_at - datetime.datetime.utcnow()
        self.token_timeout = (subtracted).total_seconds() - 300
        await asyncio.sleep(self.token_timeout)

    async def run_refresh_loop(self) -> None:
        loop = self.client.loop

        while True:
            self._refresh_event.clear()
            await asyncio.wait((
                loop.create_task(self._refresh_event.wait()),
                loop.create_task(self.schedule_token_refresh())
            ), return_when=asyncio.FIRST_COMPLETED)

            await self.do_refresh()

    async def do_refresh(self) -> None:
        async with self._refresh_lock:
            log.debug('Refreshing session')
            if self.client.user.party is not None:
                await self.client.user.party._leave()

            data = await self.grant_refresh_token(
                self.launcher_refresh_token,
                self.launcher_token
            )
            self._update_launcher_data(data)

            exchange_data = await self.grant_refresh_token(
                self.refresh_token,
                self.fortnite_token
            )
            self._update_data(exchange_data)

            log.debug('Refreshing xmpp session')
            await self.client.xmpp.close()
            await self.client.xmpp.run()

            await self.client._create_party()

            self.refresh_i += 1
            self.client.dispatch_event('auth_refresh')

    async def run_refresh(self) -> None:
        self._refresh_event.set()
        await self.client.wait_for('auth_refresh')

    def refreshing(self) -> bool:
        return self._refresh_lock.locked()


class EmailAndPasswordAuth(Auth):
    """Authenticates by email and password.

    .. warning::

        Some users might experience an error saying captcha was invalid.
        If this is the case, use :class:`AdvancedAuth` with an exchange code
        to generate a device auth.

    Parameters
    ----------
    email: :class:`str`
        The accounts email.
    password: :class:`str`
        The accounts password.
    two_factor_code: Optional[:class:`int`]
        The current two factor code if needed. If not passed here, it
        will be prompted later.
    device_id: Optional[:class:`str`]
        A 32 char hex representing your device.
    launcher_token: Optional[:class:`str`]
        The launcher token to use with authentication. You should generally
        not need to set this manually.
    fortnite_token: Optional[:class:`str`]
        The fortnite token to use with authentication. You should generally
        not need to set this manually.
    """
    def __init__(self, email: str, password: str, *,
                 two_factor_code: Optional[int] = None,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.email = email
        self.password = password
        self.two_factor_code = two_factor_code

    @property
    def identifier(self) -> str:
        return self.email

    async def fetch_xsrf_token(self) -> str:
        response = await self.client.http.epicgames_get_csrf()
        return response.cookies['XSRF-TOKEN'].value

    async def launcher_authenticate(self) -> dict:
        log.info('Fetching valid xsrf token.')
        token = await self.fetch_xsrf_token()

        await self.client.http.epicgames_reputation(token)

        try:
            log.info('Logging in.')
            await self.client.http.epicgames_login(
                self.email,
                self.password,
                token
            )
        except HTTPException as e:
            m = 'errors.com.epicgames.account.invalid_account_credentials'
            if e.message_code == m:
                raise AuthException(
                    'Invalid account credentials passed.'
                ) from e

            if e.message_code != ('errors.com.epicgames.common.'
                                  'two_factor_authentication.required'):
                raise

            log.info('Logging in interrupted. 2fa required.')
            log.info('Fetching new valid xsrf token.')
            token = await self.fetch_xsrf_token()

            code = self.two_factor_code
            if code is None:
                async with _prompt_lock:
                    code = await ainput(
                        'Please enter the 2fa code:\n',
                        loop=self.client.loop
                    )

            try:
                await self.client.http.epicgames_mfa_login(
                    e.raw['metadata']['twoFactorMethod'],
                    code,
                    token
                )
            except HTTPException as exc:
                m = (
                    'errors.com.epicgames.accountportal.mfa_code_invalid',
                    'errors.com.epicgames.accountportal.validation'
                )
                if exc.message_code in m:
                    raise AuthException(
                        'Invalid 2fa code passed.'
                    ) from exc

                raise

        await self.client.http.epicgames_redirect(token)

        log.info('Fetching exchange code.')
        data = await self.client.http.epicgames_get_exchange_data(token)

        log.info('Exchanging code.')
        data = await self.exchange_launcher_code(data['code'])
        self._update_launcher_data(data)
        return data

    async def authenticate(self) -> dict:
        await self.launcher_authenticate()
        return await self.exchange_fortnite_code()


class ExchangeCodeAuth(Auth):
    """Authenticates by exchange code. You can get the code from `here
    <https://www.epicgames.com/id/login?redirectUrl=https%3A%2F%2F
    www.epicgames.com%2Fid%2Fapi%2Fexchange>`_ by logging in and copying
    the code that then displays. If you are already logged in and want
    to change accounts, simply log out at https://www.epicgames.com,
    log in to the new account and then enter the link above again to
    generate an exchange code.

    .. note::

        The exchange code only works for a single login within a short
        timeframe. Therefore you need to get a new code for each login.
        You can get a new code by refreshing the site.

    Parameters
    ----------
    exchange_code: Union[:class:`str`, Union[Callable, Awaitable]]
        The exchange code or a function/coroutine that when called returns
        the exchange code.
    device_id: Optional[:class:`str`]
        A 32 char hex representing your device.
    launcher_token: Optional[:class:`str`]
        The launcher token to use with authentication. You should generally
        not need to set this manually.
    fortnite_token: Optional[:class:`str`]
        The fortnite token to use with authentication. You should generally
        not need to set this manually.
    """
    def __init__(self, exchange_code: Union[str, AnyCallable],
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.exchange_code = exchange_code
        self.resolved_code = None

    async def resolve(self, code_or_callable: Union[str, AnyCallable]) -> str:
        if isinstance(code_or_callable, str):
            return code_or_callable

        elif asyncio.iscoroutinefunction(code_or_callable):
            res = await code_or_callable()
        else:
            res = code_or_callable()

        if not isinstance(res, str):
            raise TypeError('Return type of callable func/coro must be str')

        return res

    @property
    def identifier(self) -> str:
        return self.resolved_code

    async def launcher_authenticate(self) -> dict:
        log.info('Exchanging code.')
        self.resolved_code = await self.resolve(self.exchange_code)

        try:
            data = await self.exchange_launcher_code(self.resolved_code)
        except HTTPException as e:
            m = 'errors.com.epicgames.account.oauth.exchange_code_not_found'
            if e.message_code == m:
                raise AuthException(
                    'Invalid exchange code supplied'
                ) from e

            raise

        self._update_launcher_data(data)
        return data

    async def authenticate(self) -> dict:
        await self.launcher_authenticate()
        return await self.exchange_fortnite_code()


class DeviceAuth(Auth):
    """Authenticate with device auth details.

    .. note::

        All device auths generated for an account is removed once the accounts
        password gets reset. If you managed to leak you device_id and secret,
        simply reset the accounts password and everything should be fine.

    Parameters
    ----------
    device_id: :class:`str`
        The device id.
    account_id: :class:`str`
        The account's id.
    secret: :class:`str`
        The secret.
    launcher_token: Optional[:class:`str`]
        The launcher token to use with authentication. You should generally
        not need to set this manually.
    fortnite_token: Optional[:class:`str`]
        The fortnite token to use with authentication. You should generally
        not need to set this manually.
    """
    def __init__(self, device_id: str,
                 account_id: str,
                 secret: str,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.device_id = device_id
        self.account_id = account_id
        self.secret = secret

        self.ios_token = kwargs.get('ios_token', 'MzQ0NmNkNzI2OTRjNGE0NDg1ZDgxYjc3YWRiYjIxNDE6OTIwOWQ0YTVlMjVhNDU3ZmI5YjA3NDg5ZDMxM2I0MWE=')  # noqa

    @property
    def identifier(self) -> str:
        return self.account_id

    async def device_auth_authenticate(self) -> dict:
        payload = {
            'grant_type': 'device_auth',
            'device_id': self.device_id,
            'account_id': self.account_id,
            'secret': self.secret,
            'token_type': 'eg1'
        }

        try:
            data = await self.client.http.account_oauth_grant(
                auth='basic {0}'.format(self.ios_token),
                data=payload
            )
        except HTTPException as exc:
            m = 'errors.com.epicgames.account.invalid_account_credentials'
            if exc.message_code == m:
                raise AuthException(
                    'Invalid device auth details passed.'
                ) from exc

            raise

        self._update_launcher_data(data)
        return data

    async def launcher_authenticate(self) -> dict:
        code = await self.get_exchange_code()
        data = await self.exchange_launcher_code(code)

        await self.kill_token(self.launcher_access_token)
        self._update_launcher_data(data)
        return data

    async def authenticate(self) -> dict:
        await self.device_auth_authenticate()
        await self.launcher_authenticate()
        return await self.exchange_fortnite_code()


class RefreshTokenAuth(Auth):
    """Authenticates by the passed launcher refresh token.

    Parameters
    ----------
    refresh_token: :class:`str`
        A valid launcher refresh token.
    """
    def __init__(self, refresh_token: str,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.refresh_token = refresh_token

    @property
    def identifier(self) -> str:
        return self.refresh_token

    async def launcher_authenticate(self) -> dict:
        data = await self.grant_refresh_token(
            self.refresh_token,
            self.launcher_token
        )
        self._update_launcher_data(data)

    async def authenticate(self) -> dict:
        await self.launcher_authenticate()
        return await self.exchange_fortnite_code()


class AdvancedAuth(Auth):
    """Authenticates by the available data in the following order:

    1. By :class:`DeviceAuth` if ``device_id``, ``account_id`` and ``secret``
    are present.
    2. By :class:`EmailAndPasswordAuth` if ``email`` and ``password`` is
    present. If authentication fails because of required captcha, it then
    attempts to authenticate with the next step.
    3. :class:`ExchangeCodeAuth` is tried if ``exchange_code`` is present
    or if ``prompt_exchange_code`` is ``True``.

    If the authentication was not done by step 1, a device auth is
    automatically generated and is available through
    :func:`event_device_auth_generate`. It is important to store
    these values somewhere since they can be used for easier logins.

    Parameters
    ----------
    email: Optional[:class:`str`]
        The email to use for the login.
    password: Optional[:class:`str`]
        The password to use for the login.
    two_factor_code: Optional[:class:`int`]
        The two factor code to use for the login if needed. If this is
        not passed but later needed, you will be prompted to enter it
        in the console.
    exchange_code: Optional[Union[:class:`str`, Union[Callable, Awaitable]]]
        The exchange code or a function/coroutine that when called returns
        the exchange code.
    device_id: Optional[:class:`str`]
        The device id to use for the login.
    account_id: Optional[:class:`str`]
        The account id to use for the login.
    secret: Optional[:class:`str`]
        The secret to use for the login.
    prompt_exchange_code: :class:`bool`
        If this is set to ``True`` and no exchange code is passed,
        you will be prompted to enter the exchange code in the console
        if needed.
    prompt_exchange_code_if_throttled: :class:`bool`
        | If this is set to ``True`` and you receive a throttling response,
        you will be prompted to enter the exchange code in the console.
        | **NOTE:** This only works if ``prompt_exchange_code`` is ``True``.
    delete_existing_device_auths: :class:`bool`
        Whether or not to delete all existing device auths when a new
        is created.
    ios_token: Optional[:class:`str`]
        The ios token to use with authentication. You should generally
        not need to set this manually.
    launcher_token: Optional[:class:`str`]
        The launcher token to use with authentication. You should generally
        not need to set this manually.
    fortnite_token: Optional[:class:`str`]
        The fortnite token to use with authentication. You should generally
        not need to set this manually.
    """
    def __init__(self, email: Optional[str] = None,
                 password: Optional[str] = None,
                 two_factor_code: Optional[int] = None,
                 exchange_code: Optional[Union[str, AnyCallable]] = None,
                 device_id: Optional[str] = None,
                 account_id: Optional[str] = None,
                 secret: Optional[str] = None,
                 prompt_exchange_code: bool = False,
                 prompt_exchange_code_if_throttled: bool = False,
                 delete_existing_device_auths: bool = False,
                 **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.email = email
        self.password = password
        self.two_factor_code = two_factor_code
        self.exchange_code = exchange_code
        self.device_id = device_id
        self.account_id = account_id
        self.secret = secret

        self.delete_existing_device_auths = delete_existing_device_auths
        self.prompt_exchange_code = prompt_exchange_code
        self.prompt_exchange_code_if_throttled = prompt_exchange_code_if_throttled  # noqa
        self.ios_token = kwargs.get('ios_token', 'MzQ0NmNkNzI2OTRjNGE0NDg1ZDgxYjc3YWRiYjIxNDE6OTIwOWQ0YTVlMjVhNDU3ZmI5YjA3NDg5ZDMxM2I0MWE=')  # noqa
        self.kwargs = kwargs

    @property
    def identifier(self) -> str:
        return self.email or self.account_id or self.exchange_code

    def email_and_password_ready(self) -> bool:
        return self.email and self.password

    def exchange_code_ready(self) -> bool:
        return self.exchange_code is not None

    def device_auth_ready(self) -> bool:
        return self.device_id and self.account_id and self.secret

    async def run_email_and_password_authenticate(self) -> dict:
        auth = EmailAndPasswordAuth(
            email=self.email,
            password=self.password,
            two_factor_code=self.two_factor_code,
            launcher_token=self.ios_token,
            **self.kwargs
        )
        auth.initialize(self.client)

        return await auth.launcher_authenticate()

    async def run_exchange_code_authenticate(self) -> dict:
        auth = ExchangeCodeAuth(
            exchange_code=self.exchange_code,
            launcher_token=self.ios_token,
            **self.kwargs
        )
        auth.initialize(self.client)

        return await auth.launcher_authenticate()

    async def run_device_authenticate(self, device_id: Optional[str] = None,
                                      account_id: Optional[str] = None,
                                      secret: Optional[str] = None
                                      ) -> dict:
        auth = DeviceAuth(
            device_id=device_id or self.device_id,
            account_id=account_id or self.account_id,
            secret=secret or self.secret,
            **self.kwargs
        )
        auth.initialize(self.client)

        data = await auth.device_auth_authenticate()
        self._update_launcher_data(data)

        data = await auth.launcher_authenticate()
        self._update_launcher_data(data)

        return await auth.exchange_fortnite_code()

    async def generate_device_auth(self, client_id: str) -> dict:
        data = await self.client.http.account_generate_device_auth(
            client_id
        )
        return {
            'device_id': data['deviceId'],
            'account_id': data['accountId'],
            'secret': data['secret'],
        }

    async def authenticate(self) -> dict:
        data = None
        if self.device_auth_ready():
            return await self.run_device_authenticate()

        elif self.email_and_password_ready():
            try:
                data = await self.run_email_and_password_authenticate()
            except HTTPException as e:
                m = ['errors.com.epicgames.accountportal.captcha_invalid']
                if (self.prompt_exchange_code
                        and self.prompt_exchange_code_if_throttled):
                    m.append('errors.com.epicgames.common.throttled')

                if e.message_code not in m:
                    raise

                if (e.message_code in m
                        and not self.exchange_code_ready()
                        and not self.prompt_exchange_code):
                    raise AuthException(
                        'This account requires exchange code.'
                    ) from e

        if data is None:
            if self.prompt_exchange_code:
                if self.email is not None:
                    text = 'Please enter the exchange code for {0}\n'.format(
                        self.email
                    )
                else:
                    text = 'Please enter an exchange code.\n'

                async with _prompt_lock:
                    self.exchange_code = await ainput(
                        text,
                        loop=self.client.loop
                    )

            data = await self.run_exchange_code_authenticate()

        client_id = data['account_id']
        self._update_launcher_data(data)

        if self.delete_existing_device_auths:
            tasks = []
            auths = await self.client.http.account_get_device_auths(client_id)
            for auth in auths:
                tasks.append(self.client.loop.create_task(
                    self.client.http.account_delete_device_auth(
                        client_id,
                        auth['deviceId']
                    )
                ))

            if tasks:
                await asyncio.gather(*tasks)

        details = await self.generate_device_auth(client_id)
        account_data = await self.client.http.account_get_by_user_id(
            client_id,
            auth='LAUNCHER_ACCESS_TOKEN'
        )

        self.client.dispatch_event('device_auth_generate',
                                   details,
                                   account_data['email'])

        code = await self.get_exchange_code()
        data = await self.exchange_launcher_code(code)

        await self.kill_token(self.launcher_access_token)
        self._update_launcher_data(data)
        return await self.exchange_fortnite_code()
