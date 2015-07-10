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

from datetime import datetime
from collections import deque
from ..core import StatsFrame, GlobalStatsFrame
import psutil
import math
import logging

log = logging.getLogger(__name__)

# make sure we don't have huge plots that take forever to render
maxlen = 2000

# the total cpu usage can only be measured in a single thread (1 per client), so
# use this variable to indicate which of the clients (identified by their context)
# needs to measure it
cpu_total_ctx = None

def init_ctx(node, ctx, cfg):
    global cpu_total_ctx

    time_span = cfg['plots_time_span']
    desired_maxlen = int(time_span / ctx.time_interval)

    if desired_maxlen > maxlen:
        ctx.stable_time_interval = ctx.time_interval * (desired_maxlen / maxlen)
    else:
        ctx.stable_time_interval = ctx.time_interval

    ctx.stats = deque(maxlen=min(desired_maxlen, maxlen))

    if node.rpc_host == 'localhost' and cpu_total_ctx is None:
        # first monitoring thread that initializes its context gets to be
        # the one that will fill in the global cpu values
        cpu_total_ctx = ctx
        ctx.global_stats = deque(maxlen=min(desired_maxlen, maxlen))


def is_valid_node(node):
    return True


def monitor(node, ctx, cfg):
    # only monitor cpu and network if we are monitoring localhost
    if node.rpc_host == 'localhost':
        p = node.process()
        if p is not None:
            s = StatsFrame(cpu=p.cpu_percent(),
                           mem=p.memory_info().rss,
                           connections=ctx.info['network_num_connections'],
                           timestamp=datetime.utcnow())
        else:
            s = StatsFrame(cpu=0, mem=0, connections=0, timestamp=datetime.utcnow())

    else:
        s = StatsFrame(cpu=0, mem=0, connections=0, timestamp=datetime.utcnow())

    def record_values():
        if ctx == cpu_total_ctx:
            gs = GlobalStatsFrame(cpu_total=psutil.cpu_percent() * psutil.cpu_count(),
                                  timestamp=datetime.utcnow())
            ctx.global_stats.append(gs)
        ctx.stats.append(s)

    # if our stats queue is full, only append now and then to reach approximately
    # the desired timespan while keeping the same number of items
    # FIXME: this decimates the data without proper downsampling (eg: averaging)
    if ctx.time_interval != ctx.stable_time_interval and len(ctx.stats) == ctx.stats.maxlen:
        # note: we could have used round() instead of ceil() here but ceil()
        #       gives us the guarantee that the time span will be at least
        #       the one asked for, not less due to rounding effects
        ratio = math.ceil(ctx.stable_time_interval / ctx.time_interval)
        if ctx.loop_index % ratio == 0:
            record_values()
    else:
        record_values()
