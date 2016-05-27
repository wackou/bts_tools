#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
# Copyright (c) 2016 Nicolas Wack <wackou@gmail.com>
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

from .. import core
from datetime import datetime
import logging

log = logging.getLogger(__name__)


def init_ctx(node, ctx, cfg):
    db = core.db[node.rpc_id]

    db.setdefault('static', {}).setdefault('monitor_witnesses', [])
    db.setdefault('last_indexed_block', 0)
    db.setdefault('total_produced', {})  # indexed by node_name
    db.setdefault('last_produced', {})   # indexed by node_name
    db.setdefault('total_missed', {})    # indexed by node_name
    db.setdefault('last_missed', {})     # indexed by node_name

    for node_name in db['static']['monitor_witnesses']:
        db['total_produced'].setdefault(node_name, 0)
        db['total_missed'].setdefault(node_name, 0)

    ctx.first_reindex = True


def is_valid_node(node):
    return True


def monitor(node, ctx, cfg):
    db = core.db[node.rpc_id]

    # Get block number
    head_block_num = node.get_head_block_num()
    period = head_block_num // 100 + 1

    if ctx.first_reindex:
        log.info('Reindexing database on {}...'.format(node.rpc_id))

    # We loop through all blocks we may have missed since the last
    # block defined above
    while head_block_num - db['last_indexed_block'] > 0:
        current_block_num = db['last_indexed_block'] + 1

        if current_block_num % period == 0:
            progress = round(current_block_num / head_block_num * 100)
            log.info('[{:2d}%] Indexing block number {} on {}'.format(progress, current_block_num, node.rpc_id))

        block = node.get_block(current_block_num)
        for witness_name in db['static']['monitor_witnesses']:
            if block['witness'] == witness_name:
                log.info('Witness {} produced block number {}'.format(witness_name, current_block_num))
                db['total_produced'][witness_name] += 1
                db['last_produced'][witness_name] = datetime.strptime(block['timestamp'], '%Y-%m-%dT%H:%M:%S')

        db['last_indexed_block'] = current_block_num

    if ctx.first_reindex:
        log.info('Reindexing done on {}!'.format(node.rpc_id))
        ctx.first_reindex = False
