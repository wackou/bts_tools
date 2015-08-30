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
from datetime import datetime
import logging

log = logging.getLogger(__name__)


def init_ctx(node, ctx, cfg):
    ctx.wallet_open = StableStateMonitor(3)
    ctx.wallet_locked = StableStateMonitor(3)


def is_valid_node(node):
    return True


class BinaryStateMonitor():
    STATE1 = 'locked'
    STATE2 = 'unlocked'

    def monitor(self):
        # generic going from 1 state to the other and sending notification on state transition
        pass



def monitor(node, ctx, cfg):
    node_names = ', '.join(n.name for n in ctx.nodes)

    # if we just came online, then our wallet is closed and locked. Force state update
    # (state was not updated before because node was offline, so plugin wasn't called)
    if ctx.online_state.just_changed():
        for _ in range(3):
            ctx.wallet_open.push('closed')
            ctx.wallet_locked.push('locked')

    # check whether wallet is open
    if ctx.info['wallet_open']:
        ctx.wallet_open.push('open')

        if ctx.wallet_open.just_changed():
            msg = 'Opened wallet for %s at time: %s' % (node_names, datetime.now().isoformat())
            log.info(msg)
            send_notification(ctx.nodes, 'opened wallet at time: %s' % datetime.now().isoformat())

    else:
        ctx.wallet_open.push('closed')

        if ctx.wallet_open.just_changed():
            msg = 'Closed wallet for %s at time: %s' % (node_names, datetime.now().isoformat())
            log.info(msg)
            send_notification(ctx.nodes, 'closed wallet at time: %s' % datetime.now().isoformat())

    # check whether wallet is unlocked
    if ctx.info['wallet_unlocked']:
        ctx.wallet_locked.push('unlocked')

        if ctx.wallet_locked.just_changed():
            msg = 'Unlocked wallet for %s at time: %s' % (node_names, datetime.now().isoformat())
            log.info(msg)
            send_notification(ctx.nodes, 'unlocked wallet at time: %s' % datetime.now().isoformat())

    else:
        ctx.wallet_locked.push('locked')

        if ctx.wallet_locked.just_changed():
            msg = 'Locked wallet for %s at time: %s' % (node_names, datetime.now().isoformat())
            log.info(msg)
            send_notification(ctx.nodes, 'locked wallet at time: %s' % datetime.now().isoformat())
