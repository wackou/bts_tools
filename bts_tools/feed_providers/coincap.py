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

from . import FeedPrice, check_online_status, check_market, FeedSet, to_bts
from retrying import retry
import pendulum
import requests
import logging

log = logging.getLogger(__name__)


NAME = 'CoinCap'

AVAILABLE_MARKETS = [('BTC', 'USD'), ('BTS', 'BTC'), ('ALTCAP', 'BTC')]

ASSET_MAP = {'MIOTA': 'IOT'}

TIMEOUT = 60

@check_online_status
@retry(retry_on_exception=lambda e: isinstance(e, requests.exceptions.Timeout),
       wait_exponential_multiplier=5000,
       stop_max_attempt_number=2)
#@check_market
def get(cur, base):
    log.debug('checking feeds for %s/%s at %s' % (cur, base, NAME))

    if cur == 'ALTCAP':
        r = requests.get('http://www.coincap.io/global', timeout=TIMEOUT).json()

        btc_cap = float(r['btcCap'])
        alt_cap = float(r['altCap'])
        price = btc_cap / alt_cap

        # log.debug('{} - btc: {}'.format(self.NAME, btc_cap))
        # log.debug('{} - total: {}'.format(self.NAME, btc_cap + alt_cap))
        # log.debug('{} - alt: {}'.format(self.NAME, alt_cap))
        log.debug('{} - ALTCAP price: {}'.format(NAME, price))

    else:
        bts = requests.get('http://coincap.io/page/{}'.format(cur)).json()
        price = bts['price_{}'.format(base.lower())]

    return FeedPrice(price, cur, base)


def get_all():
    feeds = requests.get('http://www.coincap.io/front').json()
    result = FeedSet()
    for f in feeds:
        result.append(FeedPrice(float(f['price']), to_bts(f['short']), 'USD',
                                volume=float(f['usdVolume']) / float(f['price']),
                                #last_updated=pendulum.from_timestamp(f['time'] / 1000),  # FIXME: time not present
                                provider=NAME))
    return result
