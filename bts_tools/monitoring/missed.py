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
from os.path import expanduser
from collections import defaultdict
import json
import logging

log = logging.getLogger(__name__)


def init_ctx(node, ctx, cfg):
    if node.is_graphene_based():
        ctx.total_missed = None
        db = core.db[node.rpc_id]

        db.setdefault('last_block', 1)
        db.setdefault('monitor_witnesses', [])
        if node.name not in db['monitor_witnesses']:
            db['monitor_witnesses'].append(node.name)

        db.setdefault('total_produced', {}) # indexed by node.name
        db['total_produced'].setdefault(node.name, 0)
        db.setdefault('total_missed', {})   # indexed by node.name
        db['total_missed'].setdefault(node.name, 0)

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
            log.warning('Witness %s missed another block! (%d missed total)' % (node.name, total_missed))
            send_notification([node], 'missed another block! (%d missed total)' % total_missed, alert=True)
        db['total_missed'][node.name] = total_missed

        # Get block number
        block_number = node.get_head_block_num()

        # We loop through all blocks we may have missed since the last
        # block defined above
        while block_number - db['last_block'] > 0:
            if db['last_block'] % 1000 == 0:
                log.debug('getting block number {}'.format(db['last_block']))
            block = node.get_block(db['last_block'])
            for witness_name in db['monitor_witnesses']:
                if block['witness'] == witness_name:
                    log.info('Witness {} produced block number {}'.format(witness_name, db['last_block']))
                    db['total_produced'][witness_name] += 1
            db['last_block'] += 1


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
