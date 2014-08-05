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

from os.path import join, dirname, expanduser
from collections import namedtuple
from subprocess import Popen, PIPE
from datetime import datetime
import sys
import json
import itertools
import time
import psutil
import logging

log = logging.getLogger(__name__)

platform = sys.platform
if platform.startswith('linux'):
    platform = 'linux'

def load_config():
    try:
        config_file = join(dirname(__file__), 'config.json')
        config_contents = open(config_file).read()
    except:
        log.error('Could not read config file: %s' % config_file)
        raise

    try:
        config = json.loads(config_contents)
    except:
        log.error('-'*100)
        log.error('Config file contents is not a valid JSON object:')
        log.error(config_contents)
        log.error('-'*100)
        raise

    return config

config = load_config()
env = config['env'][config['env']['active']]

if platform not in env:
    raise OSError('OS not supported yet, please submit a patch :)')

# expand '~' in path names to the user's home dir
for attr, path in env[platform].items():
    env[platform][attr] = expanduser(path)

# setup logging levels from config file
for name, level in config.get('logging', {}).items():
    logging.getLogger(name).setLevel(getattr(logging, level))


IOStream = namedtuple('IOStream', 'status, stdout, stderr')


def _run(cmd, io=False):
    if isinstance(cmd, list):
        cmd = cmd[0] + ' "' + '" "'.join(cmd[1:]) + '"'
    log.debug('SHELL: running command: %s' % cmd)
    if io:
        p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        if sys.version_info[0] >= 3:
            stdout, stderr = (str(stdout, encoding='utf-8'),
                              str(stderr, encoding='utf-8'))
        return IOStream(p.returncode, stdout, stderr)

    else:
        p = Popen(cmd, shell=True)
        p.communicate()
        return IOStream(p.returncode, None, None)


def run(cmd, io=False):
    r = _run(cmd, io)
    if r.status != 0:
        raise RuntimeError('Failed running: %s' % cmd)
    return r


class UnauthorizedError(Exception):
    pass


class RPCError(Exception):
    pass


#### util functions we want to be able to access easily, such as in templates


def delegate_name():
    # TODO: should parse my accounts to know the actual delegate name
    return config['delegate']


def get_streak():
    from . import rpcutils as rpc
    try:
        slots = rpc.main_node.blockchain_get_delegate_slot_records(delegate_name())[::-1]
        if not slots:
            return True, 0
        streak = itertools.takewhile(lambda x: (x['block_produced'] == slots[0]['block_produced']), slots)
        return slots[0]['block_produced'], len(list(streak))

    except:
        # can fail with RPCError when delegate has not been registered yet
        return False, -1


def monitoring_thread():
    from .cmdline import send_notification
    from .rpcutils import nodes

    for n in nodes:
        if n.host == config['monitoring']['host']:
            node = n
            break
    else:
        raise ValueError('"%s" is not a valid host name. Available: %s' % (config['monitor_host'], ', '.join(n.host for n in nodes)))

    MONITOR_INTERVAL = 10 # in seconds
    last_state = None
    connection_status = None

    stats = []

    while True:
        time.sleep(MONITOR_INTERVAL)
        #log.debug('-------- Monitoring status of the BitShares client --------')
        node.clear_rpc_cache()

        try:
            if node.is_online():
                if last_state == 'offline':
                    send_notification('Delegate just came online!')
                last_state = 'online'
            else:
                if last_state == 'online':
                    send_notification('Delegate just went offline...', alert=True)
                last_state = 'offline'
                continue

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

            # find bitshares process
            p = next(filter(lambda p: 'bitshares_client' in p.name(),
                            psutil.process_iter()))

            s = dict(cpu=p.cpu_percent(interval=1), # note: this blocks for 1 second
                     mem=p.memory_info().rss,
                     conn=info['network_num_connections'],
                     timestamp=datetime.utcnow().isoformat())

            stats.append(s)

            # write stats only now and then
            if len(stats) % (15 * (60 / MONITOR_INTERVAL)) == 0:
                with open(config['monitoring']['stats_file'], 'w') as f:
                    json.dump(stats, f)

        except Exception as e:
            log.error('An exception occurred in the monitoring thread:')
            log.exception(e)
