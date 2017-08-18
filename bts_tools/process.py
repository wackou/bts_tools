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

from .core import run, get_bin_name
import psutil
import logging

log = logging.getLogger(__name__)

# TODO: should move all these functions inside of GrapheneClient


# use a cache for the mapping {port: process}, as iterating over all processes with psutil is quite costly
_process_cache = {}

statuses = {psutil.STATUS_RUNNING: 'STATUS_RUNNING',
            psutil.STATUS_SLEEPING: 'STATUS_SLEEPING',
            psutil.STATUS_DISK_SLEEP: 'STATUS_DISK_SLEEP',
            psutil.STATUS_STOPPED: 'STATUS_STOPPED',
            psutil.STATUS_TRACING_STOP: 'STATUS_TRACING_STOP',
            psutil.STATUS_ZOMBIE: 'STATUS_ZOMBIE',
            psutil.STATUS_DEAD: 'STATUS_DEAD',
            psutil.STATUS_WAKING: 'STATUS_WAKING',
            psutil.STATUS_IDLE: 'STATUS_IDLE'}


def witness_process(node):
    if not node.is_witness_localhost():
        return None

    port = node.witness_port
    proc = _process_cache.get(port)

    if proc is not None:
        try:
            if proc.status() in [psutil.STATUS_RUNNING, psutil.STATUS_SLEEPING]:
                log.debug('returning cached proc for binary on port {}: {}'.format(port, proc))
                return proc

            else:
                log.debug('found cached proc on port {}, but status is {}'.format(port, statuses.get(proc.status(), proc.status())))
        except psutil.NoSuchProcess:
            del _process_cache[port]  # remove stale entry


    # find the process corresponding to our node by looking at the rpc port
    #log.debug('find bts binary on {}:{}'.format(host, port))
    try:
        lines = run('lsof -i :{}'.format(port), verbose=False, log_on_fail=False, capture_io=True).stdout.split('\n')
    except RuntimeError:
        log.debug('found no process listening on port {}'.format(port))
        return None

    lines = [l for l in lines if 'LISTEN' in l]
    if not lines:
        return None
    if len(lines) > 1:
        log.warning('More than 1 potential witness process: {}'.format(lines))

    pid = int(lines[0].split()[1])
    proc = psutil.Process(pid)

    bin_name = node.build_env().get('witness_filename') or get_bin_name(node.client_name)
    if bin_name not in proc.name():
        log.warning('Process pid={} listening on port {} doesn\'t seem to have the correct filename: '
                    'expected={}, actual={}'.format(pid, port, bin_name, proc.name()))

    _process_cache[port] = proc
    return proc


def bts_binary_running(node):
    """Return whether an instance of the bts binary could be found that is
    running or in a runnable state.
    """
    p = witness_process(node)
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
    client_version = node.about()['client_version']
    p = witness_process(node)
    if p is None:
        return client_version
    # if client is running locally, extract info from filename, usually more precise
    try:
        bin_name = node.build_env().get('witness_filename') or get_bin_name(node.client_name)
        desc = p.exe().split(bin_name + '_')[1]
    except IndexError:
        log.debug('Could not identify description from filename: %s' % p.exe())
        return client_version
    if client_version in desc:
        # we're on a tag, then just return the tag
        return client_version
    return desc

