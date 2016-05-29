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

from ..notification import send_notification
from ..monitor import StableStateMonitor
import logging

log = logging.getLogger(__name__)


def init_ctx(node, ctx, cfg):
    ctx.connection_state = StableStateMonitor(3)


def is_valid_node(node):
    return True


def monitor(node, ctx, cfg):
    # check for minimum number of connections for delegate to produce
    min_connections = cfg.get('min_connections', 5)
    num_connections = node.network_get_info()['connection_count'] if node.is_graphene_based() else ctx.info['network_num_connections']
    if num_connections <= min_connections:
        ctx.connection_state.push('starved')
        if ctx.connection_state.just_changed():
            send_notification(ctx.nodes, 'fewer than %d network connections...' % min_connections, alert=True)
    else:
        ctx.connection_state.push('connected')
        if ctx.connection_state.just_changed():
            send_notification(ctx.nodes, 'got more than %d connections now' % min_connections)
