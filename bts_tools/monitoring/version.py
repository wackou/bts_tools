#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
# Copyright (c) 2015 Nicolas Wack <wackou@gmail.com>
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

from dogpile.cache import make_region
from collections import defaultdict
import logging

log = logging.getLogger(__name__)

# no expiration time, version stays constant as long as we run the same process
# we still need to invalidate the cache when a client comes online, we might
# have upgraded
def make_published_version_region():
    r = make_region()
    r.configure('dogpile.cache.memory')
    return r

published_version_region = defaultdict(make_published_version_region)


def is_valid_node(node):
    return node.is_witness() and not node.is_graphene_based()


def monitor(node, ctx, cfg):
    # published_version needs to be client specific
    published_version = published_version_region[node.rpc_id]

    if ctx.online_state.just_changed():
        published_version.invalidate()

    # publish node version if we're not up-to-date (eg: just upgraded)
    if not node.is_locked():
        def get_published_version():
            v = node.blockchain_get_account(node.name)
            try:
                return v['public_data']['version']
            except (KeyError, TypeError):
                log.info('Client version not published yet for delegate %s' % node.name)
                return 'none'

        version = ctx.info['client_version']
        pubver = published_version.get_or_create(node.name, get_published_version)
        if version != pubver:
            log.info('Publishing version %s for delegate %s (current: %s)' % (version, node.name, pubver))
            node.wallet_publish_version(node.name)
            published_version.set(node.name, version)

