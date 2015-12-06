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
from datetime import datetime
from os.path import join, dirname, expanduser, exists, abspath
from collections import namedtuple
from subprocess import Popen, PIPE
from functools import wraps
from contextlib import suppress
import sys
import os
import shutil
import yaml
import time
import logging

log = logging.getLogger(__name__)

platform = sys.platform
if platform.startswith('linux'):
    platform = 'linux'

HERE = abspath(dirname(__file__))
BTS_TOOLS_HOMEDIR = '~/.bts_tools'
BTS_TOOLS_HOMEDIR = expanduser(BTS_TOOLS_HOMEDIR)
BTS_TOOLS_CONFIG_FILE = join(BTS_TOOLS_HOMEDIR, 'config.yaml')

config = None


def append_unique(l1, l2):
    for obj in l2:
        if obj not in l1:
            l1.append(obj)


def load_config(loglevels=None):
    log.info('Using home dir for BTS tools: %s' % BTS_TOOLS_HOMEDIR)
    global config
    if not exists(BTS_TOOLS_CONFIG_FILE):
        log.info('Copying default config file to %s' % BTS_TOOLS_CONFIG_FILE)
        try:
            os.makedirs(BTS_TOOLS_HOMEDIR)
        except OSError:
            pass
        shutil.copyfile(join(dirname(__file__), 'config.yaml'),
                        BTS_TOOLS_CONFIG_FILE)

    try:
        log.info('Loading config file: %s' % BTS_TOOLS_CONFIG_FILE)
        config_contents = open(BTS_TOOLS_CONFIG_FILE).read()
    except:
        log.error('Could not read config file: %s' % BTS_TOOLS_CONFIG_FILE)
        raise

    try:
        config = yaml.load(config_contents)
    except:
        log.error('-'*100)
        log.error('Config file contents is not a valid YAML object:')
        log.error(config_contents)
        log.error('-'*100)
        raise

    # setup given logging levels, otherwise from config file
    loglevels = loglevels or config.get('logging', {})
    for name, level in loglevels.items():
        logging.getLogger(name).setLevel(getattr(logging, level))


    # check whether config.yaml has a correct format
    errors = []
    m = config['monitoring']

    if 'email' in m:
        errors.append("'email' subsection of 'monitoring' should be moved to a 'notification' section instead")

    if 'boxcar' in m:
        errors.append("'boxcar' subsection of 'monitoring' should be moved to a 'notification' section instead")

    if 'cpu_ram_usage' not in m:
        errors.append("the 'monitoring' section should have a 'cpu_ram_usage' configuration entry")

    for node in config['nodes']:
        for notification_type in ['email', 'boxcar']:
            if notification_type in node.get('monitoring', []):
                errors.append("node '%s' has '%s' in its 'monitoring' section, it should be moved to a 'notification' property instead" %
                              (node['name'], notification_type))

    if errors:
        log.error('Invalid config.yaml file. The following errors have been found:')
        for err in errors:
            log.error('* %s' % err)
        log.error('File is located at: %s' % BTS_TOOLS_CONFIG_FILE)
        log.error('Please edit this file or delete it and let the tools create a new default one (run "bts list", for instance).')
        log.error('Note that some monitoring functionality now needs to be specified explicitly (seed, missed, network_connections)')
        log.error('Visit http://bts-tools.readthedocs.org/en/latest/config_format.html#nodes-list for more information).')
        sys.exit(1)


    # warn about parameters that should be set, and potentially adjust config with default values
    if 'feed_providers' not in m['feeds']:
        log.warning('You did not specify the monitoring.feeds.feed_providers variable')
        log.warning('Using default value of [Yahoo, Bter, Btc38, Poloniex]')
        log.warning('You might want to add [Google, Bloomberg] to that list')
        m['feeds']['feed_providers'] = ['Yahoo', 'Bter', 'Btc38', 'Poloniex']

    def check_feed_option(name, default_value):
        if name not in m['feeds']:
            log.warning("{} not in config['monitoring']['feeds']. Setting to default value: {}".format(name, default_value))
            m['feeds'][name] = default_value

    check_feed_option('core_exchange_factor', 0.95)
    check_feed_option('maintenance_collateral_ratio', 1750)
    check_feed_option('maximum_short_squeeze_ratio', 1100)

    if (m['feeds'].get('publish_time_interval') is None and
        m['feeds'].get('publish_time_slot') is None):
        log.warning('Will not be able to publish feeds. You need to specify '
                    'either publish_time_interval or publish_time_slot')

    # expand wildcards for monitoring plugins
    for n in config['nodes']:
        n.setdefault('monitoring', [])
        if not isinstance(n['monitoring'], list):
            n['monitoring'] = [n['monitoring']]

        def add_cmdline_args(args):
            # only do this for delegates running on localhost (for which we have a 'client' field defined)
            if 'client' in n:
                client = config['run_environments'][n['client']]
                # --statistics-enabled not available for PTS yet
                if client['type'] == 'pts':
                    with suppress(ValueError):
                        args.remove('--statistics-enabled')
                append_unique(client.setdefault('run_args', []), args)

        def add_monitoring(l2):
            append_unique(n['monitoring'], l2)

        # options for 'delegate' node types
        if n['type'] == 'delegate' and not is_graphene_based(n):
            add_cmdline_args(['--min-delegate-connection-count=0', '--statistics-enabled'])
        if 'delegate' in n['monitoring']:
            # TODO: add 'prefer_backbone_exclusively' when implemented; in this case we also need:

            # TODO: "--accept-incoming-connections 0" (or limit list of allowed peers from within the client)
            add_monitoring(['missed', 'network_connections', 'voted_in', 'wallet_state', 'fork', 'version', 'feeds'])
        if 'watcher_delegate' in n['monitoring']:
            # for monitoring a delegate but not publishing feeds or anything official
            add_monitoring(['missed', 'network_connections', 'voted_in', 'wallet_state', 'fork'])

        # options for seed node types
        if n['type'] == 'seed':
            add_monitoring(['seed', 'network_connections', 'fork'])

        # options for backbone node types
        if n['type'] == 'backbone':
            add_cmdline_args(['--disable-peer-advertising'])
            add_monitoring(['backbone', 'network_connections', 'fork'])

    return config


def is_graphene_based(n):
    # TODO: this function really can't get any uglier... Would benefit from a facelift
    from .rpcutils import BTSProxy
    if isinstance(n, BTSProxy):
        return is_graphene_based(n.bts_type())
    elif 'type' in n and 'client' in n:
        # if we're a node desc, get it from the run_env
        return is_graphene_based(n['client'])
    elif 'type' in n:
        # if we're a run env, get it from the build env
        return is_graphene_based(n['type'])
    else:
        # if we're a string, we might be a build env or a run env
        try:
            # if we're a run env, get the associated build env
            n = config['run_environments'][n]['type']
        except KeyError:
            pass
        return n == 'bts2' or n == 'muse'


DEFAULT_HOMEDIRS = {'development': {'linux': '~/.BitSharesXTS',
                                    'darwin': '~/Library/Application Support/BitShares XTS'},
                    'bts':         {'linux': '~/.BitShares',
                                    'darwin': '~/Library/Application Support/BitShares'},
                    'bts2':        {'linux': '~/.BitShares2',
                                    'darwin': '~/Library/Application Support/BitShares2'},
                    'muse':        {'linux': '~/.Muse',
                                    'darwin': '~/Library/Application Support/Muse'},
                    'dvs':         {'linux': '~/.DevShares',
                                    'darwin': '~/Library/Application Support/DevShares'},
                    'pts':         {'linux': '~/.PTS',
                                    'darwin': '~/Library/Application Support/PTS'},
                    'pls':         {'linux': '~/.DACPLAY',
                                    'darwin': '~/Library/Application Support/DAC PLAY'}
                    }

DEFAULT_BIN_FILENAMES = {'bts2': ['witness_node/witness_node', 'cli_wallet/cli_wallet'],
                         'muse': ['witness_node/witness_node', 'cli_wallet/cli_wallet'],
                         'bts': ['client/bitshares_client'],
                         'dvs': ['client/devshares_client'],
                         'pts': ['client/pts_client'],
                         'pls': ['client/play_client']
                         }

DEFAULT_GUI_BIN_FILENAMES = {'bts2': '',
                             'muse': '',
                             'bts': 'BitShares',
                             'dvs': 'DevShares',
                             'pts': 'PTS',
                             'pls': 'PLAY'
                             }


def get_data_dir(env):
    try:
        env = config['run_environments'][env]
    except KeyError:
        log.error('Unknown run environment: %s' % env)
        sys.exit(1)

    data_dir = env.get('data_dir') or DEFAULT_HOMEDIRS.get(env['type'], {}).get(platform)
    return expanduser(data_dir) if data_dir else None


def get_gui_bin_name(build_env):
    return DEFAULT_GUI_BIN_FILENAMES[build_env]


def get_all_bin_names(run_env=None, build_env=None):
    if run_env is not None:
        try:
            env = config['run_environments'][run_env]
        except KeyError:
            log.error('Unknown run environment: %s' % env)
            sys.exit(1)

        return get_all_bin_names(build_env=env['type'])

    elif build_env is not None:
        return DEFAULT_BIN_FILENAMES[build_env]

    else:
        raise ValueError('You need to specify either a build env or run env')


def get_full_bin_name(run_env=None, build_env=None):
    return get_all_bin_names(run_env, build_env)[0]


def get_bin_name(run_env=None, build_env=None):
    return os.path.basename(get_full_bin_name(run_env, build_env))


IOStream = namedtuple('IOStream', 'status, stdout, stderr')
GlobalStatsFrame = namedtuple('GlobalStatsFrame', 'cpu_total, timestamp')
StatsFrame = namedtuple('StatsFrame', 'cpu, mem, connections, timestamp')


def join_shell_cmd(cmd):
    if isinstance(cmd, list):
        if len(cmd) > 1: # if we have args, quote them properly
            cmd = cmd[0] + ' "' + '" "'.join(cmd[1:]) + '"'
        else:
            cmd = cmd[0]
    return cmd


def _run(cmd, capture_io=False, verbose=False):
    cmd = join_shell_cmd(cmd)

    (log.info if verbose else log.debug)('SHELL: running command: %s' % cmd)

    if capture_io:
        p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        if sys.version_info[0] >= 3:
            stdout, stderr = (str(stdout, encoding='utf-8'),
                              str(stderr, encoding='utf-8'))
        return IOStream(p.returncode, stdout, stderr)

    else:
        p = Popen(cmd, shell=True)
        p.communicate()
        return IOStream(p.returncode, None, None)


def run(cmd, capture_io=False, verbose=True):
    r = _run(cmd, capture_io, verbose)
    if r.status != 0:
        log.warning('Failed running: %s' % cmd)
        if capture_io:
            log.warning('\nSTDOUT:\n{}\nSTDERR:\n:{}'.format(r.stdout, r.stderr))
        raise RuntimeError('Failed running: %s' % cmd)
    return r


def get_version():
    version_file = join(HERE, 'version.txt')
    if exists(version_file):
        with open(version_file) as f:
            return f.read().strip()
    try:
        return run('git describe --tags', capture_io=True, verbose=False).stdout.strip()
    except Exception:
        return 'unknown'

VERSION = get_version()


class UnauthorizedError(Exception):
    pass


class RPCError(Exception):
    pass


class NoFeedData(Exception):
    pass


class hashabledict(dict):
    def __init__(self, *args, **kwargs):
        """try to also convert inner dicts to hashable dicts"""
        super().__init__(*args, **kwargs)
        for k, v in self.items():
            if isinstance(v, dict):
                self[k] = hashabledict(v)

    def __key(self):
        return tuple(sorted(self.items()))

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()


def to_list(obj):
    if obj is None:
        return []
    elif isinstance(obj, list):
        return obj
    else:
        return [obj]


def profile(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        plog = logging.getLogger('bts_tools.profile')

        args_str = ', '.join(str(arg) for arg in args)
        if kwargs:
            args_str + ', ' + ', '.join('%s=%s' % (k, v) for k, v in kwargs.items())

        try:
            start_time = time.time()
            result = f(*args, **kwargs)
            stop_time = time.time()
            plog.debug('Function %s(%s): returned in %0.3f ms' % (f.__name__, args_str, (stop_time-start_time)*1000))
            return result
        except Exception:
            stop_time = time.time()
            plog.debug('Function %s(%s): exception in %0.3f ms' % (f.__name__, args_str, (stop_time-start_time)*1000))
            raise
    return wrapper


class FeedPrice(object):
    """Represent a feed price value. Contains additional metadata such as volume, etc.

    volume should be represented as number of <cur> units, not <base>."""
    def __init__(self, price, cur, base, volume=None, last_updated=None, provider=None):
        self.price = price
        self.cur = cur
        self.base = base
        self.volume = volume
        self.last_updated = last_updated or datetime.utcnow()
        self.provider = provider

    def __str__(self):
        return 'FeedPrice: {} {}/{}{}{}'.format(
            self.price, self.cur, self.base,
            ' - vol={}'.format(self.volume) if self.volume is not None else '',
            ' from {}'.format(self.provider) if self.provider else '')

    def __repr__(self):
        return '<{}>'.format(str(self))
