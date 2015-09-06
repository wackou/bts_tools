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

from flask import render_template, Flask
from bts_tools import views
from bts_tools import rpcutils as rpc
from geolite2 import geolite2
from functools import lru_cache
import bts_tools
import bts_tools.monitor
import threading
import logging

log = logging.getLogger(__name__)


def format_datetime(d):
    if not d.strip():
        return ''
    if d == 'unknown':
        return d
    if '-' in d and ':' in d:
        # already formatted, just make it slightly nicer
        return d.replace('T', ' ')
    return '%s-%s-%s %s:%s:%s' % (d[0:4], d[4:6], d[6:8], d[9:11], d[11:13], d[13:15])


@lru_cache()
def get_country_for_ip(ip):
    if not ip.strip():
        return None
    reader = geolite2.reader()
    try:
        return reader.get(ip)['country']['iso_code'].lower()
    except:
        return None


def add_ip_flag(ip):
    country = get_country_for_ip(ip)
    if not country:
        return ip
    flag = '<i class="famfamfam-flag-%s" style="margin:0 8px 0 0;"></i>' % country
    return '<table><tr><td>%s</td><td>%s</td></tr></table>' % (flag, ip)


def create_app(settings_override=None):
    """Returns the BitShares Delegate Tools Server dashboard application instance"""

    print('creating Flask app bts_tools')
    app = Flask('bts_tools', instance_relative_config=True)

    app.config.from_object(settings_override)

    app.register_blueprint(views.bp)

    # Register custom error handlers
    app.errorhandler(404)(lambda e: (render_template('errors/404.html'), 404))

    # custom filter for showing dates
    app.jinja_env.filters['datetime'] = format_datetime
    app.jinja_env.filters['add_ip_flag'] = add_ip_flag

    # make bts_tools module available in all the templates
    app.jinja_env.globals.update(core=bts_tools.core,
                                 backbone=bts_tools.backbone,
                                 rpc=bts_tools.rpcutils,
                                 monitor=bts_tools.monitor,
                                 process=bts_tools.process)

    for (host, port), nodes in rpc.unique_node_clients():
        # launch only 1 monitoring thread for each running instance of the client
        t = threading.Thread(target=bts_tools.monitor.monitoring_thread, args=nodes)
        t.daemon = True
        t.start()

    return app



