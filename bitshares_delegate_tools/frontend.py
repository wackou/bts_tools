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

from flask import render_template, Flask
from bitshares_delegate_tools import views
import bitshares_delegate_tools
import bitshares_delegate_tools.monitor
import threading
import logging

log = logging.getLogger(__name__)


def format_datetime(d):
    return '%s-%s-%s %s:%s:%s' % (d[0:4], d[4:6], d[6:8], d[9:11], d[11:13], d[13:15])


def create_app(settings_override=None):
    """Returns the BitShares Delegate Tools Server dashboard application instance"""

    print('creating Flask app bitshares_delegate_tools')
    app = Flask('bitshares_delegate_tools', instance_relative_config=True)

    app.config.from_object(settings_override)

    app.register_blueprint(views.bp)

    # Register custom error handlers
    app.errorhandler(404)(lambda e: (render_template('errors/404.html'), 404))

    # custom filter for showing dates
    app.jinja_env.filters['datetime'] = format_datetime

    # make bitshares_delegate_tools module available in all the templates
    app.jinja_env.globals.update(core=bitshares_delegate_tools.core,
                                 rpc=bitshares_delegate_tools.rpcutils,
                                 monitor=bitshares_delegate_tools.monitor,
                                 process=bitshares_delegate_tools.process)

    c = bitshares_delegate_tools.core.config
    if (c['monitoring']['email']['active'] or
        c['monitoring']['apns']['active']):
        t = threading.Thread(target=bitshares_delegate_tools.monitor.monitoring_thread)
        t.daemon = True
        t.start()

    return app



