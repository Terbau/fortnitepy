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
import traceback
import uuid
import re
import json

from bs4 import BeautifulSoup
from .errors import AuthException, HTTPException

log = logging.getLogger(__name__)


class Auth:
    def __init__(self, client):
        self.client = client
        self.device_id = self.client.device_id or uuid.uuid4().hex

    @property
    def launcher_authorization(self):
        return 'bearer {0}'.format(self.launcher_access_token)

    @property
    def authorization(self):
        return 'bearer {0}'.format(self.access_token)

    async def authenticate(self):
        try:
            data = {
                'grant_type': 'password',
                'username': self.client.email,
                'password': self.client.password
            }

            try:
                data = await self.grant_session('LAUNCHER', data=data)
            except HTTPException as exc:
                log.debug('Could not authenticate normally, checking why now.')

                if exc.message_code != 'errors.com.epicgames.common.two_factor_authentication.required':
                    raise HTTPException(exc.response, exc.raw)
                
                log.debug('2fa code required to continue login process. Asking for code now.')

                code = self.client.two_factor_code
                if code is None:
                    code = int(input('Please enter the 2fa code:\n'))

                data = {
                    'grant_type': 'otp',
                    'otp': str(code),
                    'challenge': exc.raw['challenge']
                }
                data = await self.grant_session('LAUNCHER', data=data)
                log.debug('Valid 2fa code entered')

            self.launcher_access_token = data['access_token']
            await self.exchange_code(self.launcher_authorization)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            raise AuthException('Could not authenticate. Error: {}'.format(e))

    async def alternative_authenticate(self):
        try:
            grant_data = await self.alternative_grant_session()
            self.client_id = grant_data['client_id']
            token = await self.alternative_get_xsrf_token('login')
            
            data = await self.client.http.post(
                'https://accounts.launcher-website-prod07.ol.epicgames.com/login/doLauncherLogin',
                'LAUNCHER',
                data={
                    'fromForm': 'yes',
                    'authType': None,
                    'linkExtAuth': None,
                    'client_id': self.client_id,
                    'redirectUrl': 'https://accounts.launcher-website-prod07.ol.epicgames.com' \
                                '/login/showPleaseWait?client_id={0.client_id}' \
                                '&rememberEmail=false'.format(self),
                    'epic_username': self.client.email,
                    'password': self.client.password,
                    'rememberMe': 'NO',
                },
                headers={
                    'X-XSRF-TOKEN': token
                }
            )

            try:
                data = json.loads(data)
            except json.decoder.JSONDecodeError:
                soup = BeautifulSoup(data, 'html.parser')
                error_code = soup.find(attrs={'class': 'errorCodes'})
                if error_code is not None:
                    raise AuthException('Login form error: {0}'.format((error_code.get_text()).strip()))

                log.debug('2fa code required to continue login process. Asking for code now.')

                two_factor_elem = soup.find(id='twoFactorForm')
                if two_factor_elem is None:
                    raise AuthException('Cannot get "please wait" redirection URL')

                data = await self.alternative_2fa_submit(soup)
                log.debug('Authenticated with correct two factor code.')

            code = await self.alternative_get_exchange_code(data['redirectURL'])
            res = await self.alternative_exchange_code(code)
            self.launcher_access_token = res['access_token']
            await self.exchange_code(self.launcher_authorization)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            raise AuthException('Could not authenticate. Error: {}'.format(e))

    async def alternative_2fa_submit(self, soup, two_factor_code=None):
        data = {
            'challenge': soup.find(attrs={'name': 'challenge'}).get('value'),
            'mfaMethod': soup.find(attrs={'name': 'mfaMethod'}).get('value'),
            'alternateMfaMethods': soup.find(attrs={'name': 'alternateMfaMethods'}).get('value'),
            'epic_username': soup.find(attrs={'name': 'epic_username'}).get('value'),
            'hideMessage': soup.find(attrs={'name': 'hideMessage'}).get('value'),
            'linkExtAuth': soup.find(attrs={'name': 'linkExtAuth'}).get('value'),
            'authType': soup.find(attrs={'name': 'authType'}).get('value'),
            'clientId': soup.find(attrs={'name': 'client_id'}).get('value'),
            'redirectUrl': soup.find(attrs={'name': 'redirectUrl'}).get('value'),
            'rememberMe': soup.find(attrs={'name': 'rememberMe'}).get('value'),
        }

        code = two_factor_code = self.client.two_factor_code
        if code is None:
            code = input('Please enter the 2fa code:\n')
        
        cookies = self.client.http._jar.filter_cookies(
            'https://accounts.launcher-website-prod07.ol.epicgames.com/login/doLauncherLogin')
        token = cookies['XSRF-TOKEN'].value

        data['twoFactorCode'] = code
        data = await self.client.http.post(
            'https://accounts.launcher-website-prod07.ol.epicgames.com/login/doTwoFactor',
            None,
            data=data,
            headers={
                'X-XSRF-TOKEN': token
            },
            params={
                'client_id': self.client_id
            }
        )

        _soup = BeautifulSoup(data, 'html.parser')
        error_code = _soup.find(attrs={'class': 'errorCodes'})
        incorrect_code = _soup.find(attrs={'for': 'twoFactorCode', 'class': 'fieldValidationError'})
        if error_code is not None:
            return await self.alternative_2fa_submit(soup, two_factor_code=code)

        if incorrect_code is not None:
            raise AuthException(incorrect_code.get_text().strip())
        
        return json.loads(data)

    
    async def alternative_get_exchange_code(self, url):
        data = await self.client.http.get(
            url,
            'LAUNCHER',
            data={}
        )

        matches = re.search(
            r'com\.epicgames\.account\.web\.widgets\.loginWithExchangeCode\(\'(.*)\'(.*?)\)',
            data
        )

        if matches is not None:
            return matches.groups()[0]
        #error here

    async def alternative_exchange_code(self, code):
        data = {
            'grant_type': 'exchange_code',
            'exchange_code': code,
            'token_type': 'eg1'
        }

        return await self.grant_session(
            'LAUNCHER',
            data=data
        )

    async def alternative_grant_session(self):
        return await self.client.http.post(
            'https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/token',
            'LAUNCHER',
            data={
                'grant_type': 'client_credentials',
                'token_type': 'eg1'
            }
        )

    async def alternative_get_xsrf_token(self, location, **kwargs):
        path = 'login/doLauncherLogin' if location == 'login' else 'register/doLauncherRegister'
        data = await self.client.http.get(
            'https://accounts.launcher-website-prod07.ol.epicgames.com/{0}'.format(path),
            'LAUNCHER',
            params={
                'client_id': self.client_id,
                'redirectUrl': 'https%3A%2F%2Faccounts.launcher-website-prod07.ol.epicgames.com%2Flogin'
                               '%2FshowPleaseWait%3Fclient_id%3D${0.client_id}%26rememberEmail%3Dfalse'.format(
                                   self
                               )
            },
            raw=True
        )
        return data.cookies['XSRF-TOKEN'].value

    async def stable_authenticate(self):
        try:
            log.info('Fetching valid xsrf token.')
            token = await self.stable_get_xsrf_token()

            try:
                log.info('Logging in.')
                await self.stable_login(token)
            except HTTPException as e:
                if e.message_code != 'errors.com.epicgames.common.two_factor_authentication.required':
                    raise HTTPException(e.response, e.raw)
                
                log.info('Logging in interrupted. 2fa required.')
                log.info('Fetching new valid xsrf token.')
                token = await self.stable_get_xsrf_token()

                code = self.client.two_factor_code or input('Please enter the 2fa code:\n')
                await self.stable_2fa_login(token, code)
 
            d = await self.client.http.get(
                'https://www.epicgames.com/id/api/redirect',
                None,
                headers={
                    'x-xsrf-token': token
                }
            )

            log.info('Fetching exchange code.')
            data = await self.client.http.get(
                'https://www.epicgames.com/id/api/exchange',
                None,
                headers={
                    'x-xsrf-token': token
                }
            )
            
            log.info('Exchanging code.')
            data = await self.stable_code_exchange((json.loads(data))['code'])
            self.launcher_access_token = data['access_token']

            log.info('Running fortnite authentication.')
            await self.exchange_code(self.launcher_authorization)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            raise AuthException('Could not authenticate. Error: {}'.format(e))

    async def stable_get_xsrf_token(self):
        data = await self.client.http.get(
            'https://www.epicgames.com/id/api/csrf',
            None,
            raw=True
        )
        return data.cookies['XSRF-TOKEN'].value

    async def stable_login(self, token):
        await self.client.http.post(
            'https://www.epicgames.com/id/api/login',
            None,
            headers={
                'x-xsrf-token': token
            },
            data={
                'email': self.client.email,
                'password': self.client.password,
                'rememberMe': False
            }
        )

    async def stable_2fa_login(self, token, code):
        await self.client.http.post(
            'https://www.epicgames.com/id/api/login/mfa',
            None,
            headers={
                'x-xsrf-token': token
            },
            data={
                'code': code,
                'method': 'authenticator',
                'rememberDevice': False
            }
        )

    async def stable_code_exchange(self, code):
        data = {
            'grant_type': 'exchange_code',
            'exchange_code': code,
            'token_type': 'eg1',
        }

        return await self.client.http.post(
            'https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/token',
            'LAUNCHER',
            data=data
        )

    async def grant_refresh_token(self, refresh_token):
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        return await self.grant_session('FORTNITE', data=data)

    async def get_exchange_code(self, auth):
        res = await self.client.http.get(
            'https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/exchange',
            auth
        )
        return res.get('code')

    async def exchange_code(self, auth):
        code = await self.get_exchange_code(auth)
        if code is None:
            raise AuthException('Could not get exchange code')

        data = {
            'grant_type': 'exchange_code',
            'token_type': 'eg1',
            'exchange_code': code
        }
        
        data = await self.grant_session('FORTNITE', data=data)
        self._update(data)

    async def grant_session(self, auth, **kwargs):
        headers = {
            'X-Epic-Device-ID': self.device_id
        }
        data = await self.client.http.post(
            'https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/token',
            auth,
            **{**kwargs, 'headers': headers}
        )
        return data

    async def kill_token(self, token):
        await self.client.http.delete(
            'https://account-public-service-prod03.ol.epicgames.com/account/api/' \
            'oauth/sessions/kill/{0}'.format(token),
            self.authorization
        )

    async def kill_other_sessions(self):
        await self.client.http.delete(
            'https://account-public-service-prod03.ol.epicgames.com/account/api/' \
            'oauth/sessions/kill?killType=OTHERS_ACCOUNT_CLIENT_SERVICE',
            self.authorization
        )

    async def get_eula_version(self, account_id):
        res = await self.client.http.get(
            'https://eulatracking-public-service-prod-m.ol.epicgames.com/eulatracking/' \
            'api/public/agreements/fn/account/{0}'.format(account_id),
            self.authorization
        )
        return res['version'] if isinstance(res, dict) else 0

    async def _accept_eula(self, version, account_id):
        await self.client.http.post(
            'https://eulatracking-public-service-prod-m.ol.epicgames.com/eulatracking/' \
            'api/public/agreements/fn/version/{0}/account/{1}/accept?locale=en'.format(
                version, 
                account_id
            ),
            self.authorization
        )

    async def _grant_access(self, account_id):
        await self.client.http.post(
            'https://fortnite-public-service-prod11.ol.epicgames.com/fortnite/api/' \
            'game/v2/grant_access/{0}'.format(account_id),
            self.authorization,
            json={}
        )

    async def accept_eula(self, account_id):
        version = await self.get_eula_version(account_id)
        if version != 0:
            await self._accept_eula(version, account_id)
            await self._grant_access(account_id)

    def _update(self, data):
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
    
    async def schedule_token_refresh(self):
        self.token_timeout = (self.expires_at - datetime.datetime.utcnow()).total_seconds() - 300
        await asyncio.sleep(self.token_timeout)
        await self.do_refresh()

    async def do_refresh(self):
        log.debug('Refreshing session')

        if self.client.user.party is not None:
            await self.client.user.party._leave()

        data = await self.grant_refresh_token(self.refresh_token)
        self.launcher_access_token = data['access_token']
        await self.exchange_code('bearer {}'.format(self.launcher_access_token))

        log.debug('Refreshing xmpp session')
        await self.client.xmpp.close()
        await self.client.xmpp.run()

        await self.client._create_party()
        await self.schedule_token_refresh()
