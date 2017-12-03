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

from . import FeedPrice, check_online_status, reuse_last_value_on_fail, check_market
from retrying import retry
import requests
import logging

log = logging.getLogger(__name__)

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
    # log.debug('received: {}'.format(json.dumps(r, indent=4)))
    r = r['{}{}'.format(cur.lower(), base.lower())]
    return FeedPrice(float(r['ticker']['last']),
                     cur, base,
                     volume=float(r['ticker']['vol']),
                     last_updated=datetime.utcfromtimestamp(r['at']),
                     provider=NAME)
