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

from os.path import join, dirname, exists, islink, expanduser
from argparse import RawTextHelpFormatter
from contextlib import suppress
from pathlib import Path
from ruamel import yaml
from .core import (platform, run, get_data_dir, get_bin_name, get_gui_bin_name,
                   get_all_bin_names, is_graphene_based, join_shell_cmd,
                   hash_salt_password)
from .privatekey import PrivateKey
from . import core, init
from .rpcutils import rpc_call, GrapheneClient
import argparse
import os
import sys
import shutil
import arrow
import json
import logging

log = logging.getLogger(__name__)

BTS_GIT_REPO     = None
BTS_GIT_BRANCH   = None
BTS_BUILD_DIR    = None
BTS_HOME_DIR     = None
BTS_BIN_DIR      = None
BTS_BIN_NAME     = None
BTS_GUI_BIN_NAME = None

BUILD_ENV = None
RUN_ENV   = None


def select_build_environment(env_name):
    log.info("Using build environment '%s' on platform: '%s'" % (env_name, platform))

    if platform not in ['linux', 'darwin']:
        raise OSError('OS not supported yet, please submit a patch :)')

    try:
        env = core.config['build_environments'][env_name]
        env['name'] = env_name
    except KeyError:
        log.error('Unknown build environment: %s' % env_name)
        sys.exit(1)

    global BTS_GIT_REPO, BTS_GIT_BRANCH, BTS_BUILD_DIR, BTS_BIN_DIR, BUILD_ENV, BTS_BIN_NAME, BTS_GUI_BIN_NAME
    BTS_GIT_REPO     = env['git_repo']
    BTS_GIT_BRANCH   = env['git_branch']
    BTS_BUILD_DIR    = expanduser(env['build_dir'])
    BTS_BIN_DIR      = expanduser(env['bin_dir'])
    BTS_BIN_NAME     = get_bin_name(build_env=env_name)
    BTS_GUI_BIN_NAME = get_gui_bin_name(build_env=env_name)

    BUILD_ENV = env
    return env


def select_client(client):
    log.info("Running '%s' client" % client)
    try:
        env = core.config['clients'][client]
        env['name'] = client
    except KeyError:
        log.error('Unknown client: %s' % client)
        sys.exit(1)

    select_build_environment(env['type'])

    global BTS_HOME_DIR, RUN_ENV
    BTS_HOME_DIR = get_data_dir(client)
    RUN_ENV = env

    return env


def is_valid_environment(env):
    return (env in core.config['build_environments'] or
            env in core.config['clients'])


def clone():
    def is_git_dir(path):
        try:
            run('cd "%s"; git rev-parse' % BTS_BUILD_DIR, verbose=False)
            return True
        except RuntimeError:
            return False
    if not exists(BTS_BUILD_DIR) or not is_git_dir(BTS_BUILD_DIR):
        run('git clone %s "%s"' % (BTS_GIT_REPO, BTS_BUILD_DIR))


def clean_config():
    run('rm -f CMakeCache.txt')


CONFIGURE_OPTS = []
if platform == 'darwin':
    # assumes openssl and qt5 installed from brew
    CONFIGURE_OPTS = ['PATH=%s:$PATH' % '/usr/local/opt/qt5/bin',
                      'PKG_CONFIG_PATH=%s:$PKG_CONFIG_PATH' % '/usr/local/opt/openssl/lib/pkgconfig']


def configure(debug=False):
    cmake_opts = []
    boost_root = BUILD_ENV.get('boost_root')
    if boost_root:
        cmake_opts += ['-DBOOST_ROOT="{}"'.format(boost_root)]

    if debug:
        cmake_opts += ['-DCMAKE_BUILD_TYPE=Debug']
    else:
        cmake_opts += ['-DCMAKE_BUILD_TYPE=Release']

    cmake_opts += core.config.get('cmake_args', []) + BUILD_ENV.get('cmake_args', [])

    run('{} cmake {} .'.format(' '.join(CONFIGURE_OPTS),
                               ' '.join(cmake_opts)))



def configure_gui():
    run('%s cmake -DINCLUDE_QT_WALLET=ON .' % ' '.join(CONFIGURE_OPTS))


def build(threads=None):
    make_list = ['make'] + core.config.get('make_args', []) + BUILD_ENV.get('make_args', [])
    if threads:
        make_list.append('-j%d' % threads)
    run(make_list)


def build_gui():
    # FIXME: need to make sure that we run once: npm install -g lineman
    run('rm -fr programs/qt_wallet/htdocs')
    run('cd programs/web_wallet; npm install')
    run('make buildweb') # TODO: is 'make forcebuildweb' needed?
    build()


def install_last_built_bin():
    # install into bin dir
    date = run('git show -s --format=%ci HEAD', capture_io=True, verbose=False).stdout.split()[0]
    branch = run('git rev-parse --abbrev-ref HEAD', capture_io=True, verbose=False).stdout.strip()
    commit = run('git log -1', capture_io=True, verbose=False).stdout.splitlines()[0].split()[1]

    # find a nice filename representation
    def decorated_filename(filename):
        try:
            r = run('git describe --tags %s' % commit, capture_io=True, verbose=False, log_on_fail=False)
            if r.status == 0:
                # we are on a tag, use it for naming binary
                tag = r.stdout.strip().replace('/', '_')
                bin_filename = '%s_%s_%s' % (filename, date, tag)
            else:
                bin_filename = '%s_%s_%s_%s' % (filename, date, branch, commit[:8])
        except RuntimeError:
            # no tag yet in repo
            bin_filename = '%s_%s_%s_%s' % (filename, date, branch, commit[:8])

        return bin_filename

    def install(src, dst):
        print('Installing %s to %s' % (dst, BTS_BIN_DIR))
        if islink(src):
            result = join(dirname(src), os.readlink(src))
            print('Following symlink %s -> %s' % (src, result))
            src = result
        dst = join(BTS_BIN_DIR, os.path.basename(dst))
        shutil.copy(src, dst)
        return dst

    def install_and_symlink(bin_name):
        bin_filename = decorated_filename(bin_name)
        client = join(BTS_BUILD_DIR, 'programs', bin_name)
        c = install(client, bin_filename)
        last_installed = join(BTS_BIN_DIR, os.path.basename(bin_name))
        with suppress(Exception):
            os.unlink(last_installed)
        os.symlink(c, last_installed)

    if not exists(BTS_BIN_DIR):
        os.makedirs(BTS_BIN_DIR)

    for bname in get_all_bin_names(build_env=BUILD_ENV['name']):
        install_and_symlink(bname)


def main(flavor='bts'):
    # parse commandline args
    DESC="""following commands are available:
  - version          : show version of the tools
  - clean_homedir    : clean home directory. WARNING: this will delete your wallet!
  - clean            : clean build directory
  - build            : update and build %(bin)s client
  - build_gui        : update and build %(bin)s gui client
  - run              : run latest compiled %(bin)s client, or the one with the given hash or tag
  - run_cli          : run latest compiled %(bin)s cli wallet (graphene)
  - run_gui          : run latest compiled %(bin)s gui client
  - list             : list installed %(bin)s client binaries
  - monitor          : run the monitoring web app
  - publish_slate    : publish the slate as described in the given file
  - deploy           : deploy built binaries to a remote server
  - deploy_node      : full deploy of a seed or witness node on given ip address. Needs ssh root access

Examples:
  $ %(bin)s build          # build the latest %(bin)s client by default
  $ %(bin)s build v0.4.27  # build specific version
  $ %(bin)s run
  $ %(bin)s run debug  # run the client inside gdb

  $ %(bin)s build pts-dev v2.0.1  # build a specific client/version
  $ %(bin)s run seed-test         # run environments are defined in the config.yaml file

  $ %(bin)s build_gui
  $ %(bin)s run_gui

  $ %(bin)s publish_slate                      # will show a sample slate
  $ %(bin)s publish_slate /path/to/slate.yaml  # publish the given slate
    """ % {'bin': flavor}
    EPILOG="""You should also look into ~/.bts_tools/config.yaml to tune it to your liking."""
    parser = argparse.ArgumentParser(description=DESC, epilog=EPILOG,
                                     formatter_class=RawTextHelpFormatter)
    parser.add_argument('command', choices=['version', 'clean_homedir', 'clean', 'build', 'build_gui',
                                            'run', 'run_cli', 'run_gui', 'list', 'monitor', 'publish_slate',
                                            'deploy', 'deploy_node'],
                        help='the command to run')
    parser.add_argument('-r', '--norpc', action='store_true',  # FIXME: deprecate
                        help='run binary with RPC server deactivated')
    parser.add_argument('environment', nargs='?',
                        help='the build/run environment (bts, pts, ...)')
    parser.add_argument('-p', '--pidfile', action='store',
                        help='filename in which to write PID of child process')
    parser.add_argument('-f', '--forward-signals', action='store_true',
                        help='forward unix signals to spawned witness client child process')
    parser.add_argument('args', nargs='*',
                        help='additional arguments to be passed to the given command')
    args = parser.parse_args()

    if args.command == 'version':
        log.info('Version: %s', core.VERSION)
        return

    init()

    if args.environment is None:
        args.environment = flavor
    elif args.environment == 'dev':
        args.environment = '%s-dev' % flavor

    # if given env is not valid, we want to use it as second argument, using
    # the default environment as working env
    if not is_valid_environment(args.environment):
        args.args = [args.environment] + args.args
        args.environment = flavor

    if args.command in {'build', 'build_gui'}:
        select_build_environment(args.environment)

        clone()
        os.chdir(BTS_BUILD_DIR)
        run('git fetch --all')

        # if we are on bitshares (devshares), tags are now prepended with bts/ (dvs/),
        # check if user forgot to specify it
        def search_tag(tag):
            env = args.environment
            if env in {'bts', 'dvs', 'pls'}:
                tags = run('cd %s; git tag -l' % BTS_BUILD_DIR, capture_io=True, verbose=False).stdout.strip().split('\n')
                for pattern in ['%s/%s', '%s/v%s']:
                    if pattern % (env, tag) in tags:
                        return pattern % (env, tag)
            return tag

        tag = search_tag(args.args[0]) if args.args else None
        nthreads = None
        # if we specified -jXX, then it's not a tag, it's a thread count for compiling
        if tag and tag.startswith('-j'):
            nthreads = int(tag[2:])
            tag = None

        if tag:
            run('git checkout %s' % tag)
        else:
            run('git checkout %s && git pull' % BTS_GIT_BRANCH)
        run('git submodule update --init --recursive')
        clean_config()

        start = arrow.utcnow()

        if args.command == 'build':
            configure(debug=BUILD_ENV.get('debug', False))
            build(nthreads)
            install_last_built_bin()
        elif args.command == 'build_gui':
            configure_gui()
            build_gui()

        elapsed_seconds = (arrow.utcnow() - start).seconds
        mins = elapsed_seconds // 60
        secs = elapsed_seconds % 60
        msg = 'Compiled in%s%s' % ((' %d mins' % mins if mins else ''),
                                   (' %d secs' % secs if secs else ''))
        log.info(msg)

    elif args.command in ['run', 'run_cli']:
        client = select_client(args.environment)
        run_args = core.config.get('run_args', [])
        tag = args.args[0] if args.args else None

        if args.command == 'run':
            bin_name = BTS_BIN_NAME
        elif args.command == 'run_cli':
            bin_name = 'cli_wallet'

        # FIXME: only use tag if it actually corresponds to one
        if False: #tag:
            # if git rev specified, runs specific version
            print('Running specific instance of the %s client: %s' % (flavor, tag))
            bin_name = run('ls %s' % join(BTS_BIN_DIR,
                                          '%s_*%s*' % (bin_name, tag[:8])),
                           capture_io=True, verbose=False).stdout.strip()
            run_args += args.args[1:]
        else:
            # run last built version
            bin_name = join(BTS_BIN_DIR, bin_name)
            run_args += args.args

        if args.command == 'run':
            data_dir = client.get('data_dir')
            if data_dir:
                run_args = ['--data-dir', expanduser(data_dir)] + run_args

            genesis_file = client.get('genesis_file')
            if genesis_file:
                run_args += ['--genesis-json', expanduser(genesis_file)]

            witness_port = client.get('witness_port')
            if witness_port:
                run_args += ['--rpc-endpoint', '127.0.0.1:{}'.format(witness_port)]

            p2p_port = client.get('p2p_port')
            if p2p_port:
                run_args += ['--p2p-endpoint', '0.0.0.0:{}'.format(p2p_port)]

            seed_nodes = client.get('seed_nodes', [])
            for node in seed_nodes:
                run_args += ['--seed-node', node]


            plugins = []
            apis = []
            public_apis = []

            roles = client.get('roles', [])
            for role in roles:
                if role['role'] == 'witness':
                    plugins.append('witness')

                    if client['type'] == 'steem':
                        private_key = role.get('signing_key')
                        if private_key:
                            run_args += ['--witness', '"{}"'.format(role['name']),
                                         '--private-key', '{}'.format(private_key)]

                    else:
                        witness_id = role.get('witness_id')
                        private_key = role.get('signing_key')
                        if witness_id and private_key:
                            public_key = format(PrivateKey(private_key).pubkey, client['type'])
                            run_args += ['--witness-id', '"{}"'.format(witness_id),
                                         '--private-key', '["{}", "{}"]'.format(public_key, private_key)]

                elif role['role'] == 'seed':
                    apis += ['network_node_api']

                elif role['role'] == 'feed_publisher':
                    apis += ['network_broadcast_api']

                elif role['role'] == 'api':
                    if client['type'] == 'steem':
                        plugins += ['account_history', 'follow', 'market_history', 'private_message', 'tags']
                        public_apis += ['database_api', 'login_api', 'market_history_api', 'tag_api', 'follow_api']

            def make_unique(l):
                result = []
                for x in l:
                    if x not in result:
                        result.append(x)
                return result

            # always required for working with bts_tools, ensure they are always
            # in this order at the beginning (so database_api=0, login_api=1, etc.)
            # 'network_broadcast_api' required by the wallet (TODO: check fails only with steem >=0.16.0?)
            apis = ['database_api', 'login_api', 'network_node_api', 'network_broadcast_api'] + apis
            plugins = plugins or ['witness']  # always have at least the witness plugin

            plugins = make_unique(client.get('plugins', plugins))
            apis = make_unique(client.get('apis', apis))
            public_apis = make_unique(client.get('public_apis', public_apis))

            log.info('Running with plugins: {}'.format(plugins))
            log.info('Running with apis: {}'.format(apis))
            log.info('Running with public apis: {}'.format(public_apis))


            # enabling plugins
            if client['type'] == 'steem':
                for plugin in plugins:
                    run_args += ['--enable-plugin', plugin]

            # enabling api access
            if client['type'] == 'steem':
                for api in public_apis:
                    run_args += ['--public-api', api]

                if not public_apis:
                    # FIXME: it seems like we can't access the public apis anymore if specifying this
                    pw_hash, salt = hash_salt_password(client['witness_password'])
                    api_user_str = '{"username":"%s", ' % client['witness_user']
                    api_user_str += '"password_hash_b64": "{}", '.format(pw_hash)
                    api_user_str += '"password_salt_b64": "{}", '.format(salt)
                    allowed_apis_str = ', '.join('"{}"'.format(api) for api in make_unique(apis + public_apis))
                    api_user_str += '"allowed_apis": [{}]'.format(allowed_apis_str)
                    api_user_str += '}'
                    run_args += ['--api-user', api_user_str]

            else:
                api_access = client.get('api_access')
                if api_access:
                    run_args += ['--api-access', expanduser(api_access)]

            run_args += client.get('run_args', [])

        elif args.command == 'run_cli':
            witness_host = client.get('witness_host', '127.0.0.1')
            witness_port = client.get('witness_port')
            if witness_port:
                run_args += ['--server-rpc-endpoint', 'ws://{}:{}'.format(witness_host, witness_port)]

            run_args += ['--server-rpc-user', client['witness_user']]
            run_args += ['--server-rpc-password', client['witness_password']]

            wallet_port = client.get('wallet_port')
            if wallet_port:
                run_args += ['--rpc-http-endpoint', '127.0.0.1:{}'.format(wallet_port)]

            chain_id = client.get('chain_id')
            if chain_id:
                run_args += ['--chain-id', chain_id]

            run_args += client.get('run_cli_args', [])

        if not args.norpc and not is_graphene_based(client):
            run_args = ['--server'] + run_args

        if client.get('debug', False):
            if platform == 'linux':
                # FIXME: pidfile will write pid of gdb, not of the process being run inside gdb...
                cmd = ['gdb', '-ex', 'run', '--args', bin_name] + run_args
            else:
                log.warning('Running with debug=true is not implemented on your platform (%s)' % platform)
                cmd = [bin_name] + run_args
        else:
            cmd = [bin_name] + run_args

        data_dir = None
        if is_graphene_based(client):
            # for graphene clients, always cd to data dir first (if defined), this ensures the wallet file
            # and everything else doesn't get scattered all over the place
            data_dir = get_data_dir(client['name'])
            if data_dir:
                # ensure it exists to be able to cd into it
                with suppress(FileExistsError):
                    Path(data_dir).mkdir(parents=True)
            else:
                log.warning('No data dir specified for running {} client'.format(client['name']))

        # also install signal handler to forward signals to witness client child process (esp. SIGINT)
        pidfile = args.pidfile or client.get('pidfile')
        run(cmd, run_dir=data_dir, forward_signals=args.forward_signals, pidfile=pidfile)

    elif args.command == 'run_gui':
        select_build_environment(args.environment)
        if platform == 'darwin':
            run('open %s' % join(BTS_BUILD_DIR, 'programs/qt_wallet/bin/%s.app' % BTS_GUI_BIN_NAME))
        elif platform == 'linux':
            run(join(BTS_BUILD_DIR, 'programs/qt_wallet/bin/%s' % BTS_GUI_BIN_NAME))

    elif args.command == 'clean':
        select_build_environment(args.environment)
        print('\nCleaning build directory...')
        run('rm -fr "%s"' % BTS_BUILD_DIR, verbose=True)

    elif args.command == 'clean_homedir':
        select_client(args.environment)
        print('\nCleaning home directory...')
        if not BTS_HOME_DIR:
            print('ERROR: The home/data dir has not been specified in the build environment...')
            print('       Please check your config.yaml file')
            sys.exit(1)
        cmd = 'rm -fr "%s"' % BTS_HOME_DIR
        if args.environment != 'development':
            print('WARNING: you are about to delete your wallet on the real chain.')
            print('         you may lose some real money if you do this!...')
            print('If you really want to do it, you\'ll have to manually run the command:')
            print(cmd)
            sys.exit(1)
        run(cmd, verbose=True)

    elif args.command == 'list':
        select_build_environment(args.environment)
        print('\nListing built binaries for environment: %s' % args.environment)
        run('ls -ltr "%s"' % BTS_BIN_DIR)

    elif args.command == 'monitor':
        print('\nLaunching monitoring web app...')
        run('python3 -m bts_tools.wsgi')

    elif args.command == 'deploy':
        if not args.args:
            log.error('You need to specify a remote host to deploy to')
            sys.exit(1)

        from .deploy import deploy  # can only import now due to potential circular import

        for remote_host in args.args:
            remote_host = core.config.get('hosts', {}).get(remote_host, remote_host)
            deploy(args.environment, remote_host)

    elif args.command == 'deploy_node':
        select_build_environment(args.environment)
        print()
        if len(args.args) != 2:
            log.error('You need to specify a deployment config file as argument and a host ip or vps provider')
            log.error('eg: bts deploy_node deploy_config.yaml 123.123.123.123  # use given host for install')
            log.error('eg: bts deploy_node deploy_config.yaml vultr            # create a new vps instance')
            log.info('You can find an example config file at {}'.format(join(dirname(__file__), 'deploy_config.yaml')))
            sys.exit(1)

        config_file = args.args[0]
        host = args.args[1]

        from .deploy import deploy_node  # can only import now due to potential circular import

        deploy_node(args.environment, config_file, host)

    elif args.command == 'publish_slate':
        slate_file = args.args[0] if args.args else None
        print()
        if not slate_file:
            log.error('You need to specify a slate file as argument')
            log.info('It should be a YAML file with the following format')
            slate_example = """
delegate: publishing_delegate_name
paying: paying_account  # optional, defaults to publishing delegate
slate:
 - delegate_1
 - delegate_2
 - ...
 - delegate_N
"""
            print(slate_example)
            default_slate = join(dirname(__file__), 'slate.yaml')
            log.info('You can find a default slate at: %s' % default_slate)
            sys.exit(1)

        logging.getLogger('bts_tools').setLevel(logging.INFO)
        log.info('Reading slate from file: %s' % slate_file)
        with open(slate_file, 'r') as f:
            slate_config = yaml.load(f)
        delegate = slate_config['delegate']
        payee = slate_config.get('payee', delegate)
        slate = slate_config['slate']

        client = GrapheneClient(type='delegate', name=delegate, client=args.environment)

        if client.is_locked():
            log.error('Cannot publish slate: wallet locked...')
            log.error('Please unlock your wallet first and try again')
            sys.exit(1)

        log.info('Clearing all previously approved delegates')
        for d in client.wallet_list_approvals():
            log.debug('Unapproving delegate: %s' % d['name'])
            client.wallet_approve(d['name'], 0)

        for d in slate:
            log.info('Approving delegate: %s' % d)
            try:
                client.wallet_approve(d, 1)
            except Exception as e:
                log.error(str(e).split('\n')[0])

        log.info('Publishing slate...')
        try:
            client.wallet_publish_slate(delegate, payee)
            log.info('Slate successfully published!')
        except Exception as e:
            log.error(e)


def main_bts():
    return main(flavor='bts')


def main_bts1():
    return main(flavor='bts1')


def main_bts2():
    return main(flavor='bts')


def main_muse():
    return main(flavor='muse')


def main_steem():
    return main(flavor='steem')


def main_dvs():
    return main(flavor='dvs')


def main_pts():
    return main(flavor='pts')


def main_pls():
    return main(flavor='pls')
