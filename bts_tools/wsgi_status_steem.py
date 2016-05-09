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

from flask import render_template, Flask, Blueprint
from werkzeug.serving import run_simple
from werkzeug.wsgi import DispatcherMiddleware
from bts_tools import core, frontend, init
from bts_tools.frontend import format_datetime, hide_private_key, add_ip_flag
from bts_tools.views import check_seed_status, split_columns
import bts_tools
import threading
import logging
log = logging.getLogger(__name__)

init()
DEBUG = core.config['wsgi_debug']

bp = Blueprint('web', __name__, static_folder='static', template_folder='templates')

chain = 'steem'

@bp.route('/')
def view_seed_nodes():
    # TODO: get them from cmdline args and config.ini / config.yaml files
    if chain == 'bts':
        seed_nodes = ['faucet.bitshares.org:1776',
                      'bitshares.openledger.info:1776',
                      'bts-seed1.abit-more.com:62015',  # abit
                      'seed.blocktrades.us:1776',
                      'seed.bitsharesnodes.com:1776',  # wackou
                      'seed04.bitsharesnodes.com:1776',  # thom
                      'seed05.bitsharesnodes.com:1776',  # thom
                      'seed06.bitsharesnodes.com:1776',  # thom
                      'seed07.bitsharesnodes.com:1776',  # thom
                      'seed.cubeconnex.com:1777',  # cube
                      '54.85.252.77:39705',  # lafona
                      '104.236.144.84:1777',  # puppies
                      '40.127.190.171:1777',  # betax
                      '185.25.22.21:1776',  # liondani (greece)
                      '212.47.249.84:50696',  # iHashFury (France)
                      '104.168.154.160:50696',  # iHashFury (USA)
                      '128.199.143.47:2015']  # Harvey
    elif chain == 'muse':
        seed_nodes = ['81.89.101.133:1777',
                      '104.238.191.99:1781',
                      '120.24.182.36:8091',
                      '128.199.143.47:2017',
                      '139.129.54.169:8091',
                      '139.196.182.71:9091',
                      '159.203.251.178:1776',
                      '185.82.203.92:1974',
                      '192.241.190.227:5197',
                      '192.241.208.17:5197',
                      '54.165.143.33:5197',  # official seed node
                      '45.55.13.98:1776',  # puppies
                      '81.89.101.133:1777']  # pc
    elif chain == 'steem':
        seed_nodes = ['212.117.213.186:2016',
                      '185.82.203.92:2001',
                      '52.74.152.79:2001',
                      '52.63.172.229:2001',
                      '104.236.82.250:2001',
                      '104.199.157.70:2001',
                      'steem.kushed.com:2001',
                      'steemd.pharesim.me:2001',
                      'seed.steemnodes.com:2001',
                      'steemseed.dele-puppy.com:2001',
                      'seed.steemwitness.com:2001',
                      'seed.steemed.net:2001',
                      'steem-seed1.abit-more.com:2001',
                      'steem.clawmap.com:2001',
                      '52.62.24.225:2001',
                      'steem-id.altexplorer.xyz:2001',
                      '213.167.243.223:2001',
                      '162.213.199.171:34191',
                      '45.55.217.111:12150',
                      '212.47.249.84:40696',
                      '52.4.250.181:39705',
                      '81.89.101.133:2001',
                      '109.74.206.93:2001',
                      '192.99.4.226:2001',
                      '46.252.27.1:1337']
    else:
        seed_nodes = []

    seed_status = {}

    threads = []
    for seed in seed_nodes:
        def set_seed_status(s):
            log.debug('check seed status {}'.format(s))
            seed_status[s] = check_seed_status(s)
            log.debug('finished check seed status {}'.format(s))

        t = threading.Thread(target=set_seed_status, args=(seed,))
        threads.append(t)
        t.start()

    log.debug('created {} threads'.format(len(threads)))

    for t in threads:
        t.join(timeout=5)
        if t.is_alive():
            log.debug('thread did timeout')
        else:
            log.debug('thread exited normally')


    headers = ['seed host', 'status'] * 2

    data = [(seed, '<div class="btn btn-xs btn-success">online</div>')
            if seed_status.get(seed) == 'online' else
            (seed, '<div class="btn btn-xs btn-warning">stuck</div>')
            if seed_status.get(seed) == 'stuck' else
            (seed, '<div class="btn btn-xs btn-danger">{}</div>'.format(seed_status.get(seed, 'offline')))
            for seed in seed_nodes]

    attrs = {}

    data, attrs = split_columns(data, attrs)

    return render_template('tableview_naked.html',
                           title='{} seed nodes'.format(chain),
                           headers=headers,
                           data=data, order='[]', nrows=100)



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
                                 rpc=bts_tools.rpcutils,
                                 monitor=bts_tools.monitor,
                                 process=bts_tools.process)

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
