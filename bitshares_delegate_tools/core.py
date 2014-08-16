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
import sys
import json
import itertools
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
StatsFrame = namedtuple('StatsFrame', 'cpu, mem, connections, timestamp')


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

