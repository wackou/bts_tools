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
import requests
import functools
import logging

log = logging.getLogger('bts_tools.feeds')


def check_online_status(f):
    @functools.wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            result = f(self, *args, **kwargs)
        except Exception:
            if FeedProvider.PROVIDER_STATES.get(self.NAME) != 'offline':
                log.warning('Feed provider %s went offline' % self.NAME)
                FeedProvider.PROVIDER_STATES[self.NAME] = 'offline'
            raise
        else:
            if FeedProvider.PROVIDER_STATES.get(self.NAME) != 'online':
                log.info('Feed provider %s came online' % self.NAME)
                FeedProvider.PROVIDER_STATES[self.NAME] = 'online'
        return result
    return wrapper


class FeedProvider(object):
    NAME = 'base FeedProvider'
    PROVIDER_STATES = {}
    _ASSET_MAP = {}

    def __init__(self):
        self.state = 'offline'

    def __hash__(self):
        return hash(self.NAME)

    def __eq__(self, other):
        return hash(self) == hash(other)

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


class YahooProvider(FeedProvider):
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
            soup = BeautifulSoup(r.text)
            r = float(soup.find('span', 'time_rtq_ticker').text.replace(',', ''))
        else:
            r = float(self.query_quote_full(q)['LastTradePriceOnly'])
        return r

    @check_online_status
    def get(self, asset_list, base):
        log.debug('checking feeds for %s / %s at Yahoo' % (' '.join(asset_list), base))
        asset_list = [self.from_bts(asset) for asset in asset_list]
        base = base.upper()
        query_string = ','.join('%s%s=X' % (asset, base) for asset in asset_list)
        r = requests.get('http://download.finance.yahoo.com/d/quotes.csv',
                         timeout=60,
                         params={'s': query_string, 'f': 'l1', 'e': 'csv'})

        try:
            asset_prices = map(float, r.text.split())
        except Exception as e:
            log.warning('Could not parse feeds from yahoo, response: {}'.format(r.text))
            raise core.NoFeedData from e
        return dict(zip((self.to_bts(asset) for asset in asset_list), asset_prices))


class GoogleProvider(FeedProvider):
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
        r = requests.get(GoogleProvider._GOOGLE_URL, params=dict(q=self.from_bts(q)))
        soup = BeautifulSoup(r.text)
        r = float(soup.find(id='price-panel').find(class_='pr').text.replace(',', ''))
        return r


class BloombergProvider(FeedProvider):
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
        r = requests.get(BloombergProvider._BLOOMBERG_URL.format(self.from_bts(q)))
        soup = BeautifulSoup(r.text)
        r = float(soup.find(class_='price').text.replace(',', ''))
        return r


class PoloniexFeedProvider(FeedProvider):
    NAME = 'Poloniex'

    @check_online_status
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        r = requests.get('https://poloniex.com/public?command=returnTicker',
                         timeout=60).json()
        r = r['BTC_BTS']
        price = float(r['last'])
        volume = float(r['quoteVolume'])
        return price, volume


class BterFeedProvider(FeedProvider):
    NAME = 'Bter'

    @check_online_status
    def get(self, cur, base):
        log.debug('checking feeds for %s/%s at %s' % (cur, base, self.NAME))
        r = requests.get('http://data.bter.com/api/1/ticker/%s_%s' % (cur.lower(), base.lower()),
                         timeout=60).json()
        price = float(r['last']) or ((float(r['sell']) + float(r['buy'])) / 2)
        volume = float(r['vol_%s' % cur.lower()])
        return price, volume


class Btc38FeedProvider(FeedProvider):
    NAME = 'Btc38'

    @check_online_status
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
        price = float(r['ticker']['last']) # TODO: (bid + ask) / 2 ?
        volume = float(r['ticker']['vol'])
        return price, volume


ALL_FEED_PROVIDERS = {'yahoo': YahooProvider,
                      'bter': BterFeedProvider,
                      'btc38': Btc38FeedProvider,
                      'poloniex': PoloniexFeedProvider,
                      'google': GoogleProvider,
                      'bloomberg': BloombergProvider
                      }
