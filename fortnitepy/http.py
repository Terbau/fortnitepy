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

import aiohttp
import asyncio
import logging
import json
import re
import uuid

from typing import List, Mapping
from urllib.parse import quote
from functools import wraps
from .errors import HTTPException

log = logging.getLogger(__name__)


class Route:
    BASE = ''
    AUTH = None

    def __init__(self, path, auth=None, **params):
        self.path = path
        self.params = {k: (quote(v) if isinstance(v, str) else v)
                       for k, v in params.items()}

        if self.BASE == '':
            raise ValueError('Route must have a base')

        url = self.BASE + self.path
        self.url = url.format(**self.params) if self.params else url

        if auth:
            self.AUTH = auth


class EpicGames(Route):
    BASE = 'https://www.epicgames.com'
    AUTH = None

class LauncherWebsite(Route):
    BASE = 'https://launcher-website-prod07.ol.epicgames.com'
    AUTH = None

class EntitlementPublicService(Route):
    BASE = 'https://entitlement-public-service-prod08.ol.epicgames.com'
    AUTH = 'LAUNCHER_ACCESS_TOKEN'

class OrderprocessorPublicService(Route):
    BASE = 'https://orderprocessor-public-service-ecomprod01.ol.epicgames.com'
    AUTH = 'LAUNCHER_ACCESS_TOKEN'

class PaymentWebsite(Route):
    BASE = 'https://payment-website-pci.ol.epicgames.com'
    AUTH = 'LAUNCHER_ACCESS_TOKEN'

class LightswitchPublicService(Route):
    BASE = 'https://lightswitch-public-service-prod06.ol.epicgames.com'
    AUTH = 'LAUNCHER_ACCESS_TOKEN'

class PersonaPublicService(Route):
    BASE = 'https://persona-public-service-prod06.ol.epicgames.com'
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

class PersonaPublicService(Route):
    BASE = 'https://persona-public-service-prod06.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'

class PresencePublicService(Route):
    BASE = 'https://presence-public-service-prod.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'

class StatsproxyPublicService(Route):
    BASE = 'https://statsproxy-public-service-live.ol.epicgames.com'
    AUTH = 'FORTNITE_ACCESS_TOKEN'


class HTTPClient:
    def __init__(self, client, connector=None):
        self.client = client
        self.connector = connector
        self._jar = aiohttp.CookieJar()
        self.headers = {}
        self.device_id = self.client.device_id or uuid.uuid4().hex

        self.create_connection()

    @staticmethod
    async def json_or_text(response):
        text = await response.text(encoding='utf-8')
        if response.headers.get('content-type') == 'application/json':
            return json.loads(text)
        return text

    @property
    def user_agent(self):
        return 'EpicGamesLauncher/{0.client.build} {0.client.os}'.format(self)

    @property
    def session(self):
        return self.__session

    def get_auth(self, auth):
        if not auth.lower().startswith('bearer'):
            auth = auth.upper()

        if auth == 'LAUNCHER_BASIC_TOKEN':
            return 'basic {0}'.format(self.client.launcher_token)
        elif auth == 'FORTNITE_BASIC_TOKEN':
            return 'basic {0}'.format(self.client.fortnite_token)
        elif auth == 'LAUNCHER_ACCESS_TOKEN':
            return self.client.auth.launcher_authorization
        elif auth == 'FORTNITE_ACCESS_TOKEN':
            return self.client.auth.authorization
        return auth

    def add_header(self, key, val):
        self.headers[key] = val

    def remove_header(self, key):
        return self.headers.pop(key)

    async def close(self):
        self._jar.clear()
        if self.__session and not self.__session.closed:
            await self.__session.close()

    def create_connection(self):
        self.__session = aiohttp.ClientSession(
            connector=self.connector,
            loop=self.client.loop,
            cookie_jar=self._jar
        )

    async def request(self, method, url, **kwargs):
        try:
            params = kwargs['params']
            if isinstance(params, dict):
                kwargs['params'] = {k: (str(v).lower() if isinstance(v, bool) else v) for k, v in params.items()}
            else:
                kwargs['params'] = [(k, (str(v).lower() if isinstance(v, bool) else v)) for k, v in params]
        except KeyError:
            pass

        async with self.__session.request(method, url, **kwargs) as r:
            log.debug('{0} {1} has returned {2.status}'.format(method, url, r))

            data = await self.json_or_text(r)
            return r, data

    async def _fn_request(self, method, route, auth, **kwargs):
        url = route.url if not isinstance(route, str) else route

        headers = {**kwargs.get('headers', {}), **self.headers}
        headers['User-Agent'] = self.user_agent

        auth = auth or route.AUTH
        if auth is not None:
            headers['Authorization'] = self.get_auth(auth)
        
        device_id = kwargs.pop('device_id', None)
        if device_id is not None:
            headers['X-Epic-Device-ID'] = self.device_id if device_id is True else device_id

        kwargs['headers'] = headers

        raw = kwargs.pop('raw', False)
        r, data = await self.request(method, url, **kwargs)

        if raw:
            return r

        try:
            _data = json.loads(data)
            if 'errorCode' in _data.keys():
                raise HTTPException(r, _data)
        except (KeyError, TypeError, json.decoder.JSONDecodeError):
            pass

        return data

    async def fn_request(self, method, route, auth, **kwargs):
        try:
            return await self._fn_request(method, route, auth, **kwargs)
        except HTTPException as exc:
            if exc.message_code in ('errors.com.epicgames.common.oauth.invalid_token',
                                    'errors.com.epicgames.common.authentication.token_verification_failed'):
                await self.client.restart()
                return await self.fn_request(method, route, auth, **kwargs)

            elif exc.message_code in ('errors.com.epicgames.common.server_error',):
                await asyncio.sleep(0.5)
                return await self._fn_request(method, route, auth, **kwargs)

            elif exc.message_code in ('errors.com.epicgames.common.concurrent_modification_error',):
                return await self.fn_request(method, route, auth, **kwargs)

            exc.reraise()
            
    async def get(self, url, auth=None, **kwargs):
        return await self.fn_request('GET', url, auth, **kwargs)

    async def post(self, url, auth=None, **kwargs):
        return await self.fn_request('POST', url, auth, **kwargs)

    async def delete(self, url, auth=None, **kwargs):
        return await self.fn_request('DELETE', url, auth, **kwargs)

    async def patch(self, url, auth=None, **kwargs):
        return await self.fn_request('PATCH', url, auth, **kwargs)

    async def put(self, url, auth=None, **kwargs):
        return await self.fn_request('PUT', url, auth, **kwargs)

    ###################################
    #            Epicgames            #
    ###################################

    async def epicgames_get_csrf(self):
        return await self.get(EpicGames('/id/api/csrf'), raw=True)

    async def epicgames_login(self, email, password, xsrf_token):
        headers = {
            'x-xsrf-token': xsrf_token
        }

        payload = {
            'email': email,
            'password': password,
            'rememberMe': False
        }

        return await self.post(EpicGames('/id/api/login'), headers=headers, data=payload)

    async def epicgames_mfa_login(self, method, code, xsrf_token):
        headers = {
            'x-xsrf-token': xsrf_token
        }

        payload = {
            'code': code,
            'method': method,
            'rememberDevice': False
        }

        return await self.post(EpicGames('/id/api/login/mfa'), headers=headers, data=payload)

    async def epicgames_redirect(self, xsrf_token):
        headers = {
            'x-xsrf-token': xsrf_token
        }

        return await self.get(EpicGames('/id/api/redirect'), headers=headers)

    async def epicgames_get_exchange_data(self, xsrf_token):
        headers = {
            'x-xsrf-token': xsrf_token
        }

        data = await self.get(EpicGames('/id/api/exchange'), headers=headers)
        return json.loads(data)

    ###################################
    #          Entitlement            #
    ###################################

    async def entitlement_get_all(self):
        params = {
            'start': 0,
            'count': 5000
        }

        r = EntitlementPublicService('/entitlement/api/account/{client_id}/entitlements', client_id=self.client.user.id)
        return await self.get(r, params=params)

    ###################################
    #         Orderprocessor          #
    ###################################

    async def orderprocessor_quickpurchase(self):
        payload = {
            'salesChannel': 'Launcher-purchase-client',
            'entitlementSource': 'Launcher-purchase-client',
            'returnSplitPaymentItems': False,
            'lineOffers': [
                {
                    'offerId': '09176f4ff7564bbbb499bbe20bd6348f',
                    'quantity': 1,
                    'namespace': 'fn'
                }
            ]
        }

        r = OrderprocessorPublicService('/orderprocessor/api/shared/accounts/{client_id}/orders/quickPurchase', client_id=self.client.user.id)
        return await self.post(r, json=payload)

    ###################################
    #        Launcher Website         #
    ###################################

    async def launcher_website_purchase(self, namespace, offers):
        params = {
            'showNavigation': True,
            'namespace': namespace,
            'offers': offers
        }

        return await self.get(LauncherWebsite('/purchase'), params=params)

    ###################################
    #        Payment Website          #
    ###################################

    async def payment_website_order_preview(self, token, namespace, offers):
        headers = {
            'x-requested-with': token
        }

        payload = {
            'useDefault': True,
            'setDefault': False,
            'namespace': namespace,
            'country': None,
            'countryName': None,
            'orderComplete': None,
            'orderId': None,
            'orderError': None,
            'orderPending': None,
            'offers': [
                offers
            ],
            'offerPrice': ''
        }

        return await self.post(PaymentWebsite('/purchase/order-preview'), headers=headers, data=payload)

    async def payment_website_confirm_order(self, token, order):
        headers = {
            'x-requested-with': token
        }

        payload = {
            'useDefault': True,
            'setDefault': False,
            'namespace': order['namespace'],
            'country': order['country'],
            'countryName': order['countryName'],
            'orderId': None,
            'orderComplete': None,
            'orderError': None,
            'orderPending': None,
            'offers': order['offers'],
            'includeAccountBalance': False,
            'totalAmount': order['orderResponse']['totalPrice'],
            'affiliateId': '',
            'creatorSource': '',
            'syncToken': order['syncToken']
        }

        return self.post(PaymentWebsite('/purchase/confirm-order'), headers=headers, data=payload)

    ###################################
    #           Lightswitch           #
    ###################################

    async def lightswitch_get_status(self, *, service_id=None):
        params = {'serviceId': service_id} if service_id else None

        r = LightswitchPublicService('/lightswitch/api/service/bulk/status')
        return await self.get(r, params=params)

    async def get_by_display_name(self, display_name):
        params = {
            'q': display_name
        }

        return await self.get(PersonaPublicService('/persona/api/public/account/lookup'), params=params)

    ###################################
    #            Account              #
    ###################################

    async def account_get_exchange_data(self, auth):
        return await self.get(AccountPublicService('/account/api/oauth/exchange'), auth=auth)

    async def account_oauth_grant(self, **kwargs):
        return await self.post(AccountPublicService('/account/api/oauth/token'), **kwargs)

    async def account_sessions_kill_token(self, token):
        return await self.delete(AccountPublicService('/account/api/oauth/sessions/kill/{token}', token=token))

    async def account_sessions_kill(self, kill_type):
        params = {
            'killType': kill_type
        }

        return await self.delete(AccountPublicService('/account/api/oauth/sessions/kill'), params=params)

    async def account_get_by_display_name(self, display_name):
        r = AccountPublicService('/account/api/public/account/displayName/{display_name}', display_name=display_name)
        return await self.get(r)

    async def account_get_by_user_id(self, user_id):
        r = AccountPublicService('/account/api/public/account/{user_id}', user_id=user_id)
        return await self.get(r)

    async def account_get_multiple_by_user_id(self, user_ids):
        params = [('accountId', user_id) for user_id in user_ids]
        return await self.get(AccountPublicService('/account/api/public/account'), params=params)

    ###################################
    #          Eula Tracking          #
    ###################################

    async def eulatracking_get_data(self):
        r = EulatrackingPublicService('/eulatracking/api/public/agreements/fn/account/{client_id}', client_id=self.client.user.id)
        return await self.get(r)

    async def eulatracking_accept(self, version, *, locale='en'):
        params = {
            'locale': locale
        }

        r = EulatrackingPublicService('/eulatracking/api/public/agreements/fn/version/{version}/account/{client_id}/accept', version=version, client_id=self.client.user.id)
        return await self.post(r, params=params)

    ###################################
    #         Fortnite Public         #
    ###################################

    async def fortnite_grant_access(self):
        r = FortnitePublicService('/fortnite/api/game/v2/grant_access/{client_id}', client_id=self.client.user.id)
        return await self.post(r, json={})

    async def fortnite_get_store_catalog(self):
        return await self.get(FortnitePublicService('/fortnite/api/storefront/v2/catalog'))

    async def fortnite_get_timeline(self):
        return await self.get(FortnitePublicService('/fortnite/api/calendar/v1/timeline'))

    ###################################
    #        Fortnite Content         #
    ###################################

    async def fortnitecontent_get(self):
        data = await self.get(FortniteContentWebsite('/content/api/pages/fortnite-game'))
        return json.loads(data)

    ###################################
    #            Friends              #
    ###################################

    async def friends_get_all(self, *, include_pending=False):
        params = {
            'includePending': include_pending
        }

        r = FriendsPublicService('/friends/api/public/friends/{client_id}', client_id=self.client.user.id)
        return await self.get(r, params=params)

    async def friends_add_or_accept(self, user_id):
        r = FriendsPublicService('/friends/api/v1/{client_id}/friends/{user_id}', client_id=self.client.user.id, user_id=user_id)
        return await self.post(r)

    async def friends_remove_or_decline(self, user_id):
        r = FriendsPublicService('/friends/api/v1/{client_id}/friends/{user_id}', client_id=self.client.user.id, user_id=user_id)
        return await self.delete(r)

    async def friends_get_blocklist(self):
        r = FriendsPublicService('/friends/api/v1/{client_id}/blocklist', client_id=self.client.user.id)
        return await self.get(r)

    async def friends_set_nickname(self, user_id, nickname):
        r = FriendsPublicService('/friends/api/v1/{client_id}/friends/{user_id}/alias', client_id=self.client.user.id, user_id=user_id)
        return await self.put(r, data=nickname)

    async def friends_remove_nickname(self, user_id):
        r = FriendsPublicService('/friends/api/v1/{client_id}/friends/{user_id}/alias', client_id=self.client.user.id, user_id=user_id)
        return await self.delete(r)

    async def friends_set_note(self, user_id, note):
        r = FriendsPublicService('/friends/api/v1/{client_id}/friends/{user_id}/note', client_id=self.client.user.id, user_id=user_id)
        return await self.put(r, data=note)

    async def friends_remove_note(self, user_id):
        r = FriendsPublicService('/friends/api/v1/{client_id}/friends/{user_id}/note', client_id=self.client.user.id, user_id=user_id)
        return await self.delete(r)

    async def friends_get_summary(self):
        r = FriendsPublicService('/friends/api/v1/{client_id}/summary', client_id=self.client.user.id)
        return await self.get(r)

    async def friends_block(self, user_id):
        r = FriendsPublicService('/friends/api/v1/{client_id}/blocklist/{user_id}', client_id=self.client.user.id, user_id=user_id)
        return await self.post(r)

    async def friends_unblock(self, user_id):
        r = FriendsPublicService('/friends/api/v1/{client_id}/blocklist/{user_id}', client_id=self.client.user.id, user_id=user_id)
        return await self.delete(r)

    ###################################
    #            Presence             #
    ###################################

    async def presence_get_last_online(self):
        r = PresencePublicService('/presence/api/v1/_/{client_id}/last-online', client_id=self.client.user.id)
        return json.loads(await self.get(r))

    ###################################
    #              Stats              #
    ###################################

    async def stats_get_v2(self, user_id, *, start_time=None, end_time=None):
        params = {}
        if start_time:
            params['start_time'] = start_time
        if end_time:
            params['end_time'] = end_time

        r = StatsproxyPublicService('/statsproxy/api/statsv2/account/{user_id}', user_id=user_id)
        return await self.get(r, params=params)

    async def stats_get_mutliple_v2(self, ids, stats, *, start_time=None, end_time=None):
        payload = {
            'appId': 'fortnite',
            'owners': ids,
            'stats': stats
        }
        if start_time:
            payload['startDate'] = start_time
        if end_time:
            payload['endDate'] = end_time

        return await self.post(StatsproxyPublicService('/statsproxy/api/statsv2/query'), json=payload)

    async def stats_get_leaderboard_v2(self, stat):
        r = StatsproxyPublicService('/statsproxy/api/statsv2/leaderboards/{stat}', stat=stat)
        return await self.get(r)

    ###################################
    #             Party               #
    ###################################

    async def party_send_invite(self, party_id, user_id, send_ping=True):
        payload = {
            'urn:epic:cfg:build-id_s': self.client.party_build_id,
            'urn:epic:conn:platform_s': self.client.platform.value,
            'urn:epic:conn:type_s': 'game',
            'urn:epic:invite:platformdata_s': '',
            'urn:epic:member:dn_s': self.client.user.display_name,
        }

        params = {
            'sendPing': send_ping
        }

        r = PartyService('/party/api/v1/Fortnite/parties/{party_id}/invites/{user_id}', party_id=party_id, user_id=user_id)
        return await self.post(r, json=payload, params=params)

    # NOTE: Depracated since fortnite v11.30
    #       Use param sendPing=True with send_invite
    # async def party_send_ping(self, user_id):
    #     r = PartyService(
    #         '/party/api/v1/Fortnite/user/{user_id}/pings/{client_id}', user_id=user_id, client_id=self.client.user.id)
    #     return await self.post(r, json={})

    async def party_delete_ping(self, user_id):
        r = PartyService('/party/api/v1/Fortnite/user/{client_id}/pings/{user_id}', client_id=self.client.user.id, user_id=user_id)
        return await self.delete(r)

    async def party_decline_invite(self, party_id):
        r = PartyService('/party/api/v1/Fortnite/parties/{party_id}/invites/{client_id}/decline', party_id=party_id, client_id=self.client.user.id)
        return await self.post(r, json={})

    async def party_member_confirm(self, party_id, user_id):
        r = PartyService('/party/api/v1/Fortnite/parties/{party_id}/members/{user_id}/confirm', party_id=party_id, user_id=user_id)
        return await self.post(r, json={})

    async def party_member_reject(self, party_id, user_id):
        r = PartyService('/party/api/v1/Fortnite/parties/{party_id}/members/{user_id}/reject', party_id=party_id, user_id=user_id)
        return await self.post(r, json={})

    async def party_promote_member(self, party_id, user_id):
        r = PartyService('/party/api/v1/Fortnite/parties/{party_id}/members/{user_id}/promote', party_id=party_id, user_id=user_id)
        return await self.post(r, json={})

    async def party_kick_member(self, party_id, user_id):
        r = PartyService('/party/api/v1/Fortnite/parties/{party_id}/members/{user_id}', party_id=party_id, user_id=user_id)
        return await self.delete(r)

    async def party_leave(self, party_id):
        payload = {
            'connection': {
                'id': self.client.user.jid,
                'meta': {
                    'urn:epic:conn:platform_s': self.client.platform.value,
                    'urn:epic:conn:type_s': 'game'
                }
            },
            'meta': {
                'urn:epic:member:dn_s': self.client.user.display_name,
                'urn:epic:member:type_s': 'game',
                'urn:epic:member:platform_s': self.client.platform.value,
                'urn:epic:member:joinrequest_j': '{"CrossplayPreference_i":"1"}',
            }
        }

        r = PartyService('/party/api/v1/Fortnite/parties/{party_id}/members/{client_id}', party_id=party_id, client_id=self.client.user.id)
        return await self.delete(r, json=payload)

    async def party_join_request(self, party_id):
        payload = {
            'connection': {
                'id': str(self.client.xmpp.xmpp_client.local_jid),
                'meta': {
                    'urn:epic:conn:platform_s': self.client.platform.value,
                    'urn:epic:conn:type_s': 'game',
                },
                'yield_leadership': False,
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

        r = PartyService('/party/api/v1/Fortnite/parties/{party_id}/members/{client_id}/join', party_id=party_id, client_id=self.client.user.id)
        return await self.post(r, json=payload)

    async def party_lookup(self, party_id):
        return await self.get(PartyService('/party/api/v1/Fortnite/parties/{party_id}', party_id=party_id))

    async def party_lookup_user(self, user_id):
        return await self.get(PartyService('/party/api/v1/Fortnite/user/{user_id}', user_id=user_id))

    async def party_lookup_ping(self, user_id):
        r = PartyService('/party/api/v1/Fortnite/user/{client_id}/pings/{user_id}/parties', client_id=self.client.user.id, user_id=user_id)
        return await self.get(r)

    async def party_create(self, config):
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
                        'urn:epic:conn:type_s': 'game'
                    }
                }
            },
            'meta': {
                'urn:epic:cfg:party-type-id_s': 'default',
                'urn:epic:cfg:build-id_s': str(self.client.party_build_id),
                'urn:epic:cfg:join-request-action_s': 'Manual',
                'urn:epic:cfg:chat-enabled_b': str(config['chat_enabled']).lower()
            }
        }

        return await self.post(PartyService('/party/api/v1/Fortnite/parties'), json=payload)

    async def party_update_member_meta(self, party_id, user_id, meta, revision):
        payload = {
            'delete': [],
            'revision': revision,
            'update': meta
        }

        r = PartyService('/party/api/v1/Fortnite/parties/{party_id}/members/{user_id}/meta', party_id=party_id, user_id=user_id)
        return await self.patch(r, json=payload)

    async def party_update_meta(self, party_id, updated_meta, deleted_meta, config, revision):
        payload = {
            'config': {
                'join_confirmation': config['join_confirmation'],
                'joinability': config['joinability'],
                'max_size': config['max_size']
            },
            'meta': {
                'delete': deleted_meta,
                'update': updated_meta
            },
            'party_state_overridden': {},
            'party_privacy_type': config['joinability'],
            'party_type': config['type'],
            'party_sub_type': config['sub_type'],
            'max_number_of_members': config['max_size'],
            'invite_ttl_seconds': config['invite_ttl_seconds'],
            'revision': revision
        }

        r = PartyService('/party/api/v1/Fortnite/parties/{party_id}', party_id=party_id)
        return await self.patch(r, json=payload)
