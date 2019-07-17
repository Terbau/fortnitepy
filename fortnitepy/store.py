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

import re
import datetime

class Store:
    """Object representing store data from Fortnite Battle Royale.
    
    Attributes
    ----------
    client: :class:`Client`
        The client.
    """
    def __init__(self, client, data):
        self.client = client
        self._daily_purchase_hours = data['dailyPurchaseHrs']
        self._refresh_interval_hours = data['refreshIntervalHrs']
        self._expires_at = self.client.from_iso(data['expiration'])

        self._featured_items = self._create_featured_items(data)
        self._daily_items = self._create_daily_items(data)

    @property
    def featured_items(self):
        """List[:class:`FeaturedStoreItem`]: A list containing data about
        featured items in the item shop.
        """
        return self._featured_items

    @property
    def daily_items(self):
        """List[:class:`DailyStoreItem`]: A list containing data about
        daily items in the item shop.
        """
        return self._daily_items

    @property
    def daily_purchase_hours(self):
        """:class:`int`: How many hours a day it is possible to purchase
        items. It most likely is ``24``.
        """
        return self._daily_purchase_hours

    @property
    def refresh_interval_hours(self):
        """:class:`int`: Refresh interval hours."""
        return self._refresh_interval_hours

    @property
    def created_at(self):
        """:class:`datetime.datetime`: The UTC time of the creation
        and current day.
        """
        return self._expires_at - datetime.timedelta(days=1)
    
    @property
    def expires_at(self):
        """:class:`datetime.datetime`: The UTC time of when this
        item shop expires.
        """
        return self._expires_at

    def _find_storefront(self, data, key):
        for storefront in data['storefronts']:
            if storefront['name'] == key:
                return storefront

    def _create_featured_items(self, data):
        storefront = self._find_storefront(data, 'BRWeeklyStorefront')

        res = []
        for item in storefront['catalogEntries']:
            res.append(FeaturedStoreItem(item))
        return res

    def _create_daily_items(self, data):
        storefront = self._find_storefront(data, 'BRDailyStorefront')

        res = []
        for item in storefront['catalogEntries']:
            res.append(DailyStoreItem(item))
        return res


class StoreItemBase:
    def __init__(self, data):
        self._dev_name = data['devName']
        self._asset_path = data.get('displayAssetPath')
   
        try:
            self._asset = re.search(r'\.(.+)', self._asset_path)[1]
        except TypeError:
            self._asset = None

        self._gifts_enabled = data['giftInfo']['bIsEnabled']
        self._daily_limit = data['dailyLimit']
        self._weekly_limit = data['weeklyLimit']
        self._monthly_limit = data['monthlyLimit']
        self._offer_id = data['offerId']
        self._offer_type = data['offerType']
        self._price = data['prices'][0]['finalPrice']
        self._refundable = data['refundable']
        self._items_grants = data['itemGrants']
        self._meta_info = data.get('metaInfo', [])

    @property
    def dev_name(self):
        """:class:`str`: The dev name of this item."""
        return self._dev_name

    @property
    def asset_path(self):
        """:class:`str`: The asset path of the item. Could be ``None`` if
        not found.
        """
        return self._asset_path

    @property
    def asset(self):
        """:class:`str`: The asset of the item. Usually a CID or
        or something similar. Could be ``None`` if not found.
        """
        return self._asset

    @property
    def encryption_key(self):
        """:class:`str`: The encryption key for this item. If no encryption
        key is found, this will be ``None``.
        """
        for meta in self._meta_info:
            if meta['key'] == 'EncryptionKey':
                return meta['value']

    @property
    def gifts_enabled(self):
        """:class:`bool`: ``True`` if gifts is enabled for this
        item else ``False``.
        """
        return self._gifts_enabled

    @property
    def daily_limit(self):
        """:class:`int`: The daily account limit for this item.
        ``-1`` = Unlimited.
        """
        return self._daily_limit

    @property
    def weekly_limit(self):
        """:class:`int`: The weekly account limit for this item.
        ``-1`` = Unlimited.
        """
        return self._weekly_limit

    @property
    def monthly_limit(self):
        """:class:`int`: The monthly account limit for this item.
        ``-1`` = Unlimited.
        """
        return self._monthly_limit

    @property
    def offer_id(self):
        """:class:`str`: The offer id of this item."""
        return self._offer_id

    @property
    def offer_type(self):
        """:class:`str`: The offer type of this item."""
        return self._offer_type

    @property
    def price(self):
        """:class:`int`: The price of this item in v-bucks."""
        return self._price
    
    @property
    def refundable(self):
        """:class:`bool`: ``True`` if item is refundable else
        ``False``.
        """
        return self._refundable

    @property
    def grants(self):
        """:class:`list`: A list of items you get from this purchase.
        
        Typical output: ::
            
            [{
                'quantity': 1,
                'type': 'AthenaCharacter',
                'asset': 'cid_318_athena_commando_m_demon'
            }]  
        """
        l = []
        for item in self._items_grants:
            _type, _asset = item['templateId'].split(':')
            l.append({
                'quantity': item['quantity'],
                'type': _type,
                'asset': _asset
            })
        return l

    @property
    def new(self):
        """:class:`bool`: ``True`` if the item is in the item shop for
        the first time, else ``False``.
        """
        for meta in self._meta_info:
            if meta['value'].lower() == 'new':
                return True
        return False


class FeaturedStoreItem(StoreItemBase):
    """Featured store item."""
    def __init__(self, data):
        super().__init__(data)
        self._panel = int((data['categories'][0].split(' '))[1])

    @property
    def panel(self):
        """:class:`int`: The panel the item is listed in from left
        to right.
        """
        return self._panel


class DailyStoreItem(StoreItemBase):
    """Daily store item."""
    def __init__(self, data):
        super().__init__(data)
