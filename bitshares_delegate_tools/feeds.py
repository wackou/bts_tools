#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bitshares_delegate_tools - Tools to easily manage the bitshares client
# Copyright (c) 2014 Nicolas Wack <wackou@gmail.com>
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

from .core import config, delegate_name
from collections import deque
import threading
import requests
import logging

log = logging.getLogger(__name__)

cfg = config['monitoring']

CHECK_FEED_INTERVAL = cfg['check_feeds_time_interval']
PUBLISH_FEED_INTERVAL = cfg['publish_feeds_time_interval']

feeds = {}
nfeed_checked = 0

history_len = int(cfg['median_feed_time_span'] / CHECK_FEED_INTERVAL)
price_history = {cur: deque(maxlen=history_len) for cur in {'USD', 'BTC', 'CNY'}}


def get_from_bter(cur):
    r = requests.get('http://data.bter.com/api/1/ticker/btsx_%s' % cur.lower()).json()
    # BTSX/USD trade history seems to have disappeared and last == 0...
    return float(r['last']) or ((float(r['sell']) + float(r['buy'])) / 2)


def get_from_btc38(cur):
    headers = {'content-type': 'application/json',
               'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:22.0) Gecko/20100101 Firefox/22.0'}
    r = requests.get('http://api.btc38.com/v1/ticker.php',
                     params={'c':'btsx', 'mk_type':cur.lower()},
                     headers=headers).json()
    return float(r['ticker']['last'])


def get_feed_price(cur):
    if cur in {'CNY', 'BTC'}:
        price = (get_from_bter(cur) + get_from_btc38(cur)) / 2
    elif cur == 'USD':
        price = get_from_bter(cur)
    else:
        raise ValueError('Unsupported currency: %s' % cur)
    feeds[cur] = price
    price_history[cur].append(price)
    return price


def median(cur):
    return sorted(price_history[cur])[len(price_history[cur])//2]


def check_feeds(rpc):
    global nfeed_checked

    try:
        usd = get_feed_price('USD')
        btc = get_feed_price('BTC')
        cny = get_feed_price('CNY')
        log.debug('Got feeds: %f USD, %g BTC, %f CNY' % (usd, btc, cny))
        nfeed_checked += 1

        if nfeed_checked % int(PUBLISH_FEED_INTERVAL/CHECK_FEED_INTERVAL) == 0:
            # publish median value of the price, not latest one
            usd, btc, cny = median('USD'), median('BTC'), median('CNY')
            log.info('Publishing feeds: %f USD, %g BTC, %f CNY' % (usd, btc, cny))
            rpc.wallet_publish_price_feed(delegate_name(), usd, 'USD')
            rpc.wallet_publish_price_feed(delegate_name(), btc, 'BTC')
            rpc.wallet_publish_price_feed(delegate_name(), cny, 'CNY')

    except Exception as e:
        log.error('While checking feeds:')
        log.exception(e)

    threading.Timer(CHECK_FEED_INTERVAL, check_feeds, args=[rpc]).start()
