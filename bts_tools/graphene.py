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
import json
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



DATABASE_API = 1
NETWORK_API = None  # to be fetched upon connecting

# FIXME: this should be per-host, and would probably benefit from being integrated
#        directly in each node's rpc_cache
WSINFO = {}

def ws_rpc_call(api, method, *args):
    key = (api, method,  args)
    try:
        result = WSINFO[key]
        return result['result']
    except KeyError:
        # FIXME: distinguish when key is not in or when 'result' is not in
        #        (ie: deserialize exception if any)
        raise RuntimeError('{}: {}({}) not in websocket cache'.format(api, method, ', '.join(args)))


class MonitoringProtocol(WebSocketClientProtocol):
    def __init__(self, witness_user, witness_passwd):
        super().__init__()
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
        WSINFO[(api, method, args)] = p

        if (api, method) == (DATABASE_API, 'network_node'):
            if NETWORK_API is None:
                # we just started and finished connecting, set up the actual monitoring
                def update_info():
                    # call all that we want to cache
                    self.rpc_call(NETWORK_API, 'get_info')

                    nseconds = core.config['monitoring']['monitor_time_interval']
                    self.factory.loop.call_later(nseconds, update_info)

                self.factory.loop.call_soon(update_info)

            NETWORK_API = p['result']
            log.info('Granted access to network api')

        if not self.request_map:
            log.debug('received all responses to pending requests')
            # we could call update_info from here, but then there would be 5 seconds between
            # the last answer from the server and the first request again, whereas in the other
            # case (as implemented now), there are 5 seconds between each set of requests
            # (we don't expect it to change much, but it feels more "stable" this way. We'll see...)
            #yield from self.updateInfo()


    def onClose(self, wasClean, code, reason):
        log.debug("WebSocket connection closed: {0}".format(reason))

    def connection_lost(self, exc):
        log.debug('connection closed, stopping run loop')
        #self.loop.stop()



def run_monitoring(host, port, user, passwd):
    import threading

    log.info('Starting witness websocket monitoring on {}:{}'.format(host, port))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    log.debug('new event loop: {}'.format(loop))
    log.debug('in thread {}'.format(threading.current_thread().name))

    factory          = WebSocketClientFactory("ws://{}:{:d}".format(host, port), debug=True)
    factory.protocol = partial(MonitoringProtocol, user, passwd)

    try:
        coro = loop.create_connection(factory, host, port)
        loop.run_until_complete(coro)
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()

