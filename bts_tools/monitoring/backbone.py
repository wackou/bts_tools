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
import logging

log = logging.getLogger(__name__)


def reconnect_backbone(node):
    # try to connect to backbone nodes to which we are not currently connected
    backbone_nodes = core.config.get('backbone', [])
    if not backbone_nodes:
        log.warning('No backbone nodes configured. Cannot reconnect to backbone...')
        return
    peers = node.network_get_peer_info()
    #print('peers: {}'.format({p['addr'] for p in peers}))
    not_connected = set(backbone_nodes) - {p['addr'] for p in peers}
    #print('not connected: %s' % not_connected)
    if not_connected:
        log.debug('Trying to reconnect to the following backbone nodes: {}'.format(not_connected))
    for p in not_connected:
        # TODO: implement rate limiting to avoid hammering the server in case it's down and could
        #       have a hard time coming back up if all delegates try connecting like crazy
        node.network_add_node(p, 'add')


def is_valid_node(node):
    return True


def monitor(node, ctx, cfg):
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
    reconnect_backbone(node)


