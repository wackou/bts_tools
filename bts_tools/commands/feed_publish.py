#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
# Copyright (c) 2017 Nicolas Wack <wackou@gmail.com>
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

from .. import core
from ..rpcutils import GrapheneClient, rpc_call
from ..feeds import get_feed_prices_new, publish_bts_feed
from ruamel import yaml
import sys
import logging

log = logging.getLogger(__name__)


def short_description():
    return 'fetch all prices from feed sources and publishes them'


def help():
    return """feed_publish <config_filename>'
    
config_filename: config file
"""

def run_command(config_filename=None):
    if config_filename is None:
        log.error('You need to supply a config filename. Usage: {}'.format(help()))
        return

    cfg = yaml.safe_load(open(config_filename))
    node = None  # read from config file

    try:
        node = GrapheneClient('feed_publisher', cfg['client']['witness_name'], 'bts', cfg.get('client', {}))
    except Exception as e:
        log.error('Could not create graphene node:')
        log.exception(e)

    try:
        about = node.about()
    except Exception as e:
        log.error('Cannot connect to wallet on {}:{}'.format(cfg['client']['wallet_host'], cfg['client']['wallet_port']))
        #log.exception(e)
        #sys.exit(1)

    result, publish_list = get_feed_prices_new(node, cfg)


    base_msg = 'witness {} feeds: '.format(node.type(), node.name)

    publish_feeds = {(asset, base): 1/result.price(asset, base) for asset, base in publish_list}
    log.info(base_msg + 'publishing feeds: {}'.format(publish_feeds))

    publish_bts_feed(node, publish_feeds, base_msg)
