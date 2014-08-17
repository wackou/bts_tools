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
from .core import config, StatsFrame
from .cmdline import send_notification
from .rpcutils import nodes
import pickle
import time
import psutil
import logging

log = logging.getLogger(__name__)


MONITOR_INTERVAL = 1 # in seconds
STATS_RANGE = 15 * 60 # time range in seconds for plots

stats = deque(maxlen=int(STATS_RANGE/MONITOR_INTERVAL))

def monitoring_thread():
    for n in nodes:
        if n.host == config['monitoring']['host']:
            node = n
            break
    else:
        raise ValueError('"%s" is not a valid host name. Available: %s' % (config['monitor_host'], ', '.join(n.host for n in nodes)))

    last_state = None
    connection_status = None

    log.debug('Starting monitoring thread...')

    while True:
        time.sleep(MONITOR_INTERVAL)
        log.debug('-------- Monitoring status of the BitShares client --------')
        node.clear_rpc_cache()

        try:
            if node.is_online():
                if last_state == 'offline':
                    send_notification('Delegate just came online!')
                last_state = 'online'
            else:
                log.debug('Offline')
                if last_state == 'online':
                    send_notification('Delegate just went offline...', alert=True)
                last_state = 'offline'
                stats.append(StatsFrame(cpu=0, mem=0, connections=0, timestamp=datetime.utcnow()))
                continue

            log.debug('Online')
            info = node.get_info()
            if info['network_num_connections'] <= 5:
                if connection_status == 'connected':
                    send_notification('Fewer than 5 network connections...', alert=True)
                    connection_status = 'starved'
            else:
                if connection_status == 'starved':
                    send_notification('Got more than 5 connections now')
                    connection_status = 'connected'

            # only monitor cpu and network if we are monitoring localhost
            if node.host != 'localhost':
                continue

            log.debug('find bts')
            # find bitshares process
            p = next(filter(lambda p: 'bitshares_client' in p.name(),
                            psutil.process_iter()))

            log.debug('found bts')
            s = StatsFrame(cpu=p.cpu_percent(),
                           mem=p.memory_info().rss,
                           connections=info['network_num_connections'],
                           timestamp=datetime.utcnow())

            log.debug('appending to stats: %s' % hex(id(stats)))
            stats.append(s)
            pickle.dump(stats, open(config['monitoring']['stats_file'], 'wb'))
            log.debug('stats len: %d' % len(stats))

            # write stats only now and then
            #if len(stats) % (15 * (60 / MONITOR_INTERVAL)) == 0:
            #    with open(config['monitoring']['stats_file'], 'w') as f:
            #        json.dump(stats, f)

        except Exception as e:
            log.error('An exception occurred in the monitoring thread:')
            log.exception(e)
