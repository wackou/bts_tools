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

from .backbone import reconnect_backbone
from ..backbone import node_list
import logging

log = logging.getLogger(__name__)


def is_valid_node(node):
    return node.type == 'delegate'


def monitor(node, ctx, cfg):
    # TODO: set list of allowed peers to be only backbone nodes

    # try to connect to backbone nodes to which we are not currently connected
    reconnect_backbone(node, ctx)

    # TODO: ensure we are only connected to backbone nodes, unless the number of live backbone nodes is low
    #       otherwise, close the connections to non-backbone nodes

    # if the number of connections to the backbone is too low, open the restriction and let
    # the delegate connect to any node. In case all the backbone nodes are simultaneously DDoS'ed,
    # this lets the delegate reestablish a connection to the network before all the backbone nodes fall
    if node.network_get_connection_count() <= cfg.get('mininum_required_connections', 2):  # TODO: and not just launched
        # TODO: set list of allowed peers to all
        pass

