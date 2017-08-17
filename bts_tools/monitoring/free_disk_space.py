#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
# Copyright (c) 2016 Nicolas Wack <wackou@gmail.com>
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

from ..notification import send_notification
from ..monitor import StableStateMonitor
from ..core import run, BTS_TOOLS_CONFIG_FILE
import logging

log = logging.getLogger(__name__)


# def find_mount_point(path):
#     path = os.path.abspath(path)
#     while not os.path.ismount(path):
#         path = os.path.dirname(path)
#     return path


def to_int(s):
    if s[-1].lower() == 'g':
        return int(s[:-1]) * 1024 * 1024 * 1024
    elif s[-1].lower() == 'm':
        return int(s[:-1]) * 1024 * 1024
    elif s[-1].lower() == 'k':
        return int(s[:-1]) * 1024
    else:
        return int(s)


def free_disk_space(filename):
    lines = run('df "{}"'.format(filename), capture_io=True, verbose=False).stdout.split('\n')
    block_size = to_int(lines[0].split()[1].split('-')[0])
    device, size, used, available, *other = lines[1].split()
    return int(available) * block_size



def init_ctx(node, ctx, cfg):
    ctx.enough_space = StableStateMonitor(1)


def is_valid_node(node):
    return True


def monitor(node, ctx, cfg):
    free_space = free_disk_space(BTS_TOOLS_CONFIG_FILE)
    required = to_int(cfg['min_required_space'])

    if free_space < required:
        ctx.enough_space.push(False)
        if ctx.enough_space.just_changed():
            msg = 'there are now fewer than {} bytes free on the hard drive'.format(cfg['min_required_space'])
            send_notification(ctx.nodes, msg, alert=True)

    else:
        ctx.enough_space.push(True)
        if ctx.enough_space.just_changed():
            msg = 'there are now more than {} bytes free on the hard drive'.format(cfg['min_required_space'])
            send_notification(ctx.nodes, msg)

