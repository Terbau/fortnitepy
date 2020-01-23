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
import asyncio
import logging
import uuid

from aioconsole import ainput
from typing import TYPE_CHECKING

from .errors import AuthException, HTTPException

if TYPE_CHECKING:
    from .client import Client

log = logging.getLogger(__name__)


class Auth:
    def __init__(self, client: Client):
        self.client = client
        self.device_id = self.client.device_id or uuid.uuid4().hex
        self._refresh_event = asyncio.Event(loop=self.client.loop)
        self._refreshing = False
        self.refresh_i = 0

    @property
    def launcher_authorization(self) -> str:
        return 'bearer {0}'.format(self.launcher_access_token)

    @property
    def authorization(self) -> str:
        return 'bearer {0}'.format(self.access_token)

    async def authenticate(self) -> None:
        try:
            log.info('Fetching valid xsrf token.')
            token = await self.fetch_xsrf_token()

            await self.client.http.epicgames_reputation(token)

            try:
                log.info('Logging in.')
                await self.client.http.epicgames_login(
                    self.client.email,
                    self.client.password,
                    token
                )
            except HTTPException as e:
                if e.message_code != ('errors.com.epicgames.common.'
                                      'two_factor_authentication.required'):
                    e.reraise()

                log.info('Logging in interrupted. 2fa required.')
                log.info('Fetching new valid xsrf token.')
                token = await self.fetch_xsrf_token()

                code = (self.client.two_factor_code
                        or await ainput(
                            'Please enter the 2fa code:\n',
                            loop=self.client.loop
                        ))
                await self.client.http.epicgames_mfa_login(
                    e.raw['metadata']['twoFactorMethod'],
                    code,
                    token
                )

            await self.client.http.epicgames_redirect(token)

            log.info('Fetching exchange code.')
            data = await self.client.http.epicgames_get_exchange_data(token)

            log.info('Exchanging code.')
            data = await self.exchange_epicgames_code(data['code'])
            self.launcher_access_token = data['access_token']

            log.info('Running fortnite authentication.')
            await self.exchange_code()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            raise AuthException('Could not authenticate. '
                                'Error: {}'.format(e)) from None

    async def fetch_xsrf_token(self) -> str:
        response = await self.client.http.epicgames_get_csrf()
        return response.cookies['XSRF-TOKEN'].value

    async def exchange_epicgames_code(self, code: str) -> dict:
        payload = {
            'grant_type': 'exchange_code',
            'exchange_code': code,
            'token_type': 'eg1',
        }

        return await self.client.http.account_oauth_grant(
            auth='LAUNCHER_BASIC_TOKEN',
            device_id=True,
            data=payload
        )

    async def grant_refresh_token(self, refresh_token: str) -> dict:
        payload = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }

        return await self.client.http.account_oauth_grant(
            auth='FORTNITE_BASIC_TOKEN',
            device_id=True,
            data=payload
        )

    async def get_exchange_code(self) -> str:
        data = await self.client.http.account_get_exchange_data(
            auth='LAUNCHER_ACCESS_TOKEN'
        )
        return data.get('code')

    async def exchange_code(self) -> None:
        code = await self.get_exchange_code()
        if code is None:
            raise AuthException('Could not get exchange code')

        payload = {
            'grant_type': 'exchange_code',
            'token_type': 'eg1',
            'exchange_code': code
        }

        data = await self.client.http.account_oauth_grant(
            auth='FORTNITE_BASIC_TOKEN',
            device_id=True,
            data=payload
        )
        self._update(data)

    async def get_eula_version(self) -> int:
        data = await self.client.http.eulatracking_get_data()
        return data['version'] if isinstance(data, dict) else 0

    async def accept_eula(self) -> None:
        version = await self.get_eula_version()
        if version != 0:
            await self.client.http.eulatracking_accept(version)
            await self.client.http.fortnite_grant_access()

    def _update(self, data: dict) -> None:
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

    async def schedule_token_refresh(self) -> None:
        subtracted = self.expires_at - datetime.datetime.utcnow()
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
        log.debug('Refreshing session')
        self._refreshing = True
        if self.client.user.party is not None:
            await self.client.user.party._leave()

        data = await self.grant_refresh_token(self.refresh_token)
        self.launcher_access_token = data['access_token']
        await self.exchange_code()

        log.debug('Refreshing xmpp session')
        await self.client.xmpp.close()
        await self.client.xmpp.run()

        await self.client._create_party()

        self.refresh_i += 1
        self.client.dispatch_event('auth_refresh')
        self._refreshing = False

    async def run_refresh(self) -> None:
        self._refresh_event.set()
        await self.client.wait_for('auth_refresh')

    def refreshing(self) -> bool:
        return self._refreshing
