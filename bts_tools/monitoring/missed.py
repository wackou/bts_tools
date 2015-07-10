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
    ctx.producing_state = StableStateMonitor(3)
    ctx.last_n_notified = 0


def is_valid_node(node):
    return node.type == 'delegate' and node.is_synced()  # only monitor if synced


def monitor(node, ctx, cfg):
    # monitor for missed blocks, only for delegate nodes
    # FIXME: revisit block_age < 60 (node.is_synced()), this was meant when syncing at the beginning, but
    #        during network crisis this might happen but we still want to monitor for missed blocks
    # TODO: blocks_produced = get_streak()
    #       if blocks_produced < last_blocks_produced:
    #           # missed block somehow
    #       last_blocks_produced = blocks_produced
    producing, n = node.get_streak()
    ctx.producing_state.push(producing)

    if not producing and ctx.producing_state.just_changed():
        log.warning('Delegate %s just missed a block!' % node.name)
        send_notification([node], 'just missed a block!', alert=True)
        ctx.last_n_notified = 1

    elif ctx.producing_state.stable_state() == False and n > ctx.last_n_notified:
        log.warning('Delegate %s missed another block! (%d missed total)' % (node.name, n))
        send_notification([node], 'missed another block! (%d missed total)' % n, alert=True)
        ctx.last_n_notified = n
