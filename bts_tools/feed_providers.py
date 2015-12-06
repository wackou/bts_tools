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
import json
import requests
import functools
import logging

log = logging.getLogger('bts_tools.feeds')


def check_online_status(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            result = f(self, *args, **kwargs)
        except Exception as e:
            if FeedProvider.PROVIDER_STATES.get(self.NAME) != 'offline':
                log.warning('Feed provider %s went offline (%s)' % (self.NAME, e.__class__.__name__))
                FeedProvider.PROVIDER_STATES[self.NAME] = 'offline'
            raise
        else:
            if FeedProvider.PROVIDER_STATES.get(self.NAME) != 'online':
                log.info('Feed provider %s came online' % self.NAME)
                FeedProvider.PROVIDER_STATES[self.NAME] = 'online'
        return result
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


class FeedProvider(object):
    """need to implement a get(cur, base) method. It returns price and volume.
    The volume is expressed in <cur> units."""
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
        return core.FeedPrice(price, cur, base, volume, last_updated, provider=self.NAME)

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

        try:
            asset_prices = map(float, r.text.split())
        except Exception as e:
            log.warning('Could not parse feeds from yahoo, response: {}'.format(r.text))
            raise core.NoFeedData from e
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
    AVAILABLE_MARKETS = [('BTS', 'BTC')]

    @check_online_status
    @check_market
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        r = requests.get('https://poloniex.com/public?command=returnTicker',
                         timeout=self.TIMEOUT).json()
        r = r['{}_{}'.format(base, cur)]
        return self.feed_price(cur, base,
                               price=float(r['last']),
                               volume=float(r['quoteVolume']))


class CCEDKFeedProvider(FeedProvider):
    NAME = 'CCEDK'
    MARKET_IDS = {('BTS', 'BTC'): 50,
                  ('BTS', 'USD'): 55,
                  ('BTS', 'CNY'): 123,
                  ('BTS', 'EUR'): 54}
    AVAILABLE_MARKETS = list(MARKET_IDS.keys())

    @check_online_status
    @check_market
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        r = requests.get('https://www.ccedk.com/api/v1/stats/marketdepthfull?pair_id=%d' % self.MARKET_IDS[(cur, base)],
                         timeout=self.TIMEOUT)
        r = r.json()['response']['entity']
        return self.feed_price(cur, base,
                               price=float(r['last_price']),
                               volume=float(r['vol']))


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
    @check_market
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        headers = {'content-type': 'application/json',
                   'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:22.0) Gecko/20100101 Firefox/22.0'}
        r = requests.get('https://yunbi.com/api/v2/tickers.json',
                         timeout=10,
                         headers=headers).json()
        r = r['{}{}'.format(cur.lower(), base.lower())]
        return self.feed_price(cur, base,
                               price=float(r['ticker']['last']),
                               volume=float(r['ticker']['vol']),
                               last_updated=datetime.utcfromtimestamp(r['at']))

_suffix = 'FeedProvider'
ALL_FEED_PROVIDERS = {name[:-len(_suffix)].lower(): cls
                      for (name, cls) in globals().items()
                      if name.endswith(_suffix)}

del ALL_FEED_PROVIDERS['']  # remove base FeedProvider class
