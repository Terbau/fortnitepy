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

import aioxmpp
import asyncio
import json
import random
import logging
import datetime

from .errors import XMPPError, PartyError
from .message import FriendMessage, PartyMessage
from .friend import Friend, PendingFriend
from .party import Party, PartyMember, PartyInvitation, PartyJoinConfirmation
from .presence import Presence

log = logging.getLogger(__name__)


class XMPPClient:
    def __init__(self, client):
        self.client = client

        self.xmpp_client = None
        self.stream = None
        self._ping_task = None
        self._task = None
        self.muc_room = None

    def jid(self, id):
        return aioxmpp.JID.fromstr('{}@{}'.format(id, self.client.service_host))

    def _create_invite_from_presence(self, from_id, presence):
        now = datetime.datetime.utcnow()
        expires_at = now + datetime.timedelta(hours=4)

        inv = {
            'party_id': presence.party.id,
            'sent_by': from_id,
            'sent_to': self.client.user.id,
            'sent_at': self.client.to_iso(now),
            'updated_at': self.client.to_iso(now),
            'expires_at': self.client.to_iso(expires_at),
            'status': 'SENT',
            'meta': {
                'urn:epic:conn:type_s': 'game',
                'urn:epic:conn:platform_s': presence.party.platform,
                'urn:epic:member:dn_s': presence.friend.display_name,
                'urn:epic:cfg:build-id_s': presence.party.build_id,
                'urn:epic:invite:platformdata_s': '',
            },
        }
        return inv

    async def process_message(self, message):
        author = self.client.get_friend(message.from_.localpart)

        m = FriendMessage(
            client=self.client,
            author=author,
            content=message.body.any()
        )
        self.client.dispatch_event('friend_message', m)

    async def process_event_message(self, stanza):
        body = json.loads(stanza.body.any())
        _type = body['type']
        log.debug('XMPP: Received event `{}` with body `{}`'.format(_type, body))
        
        # [TODO]
        # Use the other received object (com.epicgames.friends.core.apiobjects.Friend) to process friend action events
        #
        # {'payload': {'accountId': 'b7af4984a77c468b83d8b16d675d76bc', 'status': 'PENDING', 'direction': 'INBOUND', 'created': '2019-06-30T22:28:18.383Z', 'favorite': False}, 'type': 'com.epicgames.friends.core.apiobjects.Friend', 'timestamp': '2019-06-30T22:28:18.393Z'}
        # {'type': 'FRIENDSHIP_REQUEST', 'timestamp': '2019-06-30T22:28:18.393Z', 'from': 'b7af4984a77c468b83d8b16d675d76bc', 'to': '26715168c5944e68b9d2c1e1d134b74e', 'status': 'PENDING'}
        # 
        # {'type': 'FRIENDSHIP_REQUEST', 'timestamp': '2019-06-30T22:28:19.248Z', 'from': 'b7af4984a77c468b83d8b16d675d76bc', 'to': '26715168c5944e68b9d2c1e1d134b74e', 'status': 'ACCEPTED'}
        # {'payload': {'accountId': 'b7af4984a77c468b83d8b16d675d76bc', 'status': 'ACCEPTED', 'direction': 'INBOUND', 'created': '2019-06-30T22:28:18.383Z', 'favorite': False}, 'type': 'com.epicgames.friends.core.apiobjects.Friend', 'timestamp': '2019-06-30T22:28:19.248Z'}
        if _type == 'FRIENDSHIP_REQUEST':
            _from = body['from']
            _status = body['status']

            if _status == 'ACCEPTED':
                data = self.client.get_user(_from)
                if data is None:
                    data = await self.client.http.get_profile(_from)
                else:
                    data = data.get_raw()

                f = Friend(self.client, {
                        **data,
                        'direction': None,
                        'status': _status,
                        'favorite': False,
                        'created': body['timestamp']
                    }
                )

                self.client._pending_friends.remove(f.id)
                self.client._friends.set(f.id, f)
                self.client.dispatch_event('friend_add', f)

            elif _status == 'PENDING':
                data = self.client.get_user(_from)
                if data is None:
                    data = await self.client.http.get_profile(_from)
                else:
                    data = data.get_raw()

                f = PendingFriend(self.client, {
                        **data,
                        'direction': 'INBOUND',
                        'status': _status,
                        'favorite': False,
                        'created': body['timestamp']
                    }
                )

                self.client._pending_friends.set(f.id, f)
                self.client.dispatch_event('friend_request', f)
        
        elif _type == 'FRIENDSHIP_REMOVE':
            _from = body['from']
            if body['reason'] == 'ABORTED':
                pf = self.client.get_pending_friend(_from)
                self.client.store_user(pf.get_raw())
                self.client._pending_friends.remove(pf.id)
            else:
                f = self.client.get_friend(_from)
                self.client.store_user(f.get_raw())
                self.client._friends.remove(f.id)
                self.client.dispatch_event('friend_removed', f)
        
        ##############################
        # Party
        ##############################
        elif _type == 'com.epicgames.social.party.notification.v0.INITIAL_INVITE':
            if body['meta']['urn:epic:cfg:build-id_s'] != self.client.party_build_id:
                raise PartyError('Incompatible build id')
            
            _raw = await self.client.http.party_lookup(body['party_id'])
            new_party = Party(self.client, _raw)
            await new_party._update_members(_raw['members'])
            
            invitation = PartyInvitation(self.client, new_party, body)
            self.client.dispatch_event('party_invite', invitation)
        
        elif _type == 'com.epicgames.social.party.notification.v0.MEMBER_LEFT':
            party = self.client.user.party
            if party is None:
                return

            if party.id != body.get('party_id'):
                return
            
            member = party.members.get(body.get('account_id'))
            if member is None:
                return

            party._remove_member(member.id)
            self.client.dispatch_event('party_member_leave', member)

        elif _type == 'com.epicgames.social.party.notification.v0.MEMBER_EXPIRED':
            party = self.client.user.party
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
            
        elif _type == 'com.epicgames.social.party.notification.v0.MEMBER_NEW_CAPTAIN':
            party = self.client.user.party
            if party is None:
                return

            if party.id != body.get('party_id'):
                return
            
            member = party.members.get(body.get('account_id'))
            if member is None:
                return
            
            for m in party.members.values():
                m.update_role(None)
            
            member.update_role('CAPTAIN')
            asyncio.ensure_future(party.update_status(), loop=self.client.loop)
            self.client.dispatch_event('party_member_promote', member)

        elif _type == 'com.epicgames.social.party.notification.v0.MEMBER_KICKED':
            party = self.client.user.party
            if party is None:
                return

            if party.id != body.get('party_id'):
                return
            
            member = party.members.get(body.get('account_id'))
            if member is None:
                return
            party._remove_member(member.id)

            if member.id == self.client.user.id:
                p = await self.client._create_party()
                
                self.client.user.set_party(p)
            
            self.client.dispatch_event('party_member_kicked', member)

        elif _type == 'com.epicgames.social.party.notification.v0.MEMBER_DISCONNECTED':
            party = self.client.user.party
            if party is None:
                return

            if party.id != body.get('party_id'):
                return
            
            member = party.members.get(body.get('account_id'))
            if member is None:
                return

            party._remove_member(member.id)
            self.client.dispatch_event('party_member_disconnected', member)

        elif _type == 'com.epicgames.social.party.notification.v0.PARTY_UPDATED':
            party = self.client.user.party
            if party is None:
                return

            if party.id != body.get('party_id'):
                return
            
            party._update(body)
            self.client.dispatch_event('party_updated', party)

        elif _type == 'com.epicgames.social.party.notification.v0.MEMBER_STATE_UPDATED':
            party = self.client.user.party
            if party is None:
                return

            if party.id != body.get('party_id'):
                return
            
            member = party.members[body.get('account_id')]
            if member is None:
                return

            member.update(body)
            self.client.dispatch_event('party_member_state_updated', member)

        elif _type == 'com.epicgames.social.party.notification.v0.MEMBER_JOINED':
            party = self.client.user.party
            if party is None:
                return

            if party.id != body.get('party_id'):
                return
            
            member = party.members.get(body.get('account_id'))
            if member is None:
                member = PartyMember(self.client, party, body)
                party._add_member(member)

            asyncio.ensure_future(party.me.patch(), loop=self.client.loop)
            if party.me and party.leader and party.me.id == party.leader.id:
                await party.patch(updated={
                    'RawSquadAssignments_j': party.meta.refresh_squad_assignments()
                })

            self.client.dispatch_event('party_member_join', member)

        elif _type == 'com.epicgames.social.party.notification.v0.MEMBER_REQUIRE_CONFIRMATION':
            party = self.client.user.party
            if party is None:
                return

            if party.id != body.get('party_id'):
                return
            
            confirmation = PartyJoinConfirmation(self.client, party, {
                **body,
                'id': body['account_id'],
                'displayName': body['account_dn']
            })
            self.client.dispatch_event('party_member_confirmation', confirmation)
        
        elif _type == 'com.epicgames.social.party.notification.v0.INVITE_CANCELLED':
            self.client.dispatch_event('party_invite_cancelled')

        elif _type == 'com.epicgames.social.party.notification.v0.INVITE_DECLINED':
            self.client.dispatch_event('party_invite_declined')

    async def process_presence(self, presence):
        if presence.from_.localpart == self.client.user.id or not presence.status:
            return

        try:
            data = json.loads(presence.status.any())
            if data.get('Status', '') == '':
                return
        except ValueError:
            return

        _pres = Presence(
            self.client, 
            presence.from_.localpart, 
            data
        )

        self.client._presences.set(presence.from_.localpart, _pres)
        self.client.dispatch_event('friend_presence', _pres)

    def setup_callbacks(self, messages=True, process_messages=True, presences=True):
        message_dispatcher = self.xmpp_client.summon(
            aioxmpp.dispatcher.SimpleMessageDispatcher
        )

        if messages:
            message_dispatcher.register_callback(
                aioxmpp.MessageType.CHAT,
                None,
                lambda m: asyncio.ensure_future(
                    self.process_message(m), 
                    loop=self.client.loop
                ),
            )

        if process_messages:
            message_dispatcher.register_callback(
                aioxmpp.MessageType.NORMAL,
                None,
                lambda m: asyncio.ensure_future(
                    self.process_event_message(m), 
                    loop=self.client.loop
                ),   
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

    async def loop_ping(self):
        while True:
            await asyncio.sleep(60)
            iq = aioxmpp.IQ(
                type_=aioxmpp.IQType.GET,
                payload=aioxmpp.ping.Ping(),
                to=None,
            )
            await self.stream.send(iq)
    
    async def _run(self, future):
        async with self.xmpp_client.connected() as stream:
            self.stream = stream
            future.set_result(None)
            while True:
                await asyncio.sleep(1)

    async def run(self):
        self.xmpp_client = aioxmpp.PresenceManagedClient(
            aioxmpp.JID(self.client.user.id, self.client.service_host, 'V2:Fortnite:WIN::E10260E2901443F3ABF26FE50D3466D8'),
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
        self._task = asyncio.ensure_future(self._run(future), loop=self.client.loop)
        await future
        self._ping_task = asyncio.ensure_future(self.loop_ping(), loop=self.client.loop)

    async def close(self):
        log.debug('Attempting to close xmpp client')
        if self.xmpp_client.running:
            self.xmpp_client.stop()
            
            # wait for client to shut down
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
    
    def muc_on_message(self, message, member, source, **kwargs):
        if member.direct_jid.localpart == self.client.user.id or member.nick is None:
            return
        
        self.client.dispatch_event('party_message', PartyMessage(
            client=self.client,
            party=self.client.user.party, 
            author=self.client.user.party.members[member.direct_jid.localpart],
            content=message.body.any()
        ))

    async def join_muc(self, party_id):
        muc_jid = aioxmpp.JID.fromstr('Party-{}@muc.prod.ol.epicgames.com'.format(party_id))
        nick = '{0.display_name}:{0.id}:{1}'.format(self.client.user, self.xmpp_client.local_jid.resource)

        room, fut = self.muc_service.join(muc_jid, nick)

        room.on_message.connect(self.muc_on_message)
        await fut
        self.muc_room = room

    async def leave_muc(self):
        if self.muc_room is not None:
            await self.muc_room.leave()
        self.muc_room = None

    async def send_party_message(self, content):
        if self.muc_room is None:
            raise PartyError('Can\'t send message. Reason: No party found')

        msg = aioxmpp.Message(
            type_=aioxmpp.MessageType.GROUPCHAT
        )
        msg.body[None] = content
        await self.muc_room.send_message(msg)

    async def send_friend_message(self, jid, content):
        if self.stream is None:
            raise XMPPError('xmpp is not connected')

        msg = aioxmpp.Message(
            to=jid,
            type_=aioxmpp.MessageType.CHAT,
        )
        msg.body[None] = content
        await self.stream.send(msg)

    def set_presence(self, status=None):
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

    async def send_presence(self, to=None, status=None):
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

    async def send_presence_probe(self, to):
        presence = aioxmpp.Presence(
            type_=aioxmpp.PresenceType.PROBE,
            to=to
        )
        await self.stream.send(presence)
