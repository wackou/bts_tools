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
from .core import hashabledict, trace
from .feed_providers import FeedPrice, FeedSet
from collections import deque
from contextlib import suppress
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import itertools
import statistics
import copy
import json
import pendulum
import re
import logging
import math

log = logging.getLogger('bts_tools.feeds')
# log = logging.getLogger(__name__)


def is_extended_precision(asset):
    return asset in {'BTC', 'GOLD', 'SILVER', 'BTWTY'}


def format_qualifier(asset):
    if is_extended_precision(asset):
        return '%g'
    return '%f'



def get_fraction(price, asset_precision, base_precision, N=6):
    """Find nice fraction with at least N significant digits in
    both the numerator and denominator."""
    numerator = int(price * 10 ** asset_precision)
    denominator = 10 ** base_precision
    multiplier = 0
    while len(str(numerator)) < N or len(str(denominator)) < N:
        multiplier += 1
        numerator = round(price * 10 ** (asset_precision + multiplier))
        denominator = 10 ** (base_precision + multiplier)
    return numerator, denominator


def get_price_for_publishing(node, cfg, asset, base, price, feeds=None):
    """feeds is only needed when base != BTS, to compute the CER (needs to be priced in BTS regardless of the base asset)"""
    c = {}    # make a copy, we don't want to update the default value
    c.update(core.config['monitoring']['feeds']['bts']['asset_params']['default'])
    c.update(cfg.get('asset_params', {})['default'])
    c.update(cfg.get('asset_params', {}).get(asset, {}))
    asset_id = node.asset_data(asset)['id']
    asset_precision = node.asset_data(asset)['precision']

    base_id = node.asset_data(base)['id']
    base_precision = node.asset_data(base_id)['precision']
    bts_precision = node.asset_data('BTS')['precision']

    numerator, denominator = get_fraction(price, asset_precision, base_precision)

    # CER price needs to be priced in BTS always. Get conversion rate
    # from the base currency to BTS, and use it to scale the CER price

    if base != 'BTS':
        #log.debug(feeds)
        try:
            base_bts_price = feeds[(base, 'BTS')]
        except KeyError:
            log.warning("Can't publish the CER for {}/BTS because we don't have feed price for {}: available = {} "
                        .format(asset, (base, 'BTS'), feeds))
        cer_numerator, cer_denominator = get_fraction(price * base_bts_price,
                                                      asset_precision, bts_precision)
        cer_denominator *= c['core_exchange_factor']  # FIXME: should round here
    else:
        cer_numerator, cer_denominator = numerator, round(denominator * c['core_exchange_factor'])

    price_obj = {
        'settlement_price': {
            'quote': {
                'asset_id': base_id,
                'amount': denominator
            },
            'base': {
                'asset_id': asset_id,
                'amount': numerator
            }
        },
        'maintenance_collateral_ratio': c['maintenance_collateral_ratio'],
        'maximum_short_squeeze_ratio': c['maximum_short_squeeze_ratio'],
        'core_exchange_rate': {
            'quote': {
                'asset_id': '1.3.0',
                'amount': cer_denominator
            },
            'base': {
                'asset_id': asset_id,
                'amount': cer_numerator
            }
        }
    }
    log.debug('Publishing feed for {}/{}: {} as {}/{} - CER: {}/{}'
             .format(asset, base, price, numerator, denominator, cer_numerator, cer_denominator))
    return price_obj


# TODO: Need 2 main classes: FeedHistory is a database of historical prices, allows querying,
#       and FeedControl is a strategy for deciding when to publish


def format_feeds(feeds, visible_feeds=None):
    display_feeds = []
    visible_feeds = visible_feeds or []
    for c in set(visible_feeds) - set(feeds.keys()):
        log.debug('No feed price available for {}, cannot display it'.format(c))
        # else:
        #     display_feeds.append(c)
    display_feeds = list(sorted(feeds))  # display given `feeds`, we ignore `visible_feeds` here

    fmt = ', '.join('%s %s/%s' % (format_qualifier(c[0]), c[0], c[1]) for c in display_feeds)
    msg = fmt % tuple(feeds[c] for c in display_feeds)
    return msg

class BitSharesFeedControl(object):
    def __init__(self, *, cfg, visible_feeds=None):
        self.cfg = copy.deepcopy(cfg)
        from .feeds import DEFAULT_VISIBLE_FEEDS
        self.visible_feeds = list(visible_feeds or DEFAULT_VISIBLE_FEEDS)

        # FIXME: deprecate self.feed_period
        try:
            self.feed_period = int(cfg['publish_strategy']['time_interval'] / cfg['check_time_interval'])
        except KeyError:
            self.feed_period = None

        self.check_time_interval = pendulum.interval(seconds=cfg.get('check_time_interval', 600))
        try:
            self.publish_time_interval = pendulum.interval(seconds=cfg['publish_strategy']['time_interval'])
        except KeyError:
            self.publish_time_interval = None

        self.feed_slot = cfg.get('publish_strategy', {}).get('time_slot', None)
        if self.feed_slot is not None:
            self.feed_slot = int(self.feed_slot)

        self.nfeed_checked = 0
        self.last_published = pendulum.utcnow().subtract(days=1)

        log.debug('successfully initialized {}'.format(self))

    def __str__(self):
        return 'BitSharesFeedControl(feed_period={}, check_time_interval={}, publish_time_interval={}, feed_slot={}'\
            .format(self.feed_period, self.check_time_interval, self.publish_time_interval, self.feed_slot)

    def format_feeds(self, feeds):
        return format_feeds(feeds, self.visible_feeds)
        # display_feeds = []
        # for c in set(self.visible_feeds) - set(feeds.keys()):
        #     log.debug('No feed price available for {}, cannot display it'.format(c))
        #     # else:
        #     #     display_feeds.append(c)
        # display_feeds = list(sorted(feeds))
        #
        # fmt = ', '.join('%s %s/%s' % (format_qualifier(c[0]), c[0], c[1]) for c in display_feeds)
        # msg = fmt % tuple(feeds[c] for c in display_feeds)
        # return msg

    def publish_status(self, feeds):
        status = ''
        if self.publish_time_interval:
            #status += ' [%d/%d]' % (self.nfeed_checked, self.feed_period)
            status += ' [every {}]'.format(self.publish_time_interval)
        if self.feed_slot:
            status += ' [t=HH:{:02d}]'.format(self.feed_slot)

        result = '{} {}'.format(self.format_feeds(feeds), status)
        #log.debug('Got feeds: {}'.format(result))
        return result


    def should_publish(self):
        # TODO: update according to: https://bitsharestalk.org/index.php?topic=9348.0;all

        #return False
        if self.nfeed_checked == 0:
            log.debug('Should publish at least once at launch of the bts_tools')
            return True

        if self.feed_period is not None and self.nfeed_checked % self.feed_period == 0:
            log.debug('Should publish because time interval has passed: {} seconds'.format(self.publish_time_interval))
            return True



        now = pendulum.utcnow()

        if self.publish_time_interval and now - self.last_published > self.publish_time_interval:
            log.debug('Should publish because time interval has passed: {}'.format(self.publish_time_interval))
            return True

        if self.feed_slot:
            target = now.replace(minute=self.feed_slot, second=0, microsecond=0)
            targets = [target.subtract(hours=1), target, target.add(hours=1)]
            diff = [now-t for t in targets]
            # check if we just passed our time slot
            if any(pendulum.interval() < d and abs(d) < 1.1*self.check_time_interval for d in diff):
                log.debug('Should publish because time slot has arrived: time {:02d}:{:02d}'.format(now.hour, now.minute))
                return True

        log.debug('No need to publish feeds')
        return False

    def should_publish_steem(self, node, price):
        # check whether we need to publish again:
        # - if published more than 12 hours ago, publish again
        # - if published price different by more than 3%, publish again
        if 'last_price' not in node.opts:  # make sure we have already published once
            log.debug('Steem should publish for the first time since launch of bts_tools')
            return True

        last_published_interval = pendulum.interval(hours=12)
        variance_trigger = 0.03

        if pendulum.utcnow() - node.opts['last_published'] > last_published_interval:  # FIXME: replace node.opts['last_published'] with self.last_published[node]
            log.debug('Steem should publish as it has not been published for {}'.format(last_published_interval))
            return True
        if abs(price - node.opts['last_price']) / node.opts['last_price'] >= variance_trigger:
            log.debug('Steem should publish as price has moved more than {}%'.format(100*variance_trigger))
            return True
        log.debug('No need for Steem to publish')
        return False


def publish_steem_feed(node, cfg, price):
    ratio = cfg['steem']['steem_dollar_adjustment']
    price_obj = {'base': '{:.3f} SBD'.format(price),
                 'quote': '{:.3f} STEEM'.format(1 / ratio)}
    log.info('Node {}:{} publishing feed price for steem: {:.3f} SBD (real: {:.3f} adjusted by {:.2f})'
             .format(node.type(), node.name, price * ratio, price, ratio))
    node.publish_feed(node.name, price_obj, True)


def publish_bts_feed(node, cfg, publish_feeds, base_msg):
    # first, try to publish all of them in a single transaction
    try:
        published = []
        handle = node.begin_builder_transaction()
        for (asset, base), price in sorted(publish_feeds.items()):
            published.append(asset)
            op = [19,  # id 19 corresponds to price feed update operation
                  hashabledict({"asset_id": node.asset_data(asset)['id'],
                                "feed": get_price_for_publishing(node, cfg, asset, base, price, publish_feeds),
                                "publisher": node.get_account(node.name)["id"]})
                  ]
            node.add_operation_to_builder_transaction(handle, op)

        # set fee
        node.set_fees_on_builder_transaction(handle, '1.3.0')

        # sign and broadcast
        node.sign_builder_transaction(handle, True)
        log.debug(base_msg + 'successfully published feeds for {}'.format(', '.join(published)))

    except Exception as e:
        #log.exception(e)
        log.warning(base_msg + 'tried to publish all feeds in a single transaction, but failed. '
                               'Will try to publish each feed separately now')
        msg_len = 400
        log.debug(str(e)[:msg_len] + (' [...]' if len(str(e)) > msg_len else ''))

        # if an error happened, publish feeds individually to make sure that
        # at least the ones that work can get published
        published = []
        failed = []
        for (asset, base), price in sorted(publish_feeds.items()):
            try:
                price_obj = hashabledict(get_price_for_publishing(node, cfg, asset, base, price, publish_feeds))
                log.debug(base_msg + 'Publishing {} {}'.format(asset, price_obj))
                node.publish_asset_feed(node.name, asset, price_obj, True)  # True: sign+broadcast
                log.debug('Successfully published feed for asset {}: {}'.format(asset, price))
                published.append(asset)

            except Exception as e:
                log.debug(base_msg + 'Failed to publish feed for asset {}'.format(asset))
                if log.isEnabledFor(logging.DEBUG):
                    log.exception(e)
                log.debug(str(e)[:msg_len] + ' [...]')
                failed.append(asset)

        if failed:
            log.warning(base_msg + 'Failed to publish feeds for: {}'.format(', '.join(failed)))
        if published:
            log.info(base_msg + 'Successfully published feeds for: {}'.format(', '.join(published)))
