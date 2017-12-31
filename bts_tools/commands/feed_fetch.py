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

from .. import core
from ..core import run, replace_in_file, load_config, get_plugin_dict
from ..feed_providers import FeedSet, FeedPrice
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import sys
import os.path
import psutil
import logging

log = logging.getLogger(__name__)


def short_description():
    return 'fetch all prices from feed sources'


def help():
    return """feed_fetch [<config_filename>]'
    
config_filename: config file
"""


def run_command(config_filename=None):
    cfg = core.config['monitoring']['feeds']

    # 1- fetch all feeds
    result = FeedSet()
    feed_providers = get_plugin_dict('bts_tools.feed_providers')

    def get_price(asset, base, provider):
        log.warning('get_price {}/{} at {}'.format(asset, base, provider))
        return provider.get(asset, base)

    def get_price_multi(asset_list, base, provider):
        log.warning('get_price_multi {}/{} at {}'.format(asset_list, base, provider))
        return provider.get_all(asset_list, base)

    with ThreadPoolExecutor(max_workers=6) as e:
        futures = {}
        for asset, base, providers in cfg['markets']:
            if isinstance(providers, str):
                providers = [providers]
            for provider in providers:
                if isinstance(asset, str):
                    futures[e.submit(get_price, asset, base, feed_providers[provider])] = [asset, base, provider]
                else:
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
                log.info('Got feeds: {}'.format(feeds))
            except Exception as e:
                log.warning('Could not fetch {}/{} on {}: {}'.format(asset, base, provider, e))
                log.exception(e)

    print(result)

    def mkt(market_pair):
        return tuple(market_pair.split('/'))

    # 2- apply rules

    def execute_rule(rule, *args):
        if rule == 'compose':
            log.warning('composing {} with {}'.format(args[0], args[1]))
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
            log.error(r)
            result.append(r)

        elif rule == 'invert':
            log.warning('inverting {}'.format(args[0]))
            asset, base = mkt(args[0])
            r = FeedPrice(price=1 / result.price(asset, base),
                          asset=base, base=asset,
                          # volume=volume / price   # FIXME: volume needs to be in the opposite unit
                          )
            log.error(r)
            result.append(r)

        elif rule == 'loop':
            log.warning('applying rule {} to the following assets: {}'.format(args[1], args[0]))
            rule, *args2 = args[1]
            for a in args[0]:
                args3 = tuple(arg.format(a) for arg in args2)
                execute_rule(rule, *args3)

        elif rule == 'copy':
            log.warning('copying {} to {}'.format(args[0], args[1]))
            src_asset, src_base = mkt(args[0])
            dest_asset, dest_base = mkt(args[1])

            #src_price = result.price(src, base)
            r = FeedPrice(result.price(src_asset, src_base), dest_asset, dest_base)
            log.error(r)
            result.append(r)

        else:
            raise ValueError('Invalid rule: {}'.format(rule))


    for rule, *args in cfg['rules']:
        try:
            execute_rule(rule, *args)

        except Exception as e:
            log.warning('Could not execute rule: {} {}'.format(rule, args))
            log.exception(e)

    # 3- publish price
    for f in result.filter(base='BTS'):
        print(repr(f))
    print(repr(result.filter('ALTCAP', 'BTC')))