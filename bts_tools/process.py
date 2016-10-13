#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
# Copyright (c) 2014 Nicolas Wack <wackou@gmail.com>
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

import psutil
import logging

log = logging.getLogger(__name__)

# TODO: should move all these functions inside of GrapheneClient

def bts_process(node):
    if not node.is_witness_localhost():
        return None

    #host = node.witness_host if node.is_graphene_based() else node.rpc_host
    port = node.witness_port if node.is_graphene_based() else node.rpc_port

    # find the process corresponding to our node by looking at the rpc port
    #log.debug('find bts binary on {}:{}'.format(host, port))
    procs = []
    for p in psutil.process_iter():
        try:
            if node.bin_name in p.name():
                if port in [c.laddr[1] for c in p.connections()]:
                    procs.append(p)
        except psutil.NoSuchProcess:
            # process disappeared in the meantime, so it's not our witness process
            pass

    if procs:
        if len(procs) > 1:
            log.warning('More than 1 potential bts process: {}'.format(','.join(p.name for p in procs)))
        return procs[0]

    return None


def bts_binary_running(node):
    """Return whether an instance of the bts binary could be found that is
    running or in a runnable state.
    """
    p = bts_process(node)
    if p is not None:
        return p.status() not in {psutil.STATUS_STOPPED,
                                  psutil.STATUS_TRACING_STOP,
                                  psutil.STATUS_ZOMBIE,
                                  psutil.STATUS_DEAD}
    return False


def binary_description(node):
    """Return a human readable version description of the running binary,
    either tag version or git revision.
    """
    if node.is_graphene_based():
        client_version = node.about()['client_version']
    else:
        client_version = node.get_info()['client_version']
    p = bts_process(node)
    if p is None:
        return client_version
    # if client is running locally, extract info from filename, usually more precise
    try:
        desc = p.exe().split(node.bin_name + '_')[1]
    except IndexError:
        log.debug('Could not identify description from filename: %s' % p.exe())
        return client_version
    if client_version in desc:
        # we're on a tag, then just return the tag
        return client_version
    return desc

