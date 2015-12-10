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
    hashabledict, to_list, FeedPrice
from .process import bts_binary_running, bts_process
from .feeds import BIT_ASSETS, BIT_ASSETS_INDICES
from . import graphene  # needed to access DATABASE_API, NETWORK_API dynamically, can't import them directly
from . import core
from collections import defaultdict, deque, OrderedDict
from os.path import join, expanduser
from datetime import datetime
from dogpile.cache import make_region
import bts_tools.core  # needed to be able to exec('raise bts.core.Exception')
import builtins        # needed to be able to reraise builtin exceptions
import importlib
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
             funcname, *args, __graphene=False):
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


class BTSProxy(object):
    def __init__(self, type, name, client=None, bts_type=None, monitoring=None, notification=None,
                 rpc_port=None, rpc_user=None, rpc_password=None, rpc_host=None, venv_path=None,
                 # graphene fields
                 witness_host=None, witness_port=None, witness_user=None, witness_password=None,
                 wallet_host=None, wallet_port=None, wallet_user=None, wallet_password=None):
        self.type = type
        if bts_type is not None:
            self._bts_type = bts_type
        self.name = name
        self.monitoring = to_list(monitoring)
        self.notification = to_list(notification)
        self.client = client
        if client:
            data_dir = get_data_dir(client)

            try:
                log.info('Loading RPC config for %s from %s (run_env = %s)' % (self.name, data_dir, client))
                if is_graphene_based(client):
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
        self.rpc_port = wallet_port or rpc_port or cfg_port or 0
        self.rpc_user = wallet_user or rpc_user or rpc.get('rpc_user') or ''
        self.rpc_password = wallet_password or rpc_password or rpc.get('rpc_password') or ''
        self.rpc_host = wallet_host or rpc_host or 'localhost'
        self.rpc_cache_key = (self.rpc_host, self.rpc_port)
        self.ws_rpc_cache_key = (self.witness_host, self.witness_port)
        self.venv_path = venv_path

        self.witness_host     = witness_host
        self.witness_port     = witness_port
        self.witness_user     = witness_user
        self.witness_password = witness_password
        self.wallet_host      = wallet_host
        self.wallet_port      = wallet_port
        self.wallet_user      = wallet_user
        self.wallet_password  = wallet_password

        self.bin_name = get_bin_name(client or 'bts')

        if self.is_graphene_based():
            # direct json-rpc call
            def direct_call(funcname, *args):
                # we want to avoid connecting to the client and block because
                # it is in a stopped state (eg: in gdb after having crashed)
                if self.is_localhost() and not bts_binary_running(self):
                    raise RPCError('Connection aborted: BTS binary does not seem to be running')

                return rpc_call(self.wallet_host, self.wallet_port,
                                self.wallet_user, self.wallet_password,
                                funcname, *args, __graphene=self.is_graphene_based())
            self._rpc_call = direct_call

        elif self.rpc_host == 'localhost':
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
            #        for instance, if command fails, we end up with sth like that in the logs:
            # 2015-08-31 00:43:48,520 WARNING  [bts_tools.core:run:190] -- Failed running: ssh myhost "source ~/.virtualenvs/bts_tools/bin/activate; bts-rpc 1234 rpcuser XXXrpcpasswordXXX get_info
            def remote_call(funcname, *args):
                cmd = 'ssh %s "' % self.rpc_host
                if self.venv_path:
                    cmd += 'source %s/bin/activate; ' % self.venv_path
                #cmd += 'bts-rpc %s %s"' % (funcname, '"%s"' % '" "'.join(str(arg) for arg in args))
                cmd += 'bts-rpc %d %s %s %s %s 2>/dev/null"' % (self.rpc_port, self.rpc_user, self.rpc_password,
                                                    funcname, ' '.join(str(arg) for arg in args))

                result = run(cmd, capture_io=True, verbose=False).stdout
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

        # caches for committee member and witness names
        self._witness_names = {}
        self._committee_member_names = {}

    def __str__(self):
        return self.name

    def __repr__(self):
        return 'BTSProxy(%s, %s)' % (self.client, self.name)

    def __getattr__(self, funcname):
        if funcname.startswith('_'):
            raise AttributeError
        def call(*args, cached=True):
            return self.rpc_call(funcname, *args, cached=cached)
        return call

    def rpc_call(self, funcname, *args, cached=True):
        log.debug(('RPC call @ %s: %s(%s)' % (self.rpc_cache_key, funcname, ', '.join(repr(arg) for arg in args))
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
                    return copy.copy(result)

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

        return copy.copy(result)

    def clear_rpc_cache(self):
        try:
            log.debug('Clearing RPC cache for host: %s:%d' % self.rpc_cache_key)
            del _rpc_cache[self.rpc_cache_key]
        except KeyError:
            pass

    def ws_rpc_call(self, api, method, *args):
        log.debug('WebSocket RPC call @ %s: %s::%s(%s)' % (self.ws_rpc_cache_key,
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

    def status(self, cached=True):
        try:
            if self.is_graphene_based():
                self.rpc_call('info', cached=cached)
            else:
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

    def get_witness_name(self, witness_id):
        try:
            return self._witness_names[witness_id]
        except KeyError:
            pass

        result = self.get_account(self.get_witness(witness_id)['witness_account'])['name']
        self._witness_names[witness_id] = result

        return result

    def get_committee_member_name(self, committee_member_id):
        try:
            return self._committee_member_names[committee_member_id]
        except KeyError:
            pass

        result = self.get_account(self.get_committee_member(committee_member_id)['committee_member_account'])['name']
        self._committee_member_names[committee_member_id] = result

        return result

    def network_get_info(self):
        if self.is_graphene_based():
            return self.ws_rpc_call(graphene.NETWORK_API, 'get_info')
        else:
            return self.rpc_call('network_get_info')

    def network_get_connected_peers(self):
        if self.is_graphene_based():
            return [p['info'] for p in self.ws_rpc_call(graphene.NETWORK_API, 'get_connected_peers')]
        else:
            return self.rpc_call('network_get_peer_info')

    def network_get_potential_peers(self):
        if self.is_graphene_based():
            return self.ws_rpc_call(graphene.NETWORK_API, 'get_potential_peers')
        else:
            return self.rpc_call('network_list_potential_peers')

    def network_set_advanced_node_parameters(self, params):
        if self.is_graphene_based():
            return self.ws_rpc_call(graphene.NETWORK_API, 'set_advanced_node_parameters', params)
        else:
            return self.rpc_call('network_get_advanced_node_parameters')

    def network_get_advanced_node_parameters(self):
        if self.is_graphene_based():
            return self.ws_rpc_call(graphene.NETWORK_API, 'get_advanced_node_parameters')
        else:
            return self.rpc_call('network_get_advanced_node_parameters')

    def process(self):
        return bts_process(self)

    def run_env(self):
        name = self.client
        if not name:
            raise ValueError('No run environment defined for node %s. Maybe a remote node?' % self.name)
        try:
            return core.config['run_environments'][name]
        except KeyError:
            raise ValueError('Unknown run environment: %s' % name)

    def build_env(self):
        name = self.run_env()['type']
        try:
            return core.config['build_environments'][name]
        except KeyError:
            raise ValueError('Unknown build environment: %s' % name)

    def bts_type(self):
        # try to get the cached value first
        try:
            return self._bts_type
        except AttributeError:
            # not cached yet. fall through so we can compute it
            pass

        # if no cached value, try to get the client type from the config file
        try:
            self._bts_type = self.run_env()['type']
            return self._bts_type
        except ValueError:
            pass

        # if the previous didn't work (eg: remote node), try to talk to the client
        # directly. This works only when the client is running.
        try:
            blockchain_name = self.about()['blockchain_name']
        except Exception:
            log.warning('Could not find blockchain name for {}:{}'.format(self.rpc_host, self.rpc_port))
            return ''
        if blockchain_name == 'BitShares':
            self._bts_type = 'bts'
        elif blockchain_name == 'DevShares':
            self._bts_type = 'dvs'
        elif blockchain_name == 'PTS':
            self._bts_type = 'pts'
        else:
            return 'unknown'

        return self._bts_type

    def is_graphene_based(self):
        return is_graphene_based(self)

    def is_active(self, delegate):
        if self.is_graphene_based():
            try:
                return self.get_witness(delegate)['id'] in self.info()['active_witnesses']
            except:
                # if witness doesn't exist (eg: at block head = 0), return False instead of failing
                return False
        else:
            active_delegates = [d['name'] for d in self.blockchain_list_delegates(0, 101)]
            return delegate in active_delegates

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
        return ((self.bts_type() in {'bts', 'dvs'} and self.api_version() >= '0.6') or
                (self.bts_type() == 'pls'))

    def get_streak(self, cached=True):
        # FIXME: support graphene
        if self.is_graphene_based():
            return True, 0
        if self.type != 'delegate':
            # only makes sense to call get_streak on delegate nodes
            return False, 1

        new_api = self.delegate_slot_records_new_api()

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
            p = BIT_ASSETS | BIT_ASSETS_INDICES.keys() | {'BTS'}
            for asset_name in BIT_ASSETS | BIT_ASSETS_INDICES.keys() | {'BTS'}:
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
        p = BIT_ASSETS | BIT_ASSETS_INDICES.keys()

        witness_id = self.get_witness(witness_name)['witness_account']
        asset_list = asset_list or BIT_ASSETS | BIT_ASSETS_INDICES.keys()
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


def load_nodes():
    global nodes, main_node
    nodes = [BTSProxy(**node) for node in core.config['nodes']]
    main_node = nodes[0]


def unique_node_clients():
    result = OrderedDict()
    for n in nodes:
        try:
            result[n.rpc_cache_key].append(n)
        except KeyError:
            result[n.rpc_cache_key] = [n]
    return list(result.items())


def client_instances():
    """return a list of triples (hostname, [node names], node_instance)"""
    for (host, port), gnodes in unique_node_clients():
        yield ('%s:%d' % (host, port), [n.name for n in gnodes], gnodes[0])


