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

from . import FeedPrice, check_online_status, FeedSet, from_bts, to_bts, check_market
from .. import core
import json
import pendulum
import requests
import logging

log = logging.getLogger(__name__)


NAME = 'CoinMarketCap'

AVAILABLE_MARKETS = [('BTC', 'USD'), ('BTS', 'BTC'), ('ALTCAP', 'BTC')]

ASSET_MAP = {'BTC': 'bitcoin',
             'BTS': 'bitshares'
             }

@check_online_status
#@check_market
def get(cur, base):
    log.debug('checking feeds for %s/%s at %s' % (cur, base, NAME))

    if cur == 'ALTCAP':
        r = requests.get('https://api.coinmarketcap.com/v1/global/').json()
        btc_cap = r['bitcoin_percentage_of_market_cap']
        alt_cap = 100 - btc_cap
        price = btc_cap / alt_cap

        #log.debug('{} - btc: {}'.format(self.NAME, btc_cap))
        #log.debug('{} - alt: {}'.format(self.NAME, alt_cap))
        log.debug('{} - ALTCAP price: {}'.format(NAME, price))

    else:
        r = requests.get('https://api.coinmarketcap.com/v1/ticker/{}/?convert={}'.format(from_bts(cur), base)).json()
        price = float(r[0]['price_{}'.format(base.lower())])

    return FeedPrice(price, cur, base)


def get_all():
    feeds = requests.get('https://api.coinmarketcap.com/v1/ticker/').json()
    result = FeedSet()
    for f in feeds:
        try:
            price = float(f['price_usd'])
            volume = float(f['24h_volume_usd']) / price if f.get('24h_volume_usd') else None
            result.append(FeedPrice(price, f['symbol'], 'USD', volume=volume,
                                    last_updated=pendulum.from_timestamp(int(f['last_updated']))))
        except TypeError as e:
            # catches: TypeError: float() argument must be a string or a number, not 'NoneType'
            # on: f['price_usd']
            log.debug('Could not get USD price for feed: {}'.format(json.dumps(f, indent=4)))
            log.exception(e)
            pass
    return result
