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

import logging

log = logging.getLogger(__name__)


def is_valid_node(node):
    return node.type == 'seed'


def sublist_index(l1, l2):
    """Returns the index at which l1 is a sublist of l2, -1 otherwise."""
    for i in range(len(l2)-len(l1)):
        for j in range(len(l1)):
            if l1[j] != l2[i+j]:
                break
            else:
                return i
    return -1


def monitor(node, ctx, cfg):
    # check that seed node does allow incoming connections
    proc = node.process()
    if proc and ('--accept-incoming-connections=0' in proc.cmdline() or
                 sublist_index(['--accept-incoming-connections', '0'], proc.cmdline()) >= 0):
        log.error('Seed nodes %s have not been launched with option to reject incoming connections' % node.name)
        log.error('This renders the seed node useless. Please fix it!')

    # if seed node just came online, set its connection count to something high
    if ctx.online_state.just_changed():
        # TODO: only if state just changed? if we crash and restart immediately, then we should do it also...
        desired = cfg.get('desired_number_of_connections', 200)
        maximum = cfg.get('maximum_number_of_connections', 400)
        log.info('Seed node just came online, setting connections to desired: %d, maximum: %d' %
                 (desired, maximum))
        node.network_set_advanced_node_parameters({'desired_number_of_connections': desired,
                                                   'maximum_number_of_connections': maximum})

