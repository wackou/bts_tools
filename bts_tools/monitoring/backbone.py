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

from .. import core
from ..backbone import non_connected_node_list
import logging

log = logging.getLogger(__name__)

WAIT_RECONNECT = 60  # seconds before trying to reconnect to a host


def reconnect_backbone(node, ctx):
    # try to connect to backbone nodes to which we are not currently connected
    period = WAIT_RECONNECT // core.config['monitoring']['monitor_time_interval']
    old_node_connect_age = ctx.get('node_connect_age', {})
    ctx.node_connect_age = {}

    for n in non_connected_node_list(node):
        ctx.node_connect_age[n] = old_node_connect_age.get(n, -1) + 1
        # implement rate limiting to avoid hammering the server in case it's down and could
        # have a hard time coming back up if all delegates try connecting like crazy
        if ctx.node_connect_age[n] % period == 0:
            log.debug('Trying to reconnect to backbone node: %s' % n)
            node.network_add_node(n, 'add')


def is_valid_node(node):
    return node.role == 'backbone'


def monitor(node, ctx, cfg):
    # check that backbone node does not perform peer exchange
    proc = node.process()
    if proc and '--disable-peer-advertising' not in proc.cmdline():
        log.error('Backbone nodes %s have not been launched with option --disable-peer-advertising' % node.name)
        log.error('This can lead to potentially revealing the connected delegates. Please fix it!')

    # if backbone node just came online, set its connection count to something high
    if ctx.online_state.just_changed():
        # TODO: only if state just changed? if we crash and restart immediately, then we should do it also...
        desired = cfg.get('desired_number_of_connections', 200)
        maximum = cfg.get('maximum_number_of_connections', 400)
        log.info('Backbone node just came online, setting connections to desired: %d, maximum: %d' %
                 (desired, maximum))
        node.network_set_advanced_node_parameters({'desired_number_of_connections': desired,
                                                   'maximum_number_of_connections': maximum})

    # try to connect to backbone nodes to which we are not currently connected
    reconnect_backbone(node, ctx)


