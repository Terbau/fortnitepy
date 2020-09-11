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
import unicodedata
import aiohttp

from xml.etree import ElementTree
from collections import defaultdict
from typing import TYPE_CHECKING, Optional, Union, Awaitable, Any, Tuple

from .errors import XMPPError, PartyError, HTTPException
from .message import FriendMessage, PartyMessage
from .party import Party, ReceivedPartyInvitation, PartyJoinConfirmation
from .presence import Presence
from .enums import AwayStatus

if TYPE_CHECKING:
    from .client import Client

log = logging.getLogger(__name__)


def is_RandALCat(c: str) -> bool:
    return unicodedata.bidirectional(c) in ('R', 'AL')


class EventContext:

    __slots__ = ('client', 'body', 'party', 'created_at')

    def __init__(self, client: 'Client', body: dict) -> None:
        self.client = client
        self.body = body

        self.party = self.client.party
        self.created_at = datetime.datetime.utcnow()


class EventDispatcher:
    def __init__(self) -> None:
        self._listeners = defaultdict(list)
        self._presence_listeners = []
        self.interactions_enabled = False

    def process_presence(self, client, *args) -> None:
        for coro in self._presence_listeners:
            if __name__ == coro.__module__:
                asyncio.ensure_future(coro(client.xmpp, *args))
            else:
                asyncio.ensure_future(coro(*args))

    def presence(self) -> Awaitable:
        def decorator(coro: Awaitable) -> Awaitable:
            self.add_presence_handler(coro)
            return coro
        return decorator

    def add_presence_handler(self, coro: Awaitable) -> None:
        if coro not in self._presence_listeners:
            self._presence_listeners.append(coro)

    def remove_presence_handler(self, coro: Awaitable) -> None:
        self._presence_listeners = [
            c for c in self._presence_listeners if c is not coro
        ]

    def process_event(self, client: 'Client', raw_body: dict) -> None:
        body = json.loads(raw_body)

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


class XMLProcessor:
    def _process_presence(self, raw: str) -> Optional[Union[tuple, bool]]:
        tree = ElementTree.fromstring(raw)

        type_ = tree.get('type')

        # Only intercept presences with either no type attribute
        # (which means available) or unavailable type.
        if type_ is not None and type_ not in ('available', 'unavailable'):
            return False

        from_ = tree.get('from')

        # If from is a party, let aioxmpp handle it.
        if from_ is not None and '-' in from_:
            return False

        status = None
        show = None
        for elem in tree:
            if 'status' in elem.tag:
                status = elem.text
            if 'show' in elem.tag:
                show = elem.text

        # We have no use for the presence if status is None and
        # therefore it's better to just let aioxmpp handle it.
        if status is None:
            return False

        split = from_.split('@')
        user_id = split[0]
        platform = split[1].split(':')[2]

        return 'presence', (user_id, platform, type_, status, show)

    def _process_message(self, raw: str) -> Optional[Union[tuple, bool]]:
        tree = ElementTree.fromstring(raw)

        type_ = tree.get('type')

        # Only intercept messages with either no type attribute
        # (which means normal) or  type.
        if type_ is not None and type_ != 'normal':
            return False

        # Let aioxmpp handle it if no body tag is found. Also, technically
        # a message can include multiple body tags for different languages
        # but afaik only one body tag is sent from epics servers.
        body = None
        for elem in tree:
            if 'body' in elem.tag:
                body = elem.text
                break
        else:
            return False

        return 'message', (body,)

    def process(self, raw: str) -> Optional[Union[tuple, bool]]:
        # Yes, this is a hacky solution but it's better than
        # using the quite unnecessary slow aioxmpp one.
        if '<presence' in raw:
            return self._process_presence(raw)
        elif '<message' in raw:
            return self._process_message(raw)

        return False


class WebsocketTransport:
    def __init__(self, loop: asyncio.AbstractEventLoop,
                 stream: 'WebsocketXMLStream',
                 client: 'Client',
                 logger: logging.Logger,
                 ws_connector: Optional[aiohttp.BaseConnector] = None) -> None:
        self.loop = loop
        self.stream = stream
        self.client = client
        self.logger = logger
        self.ws_connector = ws_connector

        self.xml_processor = XMLProcessor()

        self.connection = None
        self._buffer = b''
        self._reader_task = None
        self._close_event = asyncio.Event()
        self._called_lost = False
        self._attempt_reconnect = True

    async def create_connection(self, *args,
                                **kwargs) -> aiohttp.ClientWebSocketResponse:
        self.logger.debug('Setting up new websocket connection.')

        self.session = aiohttp.ClientSession(
            connector=self.ws_connector,
            connector_owner=self.ws_connector is None,
        )
        self.connection = con = await self.session.ws_connect(
            *args, **kwargs
        )

        self.loop.create_task(self.reader())
        self.stream.connection_made(self)
        self._called_lost = False
        self._attempt_reconnect = True

        self.logger.debug('Websocket connection established.')
        return con

    async def reader(self) -> None:
        self.logger.debug('Websocket reader is now running.')

        try:
            while True:
                msg = await self.connection.receive()

                self.logger.debug('RECV: {0}'.format(msg))
                if msg.type == aiohttp.WSMsgType.TEXT:
                    ret = self.xml_processor.process(msg.data)
                    if ret is None:
                        continue
                    elif ret is False:
                        self.stream.data_received(msg.data)
                    else:
                        type_ = ret[0]
                        if type_ == 'presence':
                            dispatcher.process_presence(
                                self.client,
                                *ret[1]
                            )
                        elif type_ == 'message':
                            dispatcher.process_event(
                                self.client,
                                *ret[1]
                            )

                if msg.type == aiohttp.WSMsgType.CLOSED:
                    if self._attempt_reconnect:
                        err = ConnectionError(
                            'websocket stream closed by peer'
                        )
                    else:
                        err = None

                    if not self._called_lost:
                        self._called_lost = True
                        self.stream.connection_lost(err)
                    break

                if msg.type == aiohttp.WSMsgType.ERROR:
                    if not self._called_lost:
                        self._called_lost = True
                        self.stream.connection_lost(
                            ConnectionError(
                                'websocket stream received an error: '
                                '{0}'.format(self.connection.exception()))
                        )
                    break
        finally:
            self.logger.debug('Websocket reader stopped.')

    async def send(self, data: bytes) -> None:
        self.logger.debug('SEND: {0}'.format(data))
        await self.connection.send_bytes(data)

    def write(self, data: bytes) -> None:
        self._buffer += data

    def flush(self) -> None:
        if self._buffer:
            asyncio.ensure_future(self.send(self._buffer))

        self._buffer = b''

    def can_write_eof(self) -> bool:
        return False

    def write_eof(self) -> None:
        raise NotImplementedError("Cannot write_eof() on ws transport.")

    def _stop_reader(self) -> None:
        if self._reader_task is not None and not self._reader_task.cancelled():
            self._reader_task.cancel()

    def close_callback(self, *args) -> None:
        self._close_event.set()

    def on_close(self, *args) -> None:
        try:
            task = self.loop.create_task(self.session.close())
        except AttributeError:
            pass
        else:
            task.add_done_callback(self.close_callback)

    def _close(self) -> None:
        if not self.connection:
            raise RuntimeError('Cannot close a non-existing connection.')

        self.logger.debug('Closing websocket connection.')

        task = self.loop.create_task(self.connection.close())
        task.add_done_callback(self.on_close)

        self._stop_reader()

    def close(self) -> None:
        self._attempt_reconnect = False
        self._close()

    def abort(self) -> None:
        self.logger.debug('Received abort signal.')
        self._close()

    async def wait_closed(self) -> None:
        await self._close_event

    def get_extra_info(self, *args, **kwargs) -> Any:
        return self.connection.get_extra_info(*args, **kwargs)


class WebsocketXMLStreamWriter(aioxmpp.xml.XMLStreamWriter):
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._writer.endElementNS(
            (aioxmpp.utils.namespaces.xmlstream, "stream"),
            None
        )
        for prefix in self._nsmap_to_use:
            self._writer.endPrefixMapping(prefix)
        self._writer.endDocument()
        self._writer.flush()
        del self._writer


class WebsocketXMLStream(aioxmpp.protocol.XMLStream):
    def _reset_state(self) -> None:
        self._kill_state()

        self._processor = aioxmpp.xml.XMPPXMLProcessor()
        self._processor.stanza_parser = self.stanza_parser
        self._processor.on_stream_header = self._rx_stream_header
        self._processor.on_stream_footer = self._rx_stream_footer
        self._processor.on_exception = self._rx_exception
        self._parser = aioxmpp.xml.make_parser()
        self._parser.setContentHandler(self._processor)
        self._debug_wrapper = None

        if self._logger.getEffectiveLevel() <= logging.DEBUG:
            dest = aioxmpp.protocol.DebugWrapper(self._transport, self._logger)
            self._debug_wrapper = dest
        else:
            dest = self._transport

        self._writer = WebsocketXMLStreamWriter(
            dest,
            self._to,
            nsmap={None: "jabber:client"},
            sorted_attributes=self._sorted_attributes)


class XMPPOverWebsocketConnector(aioxmpp.connector.BaseConnector):
    def __init__(self, client, ws_connector=None):
        self.client = client
        self.ws_connector = ws_connector

    @property
    def tls_supported(self) -> bool:
        return False

    @property
    def dane_supported(self) -> bool:
        return False

    async def connect(self, loop: asyncio.AbstractEventLoop,
                      metadata: aioxmpp.security_layer.SecurityLayer,
                      domain: str,
                      host: str,
                      port: int,
                      negotiation_timeout: Union[int, float],
                      base_logger: Optional[logging.Logger] = None
                      ) -> Tuple[WebsocketTransport,
                                 WebsocketXMLStream,
                                 aioxmpp.nonza.StreamFeatures]:
        features_future = asyncio.Future()

        stream = WebsocketXMLStream(
            to=domain,
            features_future=features_future,
            base_logger=base_logger,
        )

        if base_logger is not None:
            logger = base_logger.getChild(type(self).__name__)
        else:
            logger = logging.getLogger(".".join([
                __name__, type(self).__qualname__,
            ]))

        transport = WebsocketTransport(
            loop,
            stream,
            self.client,
            logger,
            ws_connector=self.ws_connector
        )
        await transport.create_connection(
            'wss://{host}'.format(host=host),
            protocols=('xmpp',),
            timeout=10,
        )

        return transport, stream, await features_future


# Were just patching this method to suppress an exception
# which is raised on stream error.
def _patched_done_handler(self, task):
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as err:
        try:
            if self._sm_enabled:
                self._xmlstream.abort()
            else:
                self._xmlstream.close()
        except Exception:
            pass
        self.on_failure(err)


aioxmpp.stream.StanzaStream._done_handler = _patched_done_handler


class XMPPClient:
    def __init__(self, client: 'Client', ws_connector=None) -> None:
        self.client = client
        self.ws_connector = ws_connector

        self.xmpp_client = None
        self.stream = None
        self.muc_room = None

        self._ping_task = None
        self._is_suspended = False
        self._reconnect_recover_task = None
        self._last_disconnected_at = None
        self._last_known_party_id = None
        self._task = None

    def jid(self, user_id: str) -> aioxmpp.JID:
        return aioxmpp.JID.fromstr('{}@{}'.format(
            user_id,
            self.client.service_host
        ))

    def _remove_illegal_characters(self, chars: str) -> str:
        fixed = []
        for c in chars:
            try:
                aioxmpp.stringprep.resourceprep(c)
            except ValueError:
                continue

            if is_RandALCat(c):
                continue

            fixed.append(c)
        return ''.join(fixed)

    def _create_invite(self, from_id: str, data: dict) -> dict:
        sent_at = self.client.from_iso(data['sent'])
        expires_at = sent_at + datetime.timedelta(hours=4)

        for m in data['members']:
            if m['account_id'] == from_id:
                member = m
                break

        party_m = data['meta']
        member_m = member['meta']

        meta = {
            'urn:epic:conn:type_s': 'game',
            'urn:epic:cfg:build-id_s': party_m['urn:epic:cfg:build-id_s'],
            'urn:epic:invite:platformdata_s': '',
        }

        if 'Platform_j' in member_m:
            meta['Platform_j'] = json.loads(
                member_m['Platform_j']
            )['Platform']['platformStr']

        if 'urn:epic:member:dn_s' in member['meta']:
            meta['urn:epic:member:dn_s'] = member_m['urn:epic:member:dn_s']

        inv = {
            'party_id': data['id'],
            'sent_by': from_id,
            'sent_to': self.client.user.id,
            'sent_at': self.client.to_iso(sent_at),
            'updated_at': self.client.to_iso(sent_at),
            'expires_at': self.client.to_iso(expires_at),
            'status': 'SENT',
            'meta': meta
        }
        return inv

    async def process_chat_message(self, message: aioxmpp.Message) -> None:
        user_id = message.from_.localpart
        author = self.client.get_friend(user_id)
        if author is None:
            try:
                author = await self.client.wait_for(
                    'friend_add',
                    check=lambda f: f.id == user_id,
                    timeout=2
                )
            except asyncio.TimeoutError:
                log.debug('Friend message discarded because friend not found.')
                return

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
                data = await self.client.fetch_user(_id, raw=True)
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

            try:
                del self.client._pending_friends[f.id]
            except KeyError:
                pass

            self.client.dispatch_event('friend_add', f)

        elif _status == 'PENDING':
            data = self.client.get_user(_id)
            if data is None:
                data = await self.client.fetch_user(_id, raw=True)
            else:
                data = data.get_raw()

            data = {
                **data,
                'direction': _payload['direction'],
                'status': _status,
                'created': body['timestamp']
            }
            if _payload['direction'] == 'INBOUND':
                pf = self.client.store_incoming_pending_friend(data)
            else:
                pf = self.client.store_outgoing_pending_friend(data)

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
            if pf is not None:
                self.client.store_user(pf.get_raw())

                try:
                    del self.client._pending_friends[pf.id]
                except KeyError:
                    pass

                self.client.dispatch_event('friend_request_abort', pf)
        elif body['reason'] == 'REJECTED':
            pf = self.client.get_pending_friend(_id)
            if pf is not None:
                self.client.store_user(pf.get_raw())

                try:
                    del self.client._pending_friends[pf.id]
                except KeyError:
                    pass

                self.client.dispatch_event('friend_request_decline', pf)
        else:
            f = self.client.get_friend(_id)
            if f is not None:
                self.client.store_user(f.get_raw())

                try:
                    del self.client._friends[f.id]
                except KeyError:
                    pass

                self.client.dispatch_event('friend_remove', f)

        try:
            del self.client._presences[_id]
        except KeyError:
            pass

    @dispatcher.event('com.epicgames.friends.core.apiobjects.BlockListEntryAdded')  # noqa
    async def event_blocklist_added(self, ctx: EventContext) -> None:
        body = ctx.body

        account_id = body['payload']['accountId']
        data = await self.client.fetch_user(account_id, raw=True)
        blocked_user = self.client.store_blocked_user(data)
        self.client.dispatch_event('user_block', blocked_user)

    @dispatcher.event('com.epicgames.friends.core.apiobjects.BlockListEntryRemoved')  # noqa
    async def event_blocklist_remove(self, ctx: EventContext) -> None:
        body = ctx.body

        account_id = body['payload']['accountId']
        user = await self.client.fetch_user(account_id)

        try:
            del self.client._blocked_users[user.id]
        except KeyError:
            pass

        self.client.dispatch_event('user_unblock', user)

    @dispatcher.event('com.epicgames.social.party.notification.v0.PING')
    async def event_ping_received(self, ctx: EventContext) -> None:
        body = ctx.body
        pinger = body['pinger_id']
        try:
            data = (await self.client.http.party_lookup_ping(pinger))[0]
        except (IndexError, HTTPException) as exc:
            if isinstance(exc, HTTPException):
                m = 'errors.com.epicgames.social.party.ping_not_found'
                if exc.message_code != m:
                    raise

            self.client.dispatch_event(
                'invalid_party_invite',
                self.client.get_friend(pinger)
            )
            return

        for inv in data['invites']:
            if inv['sent_by'] == pinger and inv['status'] == 'SENT':
                invite = inv
                break
        else:
            invite = self._create_invite(pinger, {**body, **data})

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

        invitation = ReceivedPartyInvitation(
            self.client,
            new_party,
            net_cl,
            invite
        )
        self.client.dispatch_event('party_invite', invitation)

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_JOINED')  # noqa
    async def event_party_member_joined(self,
                                        ctx: EventContext) -> None:
        body = ctx.body

        user_id = body.get('account_id')
        if user_id != self.client.user.id:
            await self.client.wait_until_party_ready()

        party = self.client.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        if user_id == self.client.user.id:
            await self.client._internal_join_party_lock.wait()

        member = party.get_member(user_id)
        if member is None:
            member = (await party._update_members(
                (body,),
                remove_missing=False
            ))[0]

        if party.me is not None:
            party.me.do_on_member_join_patch()

            yielding = party.me._default_config.yield_leadership
            if party.me.leader and not yielding:
                fut = asyncio.ensure_future(party.refresh_squad_assignments())

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

        user_id = body.get('account_id')
        if user_id != self.client.user.id:
            await self.client._join_party_lock.wait()

        party = self.client.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.get_member(user_id)
        if member is None:
            return

        party._remove_member(member.id)

        if party.me and party.me.leader and member.id != party.me.id:
            await party.refresh_squad_assignments()

        self.client.dispatch_event('party_member_leave', member)

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_KICKED')  # noqa
    async def event_party_member_kicked(self, ctx: EventContext) -> None:
        body = ctx.body

        user_id = body.get('account_id')
        if user_id != self.client.user.id:
            await self.client._join_party_lock.wait()

        party = self.client.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.get_member(user_id)
        if member is None:
            return

        party._remove_member(member.id)

        if party.me and party.me.leader and member.id != party.me.id:
            await party.refresh_squad_assignments()

        if member.id == self.client.user.id:
            await self.leave_muc()
            p = await self.client._create_party()

            self.client.party = p

        self.client.dispatch_event('party_member_kick', member)

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_DISCONNECTED')  # noqa
    async def event_party_member_disconnected(self, ctx: EventContext) -> None:
        body = ctx.body
        user_id = body.get('account_id')

        if user_id != self.client.user.id:
            await self.client._join_party_lock.wait()

        party = self.client.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.get_member(user_id)
        if member is None:
            return

        # Dont continue processing for old connections
        data = await self.client.http.party_lookup(party.id)
        for member_data in data['members']:
            if member_data['account_id'] == user_id:
                connections = member_data['connections']
                if len(connections) == 1:
                    break

                for connection in connections:
                    if 'disconnected_at' not in connection:
                        return

        member._update_connection(body.get('connection'))
        self.client.dispatch_event('party_member_zombie', member)

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_EXPIRED')  # noqa
    async def event_party_member_expired(self, ctx: EventContext) -> None:
        body = ctx.body

        user_id = body.get('account_id')
        if user_id != self.client.user.id:
            await self.client._join_party_lock.wait()

        party = self.client.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.get_member(user_id)
        if member is None:
            return

        party._remove_member(member.id)

        if party.me and party.me.leader and member.id != party.me.id:
            await party.refresh_squad_assignments()

        if member.id == self.client.user.id:
            p = await self.client._create_party()
            self.client.party = p

        self.client.dispatch_event('party_member_expire', member)

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_CONNECTED')  # noqa
    async def event_party_member_connected(self, ctx: EventContext) -> None:
        body = ctx.body

        user_id = body.get('account_id')
        if user_id != self.client.user.id:
            await self.client._join_party_lock.wait()

        party = self.client.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.get_member(user_id)
        if member is None:
            return

        member._update_connection(body.get('connection'))
        if member.id == self.client.user.id:
            party.update_presence()

        self.client.dispatch_event('party_member_reconnect', member)

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_NEW_CAPTAIN')  # noqa
    async def event_party_new_captain(self, ctx: EventContext) -> None:
        body = ctx.body
        party = ctx.party

        user_id = body.get('account_id')
        if user_id != self.client.user.id:
            await self.client._join_party_lock.wait()

        party = self.client.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.get_member(user_id)
        if member is None:
            return

        old_leader = party.leader
        party._update_roles(member)

        party.update_presence()
        self.client.dispatch_event('party_member_promote', old_leader, member)

    @dispatcher.event('com.epicgames.social.party.notification.v0.PARTY_UPDATED')  # noqa
    async def event_party_updated(self, ctx: EventContext) -> None:
        body = ctx.body

        user_id = body.get('account_id')
        if user_id != self.client.user.id:
            await self.client._join_party_lock.wait()

        party = self.client.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        def _getattr(member, key):
            value = getattr(member, key)
            if callable(value):
                value = value()
            return value

        check = {'playlist_info': 'playlist', 'squad_fill': None,
                 'privacy': None}
        pre_values = {k: _getattr(party, k) for k in check.keys()}

        party._update(body)
        self.client.dispatch_event('party_update', party)

        for key, pre_value in pre_values.items():
            value = _getattr(party, key)
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

        user_id = body.get('account_id')
        if user_id != self.client.user.id:
            await self.client._join_party_lock.wait()

        party = self.client.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        member = party.get_member(user_id)
        if member is None:
            def check(m):
                return m.id == user_id

            try:
                member = await self.client.wait_for(
                    'party_member_join',
                    check=check,
                    timeout=1
                )
            except asyncio.TimeoutError:
                party_data = await self.client.http.party_lookup(party.id)
                for m_data in party_data['members']:
                    if user_id == m_data['account_id']:
                        member = (await party._update_members(
                            (m_data,),
                            remove_missing=False
                        ))[0]
                        break
                else:
                    if user_id == self.client.user.id:
                        await party._leave()
                        p = await self.client._create_party()
                        self.client.party = p
                    return

                yielding = party.me._default_config.yield_leadership
                if party.me and party.me.leader and not yielding:
                    await party.refresh_squad_assignments()

        def _getattr(member, key):
            value = getattr(member, key)
            if callable(value):
                value = value()
            return value

        check = ('ready', 'input', 'assisted_challenge', 'outfit', 'backpack',
                 'pet', 'pickaxe', 'contrail', 'emote', 'emoji', 'banner',
                 'battlepass_info', 'in_match', 'match_players_left',
                 'enlightenments', 'corruption', 'outfit_variants',
                 'backpack_variants', 'pickaxe_variants', 'contrail_variants')
        pre_values = {k: _getattr(member, k) for k in check}

        member.update(body)

        if party._default_config.team_change_allowed or not party.me.leader:
            req_j = body['member_state_updated'].get(
                'Default:MemberSquadAssignmentRequest_j'
            )
            if req_j is not None:
                req = json.loads(req_j)['MemberSquadAssignmentRequest']
                version = req['version']
                if version != member._assignment_version:
                    member._assignment_version = version

                    swap_member_id = req['swapTargetMemberId']
                    if swap_member_id != 'INVALID':
                        new_positions = {
                            member.id: req['targetAbsoluteIdx'],
                            swap_member_id: req['startingAbsoluteIdx']
                        }
                        if party.me.leader:
                            await party.refresh_squad_assignments(
                                new_positions=new_positions
                            )

                        try:
                            self.client.dispatch_event(
                                'party_member_team_swap',
                                *[party._members[k] for k in new_positions]
                            )
                        except KeyError:
                            pass

        self.client.dispatch_event('party_member_update', member)

        def _dispatch(key, member, pre_value, value):
            self.client.dispatch_event(
                'party_member_{0}_change'.format(key),
                member,
                pre_value,
                value
            )

        def compare(a, b):
            def construct_set(v):
                return set(itertools.chain(
                    *[list(x.values()) if isinstance(x, dict) else (x,)
                      for x in v]
                ))

            if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
                return construct_set(a) == construct_set(b)
            return a == b

        for key, pre_value in pre_values.items():
            value = _getattr(member, key)
            if not compare(pre_value, value):
                _dispatch(key, member, pre_value, value)

    @dispatcher.event('com.epicgames.social.party.notification.v0.MEMBER_REQUIRE_CONFIRMATION')  # noqa
    async def event_party_member_require_confirmation(self,
                                                      ctx: EventContext
                                                      ) -> None:
        body = ctx.body

        user_id = body.get('account_id')
        if user_id != self.client.user.id:
            await self.client._join_party_lock.wait()

        party = self.client.party

        if party is None:
            return

        if party.id != body.get('party_id'):
            return

        user = self.client.get_user(user_id)
        if user is None:
            user = await self.client.fetch_user(user_id)

        confirmation = PartyJoinConfirmation(self.client, party, user, body)

        # Automatically confirm if event is received but no handler is found.
        if not self.client._event_has_destination('party_member_confirm'):
            return await confirmation.confirm()

        self.client.dispatch_event('party_member_confirm', confirmation)

    @dispatcher.event('com.epicgames.social.party.notification.v0.INVITE_DECLINED')  # noqa
    async def event_party_invite_declined(self, ctx: EventContext) -> None:
        body = ctx.body

        friend = self.client.get_friend(body['invitee_id'])
        if friend is not None:
            self.client.dispatch_event('party_invite_decline', friend)

    @dispatcher.presence()
    async def process_presence(self, user_id: str,
                               platform: str,
                               type_: str,
                               status: str,
                               show: str) -> None:
        try:
            data = json.loads(status)

            # We do this to filter out kairos from launcher presences
            ch = data.get('bIsEmbedded', False) or data.get('Status', '') != ''

            is_dict = isinstance(data.get('Properties', {}), dict)
            if (not ch or 'bIsPlaying' not in data or not is_dict):
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

        is_available = type_ is None or type_ == 'available'

        try:
            away = AwayStatus(show)
        except ValueError:
            away = AwayStatus.ONLINE

        _pres = Presence(
            self.client,
            user_id,
            platform,
            is_available,
            away,
            data
        )

        if _pres.party is not None:
            try:
                display_name = _pres.party.raw['sourceDisplayName']
                if display_name != _pres.friend.display_name:
                    _pres.friend._update_display_name(display_name)
            except (KeyError, AttributeError):
                pass

        before_pres = friend.last_presence

        if not is_available and friend.is_online():
            friend._update_last_logout(datetime.datetime.utcnow())

            try:
                del self.client._presences[user_id]
            except KeyError:
                pass

        else:
            self.client._presences[user_id] = _pres

        self.client.dispatch_event('friend_presence', before_pres, _pres)

    def on_stream_established(self):
        self.client.dispatch_event('xmpp_session_establish')

        async def on_establish():
            # Just incase the recover task hangs we don't want it
            # running forever in the background until a new close is
            # dispatched potentially fucking shit up big time.
            task = self._reconnect_recover_task
            if task is not None and not task.done():
                try:
                    await asyncio.wait_for(task, timeout=20)
                except asyncio.TimeoutError:
                    pass

        if self._is_suspended:
            self.client.dispatch_event('xmpp_session_reconnect')
            self.client.loop.create_task(self.client._reconnect_to_party())

        self._is_suspended = False
        self.client.loop.create_task(on_establish())

    def on_stream_suspended(self, reason):
        jid = self.xmpp_client.local_jid
        resource = jid.resource[:-32] + (uuid.uuid4().hex).upper()
        self.xmpp_client._local_jid = jid.replace(resource=resource)

        def on_events_recovered(*args):
            self._reconnect_recover_task = None

        self._reconnect_recover_task = task = self.client.loop.create_task(
            self.client.recover_events(
                refresh_caches=True,
                wait_for_close=False
            )
        )
        task.add_done_callback(on_events_recovered)

        if self.client.party is not None:
            self._last_known_party_id = self.client.party.id

        self._is_suspended = True
        self.client.dispatch_event('xmpp_session_lost')

    def on_stream_destroyed(self, reason=None):
        if not self._is_suspended:
            task = self._reconnect_recover_task
            if task is not None and not task.cancelled():
                task.cancel()

        self._last_disconnected_at = datetime.datetime.utcnow()
        self.client.dispatch_event('xmpp_session_close')

    def setup_callbacks(self, messages: bool = True) -> None:
        client = self.xmpp_client

        message_dispatcher = self.xmpp_client.summon(
            aioxmpp.dispatcher.SimpleMessageDispatcher
        )

        if messages:
            message_dispatcher.register_callback(
                aioxmpp.MessageType.CHAT,
                None,
                lambda m: asyncio.ensure_future(
                    self.process_chat_message(m)
                ),
            )

        client.on_stream_established.connect(self.on_stream_established)
        client.on_stream_suspended.connect(self.on_stream_suspended)
        client.on_stream_destroyed.connect(self.on_stream_destroyed)

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
            stream.soft_timeout = datetime.timedelta(minutes=3)
            stream.round_trip_time = datetime.timedelta(minutes=3)
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
                XMPPOverWebsocketConnector(
                    self.client,
                    ws_connector=self.ws_connector
                )
            )],
            loop=self.client.loop
        )
        self.xmpp_client.backoff_start = datetime.timedelta(seconds=0.1)

        self.muc_service = self.xmpp_client.summon(aioxmpp.MUCClient)
        self.setup_callbacks()

        future = self.client.loop.create_future()
        self._task = asyncio.ensure_future(self._run(future))
        await future

        self._ping_task = asyncio.ensure_future(self.loop_ping())

    async def close(self) -> None:
        log.debug('Attempting to close xmpp client')
        if self.xmpp_client.running:
            self.xmpp_client.stop()

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

        # let loop run one iteration for events to be dispatched
        await asyncio.sleep(0)

    def muc_on_message(self, message: aioxmpp.Message,
                       member: aioxmpp.muc.Occupant,
                       source: aioxmpp.im.dispatcher.MessageSource,
                       **kwargs: Any) -> None:
        if member.direct_jid is None:
            return

        user_id = member.direct_jid.localpart
        party = self.client.party

        if (user_id == self.client.user.id or member.nick is None
                or user_id not in party._members):
            return

        self.client.dispatch_event('party_message', PartyMessage(
            client=self.client,
            party=party,
            author=party._members[member.direct_jid.localpart],
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
            mem = self.client.party._members[member.direct_jid.localpart]
            self.client.dispatch_event('party_member_chatban',
                                       mem,
                                       muc_reason)

    async def join_muc(self, party_id: str) -> None:
        muc_jid = aioxmpp.JID.fromstr(
            'Party-{}@muc.prod.ol.epicgames.com'.format(party_id)
        )
        nick = '{0}:{1}:{2}'.format(
            self._remove_illegal_characters(self.client.user.display_name),
            self.client.user.id,
            self.xmpp_client.local_jid.resource
        )

        room, fut = self.muc_service.join(
            muc_jid,
            nick
        )

        room.on_message.connect(self.muc_on_message)
        room.on_join.connect(self.muc_on_member_join)
        room.on_enter.connect(self.muc_on_enter)
        room.on_leave.connect(self.muc_on_leave)
        self.muc_room = room

        asyncio.ensure_future(fut)
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

    def set_presence(self, *,
                     status: Optional[Union[str, dict]] = None,
                     show: Optional[str]) -> None:
        if status is None:
            self.xmpp_client.presence = aioxmpp.PresenceState(available=True)

        _status = status if isinstance(status, dict) else {'Status': status}
        self.xmpp_client.set_presence(
            state=aioxmpp.PresenceState(
                available=True,
                show=show
            ),
            status=json.dumps(_status)
        )

    async def send_presence(self, to: Optional[aioxmpp.JID] = None,
                            status: Optional[Union[str, dict]] = None,
                            show: Optional[str] = None) -> None:
        _status = {}
        if status is None:
            _status = None
        elif isinstance(status, str):
            _status['Status'] = status
        elif isinstance(status, dict):
            _status = status
        else:
            raise TypeError('status must be None, str or dict')

        pres = aioxmpp.Presence(
            type_=aioxmpp.PresenceType.AVAILABLE,
            show=aioxmpp.PresenceShow(show),
            to=to,
        )

        if _status is not None:
            pres.status[None] = json.dumps(_status)
        await self.stream.send(pres)

    async def get_presence(self, jid: aioxmpp.JID) -> Presence:
        self.client.loop.create_task(self.send_presence_probe(jid))
        _, after = await self.client.wait_for(
            'friend_presence',
            check=lambda b, a: a.friend.id == jid.localpart
        )
        return after

    async def send_presence_probe(self, to: aioxmpp.JID) -> None:
        presence = aioxmpp.Presence(
            type_=aioxmpp.PresenceType.PROBE,
            to=to
        )
        await self.stream.send(presence)
