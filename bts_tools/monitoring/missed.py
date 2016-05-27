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
from .. import core
from datetime import datetime
import logging

log = logging.getLogger(__name__)


def init_ctx(node, ctx, cfg):
    if node.is_graphene_based():
        db = core.db[node.rpc_id]
        if node.name not in db.setdefault('static', {}).setdefault('monitor_witnesses', []):
            log.debug('Adding witness {} to monitor list for {}'.format(node.name, node.rpc_id))
            db['static']['monitor_witnesses'].append(node.name)
            db['static']['need_reindex'] = True

        try:
            ctx.total_produced = db['total_produced'][node.name]
        except KeyError:
            ctx.total_produced = 0

        # start with a streak of 0 when we start the tools, as there's no way (currently)
        # to know when was the last block missed
        ctx.streak = 0

    else:
        ctx.producing_state = StableStateMonitor(3)
        ctx.last_n_notified = 0


def is_valid_node(node):
    # FIXME: revisit block_age < 60 (node.is_synced()), this was meant when syncing at the beginning, but
    #        during network crisis this might happen but we still want to monitor for missed blocks
    return node.is_witness() and node.is_synced()  # only monitor if synced


def monitor(node, ctx, cfg):
    # monitor for missed blocks, only for delegate nodes
    if node.is_graphene_based():
        db = core.db[node.rpc_id]
        total_missed = node.get_witness(node.name)['total_missed']
        if total_missed > db['total_missed'][node.name]:
            db['last_missed'][node.name] = datetime.utcnow()
            ctx.streak = min(ctx.streak, 0) - 1
            msg = 'missed another block! {} last missed ({} total)'.format(-ctx.streak, total_missed)
            log.warning('Witness {} {}'.format(node.name, msg))
            send_notification([node], msg, alert=True)
        db['total_missed'][node.name] = total_missed

        if db['total_produced'][node.name] > ctx.total_produced:
            ctx.streak = max(ctx.streak, 0) + 1
            db['streak'][node.name] = max(db['streak'], 0) + 1
            msg = 'produced block number {}. {} last produced'.format(db['last_indexed_block'], ctx.streak)
            log.info('Witness {} {}'.format(node.name, msg))
        ctx.total_produced = db['total_produced'][node.name]


    else:
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
