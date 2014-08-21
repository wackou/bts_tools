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

from .core import UnauthorizedError, RPCError, run, config, delegate_name
from .process import bts_binary_running
from collections import defaultdict
import requests
import itertools
import json
import logging

log = logging.getLogger(__name__)


_rpc_cache = defaultdict(dict)

def clear_rpc_cache():
    log.debug("------------ clearing rpc cache ------------")
    _rpc_cache.clear()


def rpc_call(host, port, user, password,
             funcname, *args):
    if host == 'localhost' or host == '127.0.0.1':
        # if host == 'localhost', we want to avoid connecting to it and blocking
        # because it is in a stopped state (for example, in gdb after having crashed)
        if not bts_binary_running():
            raise ConnectionError('Connection aborted: BTS binary does not seem to be running')

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
        if 'detail' in r['error']:
            raise RPCError(r['error']['detail'])
        else:
            raise RPCError(r['error']['message'])

    return r['result']


class BTSProxy(object):
    def __init__(self, host, port, user, password, venv_path=None):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.venv_path = venv_path

        if self.host == 'localhost':
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
                    log.debug('Received error in RPC result: %s(%s)'
                              % (result['type'], result['error']))
                    exec('raise %s("%s")' % (result['type'], result['error']))

                return result
            self._rpc_call = remote_call

    def __getattr__(self, funcname):
        def call(*args, cached=True):
            return self.rpc_call(funcname, *args, cached=cached)
        return call

    def rpc_call(self, funcname, *args, cached=True):
        log.debug(('RPC call @ %s: %s(%s)' % (self.host, funcname, ', '.join(repr(arg) for arg in args))
                  + (' (cached = False)' if not cached else '')))
        if cached:
            if (funcname, args) in _rpc_cache[self.host]:
                result = _rpc_cache[self.host][(funcname, args)]
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
            _rpc_cache[self.host][(funcname, args)] = e
            log.debug('  added exception %s in cache' % e.__class__)
            raise

        _rpc_cache[self.host][(funcname, args)] = result
        log.debug('  added result in cache')

        return result

    def clear_rpc_cache(self):
        try:
            log.debug('Clearing RPC cache for host: %s' % self.host)
            del _rpc_cache[self.host]
        except KeyError:
            pass

    def status(self, cached=True):
        try:
            self.rpc_call('get_info', cached=cached)
            return 'online'

        except (requests.exceptions.ConnectionError, # http connection refused
                ConnectionError, # bts binary is not running, no connection attempted
                RuntimeError): # host is down, ssh doesn't work
            return 'offline'

        except UnauthorizedError:
            return 'unauthorized'

    def is_online(self, cached=True):
        return self.status(cached=cached) == 'online'

    def get_streak(self, cached=True):
        try:
            slots = self.blockchain_get_delegate_slot_records(delegate_name(),
                                                              cached=cached)[::-1]
            if not slots:
                return True, 0
            streak = itertools.takewhile(lambda x: (x['block_produced'] == slots[0]['block_produced']), slots)
            return slots[0]['block_produced'], len(list(streak))

        except:
            # can fail with RPCError when delegate has not been registered yet
            return False, -1



nodes = [ BTSProxy(host=node['host'],
                   port=node['rpc_port'],
                   user=node.get('rpc_user', None),
                   password=node.get('rpc_password', None),
                   venv_path=node.get('venv_path', None))
          for node in config['nodes'] ]

main_node = nodes[0]

