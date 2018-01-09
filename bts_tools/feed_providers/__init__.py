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

# declaration of the functions a plugin needs to provide in order to be
# considered as a valid plugin

from importlib import import_module
from functools import wraps
from requests.exceptions import Timeout
from collections.abc import Sequence, Set
from .. import core
import inspect
import functools
import statistics
import pendulum
import logging

log = logging.getLogger(__name__)


REQUIRED_FUNCTIONS = ['get']  #, 'help', 'run_command']

REQUIRED_VARS = ['NAME', 'AVAILABLE_MARKETS']


PROVIDER_STATES = {}


def function_call_str(module, func_name, args, kwargs):
    args_str = ', '.join(str(arg) for arg in args)
    kwargs_str = ', '.join('{}={}'.format(k, v) for k, v in kwargs.items())
    sep = ', ' if (args_str and kwargs_str) else ''
    return '{}.{}({}{}{})'.format(module, func_name, args_str, sep, kwargs_str)


def cachedmodulefunc(f):
    """@cachedmodulefunc should be applied to free functions in modules that define the ``_cache`` attribute
    as a ``cachetools.Cache`` instance."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        func_str = function_call_str(f.__module__, f.__qualname__, args, kwargs)
        c = import_module(f.__module__)._cache
        if c is None:
            log.warning('No cache available for {}'.format(func_str))
            return f(*args, **kwargs)

        key = (f.__module__, f.__qualname__, core.make_hashable(args), core.make_hashable(kwargs))
        try:
            cached_result = c[key]
            log.debug('Returning cached value for {}: {}'.format(func_str, cached_result))
            return cached_result
        except KeyError:
            pass  # key not found

        log.debug('No cached value for {}, computing it...'.format(func_str))
        result = f(*args, **kwargs)
        c[key] = result

        return result
    return wrapper


def check_online_status(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        name = import_module(f.__module__).NAME
        try:
            result = f(*args, **kwargs)
            if PROVIDER_STATES.get(name) != 'online':
                log.info('Feed provider %s came online' % name)
                PROVIDER_STATES[name] = 'online'
            return result

        except Exception as e:
            if PROVIDER_STATES.get(name) != 'offline':
                log.warning('Feed provider {} went offline: {}'.format(name, e))
                log.debug(e)
                #log.exception(e)
                PROVIDER_STATES[name] = 'offline'
            raise

    return wrapper


def check_market(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        cur, base, *_ = args
        mod = import_module(f.__module__)
        # cur can be either a single asset or a list/set of them
        asset_list = [cur] if isinstance(cur, str) else cur
        for asset in asset_list:
            if (asset, base) not in mod.AVAILABLE_MARKETS:
                msg = '{} does not provide feeds for market {}/{}'.format(mod.NAME, asset, base)
                log.warning(msg)
                raise core.NoFeedData(msg)
        return f(*args, **kwargs)

    return wrapper


def reuse_last_value_on_fail(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        cur, base, *_ = args
        MAX_FAILS = 5
        f.last_value = getattr(f, 'last_value', {})
        f.n_consecutive_fails = getattr(f, 'n_consecutive_fails', 0)
        try:
            result = f(*args, **kwargs)
            f.last_value[(cur, base)] = result
            f.n_consecutive_fails = 0
            return result
        except Timeout:
            f.n_consecutive_fails += 1
            if f.n_consecutive_fails > MAX_FAILS:
                log.debug('Could not get feed price for {}/{} for {} times, failing with exception...'
                          .format(cur, base, f.n_consecutive_fails))
                raise
            v = f.last_value.get((cur, base))
            if v:
                log.debug('Could not get feed price for {}/{}, reusing last value: {}'.format(cur, base, v))
                return v
            else:
                log.debug('Could not get feed price for {}/{}, no last value...'.format(cur, base))
                raise

    return wrapper


def to_bts(asset):
    """The API for FeedProvider requires that all assets be named using their BTS denomination.
    However, certain providers use other names (eg: GOLD vs. XAG), and this method provides a way
    to convert an asset from its internal representation to its BTS representation."""

    frm = inspect.stack()[1]
    mod = inspect.getmodule(frm[0])
    #print('[%s] %s' % (mod.__name__, ''))
    asset_map = getattr(mod, 'ASSET_MAP', {})

    asset = asset.upper()
    for b, y in asset_map.items():
        if asset == y:
            return b
    return asset


def from_bts(asset):
    """The API for FeedProvider requires that all assets be named using their BTS denomination.
    However, certain providers use other names (eg: GOLD vs. XAG), and this method provides a way
    to convert an asset from its BTS representation to its internal representation."""
    frm = inspect.stack()[1]
    mod = inspect.getmodule(frm[0])
    #print('[%s] %s' % (mod.__name__, ''))
    asset_map = getattr(mod, 'ASSET_MAP', {})

    asset = asset.upper()
    return asset_map.get(asset, asset)


class FeedPrice(object):
    """Represent a feed price value. Contains additional metadata such as volume, etc.

    volume should be represented as number of <asset> units, not <base>."""

    def __init__(self, price, asset, base, volume=None, last_updated=None, provider=None):
        self.price = price
        self.asset = asset
        self.base = base
        self.volume = volume  # volume of the market from which this price is coming, if any
        self.last_updated = last_updated or pendulum.utcnow()
        self.provider = provider

        if self.provider is None:
            # try to get the module from the call stack
            frm = inspect.stack()[1]
            mod = inspect.getmodule(frm[0])
            name = getattr(mod, 'NAME', None)
            self.provider = name

    @staticmethod
    def from_graphene_tx(tx):
        block_num = tx['op']['block_num']
        op_id, feed = tx['op']['op']
        assert op_id == 19
        asset_id = feed['asset_id']

        import bts_tools.rpcutils as rpc

        s = feed['feed']['settlement_price']
        price = int(s['base']['amount']) / int(s['quote']['amount'])

        assert asset_id == s['base']['asset_id']

        asset_data = rpc.main_node.get_asset(asset_id)
        #print('asset data: {}'.format(asset_data))
        asset = asset_data['symbol']
        base = rpc.main_node.get_asset(s['quote']['asset_id'])['symbol']

        block_time = pendulum.parse(rpc.main_node.get_block(block_num)['timestamp'])
        f = FeedPrice(price, asset, base, last_updated=block_time)
        return f

    # FIXME: move me somewhere else
    @staticmethod
    def find_feeds(account, nfeeds=1000, valid=None):
        from bts_tools.rpcutils import main_node
        feeds = [FeedPrice.from_graphene_tx(tx) for tx in main_node.get_account_history(account, nfeeds)
                 if tx['op']['op'][0] == 19]  # only feed publishing operations
        if valid is not None:
            feeds = [f for f in feeds if valid(f)]
        return feeds

    def __str__(self):
        return 'FeedPrice: {} {}/{}{}{}'.format(
            self.price, self.asset, self.base,
            ' - vol={}'.format(self.volume) if self.volume is not None else '',
            ' from {}'.format(self.provider) if self.provider else '')

    def __repr__(self):
        return '<{}>'.format(str(self))


class FeedSet(list):
    # NOTE: use list for now and not set because we're not sure what to hash or use for __eq__

    def filter(self, asset=None, base=None):
        """Returns a new FeedSet containing only the feed prices about the given market(s)"""
        def is_valid(f):
            if asset is not None:
                if isinstance(asset, str) and f.asset != asset:
                    return False
                elif isinstance(asset, (Sequence, Set)) and f.asset not in asset:
                    return False
            if base is not None:
                if isinstance(base, str) and f.base != base:
                    return False
                elif isinstance(base, (Sequence, Set)) and f.base not in base:
                    return False
            return True

        return FeedSet([f for f in self if is_valid(f)])

    def _price(self):
        if len(self) == 0:
            raise ValueError('FeedSet is empty, can\'t get value...')
        if len(self) > 1:
            raise ValueError('FeedSet contains more than one feed. '
                             'Please use self.weighted_mean() to compute the value')

        return self[0].price

    def average_price(self, asset=None, base=None, stddev_tolerance=None):
        """Automatically compute the price of an asset using all relevant data in this FeedSet"""
        if len(self) == 0:
            raise ValueError('FeedSet is empty, can\'t compute price...')

        # check that if asset=None or base=None then there is no ambiguity
        if asset is None:
            asset_list = [f.asset for f in self]
            if asset_list.count(asset_list[0]) != len(asset_list):  # they're not all equal
                raise ValueError('asset=None: cannot decide which asset to use for computing the price: {}'
                                 .format(set(asset_list)))
        if base is None:
            base_list = [f.base for f in self]
            if base_list.count(base_list[0]) != len(base_list):  # they're not all equal
                raise ValueError('base=None: cannot decide which base to use for computing the price: {}'
                                 .format(set(base_list)))

        asset = asset or self[0].asset
        base = base or self[0].base
        prices = self.filter(asset, base)
        return prices.weighted_mean(stddev_tolerance=stddev_tolerance)

    def median_price(self, asset=None, base=None):
        # do some checks (as in average_price)
        pass

    price = average_price

    def median(self):
        # TODO: implement me!
        pass

    def weighted_mean(self, stddev_tolerance=None):
        if len(self) == 0:
            raise ValueError('FeedSet is empty, can\'t get weighted mean...')

        if len(self) == 1:
            #log.debug('Got price from single source: {}'.format(self[0]))
            return self[0].price

        asset, base = self[0].asset, self[0].base

        # check all feeds are related to the same market
        if any((f.asset, f.base) != (asset, base) for f in self):
            raise ValueError('Inconsistent feeds: there is more than 1 market in this FeedSet: {}'
                             .format(set((f.asset, f.base) for f in self)))

        # if any(f.volume is None for f in self) -> use simple mean of them, each has a weight of 1
        use_simple_mean = False
        if any(f.volume is None for f in self):
            log.debug('No volume defined for at least one feed: {}, using simple mean'.format(self))
            # FIXME: should be using the median here instead
            use_simple_mean = True
            total_volume = len(self)
        else:
            total_volume = sum(f.volume for f in self)

        weighted_mean = sum(f.price * (1 if use_simple_mean else f.volume) for f in self) / total_volume

        log.debug('Weighted mean for {}/{}: {:.6g}'.format(asset, base, weighted_mean))
        log.debug('Exchange      Price          Volume          Contribution')
        for f in self:
            percent = 100 * (1 if use_simple_mean else f.volume) / total_volume
            log.debug('{:14s} {:12.4g} {:14.2f} {:14.2f}%'.format(f.provider or 'unknown', f.price, (1 if use_simple_mean else f.volume), percent))

        if stddev_tolerance:
            price_list = [f.price for f in self]
            price = statistics.mean(price_list)
            stddev = statistics.stdev(price_list, price) / price  # relative stddev
            if stddev > stddev_tolerance:
                log.warning('Feeds for {asset} are not consistent amongst providers: {feeds} (stddev = {stddev:.7f})'
                            .format(asset=(asset, base), stddev=stddev, feeds=str(self)))
                for f in self:
                    log.warning(' -- {} {} {} {} {}'.format(f, repr(f), f.price, f.asset, f.base))

        return weighted_mean
