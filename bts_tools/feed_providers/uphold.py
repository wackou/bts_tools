#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
# Copyright (c) 2017 Nicolas Wack <wackou@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from . import FeedPrice, FeedSet, check_online_status, cachedmodulefunc, to_bts, from_bts, check_market
from ..feeds import BIT_ASSETS, FIAT_ASSETS
from cachetools import TTLCache
import requests
import logging

log = logging.getLogger(__name__)


NAME = 'Uphold'

# Fiat: AUDUSD, EURUSD, GBPUSD, NZDUSD, USDARS, USDCAD, USDCHF, USDCNY, USDDKK, USDHKD, USDJPY, USDMXN, USDNOK, USDSEK, USDSGD
# Crypto: BTCUSD, ETHUSD, LTCUSD,
# Metal: XAGUSD, XAUUSD
# Other (fiat?): USDAED, USDBRL, USDILS, USDINR, USDKES, USDPHP, USDPLN, VOXUSD, XPDUSD, XPTUSD
AVAILABLE_MARKETS = [(asset, 'USD') for asset in FIAT_ASSETS | {'GOLD', 'SILVER'}]


ASSET_MAP = {'GOLD': 'XAU',
             'SILVER': 'XAG'}


_cache = TTLCache(maxsize=8192, ttl=600)  # 10 mins


def feeds_from_reply(r):
    result = FeedSet()
    for feed in r:
        asset = to_bts(feed['pair'][:3])
        base = to_bts(feed['pair'][3:6])
        if asset in BIT_ASSETS and base in BIT_ASSETS:
            result.append(FeedPrice((float(feed['ask'])+float(feed['bid']))/2, asset, base))  # FIXME: remove provider, FeedPrice should guess automatically from calling stack

    # reverse USD pairs where USD is not base
    for f in result:
        if f.asset == 'USD':
            # only reverse if we don't have the pair yet
            if not result.filter(f.base, f.asset):
                result.append(FeedPrice(1/f.price, f.base, f.asset))

    #log.debug('got from uphold: {}'.format(result))
    return result


@cachedmodulefunc
def _get_all():
    r = requests.get('https://api.uphold.com/v0/ticker')
    r = r.json()
    return feeds_from_reply(r)


@check_online_status
def get_all(asset_list, base):
    log.debug('checking feeds for %s/%s at %s' % (asset_list, base, NAME))
    return FeedSet(f for f in _get_all() if f.asset in asset_list and f.base == base)


@check_online_status
@check_market
def get(cur, base):
    log.debug('checking feeds for %s/%s at %s' % (cur, base, NAME))

    # try to get feed price using global ticker first
    feed = _get_all().filter(cur, base)
    if feed:
        return feed.price()

    # otherwise, fetch feeds with the given base asset
    r = requests.get('https://api.uphold.com/v0/ticker/{}'.format(base)).json()
    return feeds_from_reply(r).price(cur, base)

