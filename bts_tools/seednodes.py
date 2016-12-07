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
from collections import defaultdict
import socket
import time
import threading
import logging
log = logging.getLogger(__name__)


SEED_STATUS_TIMEOUT = 5  # in seconds

SEED_NODES = {
    'bts': [
        ('bts-seed1.abit-more.com:62015',  '', 'abit',        ''),
        ('seed.blocktrades.us:1776',       '', 'blocktrades', ''),
        ('seed.bitsharesnodes.com:1776',   '', 'wackou',      ''),
        ('seed04.bitsharesnodes.com:1776', '', 'thom',        ''),
        ('seed05.bitsharesnodes.com:1776', '', 'thom',        ''),
        ('seed06.bitsharesnodes.com:1776', '', 'thom',        ''),
        ('seed07.bitsharesnodes.com:1776', '', 'thom',        ''),
        ('seed.cubeconnex.com:1777',       '', 'cube',        ''),
        ('54.85.252.77:39705',             '', 'lafona',      ''),
        ('104.236.144.84:1777',            '', 'puppies',     ''),
        ('212.47.249.84:50696',            '', 'ihashfury',   ''),
        ('128.199.143.47:2015',            '', 'harvey',      ''),
        ('seed.roelandp.nl:1776',          '', 'roelandp',    '')
    ],
    'muse': [
        ('104.238.191.99:1781',            'fr', '', ''),
        ('120.24.182.36:8091',             'cn', '', ''),
        ('128.199.143.47:2017',            'sg', '', ''),
        ('139.129.54.169:8091',            'cn', '', ''),
        ('139.196.182.71:9091',            'cn', '', ''),
        ('159.203.251.178:1776',           'us', '', ''),
        ('185.82.203.92:1975',             'nl', 'riverhead', ''),
        ('192.241.190.227:5197',           'us', '', ''),
        ('192.241.208.17:5197',            'us', '', ''),
        ('54.165.143.33:5197',             'us', 'official seed node', ''),
        ('45.55.13.98:1776',               'us', 'puppies', ''),
        ('81.89.101.133:1777',             'de', 'pc', ''),
        ('212.47.249.84:50796',            '',   'delegate.ihashfury', ''),
        ('seed.musenodes.com:1781',        'nl', 'wackou', '')
    ],
    'steem': [
        ('212.117.213.186:2016',             'ch', 'liondani',       'https://steemit.com/introduceyourself/@liondani/hi-liondani-here-aka-daniel-schwarz-happy-husband-father-steem-witness-steemit-enthusiast'),
        ('seed.riversteem.com:2001',         'nl', 'riverhead',      'https://steemit.com/witness-category/@riverhead/witness-proposal-riverhead'),
        ('52.74.152.79:2001',                'sg', 'smooth',         'https://steemit.com/witness-category/@smooth.witness/smooth-witness'),
        ('seed.rossco99.com:2001',           '',   'rossco99',       ''),
        ('104.236.82.250:2001',              'us', 'svk',            'https://steemit.com/witness-category/@witness.svk/witness-thread'),
        ('steem.kushed.com:2001',            'us', 'kushed',         'www.saluscoin.info'),
        ('steemd.pharesim.me:2001',          'de', 'pharesim',       'https://steemit.com/witness-category/@pharesim/witness-post'),
        ('seed.steemnodes.com:2001',         '',   'wackou',         'https://steemit.com/witness-category/@wackou/wackou-witness-post'),
        ('steemseed.dele-puppy.com:2001',    'us', 'puppies',        ''),
        ('seed.steemed.net:2001',            'us', 'steemed',        'https://steemdb.com/@steemed'),
        ('steem-seed1.abit-more.com:2001',   'au', 'abit',           'https://steemit.com/witness-category/@abit/abit-witness-post'),
        ('steem.clawmap.com:2001',           'gb', 'steempty',       'https://steemit.com/witness-category/@steempty/steempty-witness-post'),
        ('seed.steemfeeder.com:2001',        'au', 'au1nethyb1',     'https://steemit.com/witness-category/@au1nethyb1/au1nethyb1-witness-in-the-lan-down-under'),
        ('steem-id.altexplorer.xyz:2001',    '',   'steem-id',       'https://keybase.io/jemekite'),
        ('213.167.243.223:2001',             'fr', 'bhuz',           'https://steemit.com/witness-category/@bhuz/bhuz-witness-thread'),
        ('seed.steemd.com:34191',            'us', 'roadscape',      'https://steemit.com/witness-category/@roadscape/witness-roadscape'),
        ('52.4.250.181:39705',               'us', 'lafona',         'https://steemit.com/witness-category/@delegate.lafona/delegate'),
        ('46.252.27.1:1337',                 'de', 'jabbasteem',     'https://steemit.com/witness-category/@jabbasteem/witness-jabbasteem'),
        ('anyx.co:2001',                     '',   'anyx',           'https://steemit.com/witness-category/@anyx/witness-application-anyx'),
        ('seed.cubeconnex.com:2001',         '',   'bitcube',        'https://steemit.com/witness-category/@bitcube/bitcube-witness-post'),
        ('212.47.249.84:40696',              'fr', 'ihashfury',      'https://steemit.com/witness-category/@ihashfury/ihashfury-witness-thread'),
        ('104.199.157.70:2001',              'us', 'clayop',         'https://steemit.com/witness-category/@clayop/witness-clayop'),
        ('104.40.230.35:2001',               '',   'aizensou',       'https://steemit.com/witness-category/@aizensou/witness-application-aizensou'),
        ('gtg.steem.house:2001',             '',   'gtg',            'https://steemit.com/witness-category/@gtg/witness-gtg'),
        ('seed.steem.network:2001',          'us', 'someguy123',     'https://steemit.com/witness-category/@someguy123/someguy123-witness-thread'),
        ('seed.zapto.org:2001',              '',   'geoffrey',       'https://steemit.com/witness-category/@geoffrey/witness-geoffrey'),
        ('seed.jesta.us:2001',               '',   'jesta',          'http://jesta.us'),
        ('seed.royaltiffany.me:2001',        '',   'royaltiffany',   'https://steemit.com/witness-category/@royaltiffany/royaltiffany-witness-thread'),
        ('steem.imcoins.org:2001',           '',   'dr2073',         'https://steemit.com/witness-category/@dr2073/witness-thread-dr2073'),
        ('104.196.141.163:2001',             '',   'good-karma',     'https://steemit.com/witness-category/@good-karma/good-karma-witness-thread'),
        ('steem.global:2001',                '',   'klye',           'https://steemit.com/witness-category/@klye/klye-s-witness-campaign'),
        ('seed.thecryptodrive.com:2001',     '',   'thecryptodrive', 'https://steemit.com/witness-category/@thecryptodrive/ricardo-goncalves-thecryptodrive-first-steem-witness-in-africa-a-witness-for-the-people'),
        ('45.55.54.83:2001',                 '',   'tdv.witness',    'https://steemit.com/steemit/@dollarvigilante/announcement-the-dollar-vigilante-witness-proposal-tdv-witness'),
        ('seed.roelandp.nl:2001',            '',   'roelandp',       'https://steemit.com/witness-category/@roelandp/witness-roelandp'),
        ('seed.steempower.org:2001',         '',   'charlieshrem',   'https://steemit.com/witness-category/@charlieshrem/announcement-charlie-shrem-advisor-to-steem-and-witness-proposal'),
        ('178.63.82.69:2001',                '',   'theprophet0',    'https://steemit.com/witness-category/@theprophet0/theprophet0-steem-witness-youngest-steem-witness-at-15-years-of-age-100-of-the-funds-from-this-blog-will-be-donated-to-charity'),
        ('5.9.18.213:2001',                  '',   'pfunk', 'https://steemit.com/witness-category/@pfunk/backup-witness-pfunk'),
        ('176.31.126.187:2001',              '',   'timcliff', 'https://steemit.com/witness-category/@timcliff/i-m-timcliff-and-i-approve-this-message-my-witness-application'),
        ('seed.bitcoiner.me:2001',           '',   'bitcoiner', 'https://steemit.com/witness-category/@bitcoiner/bitcoiner-witness-thread')
    ]
}

def check_valid_seed_nodes():
    for chain, seeds in SEED_NODES.items():
        ips = [(host, resolve_dns(host), provider) for host, _, provider, *_ in seeds]
        for ip in set(x[1] for x in ips):
            found = [i for i in ips if i[1] == ip]
            if len(found) > 1:
                log.error('For chain {}, ip {} appears more than 1 time:'.format(chain, ip))
                for host, i, provider in found:
                    log.error(' - {}  ({})'.format(host, provider))

# basic check when launching the app
check_valid_seed_nodes()


def check_seed_status(seed):
    host, port = seed.split(':')
    s = socket.socket()
    s.settimeout(SEED_STATUS_TIMEOUT)
    try:
        s.connect((host, int(port)))
    except (ConnectionError, socket.timeout):
        return 'offline'
    except OSError:
        return 'not reachable'
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


_SEEDS_STATUS = defaultdict(dict)

def monitor_seed_nodes(chain):
    global _SEEDS_STATUS
    while True:
        _SEEDS_STATUS[chain] = check_all_seeds(chain)
        time.sleep(300)


def check_all_seeds_cached(chain):
    return _SEEDS_STATUS[chain]


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


def get_seeds_view_data(chain, cached=False):
    seed_nodes = SEED_NODES[chain]

    if cached:
        seed_status = check_all_seeds_cached(chain)
    else:
        seed_status = check_all_seeds(chain)

    success = lambda s: '<div class="btn btn-xs btn-success">{}</div>'.format(s)
    warning = lambda s: '<div class="btn btn-xs btn-warning">{}</div>'.format(s)
    error = lambda s: '<div class="btn btn-xs btn-danger">{}</div>'.format(s)

    def get_flag(country):
        return '<i class="famfamfam-flag-%s" style="margin:0 8px 0 0;"></i>' % country

    def add_flag(country, ip):
        if not country:
            try:
                geo = get_geoip_info(resolve_dns(ip).split(':')[0])
                country = geo['country_iso'].lower()
            except ValueError:
                pass

        return '<span>%s %s</span>' % (get_flag(country), ip)

    def add_url(witness, url):
        if url:
            return '<a href="{}">{}</a>'.format(url, witness)
        else:
            return witness

    data = [(add_flag(location, seed), success('online'), add_url(provider, url))
            if seed_status.get(seed) == 'online' else
            (add_flag(location, seed), warning('stuck'), add_url(provider, url))
            if seed_status.get(seed) == 'stuck' else
            (add_flag(location, seed), error(seed_status.get(seed, 'offline')), add_url(provider, url))
            for seed, location, provider, url in seed_nodes]

    #attrs = {}
    #data, attrs = split_columns(data, attrs)

    return data
