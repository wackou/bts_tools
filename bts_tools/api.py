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

from flask import Flask
from bts_tools import views_public
import bts_tools
import bts_tools.monitor
import logging

log = logging.getLogger(__name__)



def create_app(settings_override=None):
    """Returns the BitShares Delegate Tools Server api application instance"""

    print('creating Flask app bts_tools:api')
    app = Flask('bts_tools', instance_relative_config=True)

    app.config.from_object(settings_override)

    app.register_blueprint(views_public.bp)

    # make bts_tools module available in all the templates
    app.jinja_env.globals.update(core=bts_tools.core,
                                 backbone=bts_tools.backbone,
                                 rpc=bts_tools.rpcutils,
                                 monitor=bts_tools.monitor)

    return app



