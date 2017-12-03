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

from . import FeedPrice, check_online_status, from_bts, to_bts
from bs4 import BeautifulSoup
import requests
import logging

log = logging.getLogger(__name__)

NAME = 'Bloomberg'

_BLOOMBERG_URL = 'http://www.bloomberg.com/quote/{}'

# note: left here as a reference, from bts 0.x times
ASSET_MAP = {'SHENZHEN': 'SZCOMP:IND',
             'SHANGHAI': 'SHCOMP:IND',
             'NIKKEI': 'NKY:IND',
             'NASDAQC': 'CCMP:IND',
             'HANGSENG': 'HSI:IND',
             'GOLD': 'XAUUSD:CUR'}

AVAILABLE_MARKETS = [('SHENZHEN', 'CNY'), ('NIKKEI', 'JPY')]

@check_online_status
def query_quote(q, base_currency=None):
    log.debug('checking quote for %s at %s' % (q, NAME))
    r = requests.get(_BLOOMBERG_URL.format(from_bts(q)))
    soup = BeautifulSoup(r.text, 'html.parser')
    r = float(soup.find(class_='price').text.replace(',', ''))
    return FeedPrice(q, base_currency, r)


def get(asset, base):
    raise NotImplementedError