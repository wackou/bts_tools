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

from os.path import join, dirname, expanduser, exists
from collections import namedtuple
from subprocess import Popen, PIPE
import requests
import sys
import json
import itertools
import time
import threading
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
        log.error(config)
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


_rpc_cache = {}


def clear_rpc_cache():
    log.debug("------------ clearing rpc cache ------------")
    global _rpc_cache
    _rpc_cache = {}


class UnauthorizedError(Exception):
    pass


class RPCError(Exception):
    pass


def rpc_call(host, port, user, password,
             funcname, *args):
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

    log.debug('  received: %s %s' % (type(response), response))

    if response.status_code == 401:
        raise UnauthorizedError()

    r = response.json()

    if 'error' in r:
        raise RPCError(r['error']['detail'])

    return r['result']


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

                result = run(cmd, io=True).stdout
                try:
                    result = json.loads(result)
                except:
                    print('-'*40 + ' Error while parsing JSON: ' + '-'*40)
                    print(result)
                    print('-'*108)
                    raise

                if 'error' in result:
                    # re-raise original exception
                    # FIXME: this should be done properly without exec, could
                    #        potentially be a security issue
                    exec('raise %s("%s")' % (result['type'], result['error']))

                return result
            self._rpc_call = remote_call

    def rpc_call(self, funcname, *args, cached=True):
        log.debug(('RPC call @ %s: %s(%s)' % (self.host, funcname, ', '.join(repr(arg) for arg in args))
                  + ' (cached = False)' if cached == False else ''))
        if cached:
            if (self.host, funcname, args) in _rpc_cache:
                result = _rpc_cache[(self.host, funcname, args)]
                if isinstance(result, Exception):
                    log.debug('  using cached exception %s' % result.__class__)
                    raise result
                else:
                    log.debug('  using cached result')
                    return result

        try:
            result = self._rpc_call(funcname, *args)
        except Exception as e:
            # also cache when exceptions are raised
            _rpc_cache[(self.host, funcname, args)] = e
            log.debug('  added exception %s in cache' % e.__class__)
            raise

        _rpc_cache[(self.host, funcname, args)] = result
        log.debug('  added result in cache')

        return result

    def status(self, cached=True):
        try:
            self.rpc_call('about', cached=cached)
            return 'online'

        except requests.exceptions.ConnectionError:
            return 'offline'

        except UnauthorizedError:
            return 'unauthorized'

    def is_online(self, cached=True):
        return self.status(cached=cached) == 'online'

    def __getattr__(self, funcname):
        def call(*args, cached=True):
            return self.rpc_call(funcname, *args, cached=cached)
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
    # TODO: should parse my accounts to know the actual delegate name
    return config['delegate']


def get_streak():
    try:
        slots = rpc.blockchain_get_delegate_slot_records(delegate_name())[::-1]
        if not slots:
            return True, 0
        streak = itertools.takewhile(lambda x: (x['block_produced'] == slots[0]['block_produced']), slots)
        return slots[0]['block_produced'], len(list(streak))

    except:
        # can fail with RPCError when delegate has not been registered yet
        return False, -1


def check_online_thread():
    from bitshares_delegate_tools.cmdline import send_notification
    for n in nodes:
        if n.host == config['monitor_host']:
            node = n
            break
    else:
        raise ValueError('"%s" is not a valid host name. Available: %s' % (config['monitor_host'], ', '.join(n.host for n in nodes)))

    last_state = 'offline'

    while True:
        if node.is_online(cached=False):
            log.debug('---- NODE ONLINE ----')
            last_state = 'online'
        else:
            log.debug('**** NODE OFFLINE ****')
            if last_state == 'online':
                send_notification('Delegate %s just went offline...' % config['monitor_host'])
            last_state = 'offline'

        time.sleep(10)

