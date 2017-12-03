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
import requests
import logging

log = logging.getLogger(__name__)


NAME = 'Binance'

AVAILABLE_MARKETS = [('BTS', 'BTC')]

def get_all(self, base):
    # FIXME: implement me
    # does not include volume information...
    # https://api.binance.com/api/v1/ticker/allPrices
    pass

@check_online_status    # FIXME: only works for methods for now
@check_market
def get(asset, base):
    log.debug('checking feeds for %s/%s at %s' % (asset, base, NAME))
    data = requests.get('https://api.binance.com/api/v1/ticker/24hr?symbol={}{}'.format(asset, base)).json()

    return FeedPrice(float(data['lastPrice']), asset, base, float(data['volume']))
