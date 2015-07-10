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
    ctx.online_state = StableStateMonitor(3)


def is_valid_node(node):
    return True


def monitor(node, ctx, cfg):
    node_names = ', '.join(n.name for n in ctx.nodes)

    if not node.is_online():
        log.debug('Offline %s nodes: %s' % (ctx.nodes[0].bts_type(), node_names))
        ctx.online_state.push('offline')

        if ctx.online_state.just_changed():
            log.warning('Nodes %s just went offline...' % node_names)
            send_notification(ctx.nodes, 'node just went offline...', alert=True)

        return False

    log.debug('Online %s nodes: %s' % (ctx.nodes[0].bts_type(), node_names))
    ctx.online_state.push('online')

    if ctx.online_state.just_changed():
        log.info('Nodes %s just came online!' % node_names)
        send_notification(ctx.nodes, 'node just came online!')

    return True
