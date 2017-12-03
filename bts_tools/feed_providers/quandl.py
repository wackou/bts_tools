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

from . import FeedPrice, check_online_status, cachedmodulefunc, check_market
from cachetools import TTLCache
import pendulum
import requests
import logging

log = logging.getLogger(__name__)


NAME = 'Quandl'

AVAILABLE_MARKETS = [('GOLD', 'USD'), ('SILVER', 'USD')]

DATASETS = {('GOLD', 'USD'): ['WGC/GOLD_DAILY_USD', 'LBMA/GOLD', 'PERTH/GOLD_USD_D'],
            ('SILVER', 'USD'): ['LBMA/SILVER', 'PERTH/SLVR_USD_D']}

# TTL = 12 hours, updated daily only
_cache = TTLCache(maxsize=8192, ttl=43200)

TIMEOUT = 60

@check_online_status
@cachedmodulefunc
@check_market
def get(cur, base):
    log.debug('checking feeds for %s/%s at %s' % (cur, base, NAME))

    prices = []
    for dataset in DATASETS[(cur, base)]:
        url = 'https://www.quandl.com/api/v3/datasets/{dataset}.json?start_date={date}'.format(
            dataset=dataset,
            date=(pendulum.utcnow() - pendulum.interval(days=3)).strftime('%Y-%m-%d')
        )
        data = requests.get(url=url, timeout=TIMEOUT).json()
        if 'dataset' not in data:
            raise RuntimeError('Quandl: no dataset found for url: %s' % url)
        d = data['dataset']
        if len(d['data']):
            prices.append(d['data'][0][1])

    return FeedPrice(sum(prices) / len(prices), cur, base)

