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

#from flask_sqlalchemy import SQLAlchemy
#from flask_security import Security
from os.path import join, dirname, expanduser
from collections import namedtuple
from subprocess import Popen, PIPE
import requests
import sys
import json
import itertools
import logging

log = logging.getLogger(__name__)

platform = sys.platform
if platform.startswith('linux'):
    platform = 'linux'

# load config
config = json.load(open(join(dirname(__file__), 'config.json')))

if platform not in config:
    raise OSError('OS not supported yet, please submit a patch :)')

# expand '~' in path names to the user's home dir
for attr, path in config[platform].items():
    config[platform][attr] = expanduser(path)


IOStream = namedtuple('IOStream', 'status, stdout, stderr')

def _run(cmd, io=False):
    if isinstance(cmd, list):
        cmd = cmd[0] + ' "' + '" "'.join(cmd[1:]) + '"'
    print('-'*80)
    print('running command: %s\n' % cmd)
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


CACHED_RPC_CALLS = ['get_info']

is_online = False

_rpc_cache = {}

class UnauthorizedError(Exception):
    pass

def rpc_call(host, port, user, password,
             funcname, *args, cached=False):
    url = "http://%s:%d/rpc" % (host, port)
    headers = {'content-type': 'application/json'}

    payload = {
        "method": funcname,
        "params": args,
        "jsonrpc": "2.0",
        "id": 0,
    }

    response = requests.post(url,
                             auth=(user, password),
                             data=json.dumps(payload),
                             headers=headers)

    global is_online
    is_online = True

    log.debug('RPC received: %s %s' % (type(response), response))

    if response.status_code == 401:
        raise UnauthorizedError()

    return response.json()['result']


class BTSProxy(object):
    def __init__(self, host, port, user, password, venv_path=None):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.venv_path = venv_path

        if self.host == 'localhost' or self.host == '127.0.0.1':
            # direct json-rpc call
            def local_call(funcname, *args):
                result = rpc_call(self.host, self.port,
                                  self.user, self.password,
                                  funcname, *args)
                return result
            self._rpc_call = local_call

        else:
            # do it over ssh using bts-rpc
            def remote_call(funcname, *args):
                cmd = 'ssh %s "' % self.host
                if self.venv_path:
                    cmd += 'source %s/bin/activate; ' % self.venv_path
                cmd += 'bts-rpc %s %s"' % (funcname, ' '.join(str(arg) for arg in args))

                result = json.loads(run(cmd, io=True).stdout)
                if 'error' in result:
                    # TODO: raise exception
                    pass

                return result
            self._rpc_call = remote_call

    def is_online(self):
        try:
            self._rpc_call('about')
            return True

        except requests.exceptions.ConnectionError:
            return False

    def __getattr__(self, funcname):
        def call(*args, cached=False):
            if cached and funcname in CACHED_RPC_CALLS:
                if (self.host, funcname, args) in _rpc_cache:
                    return _rpc_cache[(self.host, funcname, args)]

            result = self._rpc_call(funcname, *args)

            if funcname in CACHED_RPC_CALLS:
                _rpc_cache[(self.host, funcname, args)] = result

            return result

        return call


nodes = [ BTSProxy(host=node['host'],
                   port=node['rpc_port'],
                   user=node['rpc_user'],
                   password=node['rpc_password'],
                   venv_path=node.get('venv_path', None))
          for node in config['nodes'] ]

rpc = nodes[0]

#### util functions we want to be able to access easily, such as in templates

def delegate_name():
    # FIXME: should parse my accounts to know the actual delegate name
    return 'wackou-delegate'


def get_streak():
    slots = rpc.blockchain_get_delegate_slot_records(delegate_name())[::-1]
    streak = itertools.takewhile(lambda x: (x['block_produced'] == slots[0]['block_produced']), slots)
    return slots[0]['block_produced'], len(list(streak))
