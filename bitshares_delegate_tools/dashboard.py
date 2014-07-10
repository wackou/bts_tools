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
from bitshares_delegate_tools.core import rpc_call, BTSProxy
from functools import wraps
import bitshares_delegate_tools
import requests.exceptions
import logging

log = logging.getLogger(__name__)

bp = Blueprint('web', __name__, static_folder='static', template_folder='templates')
rpc = BTSProxy()


@bp.route('/offline')
def offline():
    return render_template('error.html',
                           msg='The BitShares client is currently offline. '
                               'Please run it and activate the HTTP RPC server.')

@bp.route('/unauthorized')
def unauthorized():
    config_path = os.path.dirname(bitshares_delegate_tools.__file__)
    return render_template('error.html',
                           msg='Unauthorized. Make sure you have correctly set '
                               'the rpc user and password in the %s/config.json file' % config_path)

def catch_error(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except requests.exceptions.ConnectionError:
            bitshares_delegate_tools.core.is_online = False
            return offline()
        except bitshares_delegate_tools.core.UnauthorizedError:
            return unauthorized()
    return wrapper


@bp.route('/robots.txt')
#@bp.route('/sitemap.xml')
def static_from_root():
    """Allows to serve static files directly from the root url instead of the
    static folder. Files still need to be put inside the static folder."""
    return send_from_directory(bp.static_folder, request.path[1:])


@bp.route('/')
def homepage():
    return redirect('/delegates')


@bp.route('/info')
@catch_error
def view_info():
    info_items = sorted(rpc.get_info().items())
    n = len(info_items)
    if n % 2 == 1:
        info_items.append(('', ''))
        n += 1
    info_items = [(a,b,c,d) for (a,b),(c,d) in zip(info_items[:int(n/2)], info_items[int(n/2):])]
    return render_template('tableview.html', data=info_items, attrs={'bold': [1, 3]})


@bp.route('/delegates')
@catch_error
def view_delegates():
    response = rpc_call('blockchain_list_delegates', 0, 101)

    headers = ['Position', 'Delegate name', 'Votes for', 'Last block', 'Produced', 'Missed']

    data = [ (i+1,
              d['name'],
              '%.8f%%' % (d['delegate_info']['votes_for'] * 100 /
                          rpc.get_info(cached=True)['blockchain_share_supply']),
              d['delegate_info']['last_block_num_produced'],
              d['delegate_info']['blocks_produced'],
              d['delegate_info']['blocks_missed'])
             for i, d in enumerate(response) ]

    return render_template('tableview.html',
                           headers=headers,
                           data=data,
                           order='[[ 2, "desc" ]]')
