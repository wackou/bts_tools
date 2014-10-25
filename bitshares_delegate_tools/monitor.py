#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bitshares_delegate_tools - Tools to easily manage the bitshares client
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

from collections import deque
from datetime import datetime
from itertools import chain, islice
from .core import StatsFrame
from .notification import send_notification
from .feeds import check_feeds
from . import core
import math
import time
import logging

log = logging.getLogger(__name__)

stats_frames = {}
# make sure we don't have huge plots that take forever to render
maxlen = 2000

cfg = None
time_span = None
time_interval = None
desired_maxlen = None


def load_monitoring():
    global cfg, time_span, time_interval, desired_maxlen, stable_time_interval
    cfg = core.config['monitoring']
    time_span = cfg['plots_time_span']
    time_interval = cfg['monitor_time_interval']
    desired_maxlen = int(time_span / time_interval)

    if desired_maxlen > maxlen:
        stable_time_interval = time_interval * (desired_maxlen / maxlen)
    else:
        stable_time_interval = time_interval


class StableStateMonitor(object):
    """Monitor a sequence of states, and is able to compute a "stable" state value when N
    consecutive same states have happened.
    For example, we only want to decide the client is offline after 3 consecutive 'offline' states
    to absorb transient errors and avoid reacting too fast on wrong alerts.
    """
    def __init__(self, n):
        self.n = n
        self.states = deque(maxlen=n+1)

    def push(self, state):
        self.states.append(state)

    def stable_state(self):
        size = len(self.states)
        if size < self.n:
            return None
        if all(state == self.states[-1] for state in islice(self.states, size-self.n, size-1)):
            return self.states[-1]
        return None

    def just_changed(self):
        size = len(self.states)
        if size < (self.n + 1):
            return False
        if self.stable_state() is None:
            return False
        return self.states[-1] != self.states[-(self.n + 1)]


def monitoring_thread(*nodes):
    global time_interval

    client_node = nodes[0]

    # all different types of monitoring that should be considered by this thread
    monitoring = set(chain(*(node.monitoring for node in nodes)))
    node_names = [n.name for n in nodes]

    log.info('Starting thread monitoring on %s:%d for nodes %s' %
             (client_node.rpc_host, client_node.rpc_port, ', '.join(node_names)))

    stats = stats_frames[client_node.rpc_cache_key] = deque(maxlen=min(desired_maxlen, maxlen))

    # launch feed monitoring and publishing thread
    if 'feeds' in monitoring:
        check_feeds(nodes)

    online_state = StableStateMonitor(3)
    connection_state = StableStateMonitor(3)
    producing_state = StableStateMonitor(3)

    loop_index = 0

    while True:
        loop_index += 1
        time.sleep(time_interval)
        log.debug('-------- Monitoring status of the BitShares client --------')
        client_node.clear_rpc_cache()

        try:
            if not client_node.is_online():
                log.debug('Offline')
                online_state.push('offline')

                if online_state.just_changed():
                    log.warning('Nodes %s just went offline...' % node_names)
                    send_notification(nodes, 'node just went offline...', alert=True)

                stats.append(StatsFrame(cpu=0, mem=0, connections=0, timestamp=datetime.utcnow()))
                continue

            log.debug('Online')
            online_state.push('online')

            if online_state.just_changed():
                log.info('Nodes %s just came online!' % node_names)
                send_notification(nodes, 'node just came online!')

            info = client_node.get_info()

            # check for minimum number of connections for delegate to produce
            if info['network_num_connections'] <= 5:
                connection_state.push('starved')
                if connection_state.just_changed():
                    log.warning('Nodes %s: fewer than 5 network connections...' % node_names)
                    send_notification(nodes, 'fewer than 5 network connections...', alert=True)
            else:
                connection_state.push('connected')
                if connection_state.just_changed():
                    log.info('Nodes %s: got more than 5 connections now' % node_names)
                    send_notification(nodes, 'got more than 5 connections now')

            # monitor for missed blocks, only for delegate nodes
            for node in nodes:
                if node.type == 'delegate' and info['blockchain_head_block_age'] < 60:  # only monitor if synced
                    producing, n = node.get_streak()
                    producing_state.push(producing)
                    if not producing and producing_state.just_changed():
                        log.warning('Delegate %s missed a block!' % node.name)
                        send_notification([node], 'missed a block!', alert=True)

            # only monitor cpu and network if we are monitoring localhost
            if client_node.rpc_host == 'localhost':
                p = client_node.process()
                if p is not None:
                    s = StatsFrame(cpu=p.cpu_percent(),
                                   mem=p.memory_info().rss,
                                   connections=info['network_num_connections'],
                                   timestamp=datetime.utcnow())
                else:
                    s = StatsFrame(cpu=0, mem=0, connections=0, timestamp=datetime.utcnow())

            else:
                s = StatsFrame(cpu=0, mem=0, connections=0, timestamp=datetime.utcnow())

            # if our stats queue is full, only append now and then to reach approximately
            # the desired timespan while keeping the same number of items
            if time_interval != stable_time_interval and len(stats) == stats.maxlen:
                # note: we could have used round() instead of ceil() here but ceil()
                #       gives us the guarantee that the time span will be at least
                #       the one asked for, not less due to rounding effects
                ratio = math.ceil(stable_time_interval / time_interval)
                if loop_index % ratio == 0:
                    stats.append(s)
            else:
                stats.append(s)

        except Exception as e:
            log.error('An exception occurred in the monitoring thread:')
            log.exception(e)
