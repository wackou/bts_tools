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

from . import core
from .network_utils import resolve_dns, get_ip
from contextlib import suppress
import logging

log = logging.getLogger(__name__)


def get_p2p_port(node):
    # NOTE: this returns 0 while the client is starting (ie: already responds
    #       to JSON-RPC but hasn't started the p2p code yet)
    return int(node.network_get_info()['listening_on'].split(':')[1])


def node_list(node):
    backbone_nodes = {(n.split(':')[0], int(n.split(':')[1]))
                      for n in core.config.get('backbone', [])}
    if not backbone_nodes:
        log.warning('No backbone nodes configured. Cannot reconnect to backbone...')
        return set()
    # resolve dns names
    try:
        backbone_nodes = {(resolve_dns(host), port) for host, port in backbone_nodes}
    except Exception:
        # if we can't resolve names, we're probably not connected to the internet
        # FIXME: if DNS is down but we're still connected to the internet, we still
        #        want to connect to those nodes for which we already have the ip addr
        log.warning('Cannot resolve IP addresses for backbone nodes...')
        return set()
    backbone_nodes = {'%s:%d' % (host, port) for host, port in backbone_nodes}
    # need to exclude the calling node from the list
    with suppress(Exception):
        backbone_nodes -= {'%s:%d' % (get_ip(), get_p2p_port(node))}
    return backbone_nodes


def non_connected_node_list(node):
    try:
        return node_list(node) - {p['addr'] for p in node.network_get_connected_peers()}
    except:
        log.debug('Node %s not connected to the p2p network' % node.name)
        return set()
