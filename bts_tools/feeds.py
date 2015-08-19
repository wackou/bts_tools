#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
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

from . import core
from .feed_providers import YahooProvider, BterFeedProvider, Btc38FeedProvider,\
    PoloniexFeedProvider, GoogleProvider, BloombergProvider, ALL_FEED_PROVIDERS
from collections import deque, defaultdict
from contextlib import suppress
from concurrent.futures import ThreadPoolExecutor
import threading
import itertools
import statistics
import logging

log = logging.getLogger(__name__)

"""BitAssets for which we check and publish feeds."""
BIT_ASSETS = {'USD', 'CNY', 'BTC', 'GOLD', 'EUR', 'GBP', 'CAD', 'CHF', 'HKD', 'MXN',
              'RUB', 'SEK', 'SGD', 'AUD', 'SILVER', 'TRY', 'KRW', 'JPY', 'NZD'}

BIT_ASSETS_INDICES = {'SHENZHEN': 'CNY',
                      'SHANGHAI': 'CNY',
                      'NASDAQC': 'USD',
                      'NIKKEI': 'JPY',
                      'HANGSENG': 'HKD'}

"""List of feeds that should be shown on the UI and in the logs. Note that we
always check and publish all feeds, regardless of this variable."""
DEFAULT_VISIBLE_FEEDS = ['USD', 'BTC', 'CNY', 'GOLD', 'EUR']

feeds = {}
nfeed_checked = 0
cfg = None
history_len = None
price_history = None
visible_feeds = DEFAULT_VISIBLE_FEEDS


def load_feeds():
    global cfg, history_len, price_history, visible_feeds
    cfg = core.config['monitoring']['feeds']
    history_len = int(cfg['median_time_span'] / cfg['check_time_interval'])
    price_history = {cur: deque(maxlen=history_len) for cur in BIT_ASSETS | set(BIT_ASSETS_INDICES.keys())}
    visible_feeds = cfg.get('visible_feeds', DEFAULT_VISIBLE_FEEDS)


def weighted_mean(l):
    """return the weighted mean of a list of [(value, weight)]"""
    return sum(v[0]*v[1] for v in l) / sum(v[1] for v in l)


def get_multi_feeds(func, args, providers, stddev_tolerance=None):
    result = defaultdict(list)
    provider_list = defaultdict(list)

    def get_price(pargs):
        args, provider = pargs
        return provider, args, getattr(provider, func)(*args)

    with ThreadPoolExecutor(max_workers=4) as e:
        for f in [e.submit(get_price, pargs)
                  for pargs in itertools.product(args, providers)]:
            with suppress(Exception):
                provider, args, price = f.result()
                result[args].append(price)
                provider_list[args].append(provider)

    if stddev_tolerance:
        for asset, price_list in result.items():
            if len(price_list) < 2:
                continue  # cannot compute stddev with less than 2 elements
            price = statistics.mean(price_list)
            stddev = statistics.stdev(price_list, price) / price  # relative stddev
            if stddev > stddev_tolerance:
                log.warning('Feeds for {asset} are not consistent amongst providers: {feeds} (stddev = {stddev:.7f})'.format(
                    asset=asset, stddev=stddev,
                    feeds=' - '.join('{}: {}'.format(p.NAME, q) for p, q in zip(provider_list[asset], price_list))
                ))

    return result


def get_feed_prices():
    provider_names = {p.lower() for p in cfg['feed_providers']}
    active_providers = set()
    for name, provider in ALL_FEED_PROVIDERS.items():
        if name in provider_names:
            active_providers.add(provider())

    # get currency rates from yahoo
    # do not include:
    # - BTC as we don't get it from yahoo
    # - USD as it is our base currency
    yahoo = YahooProvider()
    yahoo_curs = BIT_ASSETS - {'BTC', 'USD'}
    yahoo_prices = yahoo.get(yahoo_curs, 'USD')

    # 1- get the BitShares price in BTC using the biggest markets: USD and CNY

    # first get rate conversion between USD/CNY from yahoo and CNY/BTC from
    # bter and btc38 (use CNY and not USD as the market is bigger)
    cny_usd = yahoo_prices.pop('CNY')

    bter, btc38, poloniex = BterFeedProvider(), Btc38FeedProvider(), PoloniexFeedProvider()

    providers_bts_btc = {bter, btc38, poloniex} & active_providers
    if not providers_bts_btc:
        log.warning('No feed providers for BTS/BTC feed price')
    all_feeds = get_multi_feeds('get', [('BTS', 'BTC')], providers_bts_btc)

    providers_bts_cny = {bter, btc38} & active_providers
    if not providers_bts_cny:
        log.warning('No feed providers for BTS/CNY feed price')
    all_feeds.update(get_multi_feeds('get', [('BTC', 'CNY'), ('BTS', 'CNY')], providers_bts_cny))

    feeds_btc_cny = all_feeds[('BTC', 'CNY')]
    if not feeds_btc_cny:
        raise core.NoFeedData('Could not get any BTC/CNY feeds')
    btc_cny = weighted_mean(feeds_btc_cny)
    cny_btc = 1 / btc_cny

    # then get the weighted price in btc for the most important markets
    feeds_bts_btc = all_feeds[('BTS', 'BTC')] + [(p[0]*cny_btc, p[1]) for p in all_feeds[('BTS', 'CNY')]]
    if not feeds_bts_btc:
        raise core.NoFeedData('Could not get any BTS/BTC feeds')
    btc_price = weighted_mean(feeds_bts_btc)

    cny_price = btc_price * btc_cny
    usd_price = cny_price * cny_usd

    feeds['USD'] = usd_price
    feeds['BTC'] = btc_price
    feeds['CNY'] = cny_price

    # 2- now get the BitShares price in all other required currencies
    for cur, yprice in yahoo_prices.items():
        feeds[cur] = usd_price / yprice

    # 3- get the feeds for major composite indices
    providers_quotes = {yahoo, GoogleProvider(), BloombergProvider()}

    all_quotes = get_multi_feeds('query_quote',
                                 BIT_ASSETS_INDICES.items(), providers_quotes & active_providers,
                                 stddev_tolerance=0.02)

    for asset, cur in BIT_ASSETS_INDICES.items():
        feeds[asset] = 1 / statistics.mean(all_quotes[(asset, cur)])

    # 4- update price history for all feeds
    for cur, price in feeds.items():
        price_history[cur].append(price)


def median_str(cur):
    try:
        return statistics.median(price_history[cur])
    except Exception:
        return 'N/A'

def format_qualifier(c):
    if c in {'BTC', 'GOLD', 'SILVER'} | set(BIT_ASSETS_INDICES.keys()):
        return '%g'
    return '%f'


def check_feeds(nodes):
    # TODO: update according to: https://bitsharestalk.org/index.php?topic=9348.0;all
    global nfeed_checked
    feed_period = int(cfg['publish_time_interval'] / cfg['check_time_interval'])

    try:
        get_feed_prices()
        nfeed_checked += 1

        def fmt(feeds):
            fmt = ', '.join('%s %s' % (format_qualifier(c), c) for c in visible_feeds)
            msg = fmt % tuple(feeds[c] for c in visible_feeds)
            return msg

        log.debug('Got feeds: %s  [%d/%d]' % (fmt(feeds), nfeed_checked, feed_period))

        for node in nodes:
            # if an exception occurs during publishing feeds for a delegate (eg: standby delegate),
            # then we should still go on for the other nodes (and not let exceptions propagate)
            try:
                # only publish feeds if we're running a delegate node
                # we also require rpc_host == 'localhost', we don't want to publish on remote
                # nodes (while checking on them, for instance)
                # TODO: do we really want to ignore rpc_host != 'localhost', or should we just do what is asked?
                if node.type == 'delegate' and node.rpc_host == 'localhost' and 'feeds' in node.monitoring:
                    if nfeed_checked % feed_period == 0:
                        if not node.is_online():
                            log.warning('Cannot publish feeds for delegate %s: client is not running' % node.name)
                            continue
                        if not node.get_info()['wallet_unlocked']:
                            log.warning('Cannot publish feeds for delegate %s: wallet is locked' % node.name)
                            continue
                        # publish median value of the price, not latest one
                        median_feeds = {c: statistics.median(price_history[c]) for c in feeds}
                        log.info('Node %s publishing feeds: %s' % (node.name, fmt(median_feeds)))
                        feeds_as_string = [(cur, '{:.10f}'.format(price)) for cur, price in median_feeds.items()]
                        node.wallet_publish_feeds(node.name, feeds_as_string)
            except Exception as e:
                log.exception(e)

    except core.NoFeedData as e:
        log.warning(e)

    except Exception as e:
        log.exception(e)

    threading.Timer(cfg['check_time_interval'], check_feeds, args=(nodes,)).start()
