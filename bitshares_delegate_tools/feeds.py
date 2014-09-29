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


def get_from_yahoo(cur, base):
    r = requests.get('http://download.finance.yahoo.com/d/quotes.csv',
                     params={'s': '%s%s=X' % (cur.upper(), base.upper()),
                             'f': 'l1', 'e': 'csv'})
    return float(r.text.strip())


def get_from_bter(cur, base):
    log.debug('Getting from bter: %s %s' % (cur, base))
    r = requests.get('http://data.bter.com/api/1/ticker/%s_%s' % (cur.lower(), base.lower())).json()
    price = float(r['last']) or ((float(r['sell']) + float(r['buy'])) / 2)
    volume = float(r['vol_%s' % cur.lower()])
    return price, volume


def get_from_btc38(cur, base):
    log.debug('Getting from btc38: %s %s' % (cur, base))
    headers = {'content-type': 'application/json',
               'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:22.0) Gecko/20100101 Firefox/22.0'}
    r = requests.get('http://api.btc38.com/v1/ticker.php',
                     params={'c': cur.lower(), 'mk_type': base.lower()},
                     headers=headers).json()
    price = float(r['ticker']['last']) # TODO: (bid + ask) / 2 ?
    volume = float(r['ticker']['last']) * float(r['ticker']['vol'])
    return price, volume


def weighted_mean(l):
    """return the weighted mean of a list of [(value, weight)]"""
    return sum(v[0]*v[1] for v in l) / sum(v[1] for v in l)


def adjust(v, r):
    return v[0]*r, v[1]*r


def get_feed_prices():
    # first get rate conversion between USD/CNY from yahoo and CNY/BTC from
    # bter and btc38 (use CNY and not USD as the market is bigger)
    cny_usd = get_from_yahoo('CNY', 'USD')

    btc_cny = weighted_mean([get_from_btc38('BTC', 'CNY'),
                             get_from_bter('BTC', 'CNY')])
    cny_btc = 1 / btc_cny

    # then get the weighted price in btc for the most important markets
    btc_price = weighted_mean([get_from_btc38('BTSX', 'BTC'),
                               get_from_bter('BTSX', 'BTC'),
                               adjust(get_from_btc38('BTSX', 'CNY'), cny_btc),
                               adjust(get_from_bter('BTSX', 'CNY'), cny_btc)])

    cny_price = btc_price * btc_cny
    usd_price = cny_price * cny_usd

    feeds['USD'] = usd_price
    feeds['BTC'] = btc_price
    feeds['CNY'] = cny_price

    for cur, price in feeds.items():
        price_history[cur].append(price)


def median(cur):
    return sorted(price_history[cur])[len(price_history[cur])//2]


def check_feeds(rpc):
    global nfeed_checked
    feed_period = int(PUBLISH_FEED_INTERVAL / CHECK_FEED_INTERVAL)

    try:
        log.debug('Getting feed prices...')
        get_feed_prices()
        nfeed_checked += 1

        log.debug('Got feeds: %f USD, %g BTC, %f CNY   [%d/%d]' %
                  (feeds['USD'], feeds['BTC'], feeds['CNY'],
                   nfeed_checked, feed_period))

        if nfeed_checked % feed_period == 0:
            # publish median value of the price, not latest one
            usd, btc, cny = median('USD'), median('BTC'), median('CNY')
            log.info('Publishing feeds: %f USD, %g BTC, %f CNY' % (usd, btc, cny))
            rpc.wallet_publish_feeds(delegate_name(), [['USD', usd], ['BTC', btc], ['CNY', cny]])

    except Exception as e:
        log.error('While checking feeds:')
        log.exception(e)

    log.debug('Starting feed time with interval: %d' % CHECK_FEED_INTERVAL)
    threading.Timer(CHECK_FEED_INTERVAL, check_feeds, args=[rpc]).start()
