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
    ctx.active_state = StableStateMonitor(1)


def is_valid_node(node):
    return node.is_witness()


def monitor(node, ctx, cfg):
    # FIXME: only monitor when blockchain is synced
    if node.is_active(node.name):
        ctx.active_state.push('active')

        if ctx.active_state.just_changed():
            block_num = node.get_head_block_num()
            block = node.get_block(block_num)
            msg = 'witness got voted in! (block {} / {})'.format(block_num, block['timestamp'])
            send_notification([node], msg)

    else:
        ctx.active_state.push('standby')

        if ctx.active_state.just_changed():
            block_num = node.get_head_block_num()
            block = node.get_block(block_num)
            msg = 'witness got voted out... (block {} / {})'.format(block_num, block['timestamp'])
            send_notification([node], msg, alert=True)
