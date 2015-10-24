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


# FIXME: these variables need to be set per host, not global
DATABASE_API = 1
NETWORK_API = None  # to be fetched upon connecting

def api_name(api_id):
    if api_id == DATABASE_API:
        return 'database'
    elif api_id == NETWORK_API:
        return 'network'
    else:
        return '??'


# FIXME: this should be per-host, and would probably benefit from being integrated
#        directly in each node's rpc_cache
_ws_rpc_cache = defaultdict(dict)

def ws_rpc_call(host, port, api, method, *args):
    key = (api, method,  args)
    try:
        result = _ws_rpc_cache[(host, port)][key]
        return result['result']
    except KeyError:
        # FIXME: distinguish when key is not in or when 'result' is not in
        #        (ie: deserialize exception if any)
        raise RuntimeError('{}: {}({}) not in websocket cache'.format(api, method, ', '.join(args)))


class MonitoringProtocol(WebSocketClientProtocol):
    def __init__(self, witness_host, witness_port, witness_user, witness_passwd):
        super().__init__()
        self.host = witness_host
        self.port = witness_port
        self.user = witness_user
        self.passwd = witness_passwd
        self.request_id = 0
        self.request_map = {}

    def rpc_call(self, api, method, *args):
        self.request_id += 1
        # TODO: convert args where required to hashable_dict (see: btsproxy.rpc_cache implementation)
        call_params = (api, method, args)
        self.request_map[self.request_id] = call_params
        payload = {'jsonrpc': '2.0',
                   'id': self.request_id,
                   'method': 'call',
                   'params': call_params} # TODO: use list(call_params)?? (if don't remember what this is for, then delete this comment)
        log.debug('rpc call: {}'.format(payload))
        self.sendMessage(json.dumps(payload).encode('utf8'))

    def onConnect(self, response) :
        log.debug("Server connected: {0}".format(response.peer))
        # login, authenticate
        self.rpc_call(DATABASE_API, 'login', self.user, self.passwd)
        self.rpc_call(DATABASE_API, 'network_node')

    def onMessage(self, payload, isBinary):
        global NETWORK_API
        res = json.loads(payload.decode('utf8'))
        log.debug('Got response for request id {}: {}'.format(res['id'], json.dumps(res, indent=4)))
        api, method, args = self.request_map.pop(res['id'])

        p = {'result': res['result'] if 'result' in res else None,
             'server_response': res,
             'last_updated': datetime.utcnow()}
        _ws_rpc_cache[(self.host, self.port)][(api, method, args)] = p

        if (api, method) == (DATABASE_API, 'network_node'):
            NETWORK_API = p['result']
            log.info('Granted access to network api')
            nseconds = core.config['monitoring']['monitor_time_interval']
            def update_info():
                if NETWORK_API is not None:
                    # call all that we want to cache
                    self.rpc_call(NETWORK_API, 'get_info')

                self.factory.loop.call_later(nseconds, update_info)

            self.factory.loop.call_soon(update_info)

        if not self.request_map:
            log.debug('received all responses to pending requests')
            # we could call update_info from here, but then there would be 5 seconds between
            # the last answer from the server and the first request again, whereas in the other
            # case (as implemented now), there are 5 seconds between each set of requests
            # (we don't expect it to change much, but it feels more "stable" this way. We'll see...)
            #yield from self.updateInfo()


    def onClose(self, wasClean, code, reason):
        log.debug("WebSocket connection closed: {0}".format(reason))
        log.warning("WebSocket connection closed: {0}".format(reason))

    def connection_lost(self, exc):
        log.debug('connection closed, stopping run loop')
        self.factory.loop.stop()



def run_monitoring(host, port, user, passwd):
    import threading

    log.info('Starting witness websocket monitoring on {}:{}'.format(host, port))

    while True:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        log.debug('new event loop: {}'.format(loop))
        log.debug('in thread {}'.format(threading.current_thread().name))

        factory          = WebSocketClientFactory("ws://{}:{:d}".format(host, port), debug=True)
        factory.protocol = partial(MonitoringProtocol, host, port, user, passwd)

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

        nseconds = core.config['monitoring']['monitor_time_interval']
        time.sleep(nseconds) # wait some time before trying to reconnect
