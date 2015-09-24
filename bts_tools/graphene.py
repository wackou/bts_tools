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

import logging

log = logging.getLogger(__name__)

# export bitshares 0.9.x balance keys
def print_balances():
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



from autobahn.asyncio.websocket import WebSocketClientProtocol, WebSocketClientFactory
import json
import asyncio

class GrapheneWebsocketProtocol(WebSocketClientProtocol):
    def __init__(self, loop):
        super().__init__()
        self.loop = loop
        self.request_id = 0

    def rpc_call(self, api, method, *args):
        self.request_id += 1
        payload = {'jsonrpc': '2.0',
                   'id': self.request_id,
                   'method': 'call',
                   'params': [api, method, list(args)]}
        log.debug('rpc call: {}'.format(payload))
        self.sendMessage(json.dumps(payload).encode('utf8'))

    def onConnect(self, response) :
        log.debug("Server connected: {0}".format(response.peer))

    def onMessage(self, payload, isBinary):
        res = json.loads(payload.decode('utf8'))
        log.debug("Server: " + json.dumps(res,indent=1))
        return res['result']

    def onClose(self, wasClean, code, reason):
        log.debug("WebSocket connection closed: {0}".format(reason))

    def connection_lost(self, exc):
        log.debug('connection closed, stopping run loop')
        self.loop.stop()


class SingleCall(GrapheneWebsocketProtocol):
    def __init__(self, loop, result, api, method, *args):
        super().__init__(loop)
        self.api = api
        self.method = method
        self.args = args
        self.result = result

    def onOpen(self):
        log.debug("WebSocket single call connection open.")
        self.rpc_call(self.api, self.method, self.args)

    def onMessage(self, payload, isBinary):
        super().onMessage(payload, isBinary)
        self.sendClose()


class CallSequence(GrapheneWebsocketProtocol):
    def __init__(self, loop, result_holder, calls):
        """result_holder a list of 1 element, allows to modify external ref"""
        super().__init__(loop)
        self.calls = calls
        self.call_idx = 0 # what to do when calls = []?
        self.result = result_holder

    def onOpen(self):
        log.debug("WebSocket single call connection open.")
        self.callNext()

    def callNext(self):
        api, method, *args = self.calls[self.call_idx]
        log.debug('calling next method {} {}'.format(api, method))
        self.call_idx += 1
        self.rpc_call(api, method, *args)

    def onMessage(self, payload, isBinary):
        result = super().onMessage(payload, isBinary)
        if self.call_idx < len(self.calls):
            # TODO: what happens if we fail before the end of the call sequence?
            self.callNext()
        else:
            self.result[0] = result
            self.sendClose()


def run_protocol(Protocol, host, port, *args):
    import threading

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    log.debug('loop: {}'.format(loop))
    log.debug(threading.current_thread().name)

    result = [None]

    factory          = WebSocketClientFactory("ws://{}:{:d}".format(host, port), debug=True)
    factory.protocol = lambda: Protocol(loop, result, *args)

    try:
        coro = loop.create_connection(factory, host, port)
        loop.run_until_complete(coro)
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
    return result[0]


def call_sequence(host, port, seq):
    return run_protocol(CallSequence, host, port, seq)

def single_call(host, port, api, method, *args):
    return run_protocol(CallSequence, host, port, [[api, method] + list(args)])

"""
#a=single_call(0, 'get_accounts', ['1.2.0'])
a=single_call(0, 'get_chain_id')
print('-'*100)
print(a)
""

call_sequence(host, port,
              [[1, 'login', 'user', 'password'],
               [1, 'network_node'],
               [2, 'get_connected_peers']])
"""
