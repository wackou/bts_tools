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

from .core import UnauthorizedError, RPCError, run, get_data_dir, get_bin_name, is_graphene_based,\
    hashabledict, to_list, trace
from .feed_providers import FeedPrice
from .process import bts_binary_running, bts_process
from .feeds import BIT_ASSETS, BIT_ASSETS_INDICES
from .privatekey import PrivateKey
from . import graphene  # needed to access DATABASE_API, NETWORK_API dynamically, can't import them directly
from . import core
from collections import defaultdict, deque, OrderedDict
from os.path import join, expanduser
from datetime import datetime
from dogpile.cache import make_region
import bts_tools.core  # needed to be able to exec('raise bts.core.Exception')
import builtins        # needed to be able to reraise builtin exceptions
import importlib
import functools
import requests
import itertools
import configparser
import json
import copy
import re
import logging

log = logging.getLogger(__name__)


NON_CACHEABLE_METHODS = {'wallet_publish_price_feed',
                         'wallet_publish_feeds',
                         'wallet_publish_version'}

_rpc_cache = defaultdict(dict)
_rpc_call_id = defaultdict(int)

def rpc_call(host, port, user, password,
             funcname, *args, __graphene=False, raw_response=False, rpc_args={}):
    url = 'http://%s:%d/rpc' % (host, port)
    headers = {'content-type': 'application/json'}
    _rpc_call_id[(host, port)] += 1

    if __graphene:
        payload = {
            'method': 'call',
            'params': [graphene.DATABASE_API, funcname, args],
            'jsonrpc': '2.0',
            'id': _rpc_call_id[(host, port)]
        }
    else:
        payload = {
            'method': funcname,
            'params': args,
            'jsonrpc': '2.0',
            'id': _rpc_call_id[(host, port)]
        }

    payload.update(rpc_args or {})

    response = requests.post(url,
                             auth=(user, password),
                             data=json.dumps(payload),
                             headers=headers)

    log.debug('  received: %s %s' % (type(response), response))

    if response.status_code == 401:
        raise UnauthorizedError()

    r = response.json()

    if raw_response:
        return r

    if 'error' in r:
        if 'detail' in r['error']:
            raise RPCError(r['error']['detail'] + '\n\nFor RPC call:\n{}'.format(json.dumps(payload, indent=4)))
        else:
            raise RPCError(r['error']['message'] + '\n\nFor RPC call:\n{}'.format(json.dumps(payload, indent=4)))

    return r['result']


ALL_SLOTS = {}


class GrapheneClient(object):
    def __init__(self, role, name, client_name, client, type=None,
                 monitoring=None, notification=None, venv_path=None,
                 witness_id=None, signing_key=None, **kwargs):
        self.role = role
        if type is not None:
            self._type = type
        self.name = name
        self.witness_signing_key = None
        self.monitoring = to_list(monitoring)
        self.notification = to_list(notification)
        self.client_name = client_name
        data_dir = client.get('data_dir')
        if data_dir:
            data_dir = expanduser(data_dir)

            try:
                log.info('Loading RPC config for %s from %s (run_env = %s)' % (self.name, data_dir, client_name))
                if is_graphene_based(client_name):
                    config = configparser.ConfigParser()
                    config_str = '[bts]\n' + open(expanduser(join(data_dir, 'config.ini'))).read()
                    # config parser can't handle duplicate values, and we don't need seed nodes
                    config_lines = [l for l in config_str.splitlines() if not l.startswith('seed-node')]
                    config.read_string('\n'.join(config_lines))
                    rpc = {}  # FIXME: need it to get the rpc user and rpc password, if necessary
                    try:
                        cfg_port = int(config['bts']['rpc-endpoint'].split(':')[1])
                    except KeyError:
                        cfg_port = 0
                    try:
                        if self.type() == 'steem':
                            self.witness_signing_key = config['bts']['private-key']
                        else:
                            self.witness_signing_key = json.loads(config['bts']['private-key'])[0]
                    except KeyError:
                        self.witness_signing_key = None
                    log.debug('signing key: {}'.format(self.witness_signing_key))
                else:
                    rpc = json.load(open(expanduser(join(data_dir, 'config.json'))))['rpc']
                    cfg_port = int(rpc['httpd_endpoint'].split(':')[1])
            except Exception as e:
                log.warning('Cannot read RPC config from %s' % data_dir)
                log.exception(e)
                rpc = {}
                cfg_port = None
        else:
            rpc = {}
            cfg_port = None

        self.witness_host     = client.get('witness_host')
        self.witness_port     = client.get('witness_port')
        self.witness_user     = client.get('witness_user')
        self.witness_password = client.get('witness_password')
        self.wallet_host      = client.get('wallet_host')
        self.wallet_port      = client.get('wallet_port') or client.get('rpc_port') or cfg_port or 0
        self.wallet_user      = client.get('wallet_user')
        self.wallet_password  = client.get('wallet_password')
        self.proxy_host       = client.get('proxy_host')
        self.proxy_port       = client.get('proxy_port')
        self.proxy_user       = client.get('proxy_user')
        self.proxy_password   = client.get('proxy_password')

        self.rpc_port = self.proxy_port or self.wallet_port
        self.rpc_user = self.wallet_user or client.get('rpc_user') or rpc.get('rpc_user') or ''
        self.rpc_password = self.wallet_password or client.get('rpc_password') or rpc.get('rpc_password') or ''
        self.rpc_host = self.wallet_host or client.get('rpc_host') or self.proxy_host or 'localhost'
        self.rpc_id = (self.rpc_host, self.wallet_port)
        self.ws_rpc_id = (self.witness_host, self.witness_port)
        self.venv_path = venv_path
        self.witness_id = witness_id
        self.witness_signing_key = signing_key or self.witness_signing_key
        self.bin_name = get_bin_name(client_name or 'bts')

        if self.is_graphene_based():
            # direct json-rpc call
            def direct_call(funcname, *args):
                # we want to avoid connecting to the client and block because
                # it is in a stopped state (eg: in gdb after having crashed)
                if self.is_localhost() and not bts_binary_running(self):
                    raise RPCError('Connection aborted: {} binary does not seem to be running'.format(self.type()))

                if self.proxy_host is not None and self.proxy_port is not None:
                    return rpc_call(self.proxy_host, self.proxy_port,
                                    None, None,
                                    funcname, *args, __graphene=True,
                                    rpc_args=dict(proxy_user=self.proxy_user,
                                                  proxy_password=self.proxy_password,
                                                  wallet_port=self.wallet_port))

                return rpc_call(self.wallet_host, self.wallet_port,
                                self.wallet_user, self.wallet_password,
                                funcname, *args, __graphene=True)
            self._rpc_call = direct_call

        elif self.rpc_host == 'localhost':
            # direct json-rpc call
            def local_call(funcname, *args):
                # we want to avoid connecting to the client and block because
                # it is in a stopped state (eg: in gdb after having crashed)
                if not bts_binary_running(self):
                    raise RPCError('Connection aborted: {} binary does not seem to be running'.format(self.type()))

                result = rpc_call('localhost', self.rpc_port,
                                  self.rpc_user, self.rpc_password,
                                  funcname, *args)
                return result
            self._rpc_call = local_call

        else:
            raise RuntimeError('Cannot connect to remote host for non-graphene nodes')

        if core.config.get('profile', False):
            self._rpc_call = core.profile(self._rpc_call)

        self.opts = kwargs
        if self.opts:
            log.debug('Additional opts for node {} on {}:{} - {}'.format(self.name, self.rpc_host, self.rpc_port, self.opts))

        # get a special "smart" cache for slots as it is a very expensive call
        self._slot_cache = make_region().configure('dogpile.cache.memory')

        # caches for committee member and witness names
        self._witness_names = {}
        self._committee_member_names = {}

    def __str__(self):
        return '{} ({} / {}:{})'.format(self.name, self.type(), self.rpc_host, self.rpc_port)

    def __repr__(self):
        return 'GrapheneClient(%s, %s)' % (self.client_name, self.name)

    def __getattr__(self, funcname):
        if funcname.startswith('_'):
            raise AttributeError
        def call(*args, cached=True):
            return self.rpc_call(funcname, *args, cached=cached)
        return call

    def rpc_call(self, funcname, *args, cached=True):
        log.debug(('RPC call @ %s: %s(%s)' % (self.rpc_id, funcname, ', '.join(repr(arg) for arg in args))
                  + (' (cached = False)' if not cached else '')))
        args = tuple(hashabledict(arg) if isinstance(arg, dict) else
                     tuple(arg) if isinstance(arg, list) else
                     arg
                     for arg in args)

        if cached and funcname not in NON_CACHEABLE_METHODS:
            if (funcname, args) in _rpc_cache[self.rpc_id]:
                result = _rpc_cache[self.rpc_id][(funcname, args)]
                if isinstance(result, Exception):
                    log.debug('  using cached exception %s' % result.__class__)
                    raise result
                else:
                    log.debug('  using cached result')
                    return copy.copy(result)

        try:
            result = self._rpc_call(funcname, *args)
        except Exception as e:
            # also cache when exceptions are raised
            if funcname not in NON_CACHEABLE_METHODS:
                _rpc_cache[self.rpc_id][(funcname, args)] = e
                log.debug('  added exception %s in cache: %s' % (e.__class__, str(e)))
            raise

        if funcname not in NON_CACHEABLE_METHODS:
            _rpc_cache[self.rpc_id][(funcname, args)] = result
            log.debug('  added result in cache')

        return copy.copy(result)

    def clear_rpc_cache(self):
        try:
            log.debug('Clearing RPC cache for host: %s:%d' % self.rpc_id)
            del _rpc_cache[self.rpc_id]
        except KeyError:
            pass

    def ws_rpc_call(self, api, method, *args):
        log.debug('WebSocket RPC call @ %s: %s::%s(%s)' % (self.ws_rpc_id,
                                                 graphene.api_name(api),
                                                 method,
                                                 ', '.join(repr(arg) for arg in args)))

        return graphene.ws_rpc_call(self.witness_host, self.witness_port, api, method, *args)

    def get_account_balance(self, account, symbol):
        log.debug('get_account_balance for asset %s in %s' % (symbol, account))
        asset = self.blockchain_get_asset(symbol)
        asset_id = asset['id']
        precision = asset['precision']

        # Returns the current balance of the given asset for the given account name
        balances = self.wallet_account_balance(account)  # rpc returns: [['account.name', [[asset_idx, balance]]]]
        if not balances:
            return 0
        for idx, bal in balances[0][1]:
            if idx == asset_id:
                balance = bal / precision
                # log.debug('balance: %s' % balance)
                return balance
        return 0


    def info(self, cached=True):
        if self.is_graphene_based():
            return self.rpc_call('info', cached=cached)
        else:
            return self.rpc_call('get_info', cached=cached)

    def status(self, cached=True):
        try:
            _ = self.info()
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

    def is_synced(self):
        if self.is_graphene_based():
            age = self.info()['head_block_age']
            return 'second' in age
        else:
            age = self.get_info()['blockchain_head_block_age']
            if age is not None and age < 60:
                return True
            return False

    def is_new(self):
        if self.is_graphene_based():
            return self.rpc_call('is_new')
        else:
            return not self.get_info()['wallet_open']

    def is_locked(self):
        if self.is_graphene_based():
            return self.rpc_call('is_locked')
        else:
            return not self.get_info()['wallet_unlocked']

    def is_localhost(self):
        return self.rpc_host in ['localhost', '127.0.0.1']

    def is_witness_localhost(self):
        host = self.witness_host if self.is_graphene_based() else self.rpc_host
        return host in ['localhost', '127.0.0.1']

    def is_witness(self):
        return self.role == 'delegate' or self.role == 'witness' or self.role == 'feed_publisher'

    def is_signing_key_active(self):
        if self.proxy_host:
            return self.rpc_call('is_signing_key_active')
        if self.witness_signing_key is None:
            return 'unknown'
        if not self.is_synced():
            return 'not synced'
        # the config file only specifies the private key, we need to derive the public key
        private_key = PrivateKey(self.witness_signing_key)
        public_key = format(private_key.pubkey, self.type())
        return public_key == self.get_witness(self.name)['signing_key']

    # FIXME: use a decorator for this (forever) caching (also see bitasset_data)
    def get_witness_name(self, witness_id):
        try:
            return self._witness_names[witness_id]
        except KeyError:
            pass

        result = self.get_account(self.get_witness(witness_id)['witness_account'])['name']
        self._witness_names[witness_id] = result

        return result

    # FIXME: use a decorator for this (forever) caching (also see bitasset_data)
    def get_committee_member_name(self, committee_member_id):
        try:
            return self._committee_member_names[committee_member_id]
        except KeyError:
            pass

        result = self.get_account(self.get_committee_member(committee_member_id)['committee_member_account'])['name']
        self._committee_member_names[committee_member_id] = result

        return result

    def network_get_info(self):
        if self.is_graphene_based() and not self.proxy_host:
            return self.ws_rpc_call(graphene.NETWORK_API, 'get_info')
        else:
            return self.rpc_call('network_get_info')

    def network_get_connected_peers(self):
        if self.is_graphene_based():
            if not self.proxy_host:
                return [p['info'] for p in self.ws_rpc_call(graphene.NETWORK_API, 'get_connected_peers')]
            else:
                return self.rpc_call('network_get_connected_peers')
        else:
            return self.rpc_call('network_get_peer_info')

    def network_get_potential_peers(self):
        if self.is_graphene_based():
            if not self.proxy_host:
                return self.ws_rpc_call(graphene.NETWORK_API, 'get_potential_peers')
            else:
                return self.rpc_call('network_get_potential_peers')
        else:
            return self.rpc_call('network_list_potential_peers')

    def network_set_advanced_node_parameters(self, params):
        if self.is_graphene_based() and not self.proxy_host:
            return self.ws_rpc_call(graphene.NETWORK_API, 'set_advanced_node_parameters', params)
        else:
            return self.rpc_call('network_set_advanced_node_parameters', params)

    def network_get_advanced_node_parameters(self):
        if self.is_graphene_based() and not self.proxy_host:
            return self.ws_rpc_call(graphene.NETWORK_API, 'get_advanced_node_parameters')
        else:
            return self.rpc_call('network_get_advanced_node_parameters')

    def get_object(self, oid):
        return self.ws_rpc_call(graphene.DATABASE_API, 'get_objects', [oid])

    def process(self):
        return bts_process(self)

    def run_env(self):
        name = self.client_name
        if not name:
            raise ValueError('No run environment defined for node %s. Maybe a remote node?' % self.name)
        try:
            return core.config['clients'][name]
        except KeyError:
            raise ValueError('Unknown client: %s' % name)

    def build_env(self):
        name = self.run_env()['type']
        try:
            return core.config['build_environments'][name]
        except KeyError:
            raise ValueError('Unknown build environment: %s' % name)

    def type(self):
        # try to get the cached value first
        try:
            return self._type
        except AttributeError:
            # not cached yet. fall through so we can compute it
            pass

        # if no cached value, try to get the client type from the config file
        try:
            self._type = self.run_env()['type']
            return self._type
        except ValueError:
            pass

        # if the previous didn't work (eg: remote node), try to talk to the client
        # directly. This works only when the client is running.
        try:
            blockchain_name = self.about()['blockchain_name']
        except Exception as e:
            log.warning('Could not find blockchain name for {}:{}'.format(self.rpc_host, self.rpc_port))
            return ''
        if blockchain_name == 'BitShares':
            self._type = 'bts1'
        elif blockchain_name == 'DevShares':
            self._type = 'dvs'
        elif blockchain_name == 'PTS':
            self._type = 'pts'
        else:
            return 'unknown'

        return self._type

    def is_graphene_based(self):
        return is_graphene_based(self)

    def get_active_witnesses(self):
        if self.type() == 'steem':
            return self.rpc_call('get_active_witnesses')
        else:
            return [self.get_witness_name(w)
                    for w in self.info()['active_witnesses']]

    def is_active(self, witness):
        if self.is_graphene_based():
            try:
                witnesses = self.get_active_witnesses()
                if self.type() == 'steem':
                    witnesses = sorted(((name, self.get_witness(name)['votes']) for name in witnesses), key=lambda x:int(x[1]))
                    if witness == witnesses[0][0] or witness == witnesses[1][0]:
                        return False
                return witness in witnesses

            except Exception as e:
                # if witness doesn't exist (eg: at block head = 0), return False instead of failing
                return False
        else:
            active_delegates = [d['name'] for d in self.blockchain_list_delegates(0, 101)]
            return witness in active_delegates

    def get_head_block_num(self):
        if self.is_graphene_based():
            return int(self.info()['head_block_num'])
        else:
            return int(self.get_info()['blockchain_head_block_num'])

    def get_last_slots(self):
        """Return the last delegate slots, and cache this until at least the next block
        production time of the wallet."""
        new_api = self.delegate_slot_records_new_api()

        def _get_slots():
            # make sure we get enough slots to get them all up to our latest, even if there
            # are a lot of missed blocks by other delegates
            if new_api:
                # FIXME: 5 is only enough if we monitor for missed block, so that get_streak()
                #        is called often, otherwise we need more
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

    def delegate_slot_records_new_api(self):
        return ((self.type() in {'bts1', 'dvs'} and self.api_version() >= '0.6') or
                (self.type() == 'pls'))

    def get_streak(self, cached=True):
        if self.is_graphene_based():
            streak = core.db[self.rpc_id]['streak'][self.name]
            if streak >= 0:
                return True, streak
            else:
                return False, -streak

        if not self.is_witness():
            # only makes sense to call get_streak on delegate nodes
            return False, 1

        new_api = self.delegate_slot_records_new_api()

        try:
            global ALL_SLOTS
            key = (self.type(), self.name)
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
            streak = itertools.takewhile(lambda x: (type(x.get('block_id')) is type(latest.get('block_id'))), rslots)
            return latest.get('block_id') is not None, len(list(streak))

        except Exception as e:
            # can fail with RPCError when delegate has not been registered yet
            log.error('%s: get_streak() failed with: %s(%s)' % (self.name, type(e), e))
            log.exception(e)
            return False, -1

    def asset_data(self, asset):
        # bitAssets data (id, precision, etc.) don't ever change, so cache them forever
        try:
            all_data = self._all_bitassets_data
        except AttributeError:
            all_data = {}
            for asset_name in BIT_ASSETS | {'BTS'}:
                asset_data = self.get_asset(asset_name)
                all_data[asset_name] = asset_data        # resolve SYMBOL
                all_data[asset_data['id']] = asset_data  # resolve id

            self._all_bitassets_data = all_data

        return all_data[asset]

    def get_blockchain_feeds(self, asset_list):
        result = []
        for asset in asset_list:
            asset_data = self.get_bitasset_data(asset)

            try:
                base  = asset_data['current_feed']['settlement_price']['base']
                quote = asset_data['current_feed']['settlement_price']['quote']
                assert base != '1.3.0'
                base_precision  = self.asset_data(base['asset_id'])['precision']
                quote_precision = self.asset_data(quote['asset_id'])['precision']
                base_price  = int(base['amount']) / 10**base_precision
                quote_price = int(quote['amount']) / 10**quote_precision
                result.append(FeedPrice(base_price / quote_price, asset, 'BTS'))

            except ZeroDivisionError :
                print("No price feeds for asset %s available on the blockchain, yet!" % asset)

        return result

    def get_witness_feeds(self, witness_name, asset_list=None):
        witness_id = self.get_witness(witness_name)['witness_account']
        asset_list = asset_list or BIT_ASSETS
        result = []
        for asset in asset_list:
            asset_data = self.get_bitasset_data(asset)

            try:
                for feed in asset_data['feeds']:
                    if feed[0] == witness_id:
                        last_update = datetime.strptime(feed[1][0], '%Y-%m-%dT%H:%M:%S')
                        base  = feed[1][1]['settlement_price']['base']
                        quote = feed[1][1]['settlement_price']['quote']
                        assert base != '1.3.0'
                        base_precision  = self.asset_data(base['asset_id'])['precision']
                        quote_precision = self.asset_data(quote['asset_id'])['precision']
                        base_price  = int(base['amount']) / 10**base_precision
                        quote_price = int(quote['amount']) / 10**quote_precision
                        result.append(FeedPrice(base_price / quote_price, asset, 'BTS', last_updated=last_update))
                        break
                else:
                    log.warning('No published feeds found for witness {} - id: {}'.format(witness_name, witness_id))

            except ZeroDivisionError :
                print("No price feeds for asset %s available on the blockchain, yet!" % asset)

        return result


nodes = []
main_node = None


def load_graphene_clients():
    global nodes, main_node
    nodes = []
    for client_name, client in core.config['clients'].items():
        for role in client.get('roles', []):
            kwargs = dict(client_name=client_name,
                          client=client,
                          type=client.get('type'),
                          notification=client.get('notification'))
            kwargs.update(dict(**role))
            nodes.append(GrapheneClient(**kwargs))

    try:
        main_node = nodes[0]
    except IndexError:
        log.error('No clients defined in config.yaml, or clients defined without any role')


def graphene_clients():
    result = OrderedDict()
    for n in nodes:
        try:
            result[n.rpc_id].append(n)
        except KeyError:
            result[n.rpc_id] = [n]
    return list(result.items())


def client_instances():
    """return a list of triples (hostname, [node names], node_instance)"""
    for (host, port), gnodes in graphene_clients():
        yield ('%s:%d' % (host, port), {n.name for n in gnodes}, gnodes[0])


