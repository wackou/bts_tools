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

from .core import UnauthorizedError, RPCError, run, get_data_dir
from .process import bts_binary_running, bts_process
from . import core
from collections import defaultdict
from os.path import join, expanduser
import bitshares_delegate_tools.core # needed to be able to exec('raise bts.core.Exception')
import builtins                      # needed to be able to reraise builtin exceptions
import requests
import itertools
import json
import logging

log = logging.getLogger(__name__)

NON_CACHEABLE_METHODS = {'wallet_publish_price_feed',
                         'wallet_publish_feeds'}

_rpc_cache = defaultdict(dict)

def clear_rpc_cache():
    log.debug("------------ clearing rpc cache ------------")
    _rpc_cache.clear()


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
        if 'detail' in r['error']:
            raise RPCError(r['error']['detail'])
        else:
            raise RPCError(r['error']['message'])

    return r['result']


ALL_SLOTS = {}

class hashabledict(dict):
  def __key(self):
    return tuple(sorted(self.items()))

  def __hash__(self):
    return hash(self.__key())

  def __eq__(self, other):
    return self.__key() == other.__key()


class BTSProxy(object):
    def __init__(self, type, name, client=None, monitoring=None, rpc_port=None,
                 rpc_user=None, rpc_password=None, rpc_host=None, venv_path=None,
                 desired_number_of_connections=None, maximum_number_of_connections=None):
        self.type = type
        self.name = name
        self.monitoring = ([] if monitoring is None else
                           [monitoring] if not isinstance(monitoring, list)
                           else monitoring)
        if client:
            data_dir = get_data_dir(client)

            try:
                log.info('Loading RPC config for %s from %s' % (self.name, data_dir))
                rpc=json.load(open(expanduser(join(data_dir, 'config.json'))))['rpc']
                cfg_port = int(rpc['httpd_endpoint'].split(':')[1])
            except Exception:
                log.warning('Cannot read RPC config from %s' % data_dir)
                rpc = {}
                cfg_port = None
        else:
            rpc = {}
            cfg_port = None
        self.rpc_port = rpc_port or cfg_port or 0
        self.rpc_user = rpc_user or rpc.get('rpc_user') or ''
        self.rpc_password = rpc_password or rpc.get('rpc_password') or ''
        self.rpc_host = rpc_host or 'localhost'
        self.rpc_cache_key = (self.rpc_host, self.rpc_port)
        self.venv_path = venv_path
        self.desired_number_of_connections = desired_number_of_connections
        self.maximum_number_of_connections = maximum_number_of_connections

        if self.rpc_host == 'localhost':
            # direct json-rpc call
            def local_call(funcname, *args):
                # we want to avoid connecting to the client and block because
                # it is in a stopped state (eg: in gdb after having crashed)
                if not bts_binary_running(self):
                    raise RPCError('Connection aborted: BTS binary does not seem to be running')

                result = rpc_call('localhost', self.rpc_port,
                                  self.rpc_user, self.rpc_password,
                                  funcname, *args)
                return result
            self._rpc_call = local_call

        else:
            # do it over ssh using bts-rpc
            # FIXME: make sure the password doesn't come out in an ssh log or bash history
            def remote_call(funcname, *args):
                cmd = 'ssh %s "' % self.rpc_host
                if self.venv_path:
                    cmd += 'source %s/bin/activate; ' % self.venv_path
                #cmd += 'bts-rpc %s %s"' % (funcname, '"%s"' % '" "'.join(str(arg) for arg in args))
                cmd += 'bts-rpc %d %s %s %s %s 2>/dev/null"' % (self.rpc_port, self.rpc_user, self.rpc_password,
                                                    funcname, ' '.join(str(arg) for arg in args))

                result = run(cmd, io=True).stdout
                try:
                    result = json.loads(result)
                except:
                    log.error('Error while parsing JSON:')
                    log.error(result)
                    raise

                if 'error' in result:
                    # re-raise original exception
                    # FIXME: this should be done properly without exec, could
                    #        potentially be a security issue
                    log.debug('Received error in RPC result: %s(%s)'
                              % (result['type'], result['error']))

                    raise_exc = 'raise %s("%s")' % (result['type'], result['error'])
                    log.debug('EXEC: %s' % raise_exc)
                    exec(raise_exc)

                return result
            self._rpc_call = remote_call

        if core.config.get('profile', False):
            self._rpc_call = core.profile(self._rpc_call)

    def __getattr__(self, funcname):
        def call(*args, cached=True):
            return self.rpc_call(funcname, *args, cached=cached)
        return call

    def rpc_call(self, funcname, *args, cached=True):
        log.debug(('RPC call @ %s: %s(%s)' % (self.rpc_host, funcname, ', '.join(repr(arg) for arg in args))
                  + (' (cached = False)' if not cached else '')))
        args = (hashabledict(arg) if isinstance(arg, dict) else arg for arg in args)

        if cached and funcname not in NON_CACHEABLE_METHODS:
            if (funcname, args) in _rpc_cache[self.rpc_cache_key]:
                result = _rpc_cache[self.rpc_cache_key][(funcname, args)]
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
            if funcname not in NON_CACHEABLE_METHODS:
                _rpc_cache[self.rpc_cache_key][(funcname, args)] = e
                log.debug('  added exception %s in cache: %s' % (e.__class__, str(e)))
            raise

        if funcname not in NON_CACHEABLE_METHODS:
            _rpc_cache[self.rpc_cache_key][(funcname, args)] = result
            log.debug('  added result in cache')

        return result

    def clear_rpc_cache(self):
        try:
            log.debug('Clearing RPC cache for host: %s' % self.rpc_host)
            del _rpc_cache[self.rpc_cache_key]
        except KeyError:
            pass

    def status(self, cached=True):
        try:
            self.rpc_call('get_info', cached=cached)
            return 'online'

        except (requests.exceptions.ConnectionError, # http connection refused
                RPCError, # bts binary is not running, no connection attempted
                RuntimeError): # host is down, ssh doesn't work
            return 'offline'

        except UnauthorizedError:
            return 'unauthorized'

        except Exception as e:
            log.exception(e)
            return 'error'

    def is_online(self, cached=True):
        return self.status(cached=cached) == 'online'

    def process(self):
        return bts_process(self)

    def bts_type(self):
        blockchain_name = self.about()['blockchain_name']
        if blockchain_name == 'BitShares X':
            return 'btsx'
        elif blockchain_name == 'KeyID':
            return 'dns'
        return 'unknown'

    def is_active(self, delegate):
        active_delegates = [d['name'] for d in self.blockchain_list_delegates(0, 101)]
        return delegate in active_delegates


    def get_streak(self, cached=True):
        if self.type != 'delegate':
            # only makes sense to call get_streak on delegate nodes
            return False, 1

        try:
            global ALL_SLOTS
            # get about the last 1000 blocks from us
            # this could possibly be optimized by first getting, say, 50 blocks, and if
            # they are all the same, then we could get a much bigger chunk
            if self.name not in ALL_SLOTS:
                # first time, get all slots from the delegate and cache them
                ALL_SLOTS[self.name] = self.blockchain_get_delegate_slot_records(self.name, 1, 100000,
                                                                                 cached=cached)
                log.debug('Got all %d slots for delegate %s' % (len(ALL_SLOTS[self.name]), self.name))
            else:
                # next time, only get last 10 slots and update our local copy
                log.debug('Getting last 10 slots for delegate %s' % self.name)
                for slot in self.blockchain_get_delegate_slot_records(self.name):
                    if slot not in ALL_SLOTS[self.name][-10:]:
                        ALL_SLOTS[self.name].append(slot)

            slots = ALL_SLOTS[self.name]
            if not slots:
                return True, 0
            streak = itertools.takewhile(lambda x: (type(x['block_id']) is type(slots[-1]['block_id'])), reversed(slots))
            return slots[-1]['block_id'] is not None, len(list(streak))

        except Exception as e:
            # can fail with RPCError when delegate has not been registered yet
            log.error('%s: get_streak() failed with: %s(%s)' % (self.name, type(e), e))
            log.exception(e)
            return False, -1




nodes = []
main_node = None


def load_nodes():
    global nodes, main_node
    nodes = [BTSProxy(**node) for node in core.config['nodes']]
    main_node = nodes[0]


def unique_node_clients():
    global nodes
    sort_func = lambda n: n.rpc_cache_key
    for (host, port), gnodes in itertools.groupby(sorted(nodes, key=sort_func), sort_func):
        yield (host, port), list(gnodes)


def client_instances():
    """return a list of triples (hostname, [node names], node_instance)"""
    global nodes
    for (host, port), gnodes in unique_node_clients():
        yield ('%s:%d' % (host, port), [n.name for n in gnodes], gnodes[0])


