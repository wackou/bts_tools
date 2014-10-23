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
from itertools import chain
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


def monitoring_thread(*nodes):
    # FIXME: problem with feeds checking
    global time_interval

    client_node = nodes[0]

    # all different types of monitoring that should be considered by this thread
    monitoring = set(chain(*(node.monitoring for node in nodes)))

    log.info('Starting thread monitoring on %s:%d for nodes %s' %
             (client_node.rpc_host, client_node.rpc_port, ', '.join([n.name for n in nodes])))

    stats = stats_frames[client_node.rpc_cache_key] = deque(maxlen=min(desired_maxlen, maxlen))

    # launch feed monitoring and publishing thread
    if 'feeds' in monitoring:
        check_feeds(nodes)

    loop_index = 0

    last_state = None
    last_state_consecutive = 0
    last_stable_state = None
    connection_status = None
    last_producing = True
    missed_count = 0

    while True:
        loop_index += 1
        time.sleep(time_interval)
        log.debug('-------- Monitoring status of the BitShares client --------')
        client_node.clear_rpc_cache()

        try:
            if not client_node.is_online():
                log.debug('Offline')
                if last_state == 'online':
                    last_state_consecutive = 0
                last_state = 'offline'
                last_state_consecutive += 1

                if 'email' in monitoring or 'apns' in monitoring:
                    # wait for 3 "confirmations" that we are offline, to avoid
                    # reacting too much on temporary connection errors
                    if last_state_consecutive == 3:
                        if last_stable_state and last_stable_state != last_state:
                            msg = 'nodes %s just went offline...' % [n.name for n in nodes]
                            log.warning(msg)
                            send_notification(nodes, 'node just went offline', alert=True)
                        last_stable_state = last_state

                stats.append(StatsFrame(cpu=0, mem=0, connections=0, timestamp=datetime.utcnow()))
                continue

            log.debug('Online')
            if last_state == 'offline':
                last_state_consecutive = 0
            last_state = 'online'
            last_state_consecutive += 1

            info = client_node.get_info()

            if 'email' in monitoring or 'apns' in monitoring:
                # wait for 3 "confirmations" that we are online, to avoid
                # reacting too much on temporary connection errors
                if last_state_consecutive == 3:
                    if last_stable_state and last_stable_state != last_state:
                        msg = 'Nodes %s just came online!' % [n.name for n in nodes]
                        log.info(msg)
                        send_notification(nodes, 'node just came online!')
                    last_stable_state = last_state

                # check for minimum number of connections for delegate to produce
                # TODO: we should try to avoid notifying about being connected just right after
                #       starting the client
                if info['network_num_connections'] <= 5:
                    if connection_status and connection_status != 'starved':
                        log.warning('Fewer than 5 network connections...')
                        send_notification(nodes, 'fewer than 5 network connections...', alert=True)
                    connection_status = 'starved'
                else:
                    if connection_status and connection_status != 'connected':
                        log.info('Got more than 5 connections now')
                        send_notification(nodes, 'Got more than 5 connections now')
                    connection_status = 'connected'

                # monitor for missed blocks, only for delegate nodes
                for node in nodes:
                    if node.type == 'delegate' and info['blockchain_head_block_age'] < 60:  # only monitor if synced
                        producing, n = node.get_streak()
                        if last_producing:
                            if not producing:
                                missed_count += 1
                                if missed_count == 3:
                                    # wait for 3 confirmations before finding a miss, to
                                    # avoid reacting too quick on glitches
                                    log.warning('Delegate %s missed a block!' % node.name)
                                    send_notification([node], 'missed a block!', alert=True)
                                else:
                                    # we still consider we're producing
                                    producing = True
                            else:
                                missed_count = 0

                        last_producing = producing


            # only monitor cpu and network if we are monitoring localhost
            if client_node.rpc_host != 'localhost':
                s = StatsFrame(cpu=0, mem=0, connections=0, timestamp=datetime.utcnow())

            else:
                p = client_node.process() # p should not be None otherwise we know we are offline
                s = StatsFrame(cpu=p.cpu_percent(),
                               mem=p.memory_info().rss,
                               connections=info['network_num_connections'],
                               timestamp=datetime.utcnow())

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
