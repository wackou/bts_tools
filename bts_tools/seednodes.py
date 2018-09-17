
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
from collections import defaultdict, deque
import socket
import time
import threading
import logging
log = logging.getLogger(__name__)


SEED_STATUS_TIMEOUT = 5  # in seconds

SEED_NODES = {
    'bts': [
        ('bts-seed1.abit-more.com:62015',  '', 'abit',             ''),
        ('seed.blocktrades.us:1776',       '', 'blocktrades',      ''),
        ('seed.bitsharesnodes.com:1776',   '', 'wackou',           ''),
        ('seed04.bts-nodes.net:1776',      '', 'thom',             ''),
        ('seed05.bts-nodes.net:1776',      '', 'thom',             ''),
        ('seed06.bts-nodes.net:1776',      '', 'thom',             ''),
        ('seed07.bts-nodes.net:1776',      '', 'thom',             ''),
        ('seed.cubeconnex.com:1777',       '', 'cube',             ''),
        ('bts.lafona.net:1776',             '', 'lafona',           ''),
        ('104.236.144.84:1777',            '', 'puppies',          ''),
        ('seed.bitsharesdex.com:50696',    '', 'ihashfury',        ''),
        ('128.199.143.47:2015',            '', 'harvey',           ''),
        ('seed.roelandp.nl:1776',          '', 'roelandp',         ''),
        ('node.blckchnd.com:4243',         '', 'blckchnd',         ''),
        ('23.92.53.182:1776',              '', 'sahkan-bitshares', ''),
        ('seed.bts.bangzi.info:55501',     '', 'bangzi', '')
    ],
    'muse': [
        ('138.197.68.175:33333',          '', 'muse initial', ''),
        ('muse.roelandp.nl:33333',        '', 'roelandp',     ''),
        ('5.9.18.213:33333',              '', 'pfunk',        ''),
        ('45.79.206.79:33333',            '', 'jesta',        ''),
        ('muse-seed.altcap.io:33333',     '', 'ihashfury',    ''),
        ('muse.agoric.systems:33333',     '', 'robrigo',      ''),
        ('muse-seed.lafona.net:33333',    '', 'lafona',       ''),
        ('seed.musenodes.com:33333',      '', 'wackou',       'https://steemit.com/muse/@wackou/muse-blockchain-witness-proposal-wackou'),
        ('45.76.192.171:33333',           '', 'musepeer',     ''),
        ('muse-seed.xeldal.com:33333',    '', 'xeldal',       ''),
        ('muse.rondonson.com:33333',      '', 'rondonson',    ''),
        ('seed.muse.blckchnd.com:33333',  '', 'blckchnd',     ''),
        ('muse.cervantes.one:33333',      '', 'cervantes',    ''),
        ('muse.thetimsaid.com:33333',     '', 'timsaid',      ''),
        ('muse-seed.pt-kc.net:33333',     '', 'pt-kc',        ''),
        ('104.199.134.87:33333',          '', 'clayop',       ''),
        ('35.229.192.15:33333',           '', 'wmuse.seoul',  ''),
        ('88.198.90.17:33333',            'ca', 'johnstor5',    'https://steemit.com/witness/@raymonjohnstone/today-i-am-happy-to-introduce-my-witness-campaign-for-muse'),
        ('51.15.136.238:33333',           '', 'aboutall',     'https://steemit.com/muse/@aboutall/muse-witness-proposal'),
        ('116.62.121.169:33333',          '', 'muse-up',      ''),
        ('muse.riverhead.ltd:33333',      '', 'riverhead',    'https://steemit.com/muse/@riverhead/muse-witness-proposal'),
        ('seed.muse.dgazek.tk:33333',     '', 'dgazek',       'https://steemit.com/muse/@dganic/dgazek-muse-witness-proposal')
    ],
    'steem': [
        ('seed.steem-bounty.com:2001',       'us', 'steem-bounty',   'https://steemit.com/witness-category/@steem-bounty/announcing-our-new-steem-bounty-witness'),
        ('seed1.blockbrothers.io:2001',      'de', 'blockbrothers',  'https://steemit.com/witness-category/@blockbrothers/the-blockbrothers-are-now-a-witness-for-the-steem-blockchain'),
        ('seed.minnowshares.net:2001',       'de', 'reggaemuffin',   'https://steemit.com/witness-category/@reggaemuffin/witness-reggaemuffin'),
        ('seed.liondani.com:2016',           '',   'liondani',       'https://steemit.com/introduceyourself/@liondani/hi-liondani-here-aka-daniel-schwarz-happy-husband-father-steem-witness-steemit-enthusiast'),
        ('seed.riversteem.com:2001',         'nl', 'riverhead',      'https://steemit.com/witness-category/@riverhead/witness-proposal-riverhead'),
        ('52.74.152.79:2001',                'sg', 'smooth',         'https://steemit.com/witness-category/@smooth.witness/smooth-witness'),
        ('seed.rossco99.com:2001',           '',   'rossco99',       ''),
        ('steemd.pharesim.me:2001',          'de', 'pharesim',       'https://steemit.com/witness-category/@pharesim/witness-post'),
        ('seed.steemnodes.com:2001',         '',   'wackou',         'https://steemit.com/witness-category/@wackou/wackou-witness-post'),
        ('steem-seed1.abit-more.com:2001',   'au', 'abit',           'https://steemit.com/witness-category/@abit/abit-witness-post'),
        ('seed.steemd.com:34191',            'us', 'roadscape',      'https://steemit.com/witness-category/@roadscape/witness-roadscape'),
        ('lafonasteem.com:2001',             '',   'lafona',         'https://steemit.com/witness-category/@delegate.lafona/delegate'),
        ('anyx.co:2001',                     '',   'anyx',           'https://steemit.com/witness-category/@anyx/witness-application-anyx'),
        ('steem-seed.altcap.io:40696',       'fr', 'ihashfury',      'https://steemit.com/witness-category/@ihashfury/ihashfury-witness-thread'),
        ('104.199.118.92:2001',              'us', 'clayop',         'https://steemit.com/witness-category/@clayop/witness-clayop'),
        ('gtg.steem.house:2001',             '',   'gtg',            'https://steemit.com/witness-category/@gtg/witness-gtg'),
        ('steemseed-fin.privex.io:2001',     'fi', 'privex',         'https://steemit.com/witness-category/@privex/privex-announcement-launching-our-witness'),
        ('seed.jesta.us:2001',               '',   'jesta',          'http://jesta.us'),
        ('seed.esteem.ws:2001',              '',   'good-karma',     'https://steemit.com/witness-category/@good-karma/good-karma-witness-thread'),
        ('steem.global:2001',                '',   'klye',           'https://steemit.com/witness-category/@klye/klye-s-witness-campaign'),
        ('seed.thecryptodrive.com:2001',     '',   'thecryptodrive', 'https://steemit.com/witness-category/@thecryptodrive/ricardo-goncalves-thecryptodrive-first-steem-witness-in-africa-a-witness-for-the-people'),
        ('seed.roelandp.nl:2001',            '',   'roelandp',       'https://steemit.com/witness-category/@roelandp/witness-roelandp'),
        ('5.9.18.213:2001',                  '',   'pfunk',          'https://steemit.com/witness-category/@pfunk/backup-witness-pfunk'),
        ('seed.timcliff.com:2001',           '',   'timcliff',       'https://steemit.com/witness-category/@timcliff/i-m-timcliff-and-i-approve-this-message-my-witness-application'),
        ('seed.steemviz.com:2001',           '',   'ausbitbank',     'https://steemit.com/steem/@ausbitbank/new-seed-node-online-a-seedsteemvizcom'),
        ('steem-seed.lukestokes.info:2001',  '',   'lukestokes',     'https://steemit.com/witness-category/@lukestokes/vote-luke-stokes-for-witness-as-lukestokes-mhth'),
        ('seed.steemian.info:2001',          '',   'drakos',         'https://steemit.com/witness-category/@drakos/my-witness-application'),
        ('seed.followbtcnews.com:2001',      '',   'followbtcnews',  'https://steemit.com/witness-category/@followbtcnews/full-steem-ahead-vote-followbtcnews-for-witness'),
        ('node.mahdiyari.info:2001',         '',   'mahdiyari',      'https://steemit.com/witness-category/@mahdiyari/new-steem-seed-node-node-mahdiyari-info-2001'),
        ('seed.jamzed.pl:2001',              '',   'jamzed',         ''),
        ('seed.curiesteem.com:2001',         '',   'curie',          ''),
        ('seed.steemit.lu:2001',             'lu', 'lux-witness',    'https://steemit.com/@lux-witness'),
        ('node.steem.place:2001',             '',  'moisesmcardona', 'https://steemit.com/@moisesmcardona'),
        ('seed.steem.prcolaco.com:2001',     'pt', 'prc',            'https://steemit.com/witness-category/@prc/prc-witness-proposal-after-creating-dsound-and-attending-steemfest-2-i-want-more'),
        ('seed1.cryptobot.news:2001',        '',   'libertyranger',  ''),
        ('46.4.37.176:2001',                 'de', 'yuriks2000',     'https://steemit.com/witness-category/@yuriks2000/new-witness-announcement-steemapp-dev-team-yuriks2000-is-on-board'),
        ('seed.chainchopper.com:2001',       'us', 'justinadams',    'https://steemit.com/witness/@justinadams/the-people-can-we-get-a-witness-first-things-1st'),
        ('steem-seed.furion.me:2001',        'de', 'furion',         'https://steemit.com/@furion'),
        ('steem-seed.freshterrain.com:2001', 'au', 'piquet',         'https://steemit.com/@piquet'),
        ('seed-east.steemit.com:2001',       '',   'steemit',        ''),
        ('seed-central.steemit.com:2001',    '',   'steemit',        ''),
        ('seed-west.steemit.com:2001',       '',   'steemit',        ''),
        ('seed.xeldal.com:12150',            '',   'xeldal',         'https://steemit.com/witness-category/@xeldal/xeldal-witness-information'),
        ('seed.brandonfrye.us:2001',         '',   'brandonfrye',    'https://steemit.com/witness-category/@brandonfrye/brandon-frye-steem-witness-application'),
        ('seed.firepower.ltd:2001',          '',   'firepower',      'https://steemit.com/steem/@firepower/india-steem-meetup-3-an-awesome-meetup-in-mangalore-the-city-where-it-all-began'),
        ('steemseed.koinbot.org:2001',       'kr', 'koinbot',        'https://steemit.com/witness-category/@koinbot/koinbot-steem-witness-application'),
        ('seed1.cervantes.one:2001',         '',   'cervantes',      'https://steemit.com/@cervantes'),
        ('seed01.steemulant.com:2001',       '',   'quochuy',        'https://steemit.com/witness-category/@quochuy/new-steem-witness-announcement-greetings-from-quochuy')
    ],
    'ppy': [
        ('seed.ppy.blckchnd.com:6112',     '', 'blckchnd', ''),
        ('5.9.18.213:18828',               '', 'pfunk', ''),
        ('31.171.244.121:7777',            '', 'taconator', ''),
        ('seed.peerplaysdb.com:9777',      '', 'jesta', ''),
        ('ppy.esteem.ws:7777',             '', 'good-karma', ''),
        ('peerplays.roelandp.nl:9777',     '', 'roelandp', ''),
        ('ppy-seed.xeldal.com:19777',      '', 'xeldal', ''),
        ('peerplays-seed.altcap.io:61388', '', 'winner.winner.chicken.dinner', ''),
        ('seed.peerplaysnodes.com:9777',   '', 'wackou', ''),
        ('peerplays-seed.privex.io:7777',  '', 'someguy123/privex', ''),
        ('peerplays.agoric.systems:9777',  '', 'agoric.systems', ''),
        ('212.71.253.163:9777',            '', 'xtar', ''),
        ('51.15.35.96:9777',               '', 'lafona', ''),
        ('anyx.ca:9777',                   '', 'anyx', ''),
        ('ppyseed.nuevax.com:19777',       '', 'nuevax', ''),
        ('82.223.108.91:7777',             '', 'hiltos', ''),
        ('peerplays.butler.net:9777',      '', 'billbutler', ''),
        ('peerplays.bitcoiner.me:9777',    '', 'bitcoiner', ''),
        ('ppyseed.bacchist.me:42420',      '', 'bacchist-witness', ''),
        ('peerplays.bhuz.info:9777',       '', 'bhuz', ''),
        ('node.peerblock.trade:9777',      '', 'bitcoin-sig', ''),
        ('peerplays.crypto.fans:9777',     '', 'sc-steemit / crypto.fans', ''),
        ('23.227.163.201:9777',            '', 'royal-flush', '')
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
    except OSError as e:
        log.warning('Seed {} could not be reached because: {}'.format(seed, e))
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

    def set_seed_status(s):
        log.debug('check seed status {}'.format(s))
        seed_status[s] = check_seed_status(s)
        log.debug('finished check seed status {}'.format(s))

    for seed in seed_nodes:
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


_HISTORY = defaultdict(lambda: deque(maxlen=3))
_SEEDS_STATUS = defaultdict(dict)


def stable_status(chain, seed):
    h = _HISTORY[chain]
    if not h:
        return 'no data'

    seed_history = [st.get(seed, 'unknow seed') for st in h]
    last_status = seed_history[-1]

    if all(st == last_status for st in seed_history):
        return last_status
    if any(st == 'online' for st in seed_history):
        return 'online'

    log.warning('Could not decide status for {} seed {}: {}'.format(chain, seed, ','.join(seed_history)))

    return ','.join(seed_history)


def monitor_seed_nodes(chain):
    while True:
        _HISTORY[chain].append(check_all_seeds(chain))
        seed_nodes = [s[0] for s in SEED_NODES[chain]]
        _SEEDS_STATUS[chain] = {seed: stable_status(chain, seed)
                                for seed in seed_nodes}
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
            except (ValueError, AttributeError):
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
