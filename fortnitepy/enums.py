# -*- coding: utf-8 -*-
# flake8: noqa

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

import random
import types

from typing import Optional, Any
from enum import Enum as OriginalEnum


class Enum(OriginalEnum):
    @classmethod
    def get_random_member(cls) -> Optional[Any]:
        try:
            return cls[random.choice(cls._member_names_)]
        except IndexError:
            pass

    @classmethod
    def get_random_name(cls) -> Optional[Any]:
        member = cls.get_random_member()
        if member is not None:
            return member.name

    @classmethod
    def get_random_value(cls) -> Optional[Any]:
        member = cls.get_random_member()
        if member is not None:
            return member.value


class PartyPrivacy(Enum):
    PUBLIC = {
        'partyType': 'Public',
        'inviteRestriction': 'AnyMember',
        'onlyLeaderFriendsCanJoin': False,
        'presencePermission': 'Anyone',
        'invitePermission': 'Anyone',
        'acceptingMembers': True,
    }
    FRIENDS_ALLOW_FRIENDS_OF_FRIENDS = {
        'partyType': 'FriendsOnly',
        'inviteRestriction': 'AnyMember',
        'onlyLeaderFriendsCanJoin': False,
        'presencePermission': 'Anyone',
        'invitePermission': 'AnyMember',
        'acceptingMembers': True,
    }
    FRIENDS = {
        'partyType': 'FriendsOnly',
        'inviteRestriction': 'LeaderOnly',
        'onlyLeaderFriendsCanJoin': True,
        'presencePermission': 'Leader',
        'invitePermission': 'Leader',
        'acceptingMembers': False,
    }
    PRIVATE_ALLOW_FRIENDS_OF_FRIENDS = {
        'partyType': 'Private',
        'inviteRestriction': 'AnyMember',
        'onlyLeaderFriendsCanJoin': False,
        'presencePermission': 'Noone',
        'invitePermission': 'AnyMember',
        'acceptingMembers': False,
    }
    PRIVATE = {
        'partyType': 'Private',
        'inviteRestriction': 'LeaderOnly',
        'onlyLeaderFriendsCanJoin': True,
        'presencePermission': 'Noone',
        'invitePermission': 'Leader',
        'acceptingMembers': False,
    }


class PartyDiscoverability(Enum):
    ALL          = 'ALL'
    INVITED_ONLY = 'INVITED_ONLY'


class PartyJoinability(Enum):
    OPEN              = 'OPEN'
    INVITE_ONLY       = 'INVITE_ONLY'
    INVITE_AND_FORMER = 'INVITE_AND_FORMER' 


class DefaultCharactersChapter1(Enum):
    CID_001_Athena_Commando_F_Default = 1
    CID_002_Athena_Commando_F_Default = 2
    CID_003_Athena_Commando_F_Default = 3
    CID_004_Athena_Commando_F_Default = 4
    CID_005_Athena_Commando_M_Default = 5
    CID_006_Athena_Commando_M_Default = 6
    CID_007_Athena_Commando_M_Default = 7
    CID_008_Athena_Commando_M_Default = 8


class DefaultCharactersChapter2(Enum):
    CID_556_Athena_Commando_F_RebirthDefaultA = 1
    CID_557_Athena_Commando_F_RebirthDefaultB = 2
    CID_558_Athena_Commando_F_RebirthDefaultC = 3
    CID_559_Athena_Commando_F_RebirthDefaultD = 4
    CID_560_Athena_Commando_M_RebirthDefaultA = 5
    CID_561_Athena_Commando_M_RebirthDefaultB = 6
    CID_562_Athena_Commando_M_RebirthDefaultC = 7
    CID_563_Athena_Commando_M_RebirthDefaultD = 8


class V1Gamemode(Enum):
    SOLO  = 'p2'
    DUO   = 'p10'
    SQUAD = 'p9'


class V1Platform(Enum):
    PC   = 'pc'
    XBOX = 'xb1'
    PS4  = 'ps4'


class V1Window(Enum):
    ALLTIME = 'alltime'
    WEEKLY  = 'weekly'


class V2Input(Enum):
    KEYBOARDANDMOUSE = 'keyboardmouse'
    GAMEPAD          = 'gamepad'
    TOUCH            = 'touch'


class Region(Enum):
    NAEAST     = 'NAE'
    NAWEST     = 'NAW'
    EUROPE     = 'EU'
    BRAZIL     = 'BR'
    OCEANIA    = 'OCE'
    ASIA       = 'ASIA'
    MIDDLEEAST = 'ME'


class Platform(Enum):
    WINDOWS       = 'WIN'
    MAC           = 'MAC'
    PLAYSTATION   = 'PSN'
    PLAYSTATION_4 = 'PSN'
    PLAYSTATION_5 = 'PS5'
    XBOX          = 'XBL'
    XBOX_ONE      = 'XBL'
    XBOX_X        = 'XBX'
    SWITCH        = 'SWT'
    IOS           = 'IOS'
    ANDROID       = 'AND'



class UserSearchPlatform(Enum):
    EPIC_GAMES  = 'epic'
    PLAYSTATION = 'psn'
    XBOX        = 'xbl'


class UserSearchMatchType(Enum):
    EXACT = 'exact'
    PREFIX = 'prefix'


class ReadyState(Enum):
    READY       = 'Ready'
    NOT_READY   = 'NotReady'
    SITTING_OUT = 'SittingOut'


class AwayStatus(Enum):
    ONLINE        = None
    AWAY          = 'away'
    EXTENDED_AWAY = 'xa'


class SeasonStartTimestamp(Enum):
    SEASON_1  = 1508889601
    SEASON_2  = 1513209601
    SEASON_3  = 1519257601
    SEASON_4  = 1525132801
    SEASON_5  = 1531353601
    SEASON_6  = 1538006401
    SEASON_7  = 1544054401
    SEASON_8  = 1551312001
    SEASON_9  = 1557360001
    SEASON_10 = 1564617601
    SEASON_11 = 1571097601
    SEASON_12 = 1582156801
    SEASON_13 = 1592352001
    SEASON_14 = 1598486401


class SeasonEndTimestamp(Enum):
    SEASON_1  = 1513123200
    SEASON_2  = 1519171200
    SEASON_3  = 1525046400
    SEASON_4  = 1531353600
    SEASON_5  = 1538006400
    SEASON_6  = 1544054400
    SEASON_7  = 1551312000
    SEASON_8  = 1557360000
    SEASON_9  = 1564617600
    SEASON_10 = 1570924800
    SEASON_11 = 1582156800
    SEASON_12 = 1592352000
    SEASON_13 = 1598486400


class BattlePassStat(Enum):
    SEASON_11 = ('s11_social_bp_level', SeasonEndTimestamp.SEASON_11.value)
    SEASON_12 = ('s11_social_bp_level', SeasonEndTimestamp.SEASON_12.value)
    SEASON_13 = (('s13_social_bp_level', 's11_social_bp_level'), SeasonEndTimestamp.SEASON_13.value)
    SEASON_14 = ('s14_social_bp_level', None)


class KairosBackgroundColorPreset(Enum):
    TEAL         = ["#8EFDE5","#1CBA9E","#034D3F"]
    SWEET_RED    = ["#FF81AE","#D8033C","#790625"]
    LIGHT_ORANGE = ["#FFDF00","#FBA000","#975B04"]
    GREEN        = ["#CCF95A","#30C11B","#194D12"]
    LIGHT_BLUE   = ["#B4F2FE","#00ACF2","#005679"]
    DARK_BLUE    = ["#1CA2E6","#0C5498","#081E3E"]
    PINK         = ["#FFB4D6","#FF619C","#7D3449"]
    RED          = ["#F16712","#D8033C","#6E0404"]
    GRAY         = ["#AEC1D3","#687B8E","#36404A"]
    ORANGE       = ["#FFAF5D","#FF6D32","#852A05"]
    DARK_PURPLE  = ["#E93FEB","#7B009C","#500066"]
    LIME         = ["#DFFF73","#86CF13","#404B07"]
    INDIGO       = ["#B35EEF","#4D1397","#2E0A5D"]


class StatsCollectionType(Enum):
    FISH = 'collection_fish'
