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

from . import FeedPrice, check_online_status, cachedmodulefunc, FeedSet, check_market
from ..feeds import FIAT_ASSETS
from cachetools import TTLCache
import requests
import logging

log = logging.getLogger(__name__)


NAME = 'Fixer'

AVAILABLE_MARKETS = [(asset, 'USD') for asset in FIAT_ASSETS]


# TTL = 12 hours, Fixer only updates once a day
_cache = TTLCache(maxsize=8192, ttl=43200)


@check_online_status
@cachedmodulefunc
def get_all(base):
    rates = requests.get('https://api.fixer.io/latest?base={}'.format(base)).json()['rates']
    return FeedSet(FeedPrice(1 / price, asset, base) for asset, price in rates.items())


@check_online_status
@check_market
def get(asset, base):
    return get_all(base)[asset]

