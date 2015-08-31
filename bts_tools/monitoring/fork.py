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
    ctx.blockchain_uptodate = StableStateMonitor(3)


def is_valid_node(node):
    return True


def monitor(node, ctx, cfg):
    # TODO: also check delegate participation is low (github #17)
    node_names = ', '.join(n.name for n in ctx.nodes)

    # if we just came online, force state to not in sync so we get the notification when we're up-to-date
    if ctx.online_state.just_changed():
        for _ in range(3):
            ctx.blockchain_uptodate.push('stale')

    if int(ctx.info['blockchain_head_block_age']) < 60:
        ctx.blockchain_uptodate.push('up-to-date')

        if ctx.blockchain_uptodate.just_changed():
            log.info('Blockchain synced and up-to-date for nodes %s' % node_names)
            send_notification(ctx.nodes, 'blockchain synced and up-to-date')

    else:
        ctx.blockchain_uptodate.push('stale')

        if ctx.blockchain_uptodate.just_changed():
            log.warning('Blockchain not in sync anymore for nodes %s' % node_names)
            send_notification(ctx.nodes, 'blockchain not in sync anymore')
