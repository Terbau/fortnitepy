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

import aioxmpp
import asyncio
import json
import logging
import datetime
import uuid
import itertools

from collections import defaultdict
from typing import TYPE_CHECKING, Optional, Union, Awaitable, Any

from .errors import XMPPError, PartyError
from .message import FriendMessage, PartyMessage
from .party import Party, PartyInvitation, PartyJoinConfirmation
from .presence import Presence

if TYPE_CHECKING:
    from .client import Client

log = logging.getLogger(__name__)


class EventContext:

    __slots__ = ('client', 'body', 'party', 'created_at')

    def __init__(self, client: 'Client', body: dict) -> None:
        self.client = client
        self.body = body

        self.party = self.client.user.party
        self.created_at = datetime.datetime.utcnow()


class EventDispatcher:
    def __init__(self) -> None:
        self._listeners = defaultdict(list)
        self.interactions_enabled = False

    def process_event(self, client: 'Client', body: dict) -> None:
        type_ = body.get('type')
        if type_ is None:
            if self.interactions_enabled:
                for interaction in body['interactions']:
                    self.process_event(client, interaction)
            return

        log.debug('Received event `{}` with body `{}`'.format(type_, body))

        coros = self._listeners.get(type_, [])
        for coro in coros:
            ctx = EventContext(client, body)

            if __name__ == coro.__module__:
                asyncio.ensure_future(coro(client.xmpp, ctx))
            else:
                asyncio.ensure_future(coro(ctx))

    def event(self, event: str) -> Awaitable:
        def decorator(coro: Awaitable) -> Awaitable:
            self.add_event_handler(event, coro)
            return coro
        return decorator

    def add_event_handler(self, event: str, coro: Awaitable) -> None:
        self._listeners[event].append(coro)
        log.debug('Added handler for {0} to {1}'.format(event, coro))

    def remove_event_handler(self, event: str, coro: Awaitable) -> None:
        handlers = [c for c in self._listeners[event] if c is not coro]
        log.debug('Removed {0} handler(s) for {1}'.format(
            len(self._listeners[event]) - len(handlers),
            event
        ))
        self._listeners[event] = handlers


dispatcher = EventDispatcher()


class XMPPClient:
    def __init__(self, client: 'Client') -> None:
        self.client = client

        self.xmpp_client = None
        self.stream = None
        self._ping_task = None
        self._task = None
        self.muc_room = None

    def jid(self, id: str) -> aioxmpp.JID:
        return aioxmpp.JID.fromstr('{}@{}'.format(id,
                                                  self.client.service_host))

    def _create_invite(self, from_id: str, data: dict) -> dict:
        now = datetime.datetime.utcnow()
        expires_at = now + datetime.timedelta(hours=4)

        for m in data['members']:
            if m['account_id'] == from_id:
                member = m
                break

        build_id = data['meta']['urn:epic:cfg:build-id_s']
        inv = {
            'party_id': data['id'],
            'sent_by': from_id,
            'sent_to': self.client.user.id,
            'sent_at': self.client.to_iso(now),
            'updated_at': self.client.to_iso(now),
            'expires_at': self.client.to_iso(expires_at),
            'status': 'SENT',
            'meta': {
                'urn:epic:conn:type_s': 'game',
                'urn:epic:conn:platform_s': json.loads(
                    member['meta']['Platform_j']
                )['Platform']['platformStr'],
                'urn:epic:member:dn_s': member['meta']['urn:epic:member:dn_s'],
                'urn:epic:cfg:build-id_s': build_id,
                'urn:epic:invite:platformdata_s': '',
            }
        }
        return inv

    async def process_chat_message(self, message: aioxmpp.Message) -> None:
        author = self.client.get_friend(message.from_.localpart)

        try:
            m = FriendMessage(
                client=self.client,
                author=author,
                content=message.body.any()
            )
            self.client.dispatch_event('friend_message', m)
        except ValueError:
            pass

    @dispatcher.event('com.epicgames.friends.core.apiobjects.Friend')
    async def friend_event(self, ctx: EventContext) -> None:
        body = ctx.body

        await self.client.wait_until_ready()
        _payload = body['payload']
        _status = _payload['status']
        _id = _payload['accountId']

        if _status == 'ACCEPTED':

            data = self.client.get_user(_id)
            if data is None:
                data = await self.client.fetch_profile(_id, raw=True)
            else:
                data = data.get_raw()

            try:
                timestamp = body['timestamp']
            except (TypeError, KeyError):
                timestamp = datetime.datetime.utcnow()

            f = self.client.store_friend({
                **data,
                'favorite': _payload['favorite'],
                'direction': _payload['direction'],
                'status': _status,
                'created': timestamp,
            })

            presences = await self.client.http.presence_get_last_online()
            presence = presences.get(_id)
            if presence is not None:
                f._update_last_logout(
                    self.client.from_iso(presence[0]['last_online'])
                )

            try:
                self.client._pending_friends.remove(f.id)
            except KeyError:
                pass

            self.client.dispatch_event('friend_add', f)

        elif _status == 'PENDING':
            data = self.client.get_user(_id)
            if data is None:
                data = await self.client.fetch_profile(_id, raw=True)
            else:
                data = data.get_raw()

            pf = self.client.store_pending_friend({
                **data,
                'direction': _payload['direction'],
                'status': _status,
                'created': body['timestamp']
            })

            self.client.dispatch_event('friend_request', pf)

    @dispatcher.event('FRIENDSHIP_REMOVE')
    async def friend_remove_event(self, ctx: EventContext) -> None:
        body = ctx.body

        if body['from'] == self.client.user.id:
            _id = body['to']
        else:
            _id = body['from']

        if body['reason'] == 'ABORTED':
            pf = self.client.get_pending_friend(_id)
            self.client.store_user(pf.get_raw())
            self.client._pending_friends.remove(pf.id)
            self.client.dispatch_event('friend_request_abort', pf)
        elif body['reason'] == 'REJECTED':
            pf = self.client.get_pending_friend(_id)
            self.client.store_user(pf.get_raw())
            self.client._pending_friends.remove(pf.id)
            self.client.dispatch_event('friend_request_decline', pf)
        else:
            f = self.client.get_friend(_id)
            if f is not None:
                self.client.store_user(f.get_raw())
                self.client._friends.remove(f.id)
                self.client.dispatch_event('friend_remove', f)

    @dispatcher.event('com.epicgames.friends.core.apiobjects.BlockListEntryAdded')  # noqa
    async def event_blocklist_added(self, ctx: EventContext) -> None:
        body = ctx.body

        account_id = body['payload']['accountId']
        data = await self.client.fetch_profile(account_id, raw=True)
        blocked_user = self.client.store_blocked_user(data)
        self.client.dispatch_event('user_block', blocked_user)

    @dispatcher.event('com.epicgames.friends.core.apiobjects.BlockListEntryRemoved')  # noqa
    async def event_blocklist_remove(self, ctx: EventContext) -> None:
        body = ctx.body

        account_id = body['payload']['accountId']
        profile = await self.client.fetch_profile(account_id)
        self.client._blocked_users.remove(profile.id)
        self.client.dispatch_event('user_unblock', profile)

    @dispatcher.event('com.epicgames.social.party.notification.v0.PING')
    async def event_ping_received(self, ctx: EventContext) -> None:
        body = ctx.body

        pinger = body['pinger_id']
        data = (await self.client.http.party_lookup_ping(pinger))[0]

        invite = None
        for inv in data['invites']:
            if inv['sent_by'] == pinger and inv['status'] == 'SENT':
                invite = inv

        if invite is None:
            invite = self._create_invite(pinger, data)

        if 'urn:epic:cfg:build-id_s' not in invite['meta']:
            pres = self.client.get_presence(pinger)
            if (pres is not None and pres.party is not None
                    and not pres.party.private):
                net_cl = pres.party.net_cl
            else:
                net_cl = self.client.net_cl
        else:
            s = invite['meta']['urn:epic:cfg:build-id_s']
            net_cl = s[4:] if s.startswith('1:1:') else s

        if net_cl != self.client.net_cl and self.client.net_cl != '':
            log.debug(
                'Could not match the currently set net_cl ({0!r}) to the '
                'received value ({1!r})'.format(self.client.net_cl, net_cl)
            )

        new_party = Party(self.client, data)
        await new_party._update_members(members=data['members'])

        invitation = PartyInvitation(self.client, new_party, net_cl, invite)
        self.client.dispatch_event('party_invite', invitation)

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_JOINED')  # noqa
    async def event_party_member_joined(self,
                                        ctx: EventContext) -> None:
        body = ctx.body
        party = ctx.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.members.get(body.get('account_id'))
        if member is None:
            member = party._create_member(body)

            if member.id == self.client.user.id:
                party._create_clientmember(body)

        if party.me is not None:
            asyncio.ensure_future(party.me.patch(), loop=self.client.loop)

        if party.me and party.me.leader:
            part = party.meta.refresh_squad_assignments()
            fut = asyncio.ensure_future(party.patch(updated={
                'RawSquadAssignments_j': part
            }), loop=self.client.loop)

        try:
            if member.id == self.client.user.id:
                await self.client.wait_for('muc_enter', timeout=2)
            else:
                def check(m):
                    return m.direct_jid.localpart == member.id

                await self.client.wait_for('muc_member_join',
                                           check=check,
                                           timeout=2)
        except asyncio.TimeoutError:
            pass

        try:
            await fut
        except UnboundLocalError:
            pass

        self.client.dispatch_event('party_member_join', member)

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_LEFT')
    async def event_party_member_left(self, ctx: EventContext) -> None:
        body = ctx.body
        party = ctx.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.members.get(body.get('account_id'))
        if member is None:
            return

        party._remove_member(member.id)
        self.client.dispatch_event('party_member_leave', member)

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_EXPIRED')  # noqa
    async def event_party_member_expired(self, ctx: EventContext) -> None:
        body = ctx.body
        party = ctx.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.members.get(body.get('account_id'))
        if member is None:
            return

        if member.id == self.client.user.id:
            p = await self.client._create_party()

            self.client.user.set_party(p)

        party._remove_member(member.id)
        self.client.dispatch_event('party_member_expire', member)

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_KICKED')  # noqa
    async def event_party_member_kicked(self, ctx: EventContext) -> None:
        body = ctx.body
        party = ctx.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.members.get(body.get('account_id'))
        if member is None:
            return
        party._remove_member(member.id)

        if member.id == self.client.user.id:
            await self.leave_muc()
            p = await self.client._create_party()

            self.client.user.set_party(p)

        self.client.dispatch_event('party_member_kick', member)

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_DISCONNECTED')  # noqa
    async def event_party_member_disconnected(self, ctx: EventContext) -> None:
        body = ctx.body
        party = ctx.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.members.get(body.get('account_id'))
        if member is None:
            return

        party._remove_member(member.id)
        self.client.dispatch_event('party_member_disconnect', member)

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_NEW_CAPTAIN')  # noqa
    async def event_party_new_captain(self, ctx: EventContext) -> None:
        body = ctx.body
        party = ctx.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.members.get(body.get('account_id'))
        if member is None:
            return

        old_leader = party.leader
        for m in party.members.values():
            m.update_role(None)

        member.update_role('CAPTAIN')
        if member.id == self.client.user.id:
            self.client.user.party.me.update_role('CAPTAIN')

        party.update_presence()
        self.client.dispatch_event('party_member_promote', old_leader, member)

    @dispatcher.event('com.epicgames.social.party.notification.v0.PARTY_UPDATED')  # noqa
    async def event_party_updated(self, ctx: EventContext) -> None:
        body = ctx.body
        party = ctx.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        check = {'playlist_info': 'playlist', 'squad_fill': None,
                 'privacy': None}
        pre_values = {k: getattr(party, k) for k in check.keys()}

        party._update(body)
        self.client.dispatch_event('party_update', party)

        for key, pre_value in pre_values.items():
            value = getattr(party, key)
            if pre_value != value:
                self.client.dispatch_event(
                    'party_{0}_change'.format(check[key] or key),
                    party,
                    pre_value,
                    value
                )

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_STATE_UPDATED')  # noqa
    async def event_party_member_state_updated(self,
                                               ctx: EventContext) -> None:
        body = ctx.body
        party = ctx.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.members.get(body.get('account_id'))
        if member is None:
            if body.get('account_id') == self.client.user.id:
                await party._leave()
                p = await self.client._create_party()
                self.client.user.set_party(p)
            return

        check = ('ready', 'input', 'assisted_challenge', 'outfit', 'backpack',
                 'pet', 'pickaxe', 'contrail', 'emote', 'emoji', 'banner',
                 'battlepass_info')
        pre_values = {k: getattr(member, k) for k in check}

        check_variants = ('outfit_variants', 'backpack_variants',
                          'pickaxe_variants', 'contrail_variants')
        pre_variants_values = {k: getattr(member, k) for k in check_variants}

        member.update(body)
        self.client.dispatch_event('party_member_update', member)

        for key, pre_value in pre_values.items():
            value = getattr(member, key)
            if pre_value != value:
                self.client.dispatch_event(
                    'party_member_{0}_change'.format(key),
                    member,
                    pre_value,
                    value
                )

        def compare_variants(a, b):
            def construct_set(v):
                return set(itertools.chain(*[list(x.values()) for x in v]))
            return construct_set(a) == construct_set(b)

        for key, pre_value in pre_variants_values.items():
            value = getattr(member, key)
            if not compare_variants(pre_value, value):
                self.client.dispatch_event(
                    'party_member_{0}_change'.format(key),
                    member,
                    pre_value,
                    value
                )

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_REQUIRE_CONFIRMATION')  # noqa
    async def event_party_member_require_confirmation(self,
                                                      ctx: EventContext
                                                      ) -> None:
        body = ctx.body
        party = ctx.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        user_id = body['account_id']
        user = self.client.get_user(user_id)
        if user is None:
            user = await self.client.fetch_profile(user_id)

        confirmation = PartyJoinConfirmation(self.client, party, user, body)
        self.client.dispatch_event('party_member_confirm', confirmation)

    @dispatcher.event('com.epicgames.social.party.notification.v0.INVITE_DECLINED')  # noqa
    async def event_party_invite_declined(self, ctx: EventContext) -> None:
        body = ctx.body

        friend = self.client.get_friend(body['invitee_id'])
        if friend is not None:
            self.client.dispatch_event('party_invite_decline', friend)

    async def process_presence(self, presence: aioxmpp.Presence) -> None:
        user_id = presence.from_.localpart
        if user_id == self.client.user.id or not presence.status:
            return

        if '-' in user_id:
            return

        if presence.type_ not in (aioxmpp.PresenceType.AVAILABLE,
                                  aioxmpp.PresenceType.UNAVAILABLE):
            return

        try:
            data = json.loads(presence.status.any())
            if (data.get('Status', '') == ''
                    or 'bIsPlaying' not in data
                    or not isinstance(data.get('Properties', {}), dict)):
                return
        except ValueError:
            return

        friend = self.client.get_friend(user_id)
        if friend is None:
            try:
                friend = await self.client.wait_for(
                    'friend_add',
                    check=lambda f: f.id == user_id,
                    timeout=1
                )
            except asyncio.TimeoutError:
                return

        platform = None
        if not presence.from_.is_bare:
            platform = presence.from_.resource.split(':')[2]

        _pres = Presence(
            self.client,
            user_id,
            platform,
            presence.type_ is aioxmpp.PresenceType.AVAILABLE,
            data
        )

        if _pres.party is not None:
            try:
                display_name = _pres.party.raw['sourceDisplayName']
                if display_name != _pres.friend.display_name:
                    _pres.friend._update_display_name(display_name)
            except (KeyError, AttributeError):
                pass

        if presence.type_ == (aioxmpp.PresenceType.UNAVAILABLE
                              and friend.is_online()):
            friend._update_last_logout(datetime.datetime.utcnow())

        self.client._presences.set(user_id, _pres)
        self.client.dispatch_event('friend_presence', _pres)

    def setup_callbacks(self,
                        messages: bool = True,
                        process_messages: bool = True,
                        presences: bool = True) -> None:
        message_dispatcher = self.xmpp_client.summon(
            aioxmpp.dispatcher.SimpleMessageDispatcher
        )

        if messages:
            message_dispatcher.register_callback(
                aioxmpp.MessageType.CHAT,
                None,
                lambda m: asyncio.ensure_future(
                    self.process_chat_message(m),
                    loop=self.client.loop
                ),
            )

        if process_messages:
            message_dispatcher.register_callback(
                aioxmpp.MessageType.NORMAL,
                None,
                lambda m: dispatcher.process_event(
                    self.client,
                    json.loads(m.body.any())
                )
            )

        if presences:
            presence_dispatcher = self.xmpp_client.summon(
                aioxmpp.dispatcher.SimplePresenceDispatcher,
            )

            presence_dispatcher.register_callback(
                None,
                None,
                lambda m: asyncio.ensure_future(
                    self.process_presence(m),
                    loop=self.client.loop
                ),
            )

    async def loop_ping(self) -> None:
        while True:
            await asyncio.sleep(60)
            iq = aioxmpp.IQ(
                type_=aioxmpp.IQType.GET,
                payload=aioxmpp.ping.Ping(),
                to=None,
            )
            await self.stream.send(iq)

    async def _run(self, future: asyncio.Future) -> None:
        async with self.xmpp_client.connected() as stream:
            self.stream = stream
            future.set_result(None)
            while True:
                await asyncio.sleep(1)

    async def run(self) -> None:
        resource_id = (uuid.uuid4().hex).upper()
        resource = 'V2:Fortnite:{0.client.platform.value}::{1}'.format(
            self,
            resource_id
        )

        self.xmpp_client = aioxmpp.PresenceManagedClient(
            aioxmpp.JID(
                self.client.user.id,
                self.client.service_host,
                resource
            ),
            aioxmpp.make_security_layer(
                self.client.auth.access_token,
                no_verify=True
            ),
            override_peer=[(
                self.client.service_domain,
                self.client.service_port,
                aioxmpp.connector.STARTTLSConnector()
            )],
            loop=self.client.loop
        )
        self.muc_service = self.xmpp_client.summon(aioxmpp.MUCClient)
        self.setup_callbacks()

        future = self.client.loop.create_future()
        self._task = asyncio.ensure_future(self._run(future),
                                           loop=self.client.loop)
        await future
        self._ping_task = asyncio.ensure_future(self.loop_ping(),
                                                loop=self.client.loop)

        asyncio.ensure_future(self.send_presence_on_start(),
                              loop=self.client.loop)
        self.client.dispatch_event('xmpp_session_establish')

    async def send_presence_on_start(self) -> None:
        await self.client.wait_until_ready()
        await self.send_presence(status=self.client.user.party.last_raw_status)

    async def close(self) -> None:
        log.debug('Attempting to close xmpp client')
        if self.xmpp_client.running:
            self.xmpp_client.stop()

            # let the loop run one more time so the xmpp client can stop
            while self.xmpp_client.running:
                await asyncio.sleep(0)

        if self._task:
            self._task.cancel()
        if self._ping_task:
            self._ping_task.cancel()

        self._ping_task = None
        self.xmpp_client = None
        self.stream = None
        self.muc_service = None
        log.debug('Successfully closed xmpp client')
        self.client.dispatch_event('xmpp_session_close')

        # let loop run one iteration for events to be dispatched
        await asyncio.sleep(0)

    def muc_on_message(self, message: aioxmpp.Message,
                       member: aioxmpp.muc.Occupant,
                       source: aioxmpp.im.dispatcher.MessageSource,
                       **kwargs: Any) -> None:
        if member.direct_jid is None:
            return

        user_id = member.direct_jid.localpart
        party = self.client.user.party

        if (user_id == self.client.user.id or member.nick is None
                or user_id not in party.members):
            return

        self.client.dispatch_event('party_message', PartyMessage(
            client=self.client,
            party=party,
            author=party.members[member.direct_jid.localpart],
            content=message.body.any()
        ))

    def muc_on_member_join(self, member: aioxmpp.muc.Occupant) -> None:
        self.client.dispatch_event('muc_member_join', member)

    def muc_on_enter(self, *args: list, **kwargs: Any) -> None:
        self.client.dispatch_event('muc_enter')

    def muc_on_leave(self, member: aioxmpp.muc.Occupant,
                     muc_leave_mode: aioxmpp.muc.LeaveMode,
                     muc_actor: aioxmpp.muc.xso.UserActor,
                     muc_reason: str,
                     **kwargs: Any) -> None:
        if muc_leave_mode is aioxmpp.muc.LeaveMode.BANNED:
            mem = self.client.user.party.members[member.direct_jid.localpart]
            self.client.dispatch_event('party_member_chatban',
                                       mem,
                                       muc_reason)

    async def join_muc(self, party_id: str) -> None:
        muc_jid = aioxmpp.JID.fromstr(
            'Party-{}@muc.prod.ol.epicgames.com'.format(party_id)
        )
        nick = '{0.display_name}:{0.id}:{1}'.format(
            self.client.user,
            self.xmpp_client.local_jid.resource
        )

        room, fut = self.muc_service.join(muc_jid, nick)

        room.on_message.connect(self.muc_on_message)
        room.on_join.connect(self.muc_on_member_join)
        room.on_enter.connect(self.muc_on_enter)
        room.on_leave.connect(self.muc_on_leave)
        self.muc_room = room

        asyncio.ensure_future(fut, loop=self.client.loop)
        await self.client.wait_for('muc_enter')

    async def leave_muc(self) -> None:

        # come back to this. works sometimes? wait for 2 seconds and timeout
        # to manually leave + check if muc messages is sent from correct
        # room (party-id)

        if self.muc_room is not None:
            presence = aioxmpp.stanza.Presence(
                type_=aioxmpp.structs.PresenceType.UNAVAILABLE,
                to=self.muc_room._mucjid
            )
            await self.xmpp_client.send(presence)
            try:
                self.muc_service._muc_exited(self.muc_room)
            except KeyError:
                pass

    async def send_party_message(self, content: str) -> None:
        if self.muc_room is None:
            raise PartyError('Can\'t send message. Reason: No party found')

        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT
        )
        msg.body[None] = content
        self.muc_room.send_message(msg)

    async def send_friend_message(self, jid: aioxmpp.JID,
                                  content: str) -> None:
        if self.stream is None:
            raise XMPPError('xmpp is not connected')

        msg = aioxmpp.Message(
            to=jid,
            type_=aioxmpp.MessageType.CHAT,
        )
        msg.body[None] = content
        await self.stream.send(msg)

    def set_presence(self, status: Optional[Union[str, dict]] = None) -> None:
        if status is None:
            self.xmpp_client.presence = aioxmpp.PresenceState(available=True)

        elif isinstance(status, dict):
            self.xmpp_client.set_presence(
                aioxmpp.PresenceState(available=True),
                json.dumps(status),
            )

        else:
            self.xmpp_client.set_presence(
                aioxmpp.PresenceState(available=True),
                json.dumps({'Status': status}),
            )

    async def send_presence(self, to: Optional[aioxmpp.JID] = None,
                            status: Optional[Union[str, dict]] = None) -> None:
        _status = {}
        if status is None:
            _status = None
        elif isinstance(status, str):
            _status['Status'] = status
        elif isinstance(status, dict):
            _status = status
        else:
            raise TypeError('status must be None, str or dict')

        pres = aioxmpp.Presence(type_=aioxmpp.PresenceType.AVAILABLE, to=to)

        if _status is not None:
            pres.status[None] = json.dumps(_status)
        await self.stream.send(pres)

    async def get_presence(self, jid: aioxmpp.JID) -> Presence:
        self.client.loop.create_task(self.send_presence_probe(jid))
        return await self.client.wait_for(
            'friend_presence',
            check=lambda p: p.friend.id == jid.localpart
        )

    async def send_presence_probe(self, to: aioxmpp.JID) -> None:
        presence = aioxmpp.Presence(
            type_=aioxmpp.PresenceType.PROBE,
            to=to
        )
        await self.stream.send(presence)
