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

from collections import deque, defaultdict
from datetime import datetime
from itertools import chain, islice
from .core import StatsFrame
from .notification import send_notification
from .feeds import check_feeds
from . import core, monitoring
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
        self.last_stable_state = None

    def push(self, state):
        stable_state = self.stable_state()
        if stable_state is not None:
            self.last_stable_state = stable_state
        self.states.append(state)

    def stable_state(self):
        size = len(self.states)
        if size < self.n:
            return None
        last_state = self.states[-1]
        if all(state == last_state for state in islice(self.states, size-self.n, size)):
            return last_state
        return None

    def just_changed(self):
        stable_state = self.stable_state()
        if stable_state is None or self.last_stable_state is None:
            return False
        return stable_state != self.last_stable_state


def monitoring_thread(*nodes):
    global time_interval

    client_node = nodes[0]

    # all different types of monitoring that should be considered by this thread
    all_monitoring = set(chain(*(node.monitoring for node in nodes)))
    node_names = [n.name for n in nodes]

    log.info('Starting thread monitoring on %s:%d for nodes %s' %
             (client_node.rpc_host, client_node.rpc_port, ', '.join(node_names)))

    stats = stats_frames[client_node.rpc_cache_key] = deque(maxlen=min(desired_maxlen, maxlen))

    # launch feed monitoring and publishing thread
    if 'feeds' in all_monitoring:
        check_feeds(nodes)

    online_state = StableStateMonitor(3)
    connection_state = StableStateMonitor(3)

    # need to have one for each node name (hence the defaultdict)
    producing_state = defaultdict(lambda: StableStateMonitor(3))
    last_n_notified = defaultdict(int)

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

            if client_node.type == 'seed':
                monitoring.seed.monitor(client_node, online_state)

            # check for minimum number of connections for delegate to produce
            MIN_CONNECTIONS = 5
            if info['network_num_connections'] <= MIN_CONNECTIONS:
                connection_state.push('starved')
                if connection_state.just_changed():
                    log.warning('Nodes %s: fewer than %d network connections...' % (node_names, MIN_CONNECTIONS))
                    send_notification(nodes, 'fewer than %d network connections...' % MIN_CONNECTIONS, alert=True)
            else:
                connection_state.push('connected')
                if connection_state.just_changed():
                    log.info('Nodes %s: got more than %d connections now' % (node_names, MIN_CONNECTIONS))
                    send_notification(nodes, 'got more than %d connections now' % MIN_CONNECTIONS)

            # monitor each node
            for node in nodes:
                monitoring.missed.monitor(node, info, producing_state[node.name], last_n_notified)
                monitoring.version.monitor(node, info, online_state)
                monitoring.payroll.monitor(node)

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
