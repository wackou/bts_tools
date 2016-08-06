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

from bts_tools.network_utils import get_geoip_info, resolve_dns
import socket
import threading
import logging
log = logging.getLogger(__name__)


SEED_STATUS_TIMEOUT = 5  # in seconds

SEED_NODES = {
    'bts': [
        ('bts-seed1.abit-more.com:62015',  'cn', 'abit'),
        ('seed.blocktrades.us:1776',       'us', 'blocktrades'),
        ('seed.bitsharesnodes.com:1776',   'nl', 'wackou'),
        ('seed04.bitsharesnodes.com:1776', 'au', 'thom'),
        ('seed05.bitsharesnodes.com:1776', 'de', 'thom'),
        ('seed06.bitsharesnodes.com:1776', 'ca', 'thom'),
        ('seed07.bitsharesnodes.com:1776', 'sg', 'thom'),
        ('seed.cubeconnex.com:1777',       'us', 'cube'),
        ('54.85.252.77:39705',             'us', 'lafona'),
        ('104.236.144.84:1777',            'us', 'puppies'),
        ('212.47.249.84:50696',            'fr', 'ihashfury'),
        ('128.199.143.47:2015',            'sg', 'harvey')
    ],
    'muse': [
        ('81.89.101.133:1777',             'de', ''),
        ('104.238.191.99:1781',            'fr', ''),
        ('120.24.182.36:8091',             'cn', ''),
        ('128.199.143.47:2017',            'sg', ''),
        ('139.129.54.169:8091',            'cn', ''),
        ('139.196.182.71:9091',            'cn', ''),
        ('159.203.251.178:1776',           'us', ''),
        ('185.82.203.92:1974',             'nl', ''),
        ('192.241.190.227:5197',           'us', ''),
        ('192.241.208.17:5197',            'us', ''),
        ('54.165.143.33:5197',             'us', 'official seed node'),
        ('45.55.13.98:1776',               'us', 'puppies'),
        ('81.89.101.133:1777',             'de', 'pc')
    ],
    'steem': [
        ('212.117.213.186:2016',           'ch', 'liondani'),
        ('seed.riversteem.com:2001',       'nl', 'riverhead'),
        ('52.74.152.79:2001',              'sg', 'smooth'),
        ('52.63.172.229:2001',             'au', 'rossco99'),
        ('104.236.82.250:2001',            'us', 'svk'),
        ('steem.kushed.com:2001',          'us', 'kushed'),
        ('steemd.pharesim.me:2001',        'de', 'pharesim'),
        ('seed.steemnodes.com:2001',       'nl', 'wackou'),
        ('steemseed.dele-puppy.com:2001',  'us', 'puppies'),
        ('seed.steemwitness.com:2001',     'us', 'nextgencrypto'),
        ('seed.steemed.net:2001',          'us', 'steemed'),
        ('steem-seed1.abit-more.com:2001', 'au', 'abit'),
        ('steem.clawmap.com:2001',         'gb', 'steempty'),
        ('52.62.24.225:2001',              'au', 'au1nethyb1'),
        ('steem-id.altexplorer.xyz:2001',  'id', 'steem-id'),
        ('213.167.243.223:2001',           'fr', 'bhuz'),
        ('seed.steemd.com:34191',          'us', 'roadscape'),
        ('52.4.250.181:39705',             'us', 'lafona'),
        ('46.252.27.1:1337',               'de', 'jabbasteem'),
        ('anyx.co:2001',                   '',   'anyx'),
        ('seed.cubeconnex.com:2001',       '',   'bitcube'),
        ('212.47.249.84:40696',            'fr', 'ihashfury'),
        ('104.199.157.70:2001',            'us', 'clayop'),
        ('104.40.230.35:2001',             '',   'aizensou'),
        ('gtg.steem.house:2001',           '',   'gtg / gandalf'),
        ('45.55.217.111:12150',            'us', ''),
        ('81.89.101.133:2001',             'de', ''),
        ('192.99.4.226:2001',              'ca', ''),
    ]
}


def check_seed_status(seed):
    host, port = seed.split(':')
    s = socket.socket()
    s.settimeout(SEED_STATUS_TIMEOUT)
    try:
        s.connect((host, int(port)))
    except (ConnectionError, socket.timeout):
        return 'offline'
    try:
        # do we receive a hello message?
        s.recv(256)
    except socket.timeout:
        return 'stuck'
    s.close()
    return 'online'


def check_all_seeds(chain):
    seed_nodes = [s[0] for s in SEED_NODES[chain]]
    seed_status = {}
    threads = {}
    for seed in seed_nodes:
        def set_seed_status(s):
            log.debug('check seed status {}'.format(s))
            seed_status[s] = check_seed_status(s)
            log.debug('finished check seed status {}'.format(s))


        t = threading.Thread(target=set_seed_status, args=(seed,))
        threads[seed] = t
        t.start()

    log.debug('created {} threads'.format(len(threads)))

    for seed, t in threads.items():
        t.join(timeout=2 * SEED_STATUS_TIMEOUT)
        if t.is_alive():
            log.debug('thread for {} did timeout'.format(seed))
        else:
            log.debug('thread for {} exited normally'.format(seed))

    return seed_status


def split_columns(items, attrs):
    # split into 2 columns, more readable on a laptop
    n = len(items)
    ncols = len(items[0]) if items else 0
    if n % 2 == 1:
        items.append(('',)*ncols)
        n += 1
    offset = int(n/2)

    items = [left+right for left, right in zip(items[:offset],
                                              items[offset:])]
    for a, l in attrs.items():
        for i, v in enumerate(l):
            l[i] = ((l[i][0], l[i][1])
                    if l[i][0] < offset
                    else (l[i][0] - offset, l[i][1] + ncols))

    return items, attrs


def get_seeds_as_peers(chain):
    return [{'addr': d[0], 'provided_by': d[2]} for d in SEED_NODES[chain]]


def get_seeds_view_data(chain):
    seed_nodes = [(s[0], s[1], s[2]) for s in SEED_NODES[chain]]
    seed_status = check_all_seeds(chain)

    success = lambda s: '<div class="btn btn-xs btn-success">{}</div>'.format(s)
    warning = lambda s: '<div class="btn btn-xs btn-warning">{}</div>'.format(s)
    error = lambda s: '<div class="btn btn-xs btn-danger">{}</div>'.format(s)

    def get_flag(country):
        return '<i class="famfamfam-flag-%s" style="margin:0 8px 0 0;"></i>' % country

    def add_flag(country, ip):
        try:
            geo = get_geoip_info(resolve_dns(ip).split(':')[0])
            country = geo['country_iso'].lower()
        except ValueError:
            pass

        return '<span>%s %s</span>' % (get_flag(country), ip)

    data = [(add_flag(location, seed), success('online'), provider)
            if seed_status.get(seed) == 'online' else
            (add_flag(location, seed), warning('stuck'), provider)
            if seed_status.get(seed) == 'stuck' else
            (add_flag(location, seed), error(seed_status.get(seed, 'offline')), provider)
            for seed, location, provider in seed_nodes]


    #attrs = {}
    #data, attrs = split_columns(data, attrs)

    return data
