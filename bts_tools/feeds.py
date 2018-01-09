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
from .feed_providers import FeedPrice, FeedSet, bit20
from collections import deque, defaultdict
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


def get_bit20_feed(node, usd_price):
    bit20_value = bit20.get_bit20_feed_usd(node)
    # get bit20 value in BTS
    bit20_value /= usd_price
    log.debug('Value of the bit20 asset in BTS: {} BTS'.format(bit20_value))

    return 1 / bit20_value


def get_hertz_feed(reference_timestamp, current_timestamp, period_days, phase_days, reference_asset_value, amplitude):
    """Given the reference timestamp, the current timestamp, the period (in days), the phase (in days), the reference asset value (ie 1.00) and the amplitude (> 0 && < 1), output the current hertz value.
    You can use this for an alternative HERTZ asset!
    """
    hz_reference_timestamp = pendulum.parse(reference_timestamp).timestamp() # Retrieving the Bitshares2.0 genesis block timestamp
    hz_period = pendulum.SECONDS_PER_DAY * period_days
    hz_phase = pendulum.SECONDS_PER_DAY * phase_days
    hz_waveform = math.sin(((((current_timestamp - (hz_reference_timestamp + hz_phase))/hz_period) % 1) * hz_period) * ((2*math.pi)/hz_period)) # Only change for an alternative HERTZ ABA.
    hertz_value = reference_asset_value + ((amplitude * reference_asset_value) * hz_waveform)
    log.debug('Value of the HERTZ asset in BTS: {} BTS'.format(hertz_value))
    return hertz_value


def get_feed_prices_new(node):
    cfg = core.config['monitoring']['feeds']

    # 1- fetch all feeds
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
                log.exception(e)

    def mkt(market_pair):
        return tuple(market_pair.split('/'))

    # 2- apply rules

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

            #src_price = result.price(src, base)
            r = FeedPrice(result.price(src_asset, src_base), dest_asset, dest_base)
            result.append(r)

        else:
            raise ValueError('Invalid rule: {}'.format(rule))


    for rule, *args in cfg['rules']:
        try:
            execute_rule(rule, *args)

        except Exception as e:
            log.warning('Could not execute rule: {} {}'.format(rule, args))
            log.exception(e)

    return result


def get_feed_prices(node):
    result = get_feed_prices_new(node)
    feeds = {}
    for f in result.filter(base='BTS'):
        feeds[f.asset] = 1/f.price
    feeds['ALTCAP'] = 1/result.filter('ALTCAP', 'BTC')[0].price

    return feeds

def get_feed_prices_old(node):

    def active_providers_bts(providers):
        feed_providers = {p.lower() for p in cfg['bts']['feed_providers']}
        return {p for p in providers if p.NAME.lower() in feed_providers}

    def active_providers_steem(providers):
        feed_providers = {p.lower() for p in cfg['steem']['feed_providers']}
        return {p for p in providers if p.NAME.lower() in feed_providers}

    providers = core.get_plugin_dict('bts_tools.feed_providers')

    # 0- get forex data + gold/silved in USD
    currency_layer_prices = []
    try:
        currency_layer_prices = providers.CurrencyLayer.get(BASE_ASSETS - {'BTC', 'USD'}, 'USD')
    except Exception as e:
        log.debug('Could not get feeds from CurrencyLayer: {}'.format(e))

    fixer_prices = []
    try:
        fixer_prices = providers.Fixer.get_all(base='USD')
    except Exception as e:
        log.debug('Could not get feeds from fixer.io: {}'.format(e))

    gold_silver_prices = []
    try:
        gold_silver_prices += [providers.Quandl.get('GOLD', 'USD'),
                               providers.Quandl.get('SILVER', 'USD')]
    except Exception as e:
        log.debug('Could not get gold/silver feeds from Quandl: {}'.format(e))


    base_usd_price = FeedSet(currency_layer_prices + fixer_prices + gold_silver_prices + providers.Uphold.get_all())

    base_usd_price = base_usd_price.filter(base='USD')

    # 1- get the BitShares price in major markets: BTC, USD and CNY

    # 1.1- first get the bts/btc valuation
    providers_bts_btc = active_providers_bts({providers.Poloniex,
                                              providers.Bittrex,
                                              providers.Livecoin,
                                              providers.aex,
                                              providers.zb,
                                              providers.Binance})
    if not providers_bts_btc:
        log.warning('No feed providers for BTS/BTC feed price')
    all_feeds = get_multi_feeds('get', [('BTS', 'BTC')], providers_bts_btc)

    feeds_bts_btc = all_feeds.filter('BTS', 'BTC')

    if not feeds_bts_btc:
        # in last resort, just get our data from coinmarketcap and coincap
        log.info('getting bts/btc directly from coinmarketcap, no other sources available')
        feeds_bts_btc = FeedSet([providers.CoinMarketCap.get('BTS', 'BTC'),
                                 providers.CoinCap.get('BTS', 'BTC')])

    if not feeds_bts_btc:
        raise core.NoFeedData('Could not get any BTS/BTC feeds')

    btc_price = feeds_bts_btc.price()

    # 1.2- get the btc/usd (bitcoin avg)
    feeds_btc_usd = get_multi_feeds('get', [('BTC', 'USD')],
                                    active_providers_bts({providers.BitcoinAverage,
                                                          providers.CoinMarketCap,
                                                          providers.Bitfinex,
                                                          providers.Bitstamp}))  # coincap seems to be off sometimes, do not use it
    if not feeds_btc_usd:
        raise core.NoFeedData('Could not get any BTC/USD feeds')

    btc_usd = feeds_btc_usd.price()

    usd_price = btc_price * btc_usd

    # 1.3- get the bts/cny valuation directly from cny markets. Going from bts/btc and
    #      btc/cny to bts/cny introduces a slight difference (2-3%) that doesn't exist on
    #      the actual chinese markets

    # TODO: should go at the beginning: submit all fetching tasks to an event loop / threaded executor,
    # compute valuations once we have everything
    feeds_bts_cny = get_multi_feeds('get', [('BTS', 'CNY')],
                                    active_providers_bts({providers.Bter,
                                                          providers.BTC38,
                                                          providers.Yunbi}))
    if not feeds_bts_cny:
        # if we couldn't get the feeds for cny, go BTS->BTC, BTC->CNY
        log.debug('Could not get any BTS/CNY feeds, going BTS->BTC, BTC->CNY')
        bts_cny = btc_price * btc_usd / base_usd_price.price('CNY')

        # # if we couldn't get the feeds for cny, try picking up our last value
        # if price_history.get('cny'):
        #     log.warning('Could not get any BTS/CNY feeds, using last feed price')
        #     bts_cny = price_history['cny'][-1]
        # else:
        #     raise core.NoFeedData('Could not get any BTS/CNY feeds')
    else:
        bts_cny = feeds_bts_cny.price()

    cny_price = bts_cny

    feeds = {}  # TODO: do we really want to reset the global var 'feeds' everytime we come here?
    feeds['BTC'] = btc_price
    feeds['USD'] = usd_price
    feeds['CNY'] = cny_price

    feeds['HERO'] = usd_price / (1.05 ** ((pendulum.today() - pendulum.Pendulum(1913, 12, 23)).in_days() / 365.2425))

    log.debug('Got btc/usd price: {}'.format(btc_usd))
    log.debug('Got usd price: {}'.format(usd_price))
    log.debug('Got cny price: {}'.format(cny_price))

    # 2- now get the BitShares price in all other required currencies
    for asset in BASE_ASSETS - {'BTC', 'USD', 'CNY'}:
        try:
            feeds[asset] = usd_price / base_usd_price.price(asset, 'USD')
        except Exception:
            log.warning('no feed price for asset {}'.format(asset))


    # 2.1- RUBLE is used temporarily by RUDEX instead of bitRUB (black swan)
    #      see https://bitsharestalk.org/index.php/topic,24004.0/all.html
    feeds['RUBLE'] = feeds['RUB']

    # 3- get the feeds for major composite indices   # REMOVED, was using yahoo, GoogleFeedProvider, BloombergFeedProvider

    # 4- get other assets
    altcap = get_multi_feeds('get', [('ALTCAP', 'BTC')], {providers.CoinCap, providers.CoinMarketCap})
    altcap = altcap.price(stddev_tolerance=0.08)
    feeds['ALTCAP'] = altcap

    gridcoin = get_multi_feeds('get', [('GRIDCOIN', 'BTC')], {providers.Poloniex, providers.Bittrex})
    feeds['GRIDCOIN'] = btc_price / gridcoin.price(stddev_tolerance=0.1)

    steem_btc = get_multi_feeds('get', [('STEEM', 'BTC')], active_providers_steem({providers.Poloniex, providers.Bittrex}))
    steem_usd = steem_btc.price() * btc_usd
    feeds['STEEM'] = steem_usd

    golos_btc = get_multi_feeds('get', [('GOLOS', 'BTC')], active_providers_steem({providers.Bittrex, providers.Livecoin}))
    golos_bts = btc_price / golos_btc.price()
    feeds['GOLOS'] = golos_bts

    # 5- Bit20 asset
    if 'BTWTY' not in get_disabled_assets():
        try:
            bit20 = get_bit20_feed(node, usd_price)
            if bit20 is not None:
                feeds['BTWTY'] = bit20
        except core.NoFeedData as e:
            log.warning(e)

    # 6- HERTZ asset
    if 'HERTZ' not in get_disabled_assets():
        hertz_reference_timestamp = "2015-10-13T14:12:24+00:00" # Bitshares 2.0 genesis block timestamp
        hertz_current_timestamp = pendulum.now().timestamp() # Current timestamp for reference within the hertz script
        hertz_amplitude = 1/3 # 33.33..% fluctuation
        hertz_period_days = 28 # 30.43 days converted to an UNIX timestamp // TODO: Potentially change this value to 28
        hertz_phase_days = 0.908056 # Time offset from genesis till the first wednesday, to set wednesday as the primary Hz day.
        hertz_reference_asset_price = usd_price
        
        hertz = get_hertz_feed(hertz_reference_timestamp, hertz_current_timestamp, hertz_period_days, hertz_phase_days, hertz_reference_asset_price, hertz_amplitude)
        if hertz is not None:
            feeds['HERTZ'] = hertz

    # 7- update price history for all feeds
    for cur, price in feeds.items():
        price_history[cur].append(price)

    return feeds


def median_str(cur):
    try:
        return statistics.median(price_history[cur])
    except Exception:
        return 'N/A'


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


def get_price_for_publishing(node, median_feeds, asset, price):
    c = dict(cfg['bts']['asset_params']['default'])  # make a copy, we don't want to update the default value
    c.update(cfg['bts']['asset_params'].get(asset) or {})
    asset_id = node.asset_data(asset)['id']
    asset_precision = node.asset_data(asset)['precision']

    base = 'BTS'
    if asset == 'ALTCAP':
        base = 'BTC'
    base_id = node.asset_data(base)['id']
    base_precision = node.asset_data(base_id)['precision']
    bts_precision = node.asset_data('BTS')['precision']

    numerator, denominator = get_fraction(price, asset_precision, base_precision)

    # CER price needs to be priced in BTS always. Get conversion rate
    # from the base currency to BTS, and use it to scale the CER price

    if base != 'BTS':
        base_bts_price = median_feeds[base]
        cer_numerator, cer_denominator = get_fraction(price * base_bts_price,
                                                      asset_precision, bts_precision)
        cer_denominator *= c['core_exchange_factor']
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
    # log.debug('Publishing feed for {}/{}: {} as {}/{} - CER: {}/{}'
    #          .format(asset, base, price, numerator, denominator, cer_numerator, cer_denominator))
    return price_obj


def get_disabled_assets():
    cfg_enabled = set(cfg['bts'].get('enabled_assets', []))
    cfg_disabled = set(cfg['bts'].get('disabled_assets', []))
    for asset in cfg_enabled:
        if asset in cfg_disabled:
            log.warning("Asset {} is both in 'enabled_assets' and 'disabled_assets'. Disabling it".format(asset))

    # Steem is disabled as it appears in the feed history but should not be published on BitShares
    # NOTE: the proper fix would be to maintain feeds per client type, and not as a global object
    disabled_assets = {'STEEM'}

    # these are not published by default as they are experimental or have some requirements
    # eg: need to be an approved witness to publish
    disabled_assets.update({'BTWTY', 'RUBLE', 'ALTCAP', 'HERO', 'HERTZ'})

    # enable plugins in cfg
    disabled_assets.difference_update(cfg_enabled)

    # disable plugins in cfg
    disabled_assets.update(cfg_disabled)

    return disabled_assets


# TODO: Need 2 main classes: FeedHistory is a database of historical prices, allows querying,
#       and FeedControl is a strategy for deciding when to publish

class BitSharesFeedControl(object):
    def __init__(self, *, cfg, visible_feeds=DEFAULT_VISIBLE_FEEDS):
        self.cfg = dict(cfg)
        self.visible_feeds = list(visible_feeds)

        # FIXME: deprecate self.feed_period
        try:
            self.feed_period = int(cfg['bts']['publish_time_interval'] / cfg['check_time_interval'])
        except KeyError:
            self.feed_period = None

        self.check_time_interval = pendulum.interval(seconds=cfg.get('check_time_interval', 600))
        self.publish_time_interval = None
        if 'publish_time_interval' in cfg['bts']:
            self.publish_time_interval = pendulum.interval(seconds=cfg['bts']['publish_time_interval'])

        self.feed_slot = cfg['bts'].get('publish_time_slot', None)
        if self.feed_slot is not None:
            self.feed_slot = int(self.feed_slot)

        self.nfeed_checked = 0
        self.last_published = pendulum.utcnow().subtract(days=1)

    def format_feeds(self, feeds):
        display_feeds = []
        for c in set(self.visible_feeds) | set(feeds.keys()):
            if c not in feeds:
                log.debug('No feed price available for {}, cannot display it'.format(c))
            else:
                display_feeds.append(c)
        display_feeds = list(sorted(feeds))

        fmt = ', '.join('%s %s' % (format_qualifier(c), c) for c in display_feeds)
        msg = fmt % tuple(feeds[c] for c in display_feeds)
        return msg

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
            log.debug('Should publish because time interval has passed: {} seconds'.format(cfg['bts']['publish_time_interval']))
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

        # check_time_interval_minutes = cfg['check_time_interval'] // 60 + 1
        # if self.feed_slot is not None:
        #     start_slot = self.feed_slot
        #     end_slot = self.feed_slot + check_time_interval_minutes
        #     if (((start_slot <= now.minute <= end_slot) or
        #          (end_slot >= 60 and now.minute <= end_slot % 60)) and
        #         now - self.last_published > timedelta(minutes=max(3*check_time_interval_minutes, 50))):
        #
        #         log.debug('Should publish because time slot has arrived: time {:02d}:{:02d} - target'.format(now.hour, now.minute))
        #         return True

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

        if pendulum.utcnow() - node.opts['last_published'] > last_published_interval:
            log.debug('Steem should publish as it has not been published for {}'.format(last_published_interval))
            return True
        if abs(price - node.opts['last_price']) / node.opts['last_price'] >= variance_trigger:
            log.debug('Steem should publish as price has moved more than {}%'.format(100*variance_trigger))
            return True
        log.debug('No need for Steem to publish')
        return False


def check_feeds(nodes):
    # need to:
    # 1- get all feeds from all feed providers (FP) at once. Only use FP designated as active
    # 2- compute price from the FeedSet using adequate strategy. FP can (should) be weighted
    #    (eg: BitcoinAverage: 4, BitFinex: 1, etc.) if no volume is present
    # 3- order of computation should be clearly defined and documented, or configurable in the yaml file (preferable)
    #
    # details:
    #
    # 1-
    # - for each asset, get the list of authorized and authenticated feed providers able to give a feed for it
    # - for each feed provider, get the list of required assets
    # - execute in parallel all requests and gather the results in a FeedSet

    global feeds, feed_control

    try:
        feeds = get_feed_prices(nodes[0]) # use first node if we need to query the blockchain, eg: for bit20 asset composition
        feed_control.nfeed_checked += 1

        status = feed_control.publish_status(feeds)
        log.debug('Got feeds on {}: {}'.format(nodes[0].type(), status))

        for node in nodes:
            if node.role != 'feed_publisher':
                continue

            # TODO: dealt with as an exceptional case for now, should be refactored
            if node.type() == 'steem':
                price = statistics.median(price_history['STEEM'])

                # publish median value of the price, not latest one
                if feed_control.should_publish_steem(node, price):
                    if not node.is_online():
                        log.warning('Cannot publish feeds for steem witness %s: client is not running' % node.name)
                        continue
                    if node.is_locked():
                        log.warning('Cannot publish feeds for steem witness %s: wallet is locked' % node.name)
                        continue

                    ratio = cfg['steem']['steem_dollar_adjustment']
                    price_obj = {'base': '{:.3f} SBD'.format(price),
                                 'quote': '{:.3f} STEEM'.format(1/ratio)}
                    log.info('Node {}:{} publishing feed price for steem: {:.3f} SBD (real: {:.3f} adjusted by {:.2f})'
                             .format(node.type(), node.name, price*ratio, price, ratio))
                    node.publish_feed(node.name, price_obj, True)
                    node.opts['last_price'] = price
                    node.opts['last_published'] = pendulum.utcnow()

                continue


            # if an exception occurs during publishing feeds for a delegate (eg: standby delegate),
            # then we should still go on for the other nodes (and not let exceptions propagate)
            try:
                if feed_control.should_publish():
                    base_error_msg = 'Cannot publish feeds for {} witness {}: '.format(node.type(), node.name)
                    if not node.is_online():
                        log.warning(base_error_msg + 'client is not running')
                        continue
                    if node.is_locked():
                        log.warning(base_error_msg + 'wallet is locked')
                        continue
                    if not node.is_synced():
                        log.warning(base_error_msg + 'client is not synced')
                        continue

                    base_msg = '{} witness {} feeds: '.format(node.type(), node.name)
                    # publish median value of the price, not latest one
                    median_feeds = {c: statistics.median(price_history[c]) for c in feeds}
                    disabled_assets = get_disabled_assets()
                    publish_feeds = {asset: price for asset, price in median_feeds.items() if asset not in disabled_assets}
                    log.info(base_msg + 'publishing feeds: {}'.format(feed_control.format_feeds(publish_feeds)))
                    log.debug(base_msg + 'not publishing: {}'.format(disabled_assets))

                    # first, try to publish all of them in a single transaction
                    try:
                        published = []
                        handle = node.begin_builder_transaction()
                        for asset, price in publish_feeds.items():
                            published.append(asset)
                            op = [19,  # id 19 corresponds to price feed update operation
                                  hashabledict({"asset_id": node.asset_data(asset)['id'],
                                                "feed": get_price_for_publishing(node, publish_feeds, asset, price),
                                                "publisher": node.get_account(node.name)["id"]})
                                  ]
                            node.add_operation_to_builder_transaction(handle, op)

                        # set fee
                        node.set_fees_on_builder_transaction(handle, '1.3.0')

                        # sign and broadcast
                        node.sign_builder_transaction(handle, True)
                        log.debug(base_msg + 'successfully published feeds for {}'.format(', '.join(published)))


                    except Exception as e:
                        log.warning(base_msg + 'tried to publish all feeds in a single transaction, but failed. '
                                               'Will try to publish each feed separately now')
                        msg_len = 400
                        log.debug(str(e)[:msg_len] + (' [...]' if len(str(e)) > msg_len else ''))

                        # if an error happened, publish feeds individually to make sure that
                        # at least the ones that work can get published
                        published = []
                        for asset, price in publish_feeds.items():
                            try:
                                price = hashabledict(get_price_for_publishing(node, publish_feeds, asset, price))
                                log.debug(base_msg + 'Publishing {} {}'.format(asset, price))
                                node.publish_asset_feed(node.name, asset, price, True)  # True: sign+broadcast
                                published.append(asset)
                            except Exception as e:
                                #log.exception(e)
                                log.warning(base_msg + 'Failed to publish feed for asset {}'.format(asset))
                                log.debug(str(e)[:msg_len] + ' [...]')

                        log.debug(base_msg + 'successfully published feeds for {}'.format(', '.join(published)))

                    #last_published = datetime.utcnow()
                    feed_control.last_published = pendulum.utcnow()

            except Exception as e:
                log.exception(e)

    except core.NoFeedData as e:
        log.warning(e)

    except Exception as e:
        log.exception(e)

    threading.Timer(cfg['check_time_interval'], check_feeds, args=(nodes,)).start()
