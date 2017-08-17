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

from flask import Blueprint, send_from_directory, jsonify
from functools import wraps
import bts_tools.rpcutils as rpc
from bts_tools import core
import bts_tools
import requests.exceptions
import itertools
import arrow
import logging

log = logging.getLogger(__name__)

bp = Blueprint('api', __name__, static_folder='static', template_folder='templates')


@bp.route('/robots.txt')
def static_from_root():
    """Allows to serve static files directly from the root url instead of the
    static folder. Files still need to be put inside the static folder."""
    return send_from_directory(bp.static_folder, request.path[1:])


def offline():
    return jsonify(error='offline')


def unauthorized():
    return jsonify(error=('Unauthorized. Make sure you have correctly set '
                          'the rpc user and password in the %s file'
                          % core.BTS_TOOLS_CONFIG_FILE))


def unknown_exception(e):
    return jsonify(error='exception: %s' % e)


def catch_error(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except (core.RPCError,
                requests.exceptions.ConnectionError):
            core.is_online = False
            return offline()
        except core.UnauthorizedError:
            return unauthorized()
        except Exception as e:
            return unknown_exception(e)
    return wrapper


# snippet from: http://flask.pocoo.org/snippets/56/
from datetime import timedelta
from flask import make_response, current_app, request
from functools import update_wrapper

def crossdomain(origin=None, methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, str):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, str):
        origin = ', '.join(origin)
    if isinstance(max_age, timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator

# Note: before each view, we clear the rpc cache, and have cached=True by default
# this allows to ensure we only perform a given rpc call once with a given set
# of args, no matter how many times we call it from the view (ie: we might need
# to call 'is_online' or 'info' quite a few times, and we don't want to be sending
# all these requests over ssh...)
def clear_rpc_cache(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        rpc.main_node.clear_rpc_cache()
        return f(*args, **kwargs)
    return wrapper


"""
@bp.route('/')
def homepage():
    return redirect('/info')
"""

@bp.route('/delegates')
@crossdomain(origin='*')
@clear_rpc_cache
@catch_error
def api_delegates():
    total_shares = rpc.main_node.get_info()['blockchain_share_supply']

    delegates = rpc.main_node.blockchain_list_delegates(0, 400)

    return jsonify(result=[[d['name'],
                           '%.2f%%' % (d['delegate_info']['votes_for'] * 100 / total_shares)]
                           for d in delegates])

@bp.route('/delegate_info/<delegate_name>')
@crossdomain(origin='*')
@clear_rpc_cache
@catch_error
def delegate_info(delegate_name):
    delegates = rpc.main_node.blockchain_list_delegates(0, 400)
    for i, d in enumerate(delegates):
        if d['name'] == delegate_name:
            delegate = d
            rank = i + 1
            break
    else:
        raise ValueError('Unknown delegate: %s' % delegate_name)

    total_shares = rpc.main_node.get_info()['blockchain_share_supply']
    votes_for = '%.2f%%' % (d['delegate_info']['votes_for'] * 100 / total_shares)

    # there are ~2650 blocks/month/delegate, so no need to get more of them
    # FIXME: this needs to be cached, same as in rpcutils...
    slots = rpc.main_node.blockchain_get_delegate_slot_records(delegate_name, 10000)
    if slots:
        producing = slots[0].get('block_id') is not None
        streak = list(itertools.takewhile(lambda x: (type(x.get('block_id')) is type(slots[0].get('block_id'))), slots))
        last_produced = len(streak)

        def get_ts(slot):
            return slot['index']['timestamp']
        did_not_miss_since = get_ts(streak[-1])

        now = arrow.utcnow()
        one_day_ago = now.replace(days=-1)
        one_week_ago = now.replace(weeks=-1)
        one_month_ago = now.replace(months=-1)

        def ratio(slots):
            produced, total = 0, 0
            for s in slots:
                if s.get('block_id') is not None:
                    produced += 1
                total += 1
            return float(produced) / total

        last_day = list(filter(lambda x: arrow.get(get_ts(x)) > one_day_ago, slots))
        last_week = list(filter(lambda x: arrow.get(get_ts(x)) > one_week_ago, slots))
        last_month = list(filter(lambda x: arrow.get(get_ts(x)) > one_month_ago, slots))
        ratio_last_day = '%.2f%%' % (ratio(last_day) * 100) if last_day else 'N/A'
        ratio_last_week = '%.2f%%' % (ratio(last_week) * 100) if last_week else 'N/A'
        ratio_last_month = '%.2f%%' % (ratio(last_month) * 100) if last_month else 'N/A'

    else:
        producing = True
        last_produced = 0
        did_not_miss_since = 'N/A'
        ratio_last_day = 'N/A'
        ratio_last_week = 'N/A'
        ratio_last_month = 'N/A'


    result = { 'votes_for': votes_for,
               'rank': rank,
               'producing': producing,
               'last_produced': last_produced,
               'ratio_last_day': ratio_last_day,
               'ratio_last_week': ratio_last_week,
               'ratio_last_month': ratio_last_month,
               'not_missed_since': did_not_miss_since,
               #'accumulated pay': 0
               }

    return jsonify(result=result)
