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

__version__ = '1.0.2'

from .client import Client, get_event_loop
from .friend import Friend, PendingFriend
from .message import FriendMessage, PartyMessage
from .party import PartyMember, ClientPartyMember, Party, ClientParty, PartyInvitation, PartyJoinConfirmation
from .presence import Presence, PresenceGameplayStats, PresenceParty
from .user import ClientUser, User
from .stats import StatsV2
from .enums import *
from .errors import *
from .store import Store, FeaturedStoreItem, DailyStoreItem
from .news import BattleRoyaleNewsPost
from .playlist import Playlist

# temporary fix for python 3.8
get_event_loop()
