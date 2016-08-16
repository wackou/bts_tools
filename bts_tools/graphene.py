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

from . import core
from datetime import datetime
from functools import partial
from autobahn.asyncio.websocket import WebSocketClientProtocol, WebSocketClientFactory
from collections import defaultdict
from concurrent.futures import Future
from contextlib import suppress
import functools
import threading
import json
import time
import asyncio
import logging

log = logging.getLogger(__name__)


# export bitshares 0.9.x balance keys
def print_balances(n):
    for account, addresses in n.wallet_account_balance_ids():
        print('\nAccount: %s\n' % account)
        keys = set()
        for address in addresses:
            b = n.blockchain_get_balance(address)
            balance = b['balance']
            owner = b['condition']['data']['owner']
            #print(address, balance, owner)
            key = n.wallet_dump_private_key(owner)
            keys.add(key)
        print('\n\nTO IMPORT: keys = ["%s"]\n\n' % '", "'.join(keys))


# Note: this is only an enum, it does not correspond to the actual api id
DATABASE_API = 0
LOGIN_API = 1
NETWORK_API = 2
NETWORK_BROADCAST_API = 3


def api_name(api_id):
    if api_id == DATABASE_API:
        return 'database_api'
    elif api_id == LOGIN_API:
        return 'login_api'
    elif api_id == NETWORK_API:
        return 'network_node_api'
    elif api_id == NETWORK_BROADCAST_API:
        return 'network_broadcast_api'
    else:
        log.warning('unknown api id: {}'.format(api_id))
        return '??'


_event_loops = {}

# FIXME: this would probably benefit from being integrated
#        directly in each node's rpc_cache
_ws_rpc_cache = defaultdict(dict)

# dict of active monitoring protocols
_monitoring_protocols = {}


def ws_rpc_call(host, port, api, method, *args):
    cached = False  # TODO: decide whether to maintain cached=True
    if not cached:
        result = Future()
        try:
            loop = _event_loops[(host, port)]
        except KeyError as e:
            raise core.RPCError('Connection aborted: Websocket event loop for {}:{} not available yet'.format(host, port)) from e
        protocol = _monitoring_protocols[(host, port)]

        loop.call_soon_threadsafe(functools.partial(protocol.rpc_call, api, method, *args, result=result))
        try:
            return result.result(timeout=10)
        except TimeoutError:
            log.warning('timeout while calling {} {}({})'.format(api, method, ', '.join(args)))
            return None

    # else: check whether it is in the cache
    key = (api, method,  args)
    try:
        result = _ws_rpc_cache[(host, port)][key]
        return result['result']
    except KeyError:
        # FIXME: distinguish when key is not in or when 'result' is not in
        #        (ie: deserialize exception if any)
        raise core.RPCError('{}: {}({}) not in websocket cache'.format(api, method, ', '.join(args)))


class MonitoringProtocol(WebSocketClientProtocol):
    def __init__(self, type, witness_host, witness_port, witness_user, witness_passwd):
        super().__init__()
        self.type = type
        self.host = witness_host
        self.port = witness_port
        self.user = witness_user
        self.passwd = witness_passwd
        self.request_id = 0
        self.request_map = {}
        _monitoring_protocols[(witness_host, witness_port)] = self
        if type == 'steem':
            _ws_rpc_cache[(witness_host, witness_port)] = {'login_api': 1}
        else:
            _ws_rpc_cache[(witness_host, witness_port)] = {'database_api': 0, 'login_api': 1}


    def rpc_call(self, api, method, *args, result=None):
        """result should be a Future instance"""
        self.request_id += 1
        # TODO: convert args where required to hashable_dict (see: btsproxy.rpc_cache implementation)
        # get actual api id
        real_api = _ws_rpc_cache[(self.host, self.port)].get(api_name(api))
        if real_api is None:
            log.debug('Not calling api: {} - unauthorized access to {} api'.format(method, api_name(api)))
            return
        call_params = (real_api, method, args)
        self.request_map[self.request_id] = (result, call_params)
        payload = {'jsonrpc': '2.0',
                   'id': self.request_id,
                   'method': 'call',
                   'params': call_params}
        log.debug('rpc call: {}'.format(payload))
        self.sendMessage(json.dumps(payload).encode('utf8'))

    def onConnect(self, response) :
        log.debug("Server connected: {0}".format(response.peer))
        # login, authenticate
        self.rpc_call(LOGIN_API, 'login', self.user, self.passwd)
        if self.type == 'steem':
            self.rpc_call(LOGIN_API, 'get_api_by_name', 'database_api')
            self.rpc_call(LOGIN_API, 'get_api_by_name', 'network_node_api')
            self.rpc_call(LOGIN_API, 'get_api_by_name', 'network_broadcast_api')  # only needed for feed_publisher role
        else:
            self.rpc_call(LOGIN_API, 'network_node')

    def onMessage(self, payload, isBinary):
        res = json.loads(payload.decode('utf8'))
        log.debug('Got response for request id {}: {}'.format(res['id'], json.dumps(res, indent=4)))
        result, (api, method, args) = self.request_map.pop(res['id'])
        args = tuple(core.hashabledict(arg) if isinstance(arg, dict) else arg for arg in args)
        cache = _ws_rpc_cache[(self.host, self.port)]

        # FIXME: what if res raises an exception?
        p = {'result': res['result'] if 'result' in res else None,
             'server_response': res,
             'last_updated': datetime.utcnow()}
        # if we gave a future, return it, otherwise put the result in the cache
        if result is not None:
            result.set_result(p['result'])
        else:
            cache[(api, method, args)] = p

        if (api, method) == (LOGIN_API, 'network_node'):
            api_id = p['result']
            if api_id is not None:
                cache['network_node_api'] = api_id
                log.info('Granted access to network api on {}:{}'.format(self.host, self.port))
            else:
                log.warning('Refused access to network api. Make sure to set your user/password properly!')

        if (api, method) == (LOGIN_API, 'get_api_by_name'):
            api_id = p['result']
            if api_id is not None:
                log.info('Granted access to {} api on {}:{}'.format(args[0], self.host, self.port))
                cache[args[0]] = api_id
            else:
                log.warning('Refused access to {} api on {}:{}. Make sure to set your user/password properly!'.format(args[0], self.host, self.port))

        if not self.request_map:
            log.debug('received all responses to pending requests')

    def onClose(self, wasClean, code, reason):
        log.debug("WebSocket connection closed: {0}".format(reason))
        log.warning("WebSocket connection closed: {0}".format(reason))

    def connection_lost(self, exc):
        log.debug('connection closed, stopping run loop')
        self.factory.loop.stop()


def run_monitoring(type, host, port, user, passwd):
    log.info('Starting witness websocket monitoring on {}:{}'.format(host, port))

    while True:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _event_loops[(host, port)] = loop
        log.debug('new event loop: {}'.format(loop))
        log.debug('in thread {}'.format(threading.current_thread().name))

        factory = WebSocketClientFactory("ws://{}:{:d}".format(host, port))
        factory.protocol = partial(MonitoringProtocol, type, host, port, user, passwd)

        try:
            coro = loop.create_connection(factory, host, port)
            loop.run_until_complete(coro)
            log.info('Successfully connected to witness on {}:{}'.format(host, port))
            loop.run_forever()
            log.warning('Lost connection to witness node on {}:{}'.format(host, port))
        except KeyboardInterrupt:
            log.info('Run loop exited manually (ctrl-C)')
        except OSError:
            log.debug('WebSocket connection refused to {}:{}'.format(host, port))
        finally:
            loop.close()

        with suppress(KeyError):
            del _monitoring_protocols[(host, port)]
        del _event_loops[(host, port)]

        nseconds = core.config['monitoring']['monitor_time_interval']
        time.sleep(nseconds) # wait some time before trying to reconnect
