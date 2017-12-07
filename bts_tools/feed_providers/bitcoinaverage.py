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

from . import FeedPrice, check_online_status, check_market, cachedmodulefunc
from .. import core
from bitcoinaverage import RestfulClient
from cachetools import TTLCache
import pendulum
import logging

log = logging.getLogger(__name__)

NAME = 'BitcoinAverage'

AVAILABLE_MARKETS = [('BTC', 'USD')]

_cache = TTLCache(maxsize=8192, ttl=1200)  # 20 minutes should work for the free plan, developer plan can get rid of the cache if wanted


@check_online_status
@cachedmodulefunc
@check_market
def get(cur, base):
    log.debug('checking feeds for %s/%s at %s' % (cur, base, NAME))


    try:
        secret_key = core.config['credentials']['bitcoinaverage']['secret_key']
        public_key = core.config['credentials']['bitcoinaverage']['public_key']
    except KeyError:
        raise KeyError('config.yaml does not specify both "credentials.bitcoinaverage.secret_key" and '
                       '"credentials.bitcoinaverage.public_key" variables')


    client = RestfulClient(secret_key=secret_key, public_key=public_key)
    r = client.ticker_short_local()[cur + base]

    return FeedPrice(float(r['last']), cur, base,
                     last_updated=pendulum.from_timestamp(r['timestamp']),
                     provider=NAME)
