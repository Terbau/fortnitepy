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

import re
import datetime

from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from .client import Client


class StoreItemBase:
    def __init__(self, data: dict) -> None:
        self._dev_name = data['devName']
        self._asset_path = data.get('displayAssetPath')

        try:
            self._asset = re.search(r'\.(.+)', self._asset_path)[1]
        except TypeError:
            self._asset = None

        self._gifts_enabled = (data['giftInfo']['bIsEnabled']
                               if 'giftInfo' in data else False)
        self._daily_limit = data['dailyLimit']
        self._weekly_limit = data['weeklyLimit']
        self._monthly_limit = data['monthlyLimit']
        self._offer_id = data['offerId']
        self._offer_type = data['offerType']
        self._price = data['prices'][0]['finalPrice']
        self._refundable = data['refundable']
        self._items_grants = data['itemGrants']
        self._meta_info = data.get('metaInfo', [])
        self._meta = data.get('meta', {})

    def __str__(self) -> str:
        return self.dev_name

    @property
    def display_names(self) -> List[str]:
        """List[:class:`str`]: The display names for this item."""
        match = re.search(r'^\[VIRTUAL][0-9]+ x (.*) for [0-9]+ .*$',
                          self._dev_name)[1]
        return re.split(r', [0-9]+ x ', match)

    @property
    def dev_name(self) -> str:
        """:class:`str`: The dev name of this item."""
        return self._dev_name

    @property
    def asset_path(self) -> Optional[str]:
        """:class:`str`: The asset path of the item. Could be ``None`` if
        not found.
        """
        return self._asset_path

    @property
    def asset(self) -> Optional[str]:
        """:class:`str`: The asset of the item. Usually a CID or
        or something similar. Could be ``None`` if not found.
        """
        return self._asset

    @property
    def encryption_key(self) -> Optional[str]:
        """:class:`str`: The encryption key for this item. If no encryption
        key is found, this will be ``None``.
        """
        for meta in self._meta_info:
            if meta['key'] == 'EncryptionKey':
                return meta['value']

    @property
    def gifts_enabled(self) -> bool:
        """:class:`bool`: ``True`` if gifts is enabled for this
        item else ``False``.
        """
        return self._gifts_enabled

    @property
    def daily_limit(self) -> int:
        """:class:`int`: The daily account limit for this item.
        ``-1`` = Unlimited.
        """
        return self._daily_limit

    @property
    def weekly_limit(self) -> int:
        """:class:`int`: The weekly account limit for this item.
        ``-1`` = Unlimited.
        """
        return self._weekly_limit

    @property
    def monthly_limit(self) -> int:
        """:class:`int`: The monthly account limit for this item.
        ``-1`` = Unlimited.
        """
        return self._monthly_limit

    @property
    def offer_id(self) -> str:
        """:class:`str`: The offer id of this item."""
        return self._offer_id

    @property
    def offer_type(self) -> str:
        """:class:`str`: The offer type of this item."""
        return self._offer_type

    @property
    def price(self) -> int:
        """:class:`int`: The price of this item in v-bucks."""
        return self._price

    @property
    def refundable(self) -> bool:
        """:class:`bool`: ``True`` if item is refundable else
        ``False``.
        """
        return self._refundable

    @property
    def grants(self) -> List[dict]:
        """:class:`list`: A list of items you get from this purchase.

        Typical output: ::

            [{
                'quantity': 1,
                'type': 'AthenaCharacter',
                'asset': 'cid_318_athena_commando_m_demon'
            }]
        """
        grants = []
        for item in self._items_grants:
            _type, _asset = item['templateId'].split(':')
            grants.append({
                'quantity': item['quantity'],
                'type': _type,
                'asset': _asset
            })
        return grants

    @property
    def new(self) -> bool:
        """:class:`bool`: ``True`` if the item is in the item shop for
        the first time, else ``False``.
        """
        for meta in self._meta_info:
            if meta['value'].lower() == 'new':
                return True
        return False

    @property
    def violator(self) -> Optional[str]:
        """:class:`str`: The violator of this item. Violator is the
        red tag at the top of an item in the shop. Will be ``None``
        if no violator is found for this item.
        """
        unfixed = self._meta.get('BannerOverride')
        if unfixed:
            return ' '.join(re.findall(r'[A-Z][^A-Z]*', unfixed))


class FeaturedStoreItem(StoreItemBase):
    """Featured store item."""
    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._panel = int((data['categories'][0].split(' '))[1])

    def __repr__(self) -> str:
        return ('<FeaturedStoreItem dev_name={0.dev_name!r} asset={0.asset!r} '
                'price={0.price!r}>'.format(self))

    @property
    def panel(self) -> int:
        """:class:`int`: The panel the item is listed in from left
        to right.
        """
        return self._panel


class DailyStoreItem(StoreItemBase):
    """Daily store item."""
    def __init__(self, data: dict) -> None:
        super().__init__(data)

    def __repr__(self) -> str:
        return ('<DailyStoreItem dev_name={0.dev_name!r} asset={0.asset!r} '
                'price={0.price!r}>'.format(self))


class Store:
    """Object representing store data from Fortnite Battle Royale.

    Attributes
    ----------
    client: :class:`Client`
        The client.
    """
    def __init__(self, client: 'Client', data: dict) -> None:
        self.client = client
        self._daily_purchase_hours = data['dailyPurchaseHrs']
        self._refresh_interval_hours = data['refreshIntervalHrs']
        self._expires_at = self.client.from_iso(data['expiration'])

        self._featured_items = self._create_featured_items(data)
        self._daily_items = self._create_daily_items(data)

    def __repr__(self) -> str:
        return ('<Store created_at={0.created_at!r} '
                'expires_at={0.expires_at!r}>'.format(self))

    @property
    def featured_items(self) -> List[FeaturedStoreItem]:
        """List[:class:`FeaturedStoreItem`]: A list containing data about
        featured items in the item shop.
        """
        return self._featured_items

    @property
    def daily_items(self) -> List[DailyStoreItem]:
        """List[:class:`DailyStoreItem`]: A list containing data about
        daily items in the item shop.
        """
        return self._daily_items

    @property
    def daily_purchase_hours(self) -> int:
        """:class:`int`: How many hours a day it is possible to purchase
        items. It most likely is ``24``.
        """
        return self._daily_purchase_hours

    @property
    def refresh_interval_hours(self) -> int:
        """:class:`int`: Refresh interval hours."""
        return self._refresh_interval_hours

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: The UTC time of the creation
        and current day.
        """
        return self._expires_at - datetime.timedelta(days=1)

    @property
    def expires_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: The UTC time of when this
        item shop expires.
        """
        return self._expires_at

    def _find_storefront(self, data: dict, key: str) -> Optional[dict]:
        for storefront in data['storefronts']:
            if storefront['name'] == key:
                return storefront

    def _create_featured_items(self, data: dict) -> List[FeaturedStoreItem]:
        storefront = self._find_storefront(data, 'BRWeeklyStorefront')

        res = []
        for item in storefront['catalogEntries']:
            res.append(FeaturedStoreItem(item))
        return res

    def _create_daily_items(self, data: dict) -> List[DailyStoreItem]:
        storefront = self._find_storefront(data, 'BRDailyStorefront')

        res = []
        for item in storefront['catalogEntries']:
            res.append(DailyStoreItem(item))
        return res
