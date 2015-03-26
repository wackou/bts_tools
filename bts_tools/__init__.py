#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
# Copyright (c) 2014 Nicolas Wack <wackou@gmail.com>
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

import logging
from .slogging import setupLogging

setupLogging(with_time=True, with_lineno=True)

# default logging levels
logging.getLogger('bts_tools').setLevel(logging.INFO)

from .rpcutils import main_node as rpc

def init(loglevels=None):
    from .core import load_config
    from .rpcutils import load_nodes
    from .feeds import load_feeds

    load_config(loglevels)
    load_nodes()
    load_feeds()

    from . import core
    log = logging.getLogger('bts_tools.profile')
    if core.config.get('profile', False):
        log.info('Profiling RPC calls')
    else:
        log.debug('Not profiling RPC calls')

