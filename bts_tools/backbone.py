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
from contextlib import suppress
import socket
import fcntl
import struct
import logging

log = logging.getLogger(__name__)


def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])


def get_ip():
    for iface in [b'eth0', b'en1']:
        with suppress(Exception):
            return get_ip_address(iface)
    raise OSError('Could not get IP address')


def get_p2p_port(node):
    # NOTE: this returns 0 while the client is starting (ie: already responds
    #       to JSON-RPC but hasn't started the p2p code yet)
    return int(node.network_get_info()['listening_on'].split(':')[1])


def node_list(node):
    backbone_nodes = {(n.split(':')[0], int(n.split(':')[1]))
                      for n in core.config.get('backbone', [])}
    if not backbone_nodes:
        log.warning('No backbone nodes configured. Cannot reconnect to backbone...')
        return []
    # resolve dns names
    backbone_nodes = {(socket.gethostbyname(host), port) for host, port in backbone_nodes}
    backbone_nodes = {'%s:%d' % (host, port) for host, port in backbone_nodes}
    # need to exclude the calling node from the list
    with suppress(Exception):
        backbone_nodes -= {'%s:%d' % (get_ip(), get_p2p_port(node))}
    return backbone_nodes


def non_connected_node_list(node):
    return node_list(node) - {p['addr'] for p in node.network_get_peer_info()}
