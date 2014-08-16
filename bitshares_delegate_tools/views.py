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

from flask import Blueprint, render_template, request, redirect, send_from_directory
from functools import wraps
from collections import defaultdict
from os.path import dirname
from datetime import datetime
import bitshares_delegate_tools.rpcutils as rpc
from bitshares_delegate_tools import core, monitor
import bitshares_delegate_tools
import requests.exceptions
import pickle
import logging

log = logging.getLogger(__name__)

bp = Blueprint('web', __name__, static_folder='static', template_folder='templates')


@bp.route('/robots.txt')
#@bp.route('/sitemap.xml')
def static_from_root():
    """Allows to serve static files directly from the root url instead of the
    static folder. Files still need to be put inside the static folder."""
    return send_from_directory(bp.static_folder, request.path[1:])


def offline():
    return render_template('error.html',
                           msg='The BitShares client is currently offline. '
                               'Please run it and activate the HTTP RPC server.')


def unauthorized():
    config_path = dirname(bitshares_delegate_tools.__file__)
    return render_template('error.html',
                           msg='Unauthorized. Make sure you have correctly set '
                               'the rpc user and password in the %s/config.json file' % config_path)


def catch_error(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except requests.exceptions.ConnectionError:
            core.is_online = False
            return offline()
        except core.UnauthorizedError:
            return unauthorized()
    return wrapper


# Note: before each view, we clear the rpc cache, and have cached=True by default
# this allows to ensure we only perform a given rpc call once with a given set
# of args, no matter how many times we call it from the view (ie: we might need
# to call 'is_online' or 'info' quite a few times, and we don't want to be sending
# all these requests over ssh...)
def clear_rpc_cache(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        bitshares_delegate_tools.rpcutils.clear_rpc_cache()
        return f(*args, **kwargs)
    return wrapper


@bp.route('/')
def homepage():
    return redirect('/info')


@bp.route('/status')
@clear_rpc_cache
@catch_error
def view_status():
    log.debug('getting stats from: %s' % hex(id(monitor.stats)))

    log.warning('size: %d' % len(monitor.stats))
    log.warning('size: %d' % len(bitshares_delegate_tools.monitor.stats))

    stats = list(monitor.stats)
    stats = pickle.load(open(core.config['monitoring']['stats_file'], 'rb'))

    points = []
    for stat in stats:
        points.append([int((stat.timestamp - datetime(1970,1,1)).total_seconds() * 1000),
                       stat.cpu,
                       int(stat.mem / (1024*1024)),
                       stat.connections])
    return render_template('status.html', title='BTS Client - Status', points=points)


def split_columns(items, attrs):
    # split into 2 columns, more readable on a laptop
    n = len(items)
    if n % 2 == 1:
        items.append(('', ''))
        n += 1
    offset = int(n/2)

    items = [(a,b,c,d) for (a,b),(c,d) in zip(items[:offset],
                                              items[offset:])]
    for a, l in attrs.items():
        for i, v in enumerate(l):
            l[i] = ((l[i][0], l[i][1])
                    if l[i][0] < offset
                    else (l[i][0] - offset, l[i][1] + 2))

    return items, attrs


@bp.route('/info')
@clear_rpc_cache
@catch_error
def view_info():
    attrs = defaultdict(list)
    info_items = sorted(rpc.main_node.get_info().items())

    attrs['bold'] = [(i, 0) for i in range(len(info_items))]
    for i, (prop, value) in enumerate(info_items):
        def green_if_true(cond):
            if cond:
                attrs['green'].append((i, 1))
            else:
                attrs['red'].append((i, 1))

        if prop in ('wallet_open',
                    'wallet_unlocked',
                    'wallet_block_production_enabled'):
            green_if_true(value)

        elif prop == 'network_num_connections':
            green_if_true(value >= 5)

        elif prop == 'blockchain_head_block_age':
            green_if_true(value < 60)

        elif prop == 'wallet_next_block_production_time':
            if value and value < 60:
                attrs['orange'].append((i, 1))

    info_items, attrs = split_columns(info_items, attrs)

    return render_template('tableview.html', title='BTS Client - Info', data=info_items, attrs=attrs)


@bp.route('/rpchost/<host>')
@catch_error
def set_rpchost(host):
    for node in rpc.nodes:
        if node.host == host:
            rpc.main_node = node
            break
    else:
        # invalid host name
        pass

    return redirect('/info')


@bp.route('/delegates')
@clear_rpc_cache
@catch_error
def view_delegates():
    response = rpc.main_node.blockchain_list_delegates(0, 300)

    headers = ['Position', 'Delegate name', 'Votes for', 'Last block', 'Produced', 'Missed']
    total_shares = rpc.main_node.get_info()['blockchain_share_supply']

    data = [ (i+1,
              d['name'],
              '%.8f%%' % (d['delegate_info']['votes_for'] * 100 / total_shares),
              d['delegate_info']['last_block_num_produced'],
              d['delegate_info']['blocks_produced'],
              d['delegate_info']['blocks_missed'])
             for i, d in enumerate(response) ]

    return render_template('tableview.html',
                           headers=headers,
                           data=data,
                           order='[[ 2, "desc" ]]')
