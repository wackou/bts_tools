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

import os.path
import psutil
import logging

log = logging.getLogger(__name__)


def bts_process():
    #log.debug('find bts binary')
    # find bitshares process
    try:
        p = next(filter(lambda p: 'bitshares_client' in p.name(),
                        psutil.process_iter()))
        return p
    except StopIteration:
        return None


def bts_binary_running():
    """Return whether an instance of the bts binary could be found that is
    running or in a runnable state.
    """
    p = bts_process()
    if p is not None:
        return p.status() not in {psutil.STATUS_STOPPED,
                                  psutil.STATUS_TRACING_STOP,
                                  psutil.STATUS_ZOMBIE,
                                  psutil.STATUS_DEAD}
    return False


def binary_description():
    """Return a human readable version description of the running binary,
    either tag version of git revision.
    Return an empty string if no running BTS client could be found.
    """
    p = bts_process()
    if p is None:
        return ''
    name = os.path.realpath(p.cmdline()[0])
    if '_v' in name: # weak check for detecting tags...
        return name[name.index('_v')+1:]
    return name.split('bitshares_client_')[1]

