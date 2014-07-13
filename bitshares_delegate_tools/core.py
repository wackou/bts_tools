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

#from flask_sqlalchemy import SQLAlchemy
#from flask_security import Security
from os.path import join, dirname, expanduser
import requests
import sys
import json
import itertools
import logging

log = logging.getLogger(__name__)

platform = sys.platform
if platform.startswith('linux'):
    platform = 'linux'

# load config
config = json.load(open(join(dirname(__file__), 'config.json')))

if platform not in config:
    raise OSError('OS not supported yet, please submit a patch :)')

# expand '~' in path names to the user's home dir
for attr, path in config[platform].items():
    config[platform][attr] = expanduser(path)

#: Flask-SQLAlchemy extension instance
#db = SQLAlchemy()

#: Flask-Security extension instance
#security = Security()

CACHED_RPC_CALLS = ['get_info']

is_online = False

_rpc_cache = {}

class UnauthorizedError(Exception):
    pass

def rpc_call(funcname, *args, cached=False):
    url = "http://localhost:%d/rpc" % config['rpc_port']
    headers = {'content-type': 'application/json'}

    payload = {
        "method": funcname,
        "params": args,
        "jsonrpc": "2.0",
        "id": 0,
    }

    if cached and funcname in CACHED_RPC_CALLS:
        if funcname in _rpc_cache:
            return _rpc_cache[funcname]

    response = requests.post(url,
                             auth=(config['rpc_user'], config['rpc_password']),
                             data=json.dumps(payload),
                             headers=headers)

    global is_online
    is_online = True

    log.debug('RPC received: %s %s' % (type(response), response))

    if response.status_code == 401:
        raise UnauthorizedError()

    result = response.json()['result']

    if funcname in CACHED_RPC_CALLS:
        _rpc_cache[funcname] = result

    return result



class BTSProxy(object):
    def __getattr__(self, funcname):
        return lambda *args, **kwargs: rpc_call(funcname, *args, **kwargs)


rpc = BTSProxy()


#### util functions we want to be able to access easily, such as in templates

def delegate_name():
    # FIXME: should parse my accounts to know the actual delegate name
    return 'wackou-delegate'


def get_streak():
    slots = rpc.blockchain_get_delegate_slot_records(delegate_name())[::-1]
    streak = itertools.takewhile(lambda x: (x['block_produced'] == slots[0]['block_produced']), slots)
    return slots[0]['block_produced'], len(list(streak))
