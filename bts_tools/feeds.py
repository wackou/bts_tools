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
from .core import hashabledict
from .feed_providers import FeedPrice, FeedSet
from .feed_publish import publish_bts_feed, publish_steem_feed, BitSharesFeedControl
from collections import deque
from contextlib import suppress
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import itertools
import statistics
import json
import pendulum
import re
import logging
import math

log = logging.getLogger(__name__)

"""BitAssets for which we check and publish feeds."""
FIAT_ASSETS = {'USD', 'CNY', 'EUR', 'GBP', 'CAD', 'CHF', 'HKD', 'MXN', 'RUB', 'SEK', 'SGD',
               'AUD', 'TRY', 'KRW', 'JPY', 'NZD', 'ARS'}

BASE_ASSETS = {'BTC', 'GOLD', 'SILVER'} | FIAT_ASSETS

OTHER_ASSETS = {'ALTCAP', 'GRIDCOIN', 'STEEM', 'GOLOS',
                'BTWTY', 'RUBLE', 'HERO', 'HERTZ'}

BIT_ASSETS = BASE_ASSETS | OTHER_ASSETS

"""List of feeds that should be shown on the UI and in the logs. Note that we
always check and publish all feeds, regardless of this variable."""
DEFAULT_VISIBLE_FEEDS = ['USD', 'BTC', 'CNY', 'SILVER', 'EUR']

cfg = None


history_len = None
price_history = None
feeds = {}

feed_control = None
#nfeed_checked = 0
#visible_feeds = DEFAULT_VISIBLE_FEEDS


def load_feeds():
    global cfg, history_len, price_history, visible_feeds, feed_control
    cfg = core.config['monitoring']['feeds']
    history_len = int(cfg['median_time_span'] / cfg['check_time_interval'])
    price_history = {cur: deque(maxlen=history_len) for cur in BIT_ASSETS}
    visible_feeds = cfg['bts'].get('visible_feeds', DEFAULT_VISIBLE_FEEDS)
    feed_control = BitSharesFeedControl(cfg=cfg, visible_feeds=visible_feeds)


def get_multi_feeds(func, args, providers, stddev_tolerance=None):
    result = FeedSet()
    provider_list = []

    def get_price(pargs):
        args, provider = pargs
        return provider, args, getattr(provider, func)(*args)

    with ThreadPoolExecutor(max_workers=4) as e:
        for f in [e.submit(get_price, pargs)
                  for pargs in itertools.product(args, providers)]:
            with suppress(Exception):
                provider, args, price = f.result()
                result.append(price)
                provider_list.append(provider)

    return result


def _fetch_feeds(node, cfg):
    result = FeedSet()
    feed_providers = core.get_plugin_dict('bts_tools.feed_providers')

    def get_price(asset, base, provider):
        #log.warning('get_price {}/{} at {}'.format(asset, base, provider))
        return provider.get(asset, base)

    def get_price_multi(asset_list, base, provider):
        #log.warning('get_price_multi {}/{} at {}'.format(asset_list, base, provider))
        return provider.get_all(asset_list, base)

    def get_price_with_node(asset, base, provider, node):
        #log.warning('get_price_with_node {}/{} at {}, node = {}'.format(asset, base, provider, node))
        return provider.get(asset, base, node)

    with ThreadPoolExecutor(max_workers=6) as e:
        futures = {}
        for asset, base, providers in cfg['markets']:
            if isinstance(providers, str):
                providers = [providers]
            for provider in providers:
                if getattr(feed_providers[provider], 'REQUIRES_NODE', False) is True:
                    futures[e.submit(get_price_with_node, asset, base, feed_providers[provider], node)] = [asset, base, provider]
                elif isinstance(asset, str):
                    futures[e.submit(get_price, asset, base, feed_providers[provider])] = [asset, base, provider]
                else:
                    # asset is an asset_list
                    futures[e.submit(get_price_multi, asset, base, feed_providers[provider])] = [asset, base, provider]

        # futures = {e.submit(get_price, asset, base, feed_providers[provider])
        #            if isinstance(asset, str)
        #            else e.submit(get_price_multi, asset, base, feed_providers[provider]): [asset, base, provider]
        #            for asset, base, provider in cfg['markets']}

        for f in as_completed(futures):
            asset, base, provider = futures[f]
            try:
                feeds = f.result()
                if isinstance(feeds, FeedPrice):
                    feeds = FeedSet([feeds])
                result += feeds
                log.debug('Provider {} got feeds: {}'.format(provider, feeds))
            except Exception as e:
                log.warning('Could not fetch {}/{} on {}: {}'.format(asset, base, provider, e))
                #log.exception(e)

    return result


def _apply_rules(node, cfg, result):
    publish_list = []  # list of (asset, base) that need to be published

    def mkt(market_pair):
        return tuple(market_pair.split('/'))

    def execute_rule(rule, *args):
        if rule == 'compose':
            log.debug('composing {} with {}'.format(args[0], args[1]))
            (market1_asset, market1_base), (market2_asset, market2_base) = mkt(args[0]), mkt(args[1])
            if market1_base != market2_asset:
                raise ValueError('`base` in first market {}/{} is not the same as `asset` in second market {}/{}'
                                 .format(market1_asset, market1_base, market2_asset, market2_base))

            p1 = result.price(market1_asset, market1_base)
            p2 = result.price(market2_asset, market2_base)
            if p1 is None:
                raise core.NoFeedData('No feed for market {}/{}'.format(market1_asset, market1_base))
            if p2 is None:
                raise core.NoFeedData('No feed for market {}/{}'.format(market2_asset, market2_base))

            r = FeedPrice(price=p1 * p2, asset=market1_asset, base=market2_base)
            result.append(r)

        elif rule == 'invert':
            log.debug('inverting {}'.format(args[0]))
            asset, base = mkt(args[0])
            r = FeedPrice(price=1 / result.price(asset, base),
                          asset=base, base=asset,
                          # volume=volume / price   # FIXME: volume needs to be in the opposite unit
                          )
            result.append(r)

        elif rule == 'loop':
            log.debug('applying rule {} to the following assets: {}'.format(args[1], args[0]))
            rule, *args2 = args[1]
            for a in args[0]:
                args3 = tuple(arg.format(a) for arg in args2)
                execute_rule(rule, *args3)

        elif rule == 'copy':
            log.debug('copying {} to {}'.format(args[0], args[1]))
            src_asset, src_base = mkt(args[0])
            dest_asset, dest_base = mkt(args[1])

            r = FeedPrice(result.price(src_asset, src_base), dest_asset, dest_base)
            result.append(r)

        elif rule == 'publish':
            asset, base = mkt(args[0])
            log.debug('should publish {}/{}'.format(asset, base))
            publish_list.append((asset, base))

        else:
            raise ValueError('Invalid rule: {}'.format(rule))

    for rule, *args in cfg['rules']:
        try:
            execute_rule(rule, *args)

        except Exception as e:
            log.warning('Could not execute rule: {} {}'.format(rule, args))
            log.exception(e)

    return result, publish_list


def get_feed_prices_new(node, cfg):
    # 1- fetch all feeds
    result = _fetch_feeds(node, cfg)

    # 2- apply rules
    return _apply_rules(node, cfg, result)



def get_feed_prices(node, cfg):
    result, publish_list = get_feed_prices_new(node, cfg)
    feeds = {}

    base_blockchain = node.type().split('-')[0]
    if base_blockchain == 'bts':
        for f in result.filter(base='BTS'):
            feeds[f.asset] = 1/f.price

        try:
            feeds['ALTCAP'] = 1/result.filter('ALTCAP', 'BTC')[0].price
        except Exception:
            #log.debug('Did not have a price for ALTCAP/BTC')
            pass

    elif base_blockchain == 'steem':
        try:
            feeds['STEEM'] = result.price('STEEM', 'USD')
        except Exception:
            pass

    # update price history for all feeds
    # FIXME: remove this from here (use of shared global var price_history)
    for cur, price in feeds.items():
        price_history[cur].append(price)

    # try:
    #     price_history['STEEM'].append(result.price('STEEM', 'USD'))
    # except ValueError:
    #     pass

    return feeds, publish_list


def median_str(cur):
    try:
        return statistics.median(price_history[cur])
    except Exception:
        return 'N/A'


def check_node_is_ready(node, base_error_msg=''):
    if not node.is_online():
        log.warning(base_error_msg + 'wallet is not running')
        return False
    if node.is_locked():
        log.warning(base_error_msg + 'wallet is locked')
        return False
    if not node.is_synced():
        log.warning(base_error_msg + 'client is not synced')
        return False
    return True


def get_base_for(asset):  # FIXME: deprecate / remove me
    if asset == 'ALTCAP':
        return 'BTC'
    return 'BTS'


def check_feeds(nodes):
    # 1- get all feeds from all feed providers (FP) at once. Only use FP designated as active
    # 2- compute price from the FeedSet using adequate strategy. FP can (should) be weighted
    #    (eg: BitcoinAverage: 4, BitFinex: 1, etc.) if no volume is present
    # 3- order of computation should be clearly defined and documented, or configurable in the yaml file (preferable)
    #
    global feeds, feed_control

    try:
        feeds, publish_list = get_feed_prices(nodes[0], core.config['monitoring']['feeds'][nodes[0].type()]) # use first node if we need to query the blockchain, eg: for bit20 asset composition
        feed_control.nfeed_checked += 1

        status = feed_control.publish_status({(k, get_base_for(k)): v for k, v in feeds.items()})
        log.debug('Got feeds on {}: {}'.format(nodes[0].type(), status))

        for node in nodes:
            if node.role != 'feed_publisher':
                continue

            # if an exception occurs during publishing feeds for a witness (eg: inactive witness),
            # then we should still go on for the other nodes (and not let exceptions propagate)
            try:
                if node.type() == 'bts':
                    if feed_control.should_publish():
                        base_error_msg = 'Cannot publish feeds for {} witness {}: '.format(node.type(), node.name)
                        if check_node_is_ready(node, base_error_msg) is False:
                            continue

                        base_msg = '{} witness {} feeds: '.format(node.type(), node.name)
                        # publish median value of the price, not latest one
                        median_feeds = {(c, get_base_for(c)): statistics.median(price_history[c]) for c in feeds}
                        publish_feeds = {(asset, base): median_feeds[(asset, base)] for asset, base in publish_list}
                        log.info(base_msg + 'publishing feeds: {}'.format(feed_control.format_feeds(publish_feeds)))

                        publish_bts_feed(node, cfg['bts'], publish_feeds, base_msg)

                        feed_control.last_published = pendulum.utcnow()  # FIXME: last_published is only for 'bts' now...

                elif node.type() == 'steem':
                    price = statistics.median(price_history['STEEM'])

                    # publish median value of the price, not latest one
                    if feed_control.should_publish_steem(node, price):
                        base_error_msg = 'Cannot publish feeds for steem witness {}: '.format(node.name)
                        if check_node_is_ready(node, base_error_msg) is False:
                            continue

                        publish_steem_feed(node, cfg['steem'], price)
                        node.opts['last_price'] = price
                        node.opts['last_published'] = pendulum.utcnow()

                # elif node.type() == 'muse':
                #  ...
                else:
                    log.error('Unknown blockchain type for feeds publishing: {}'.format(node.type()))

            except Exception as e:
                log.exception(e)

    except core.NoFeedData as e:
        log.warning(e)

    except Exception as e:
        log.exception(e)

    threading.Timer(cfg['check_time_interval'], check_feeds, args=(nodes,)).start()
