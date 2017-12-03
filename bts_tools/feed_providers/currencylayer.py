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

from . import FeedPrice, check_online_status_func, cachedmodulefunc, FeedSet
from . import from_bts, to_bts
from .. import core
from cachetools import TTLCache
import requests
import logging

log = logging.getLogger(__name__)


NAME = 'CurrencyLayer'

ASSET_MAP = {'GOLD': 'XAU',
             'SILVER': 'XAG'}


# TTL = 2 hours, max requests per month = 12 * 30 < 1000, allows for free account
_cache = TTLCache(maxsize=8192, ttl=7200)


@check_online_status_func
@cachedmodulefunc
def get(asset_list, base):
    log.debug('checking feeds for %s / %s at CurrencyLayer' % (' '.join(asset_list), base))
    asset_list = [from_bts(asset) for asset in asset_list]
    base = base.upper()

    try:
        access_key = core.config['credentials']['currencylayer']['access_key']
    except KeyError:
        raise KeyError('config.yaml does not specify a "credentials.currencylayer.access_key" variable')

    url = 'http://apilayer.net/api/live?access_key={}&currencies={}'.format(access_key, ','.join(asset_list))
    r = requests.get(url).json()
    if not r['success']:
        error = r['error']
        raise ValueError('Error code {}: {}'.format(error['code'], error['info']))

    return FeedSet(FeedPrice(1 / r['quotes']['USD{}'.format(asset)],
                             to_bts(asset), base)
                   for asset in asset_list)
