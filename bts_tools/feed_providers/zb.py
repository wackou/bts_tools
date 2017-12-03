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

from . import FeedPrice, check_online_status, check_market
import pendulum
import requests
import logging

log = logging.getLogger(__name__)

NAME = 'ZB'
AVAILABLE_MARKETS = [('BTS', 'BTC')]


@check_online_status
@check_market
def get(asset, base):
    log.debug('checking feeds for %s/%s at %s' % (asset, base, NAME))
    headers = {'content-type': 'application/json',
               'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:22.0) Gecko/20100101 Firefox/22.0'}

    data = requests.get('http://api.zb.com/data/v1/ticker?market={}_{}'.format(asset.lower(), base.lower()),
                        headers=headers).json()
    t = data['ticker']
    return FeedPrice(float(t['last']), asset, base,
                     volume=float(t['vol']),
                     last_updated=pendulum.from_timestamp(float(data['date']) / 1000),
                     provider=NAME)
