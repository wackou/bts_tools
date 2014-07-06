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

from functools import wraps
from flask import render_template, Flask
from bitshares_delegate_tools import dashboard
import bitshares_delegate_tools
import logging

log = logging.getLogger(__name__)



# Jinja filter for dates
def format_datetime(value, fmt='full'):
    if fmt == 'full':
        result = value.strftime('%Y-%m-%d %H:%M:%S')
        tzinfo = value.strftime('%Z')
        if tzinfo:
            result = result + ' ' + tzinfo
        return result
    return value.strftime(fmt)



def create_app(settings_override=None):
    """Returns the BitShares Delegate Tools Server dashboard application instance"""

    print('creating Flask app bitshares_delegate_tools')
    app = Flask('bitshares_delegate_tools', instance_relative_config=True)

    app.config.from_object(settings_override)

    app.register_blueprint(dashboard.bp)

    # Register custom error handlers
    app.errorhandler(404)(lambda e: (render_template('errors/404.html'), 404))
    #app.errorhandler(500)(lambda e: (render_template('errors/500.html'), 500))

    # custom filter for showing dates
    app.jinja_env.filters['datetime'] = format_datetime

    # make bitshares_delegate_tools module available in all the templates
    app.jinja_env.globals.update(bitshares_delegate_tools=bitshares_delegate_tools)

    app.debug = True

    return app


def handle_error(e):
    return render_template('errors/%s.html' % e.code), e.code



