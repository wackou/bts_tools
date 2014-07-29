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

from werkzeug.serving import run_simple
from werkzeug.wsgi import DispatcherMiddleware
from bitshares_delegate_tools import frontend
import logging
log = logging.getLogger(__name__)

frontend_app = frontend.create_app()

application = DispatcherMiddleware(frontend_app)

DEBUG = False

def main():
    print('-'*100)
    print('Registered frontend routes:')
    print(frontend_app.url_map)

    run_simple('0.0.0.0', 5000, application,
               use_reloader=DEBUG,
               use_debugger=DEBUG)

if __name__ == '__main__':
    main()
