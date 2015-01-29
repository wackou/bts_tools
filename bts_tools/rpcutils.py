#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
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

from .core import UnauthorizedError, RPCError, run, get_data_dir, get_bin_name
from .process import bts_binary_running, bts_process
from . import core
from collections import defaultdict, deque
from os.path import join, expanduser
from dogpile.cache import make_region
import bts_tools.core  # needed to be able to exec('raise bts.core.Exception')
import builtins        # needed to be able to reraise builtin exceptions
import importlib
import requests
import itertools
import json
import re
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
        self.bin_name = get_bin_name(client or 'bts')
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
                    log.debug('Received error in RPC result: %s(%s)'
                              % (result['type'], result['error']))
                    try:
                        exc_module, exc_class = result['type'].rsplit('.', 1)
                    except ValueError:
                        exc_module, exc_class = 'builtins', result['type']

                    exc_class = getattr(importlib.import_module(exc_module), exc_class)
                    raise exc_class(result['error'])

                return result
            self._rpc_call = remote_call

        if core.config.get('profile', False):
            self._rpc_call = core.profile(self._rpc_call)

        # get a special "smart" cache for slots as it is a very expensive call
        self._slot_cache = make_region().configure('dogpile.cache.memory')

    def __getattr__(self, funcname):
        if funcname.startswith('_'):
            raise AttributeError
        def call(*args, cached=True):
            return self.rpc_call(funcname, *args, cached=cached)
        return call

    def rpc_call(self, funcname, *args, cached=True):
        log.debug(('RPC call @ %s: %s(%s)' % (self.rpc_host, funcname, ', '.join(repr(arg) for arg in args))
                  + (' (cached = False)' if not cached else '')))
        args = tuple(hashabledict(arg) if isinstance(arg, dict) else arg for arg in args)

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
        try:
            return self._bts_type
        except AttributeError:
            blockchain_name = self.about()['blockchain_name']
            if blockchain_name == 'BitShares':
                self._bts_type = 'bts'
            elif blockchain_name == 'DevShares':
                self._bts_type = 'dvs'
            elif blockchain_name == 'PTS':
                self._bts_type = 'pts'
            elif blockchain_name == 'Sparkle':
                self._bts_type = 'sparkle'
            else:
                return 'unknown'
        return self._bts_type

    def is_active(self, delegate):
        active_delegates = [d['name'] for d in self.blockchain_list_delegates(0, 101)]
        return delegate in active_delegates

    def get_last_slots(self):
        """Return the last delegate slots, and cache this until at least the next block
        production time of the wallet."""
        new_api = self.bts_type() in {'bts', 'dvs'} and self.get_info()['client_version'] >= '0.6'

        def _get_slots():
            # make sure we get enough slots to get them all up to our latest, even if there
            # are a lot of missed blocks by other delegates
            if new_api:
                slots = self.blockchain_get_delegate_slot_records(self.name, 5)
            else:
                slots = self.blockchain_get_delegate_slot_records(self.name, -500, 100)
            # non-producing wallets can afford to have a 1-min time resolution for this
            next_production_time = self.get_info()['wallet_next_block_production_time'] or 60
            # make it +1 to ensure we produce the block first, and then peg the CPU
            # Note: with bts>=0.6, this shouldn't be such a time consuming operation anymore
            self._slot_cache.expiration_time = next_production_time + 1
            return slots
        return self._slot_cache.get_or_create('slots', _get_slots)

    def api_version(self):
        return re.search(r'[\d.]+', self.get_info()['client_version']).group()

    def get_streak(self, cached=True):
        if self.type != 'delegate':
            # only makes sense to call get_streak on delegate nodes
            return False, 1

        # TODO: remove this once all clients (PTS included) use the new api
        new_api = self.bts_type() in {'bts', 'dvs'} and self.api_version() >= '0.6'

        try:
            global ALL_SLOTS
            key = (self.bts_type(), self.name)
            if key not in ALL_SLOTS:
                # first time, get all slots from the delegate and cache them
                if new_api:
                    slots = self.blockchain_get_delegate_slot_records(self.name, 10000, cached=cached)
                    # workaround for https://github.com/BitShares/bitshares/issues/1289
                    delegate_id = slots[0]['index']['delegate_id'] if slots else None
                    ALL_SLOTS[key] = deque(s for s in slots if s['index']['delegate_id'] == delegate_id)
                else:
                    slots = self.blockchain_get_delegate_slot_records(self.name, 1, 1000000, cached=cached)
                    ALL_SLOTS[key] = slots
                log.debug('Got all %d slots for delegate %s' % (len(ALL_SLOTS[key]), self.name))
            else:
                # next time, only get last slots and update our local copy
                log.debug('Getting last slots for delegate %s' % self.name)
                if new_api:
                    for slot in reversed(self.get_last_slots()):
                        if slot not in itertools.islice(ALL_SLOTS[key], 0, 10):
                            ALL_SLOTS[key].appendleft(slot)
                else:
                    for slot in self.get_last_slots():
                        if slot not in ALL_SLOTS[key][-10:]:
                            ALL_SLOTS[key].append(slot)

            slots = ALL_SLOTS[key]
            if not slots:
                return True, 0
            if new_api:
                latest = slots[0]
                rslots = slots
            else:
                latest = slots[-1]
                rslots = reversed(slots)
            streak = itertools.takewhile(lambda x: (type(x['block_id']) is type(latest['block_id'])), rslots)
            return latest['block_id'] is not None, len(list(streak))

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


