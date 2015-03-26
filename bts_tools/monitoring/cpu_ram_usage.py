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
from ..core import StatsFrame
import math
import logging

log = logging.getLogger(__name__)

# make sure we don't have huge plots that take forever to render
maxlen = 2000


def init_ctx(ctx, cfg):
    time_span = cfg['plots_time_span']
    desired_maxlen = int(time_span / ctx.time_interval)

    if desired_maxlen > maxlen:
        ctx.stable_time_interval = ctx.time_interval * (desired_maxlen / maxlen)
    else:
        ctx.stable_time_interval = ctx.time_interval

    ctx.stats = deque(maxlen=min(desired_maxlen, maxlen))


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

    # if our stats queue is full, only append now and then to reach approximately
    # the desired timespan while keeping the same number of items
    if ctx.time_interval != ctx.stable_time_interval and len(ctx.stats) == ctx.stats.maxlen:
        # note: we could have used round() instead of ceil() here but ceil()
        #       gives us the guarantee that the time span will be at least
        #       the one asked for, not less due to rounding effects
        ratio = math.ceil(ctx.stable_time_interval / ctx.time_interval)
        if ctx.loop_index % ratio == 0:
            ctx.stats.append(s)
    else:
        ctx.stats.append(s)
