#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
# Copyright (c) 2015 Nicolas Wack <wackou@gmail.com>
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
from bs4 import BeautifulSoup
from datetime import datetime
from retrying import retry
from requests.exceptions import Timeout
import json
import arrow
import requests
import statistics
import functools
import logging

log = logging.getLogger('bts_tools.feeds')


class FeedPrice(object):
    """Represent a feed price value. Contains additional metadata such as volume, etc.

    volume should be represented as number of <asset> units, not <base>."""
    def __init__(self, price, asset, base, volume=None, last_updated=None, provider=None):
        self.price = price
        self.asset = asset
        self.base = base
        self.volume = volume
        self.last_updated = last_updated or datetime.utcnow()
        self.provider = provider

    def __str__(self):
        return 'FeedPrice: {} {}/{}{}{}'.format(
            self.price, self.asset, self.base,
            ' - vol={}'.format(self.volume) if self.volume is not None else '',
            ' from {}'.format(self.provider) if self.provider else '')

    def __repr__(self):
        return '<{}>'.format(str(self))


class FeedSet(list):
    # NOTE: use list for now and not set because we're not sure what to hash or use for __eq__

    def filter(self, asset, base):
        """Returns a new FeedSet containing only the feed prices about the given market"""
        return FeedSet([f for f in self if f.asset == asset and f.base == base])

    def _price(self):
        if len(self) == 0:
            raise ValueError('FeedSet is empty, can\'t get value...')
        if len(self) > 1:
            raise ValueError('FeedSet contains more than one feed. Please use self.weighted_mean() to compute the value')

        return self[0].price

    def price(self, asset=None, base=None, stddev_tolerance=None):
        """Automatically compute the price of an asset using all relevant data in this FeedSet"""
        if len(self) == 0:
            raise ValueError('FeedSet is empty, can\'t compute price...')
        asset = asset or self[0].asset
        base = base or self[0].base
        prices = self.filter(asset, base)
        return prices.weighted_mean(stddev_tolerance=stddev_tolerance)

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
        if any(f.volume is None for f in self):
            log.debug('No volume defined for at least one feed: {}, using simple mean'.format(self))
            total_volume = len(self)
        else:
            total_volume = sum(f.volume for f in self)

        weighted_mean = sum(f.price * (f.volume or 1) for f in self) / total_volume

        log.debug('Weighted mean for {}/{}: {:.6g}'.format(asset, base, weighted_mean))
        log.debug('Exchange      Price          Volume          Contribution')
        for f in self:
            percent = 100 * (f.volume or 1) / total_volume
            log.debug('{:14s} {:12.4g} {:14.2f} {:14.2f}%'.format(f.provider, f.price, (f.volume or 1), percent))

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


def check_online_status(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            result = f(self, *args, **kwargs)
            if FeedProvider.PROVIDER_STATES.get(self.NAME) != 'online':
                log.info('Feed provider %s came online' % self.NAME)
                FeedProvider.PROVIDER_STATES[self.NAME] = 'online'
            return result

        except Exception as e:
            if FeedProvider.PROVIDER_STATES.get(self.NAME) != 'offline':
                log.warning('Feed provider %s went offline (%s)' % (self.NAME, e.__class__.__name__))
                FeedProvider.PROVIDER_STATES[self.NAME] = 'offline'
            raise
    return wrapper


def check_market(f):
    @functools.wraps(f)
    def wrapper(self, cur, base):
        if (cur, base) not in self.AVAILABLE_MARKETS:
            msg = '{} does not provide feeds for market {}/{}'.format(self.NAME, cur, base)
            log.warning(msg)
            raise core.NoFeedData(msg)
        return f(self, cur, base)
    return wrapper


def reuse_last_value_on_fail(f):
    @functools.wraps(f)
    def wrapper(self, cur, base):
        MAX_FAILS = 5
        f.last_value = getattr(f, 'last_value', {})
        f.n_consecutive_fails = getattr(f, 'n_consecutive_fails', 0)
        try:
            result = f(self, cur, base)
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

# TODO: make use of this: https://pymotw.com/3/abc/index.html
class FeedProvider(object):
    """need to implement a get(asset, base) method. It returns price and volume.
    The volume is expressed in <asset> units."""
    NAME = 'base FeedProvider'
    AVAILABLE_MARKETS = []  # redefine in derived classes, used by @check_market decorator
    PROVIDER_STATES = {}
    _ASSET_MAP = {}
    TIMEOUT = 60

    def __init__(self):
        self.state = 'offline'

    def __hash__(self):
        return hash(self.NAME)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def feed_price(self, cur, base, price, volume=None, last_updated=None):
        return FeedPrice(price, cur, base, volume, last_updated, provider=self.NAME)

    @classmethod
    def to_bts(cls, c):
        c = c.upper()
        for b, y in cls._ASSET_MAP.items():
            if c == y:
                return b
        return c

    @classmethod
    def from_bts(cls, c):
        c = c.upper()
        return cls._ASSET_MAP.get(c, c)


class YahooFeedProvider(FeedProvider):
    NAME = 'Yahoo'
    _YQL_URL = 'http://query.yahooapis.com/v1/public/yql'
    _ASSET_MAP = {'GOLD': 'XAU',
                  'SILVER': 'XAG',
                  'SHENZHEN': '399106.SZ',
                  'SHANGHAI': '000001.SS',
                  'NIKKEI': '^N225',
                  'NASDAQC': '^IXIC',
                  'HANGSENG': '^HSI'}

    @check_online_status
    def query_yql(self, query):
        r = requests.get(self._YQL_URL,
                         params=dict(q = query,
                                     env = 'http://datatables.org/alltables.env',
                                     format='json')).json()
        try:
            return r['query']['results']['quote']
        except KeyError:
            return r

    def query_quote_full(self, q):
        log.debug('checking quote for %s at %s' % (q, self.NAME))
        r = self.query_yql('select * from yahoo.finance.quotes where symbol in ("{}")'.format(self.from_bts(q)))
        return r

    def query_quote(self, q, base_currency=None):
        # Yahoo seems to have a bug on Shanghai index, use another way
        if q == 'SHANGHAI':
            log.debug('checking quote for %s at Yahoo' % q)
            r = requests.get('http://finance.yahoo.com/q?s=000001.SS')
            soup = BeautifulSoup(r.text, 'html.parser')
            r = float(soup.find('span', 'time_rtq_ticker').text.replace(',', ''))
        else:
            r = float(self.query_quote_full(q)['LastTradePriceOnly'])
        return self.feed_price(q, base_currency, r)

    @check_online_status
    def get(self, asset_list, base):
        log.debug('checking feeds for %s / %s at Yahoo' % (' '.join(asset_list), base))
        asset_list = [self.from_bts(asset) for asset in asset_list]
        base = base.upper()
        query_string = ','.join('%s%s=X' % (asset, base) for asset in asset_list)
        r = requests.get('http://download.finance.yahoo.com/d/quotes.csv',
                         timeout=self.TIMEOUT,
                         params={'s': query_string, 'f': 'l1', 'e': 'csv'})
        log.debug('Received from yahoo: {}'.format(repr(r.text)))

        try:
            asset_prices = list(map(float, r.text.split()))
        except Exception as e:
            log.warning('Could not parse feeds from yahoo, response: {}'.format(r.text))
            raise core.NoFeedData from e

        if 'XAU' in asset_list:
            # get correct price for gold from yahoo. see: https://bitsharestalk.org/index.php/topic,23614.0/all.html
            r = requests.get('http://download.finance.yahoo.com/d/quotes.csv?s=GC=F&f=l1&e=.csv')
            idx = asset_list.index('XAU')
            asset_prices[idx] = float(r.text)

        return dict(zip((self.to_bts(asset) for asset in asset_list), asset_prices))


class GoogleFeedProvider(FeedProvider):
    NAME = 'Google'
    _GOOGLE_URL = 'https://www.google.com/finance'
    _ASSET_MAP = {'SHENZHEN': 'SHE:399106',
                  'SHANGHAI': 'SHA:000001',
                  'NIKKEI': 'NI225',
                  'NASDAQC': '.IXIC',
                  'HANGSENG': 'HSI'}

    @check_online_status
    def query_quote(self, q, base_currency=None):
        log.debug('checking quote for %s at %s' % (q, self.NAME))
        r = requests.get(self._GOOGLE_URL, params=dict(q=self.from_bts(q)))
        soup = BeautifulSoup(r.text, 'html.parser')
        r = float(soup.find(id='price-panel').find(class_='pr').text.replace(',', ''))
        return self.feed_price(q, base_currency, r)


class BloombergFeedProvider(FeedProvider):
    NAME = 'Bloomberg'
    _BLOOMBERG_URL = 'http://www.bloomberg.com/quote/{}'
    _ASSET_MAP = {'SHENZHEN': 'SZCOMP:IND',
                  'SHANGHAI': 'SHCOMP:IND',
                  'NIKKEI': 'NKY:IND',
                  'NASDAQC': 'CCMP:IND',
                  'HANGSENG': 'HSI:IND'}

    @check_online_status
    def query_quote(self, q, base_currency=None):
        log.debug('checking quote for %s at %s' % (q, self.NAME))
        r = requests.get(self._BLOOMBERG_URL.format(self.from_bts(q)))
        soup = BeautifulSoup(r.text, 'html.parser')
        r = float(soup.find(class_='price').text.replace(',', ''))
        return self.feed_price(q, base_currency, r)


class BitcoinAverageFeedProvider(FeedProvider):
    NAME = 'BitcoinAverage'
    AVAILABLE_MARKETS = [('BTC', 'USD')]

    @check_online_status
    @check_market
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        r = requests.get('https://api.bitcoinaverage.com/ticker/{}'.format(base),
                         timeout=self.TIMEOUT).json()
        return self.feed_price(cur, base, float(r['last']), float(r['total_vol']))


class BitfinexFeedProvider(FeedProvider):
    NAME = 'Bitfinex'
    AVAILABLE_MARKETS = [('BTC', 'USD')]

    @check_online_status
    @check_market
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        r = requests.get('https://api.bitfinex.com/v1/pubticker/{}{}'.format(cur.lower(), base.lower()),
                         timeout=self.TIMEOUT).json()
        return self.feed_price(cur, base, float(r['last_price']), float(r['volume']))


class BitstampFeedProvider(FeedProvider):
    NAME = 'Bitstamp'
    AVAILABLE_MARKETS = [('BTC', 'USD')]

    @check_online_status
    @check_market
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        r = requests.get('https://www.bitstamp.net/api/ticker/',
                         timeout=self.TIMEOUT).json()
        return self.feed_price(cur, base, float(r['last']), float(r['volume']))


class PoloniexFeedProvider(FeedProvider):
    NAME = 'Poloniex'
    AVAILABLE_MARKETS = [('BTS', 'BTC'), ('STEEM', 'BTC'), ('GRIDCOIN', 'BTC')]
    _ASSET_MAP = {'GRIDCOIN': 'GRC'}

    @check_online_status
    @check_market
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        r = requests.get('https://poloniex.com/public?command=returnTicker',
                         timeout=self.TIMEOUT).json()
        r = r['{}_{}'.format(base, self.from_bts(cur))]
        return self.feed_price(cur, base,
                               price=float(r['last']),
                               volume=float(r['quoteVolume']))


class BterFeedProvider(FeedProvider):
    NAME = 'Bter'
    AVAILABLE_MARKETS = [('BTS', 'BTC'), ('BTS', 'CNY'), ('BTC', 'CNY')]

    @check_online_status
    @check_market
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        r = requests.get('http://data.bter.com/api/1/ticker/%s_%s' % (cur.lower(), base.lower()),
                         timeout=self.TIMEOUT).json()
        return self.feed_price(cur, base,
                               price=float(r['last']) or ((float(r['sell']) + float(r['buy'])) / 2),
                               volume=float(r['vol_%s' % cur.lower()]))


class Btc38FeedProvider(FeedProvider):
    NAME = 'Btc38'
    AVAILABLE_MARKETS = [('BTS', 'BTC'), ('BTS', 'CNY'), ('BTC', 'CNY')]

    @check_online_status
    @reuse_last_value_on_fail
    @retry(retry_on_exception=lambda e: isinstance(e, requests.exceptions.Timeout),
           wait_exponential_multiplier=5000,
           stop_max_attempt_number=3)
    @check_market
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        headers = {'content-type': 'application/json',
                   'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:22.0) Gecko/20100101 Firefox/22.0'}
        r = requests.get('http://api.btc38.com/v1/ticker.php',
                         timeout=10,
                         params={'c': cur.lower(), 'mk_type': base.lower()},
                         headers=headers)
        try:
            # see: http://stackoverflow.com/questions/24703060/issues-reading-json-from-txt-file
            r.encoding = 'utf-8-sig'
            r = r.json()
        except ValueError:
            log.error('Could not decode response from btc38: %s' % r.text)
            raise
        return self.feed_price(cur, base,
                               price=float(r['ticker']['last']), # TODO: (bid + ask) / 2 ?
                               volume=float(r['ticker']['vol']))


class YunbiFeedProvider(FeedProvider):
    NAME = 'Yunbi'
    AVAILABLE_MARKETS = [('BTS', 'BTC'), ('BTS', 'CNY'), ('BTC', 'CNY')]

    @check_online_status
    @reuse_last_value_on_fail
    @retry(retry_on_exception=lambda e: isinstance(e, requests.exceptions.Timeout),
           wait_exponential_multiplier=5000,
           stop_max_attempt_number=3)
    @check_market
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        headers = {'content-type': 'application/json',
                   'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:22.0) Gecko/20100101 Firefox/22.0'}
        r = requests.get('https://yunbi.com/api/v2/tickers.json',
                         timeout=10,
                         headers=headers).json()
        #log.debug('received: {}'.format(json.dumps(r, indent=4)))
        r = r['{}{}'.format(cur.lower(), base.lower())]
        return self.feed_price(cur, base,
                               price=float(r['ticker']['last']),
                               volume=float(r['ticker']['vol']),
                               last_updated=datetime.utcfromtimestamp(r['at']))


class CoinCapFeedProvider(FeedProvider):
    NAME = 'CoinCap'
    AVAILABLE_MARKETS = [('ALTCAP', 'BTC')]

    @check_online_status
    @check_market
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        r = requests.get('http://www.coincap.io/global', timeout=self.TIMEOUT).json()

        btc_cap = float(r['btcCap'])
        alt_cap = float(r['altCap'])
        price = btc_cap / alt_cap

        #log.debug('{} - btc: {}'.format(self.NAME, btc_cap))
        #log.debug('{} - total: {}'.format(self.NAME, btc_cap + alt_cap))
        #log.debug('{} - alt: {}'.format(self.NAME, alt_cap))
        log.debug('{} - ALTCAP price: {}'.format(self.NAME, price))

        return self.feed_price(cur, base, price=price)


    def get_all(self):
        feeds = requests.get('http://www.coincap.io/front').json()
        result = FeedSet()
        for f in feeds:
            result.append(self.feed_price(f['short'], 'USD', price=float(f['price']),
                                          volume=float(f['usdVolume']),
                                          last_updated=arrow.get(f['time']/1000)))
        return result


class CoinMarketCapFeedProvider(FeedProvider):
    NAME = 'CoinMarketCap'
    AVAILABLE_MARKETS = [('ALTCAP', 'BTC')]

    @check_online_status
    @check_market
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        r = requests.get('https://api.coinmarketcap.com/v1/global/').json()
        btc_cap = r['bitcoin_percentage_of_market_cap']
        alt_cap = 100 - btc_cap
        price = btc_cap / alt_cap

        #log.debug('{} - btc: {}'.format(self.NAME, btc_cap))
        #log.debug('{} - alt: {}'.format(self.NAME, alt_cap))
        log.debug('{} - ALTCAP price: {}'.format(self.NAME, price))

        return self.feed_price(cur, base, price=price)

    def get_all(self):
        feeds = requests.get('https://api.coinmarketcap.com/v1/ticker/').json()
        result = FeedSet()
        for f in feeds:
            try:
                result.append(self.feed_price(f['symbol'], 'USD', price=float(f['price_usd']),
                                              volume=float(f['24h_volume_usd']) if f['24h_volume_usd'] else None,
                                              last_updated=arrow.get(f['last_updated'])))
            except TypeError:
                # catches: TypeError: float() argument must be a string or a number, not 'NoneType'
                # on: f['price_usd']
                #log.debug('Could not get USD price for feed: {}'.format(json.dumps(f, indent=4)))
                pass
        return result


class BittrexFeedProvider(FeedProvider):
    NAME = 'Bittrex'
    AVAILABLE_MARKETS = [('BTS', 'BTC'), ('STEEM', 'BTC'), ('GRIDCOIN', 'BTC')]
    _ASSET_MAP = {'GRIDCOIN': 'GRC'}

    @check_online_status
    @check_market
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        r = requests.get('https://bittrex.com/api/v1.1/public/getmarketsummary?market={}-{}'.format(base, self.from_bts(cur)),
                         timeout=self.TIMEOUT).json()

        summary = r['result'][0]
        #log.debug('Got feed price for {}: {} (from bittrex)'.format(cur, summary['Last']))
        return self.feed_price(cur, base,
                               price=summary['Last'],
                               volume=summary['Volume'],
                               last_updated=datetime.strptime(summary['TimeStamp'].split('.')[0], '%Y-%m-%dT%H:%M:%S'))


_suffix = 'FeedProvider'
ALL_FEED_PROVIDERS = {name[:-len(_suffix)].lower(): cls
                      for (name, cls) in globals().items()
                      if name.endswith(_suffix)}

del ALL_FEED_PROVIDERS['']  # remove base FeedProvider class
