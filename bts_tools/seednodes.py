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

import socket
import threading
import logging
log = logging.getLogger(__name__)


SEED_STATUS_TIMEOUT = 5  # in seconds

SEED_NODES = {
    'bts': [
        ('faucet.bitshares.org:1776',      '', ''),
        ('bitshares.openledger.info:1776', '', 'openledger'),
        ('bts-seed1.abit-more.com:62015',  '', 'abit'),
        ('seed.blocktrades.us:1776',       '', 'blocktrades'),
        ('seed.bitsharesnodes.com:1776',   '', 'wackou'),
        ('seed04.bitsharesnodes.com:1776', '', 'thom'),
        ('seed05.bitsharesnodes.com:1776', '', 'thom'),
        ('seed06.bitsharesnodes.com:1776', '', 'thom'),
        ('seed07.bitsharesnodes.com:1776', '', 'thom'),
        ('seed.cubeconnex.com:1777',       '', 'cube'),
        ('54.85.252.77:39705',             '', 'lafona'),
        ('104.236.144.84:1777',            '', 'puppies'),
        ('40.127.190.171:1777',            '', 'betax'),
        ('185.25.22.21:1776',              '', 'liondani'),
        ('212.47.249.84:50696',            '', 'ihashfury'),
        ('104.168.154.160:50696',          '', 'ihashfury'),
        ('128.199.143.47:2015'             '', 'harvey')
    ],
    'muse': [
        ('81.89.101.133:1777',   '', ''),
        ('104.238.191.99:1781',  '', ''),
        ('120.24.182.36:8091',   '', ''),
        ('128.199.143.47:2017',  '', ''),
        ('139.129.54.169:8091',  '', ''),
        ('139.196.182.71:9091',  '', ''),
        ('159.203.251.178:1776', '', ''),
        ('185.82.203.92:1974',   '', ''),
        ('192.241.190.227:5197', '', ''),
        ('192.241.208.17:5197',  '', ''),
        ('54.165.143.33:5197',   '', 'official seed node'),
        ('45.55.13.98:1776',     '', 'puppies'),
        ('81.89.101.133:1777'    '', 'pc')
    ],
    'steem': [
        ('212.117.213.186:2016',           '', 'liondani'),
        ('185.82.203.92:2001',             '', ''),
        ('52.74.152.79:2001',              '', 'smooth'),
        ('52.63.172.229:2001',             '', ''),
        ('104.236.82.250:2001',            '', ''),
        ('104.199.157.70:2001',            '', ''),
        ('steem.kushed.com:2001',          '', 'kushed'),
        ('steemd.pharesim.me:2001',        '', 'pharesim'),
        ('seed.steemnodes.com:2001',       '', 'wackou'),
        ('steemseed.dele-puppy.com:2001',  '', 'puppies'),
        ('seed.steemwitness.com:2001',     '', ''),
        ('seed.steemed.net:2001',          '', ''),
        ('steem-seed1.abit-more.com:2001', '', 'abit'),
        ('steem.clawmap.com:2001',         '', ''),
        ('52.62.24.225:2001',              '', ''),
        ('steem-id.altexplorer.xyz:2001',  '', ''),
        ('213.167.243.223:2001',           '', ''),
        ('162.213.199.171:34191',          '', ''),
        ('45.55.217.111:12150',            '', ''),
        ('212.47.249.84:40696',            '', ''),
        ('52.4.250.181:39705',             '', ''),
        ('81.89.101.133:2001',             '', ''),
        ('109.74.206.93:2001',             '', ''),
        ('192.99.4.226:2001',              '', ''),
        ('46.252.27.1:1337',               '', '')
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
        t.join(timeout=2 * SEED_STATUS_TIMEOUT)
        if t.is_alive():
            log.debug('thread did timeout')
        else:
            log.debug('thread exited normally')

    return seed_status


def split_columns(items, attrs):
    # split into 2 columns, more readable on a laptop
    n = len(items)
    if n % 2 == 1:
        items.append(('', ''))
        n += 1
    offset = int(n/2)

    items = [(a,b,c,d) for (a,b),(c,d) in zip(items[:offset],
                                              items[offset:])]
    for a, l in attrs.items():
        for i, v in enumerate(l):
            l[i] = ((l[i][0], l[i][1])
                    if l[i][0] < offset
                    else (l[i][0] - offset, l[i][1] + 2))

    return items, attrs


def get_seeds_view_data(chain):
    seed_nodes = [s[0] for s in SEED_NODES[chain]]
    seed_status = check_all_seeds(chain)

    data = [(seed, '<div class="btn btn-xs btn-success">online</div>')
            if seed_status.get(seed) == 'online' else
            (seed, '<div class="btn btn-xs btn-warning">stuck</div>')
            if seed_status.get(seed) == 'stuck' else
            (seed, '<div class="btn btn-xs btn-danger">{}</div>'.format(seed_status.get(seed, 'offline')))
            for seed in seed_nodes]


    attrs = {}

    data, attrs = split_columns(data, attrs)

    return data
