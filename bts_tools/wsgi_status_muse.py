#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
# Copyright (c) 2016 Nicolas Wack <wackou@gmail.com>
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

from flask import render_template, Flask, Blueprint, jsonify
from werkzeug.serving import run_simple
from werkzeug.wsgi import DispatcherMiddleware
from bts_tools import core, init, seednodes, network_utils
from bts_tools.frontend import format_datetime, hide_private_key, add_ip_flag
from collections import defaultdict
import bts_tools
import threading
import logging
log = logging.getLogger(__name__)

init()
DEBUG = core.config['wsgi_debug']

bp = Blueprint('web', __name__, static_folder='static', template_folder='templates')

chain = 'muse'


@bp.route('/')
def view_seed_nodes():
    headers = ['seed host', 'status', 'provided by']
    data = seednodes.get_seeds_view_data(chain, cached=True)
    headers *= (len(data[0]) // len(headers))

    peers = seednodes.get_seeds_as_peers(chain)
    points = network_utils.get_world_map_points_from_peers(peers)
    countries = defaultdict(int)
    for pt in points:
        countries[pt['country_iso'].lower()] += 1

    return render_template('tableview_naked.html',
                           title='{} seed nodes'.format(chain),
                           headers=headers,
                           points=points,
                           countries=countries,
                           data=data, order='[[1, "desc"]]', nrows=100, sortable=True)


@bp.route('/status.json')
def json_online_nodes():
    status = seednodes.check_all_seeds_cached(chain)
    return jsonify(status)


def create_app(settings_override=None):
    print('creating Flask app bts_tools')
    app = Flask('bts_tools', instance_relative_config=True)

    app.config.from_object(settings_override)

    app.register_blueprint(bp)

    # Register custom error handlers
    app.errorhandler(404)(lambda e: (render_template('errors/404.html'), 404))

    # custom filter for showing dates
    app.jinja_env.filters['datetime'] = format_datetime
    app.jinja_env.filters['hide_private_key'] = hide_private_key
    app.jinja_env.filters['add_ip_flag'] = add_ip_flag

    # make bts_tools module available in all the templates
    app.jinja_env.globals.update(core=bts_tools.core,
                                 backbone=bts_tools.backbone,
                                 network_utils=bts_tools.network_utils,
                                 rpc=bts_tools.rpcutils,
                                 monitor=bts_tools.monitor,
                                 process=bts_tools.process)

    t = threading.Thread(target=bts_tools.seednodes.monitor_seed_nodes, args=(chain,))
    t.daemon = True
    t.start()

    return app

frontend_app = create_app()
frontend_app.debug = DEBUG

application = DispatcherMiddleware(frontend_app)

def main():
    print('-'*100)
    print('Registered frontend routes:')
    print(frontend_app.url_map)

    run_simple('0.0.0.0', 5000, application,
               use_reloader=DEBUG,
               use_debugger=DEBUG)

if __name__ == '__main__':
    main()
