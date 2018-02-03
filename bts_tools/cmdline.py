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

from os.path import join, dirname, exists, islink, expanduser, basename
from argparse import RawTextHelpFormatter
from contextlib import suppress
from pathlib import Path
from ruamel import yaml
from .core import (platform, run, get_data_dir, get_bin_name, get_gui_bin_name, get_cli_bin_name,
                   get_all_bin_names, get_full_bin_name, hash_salt_password)
from .privatekey import PrivateKey
from . import core, init
from .rpcutils import rpc_call, GrapheneClient
import argparse
import os
import sys
import copy
import shutil
import pendulum
import psutil
import logging

log = logging.getLogger(__name__)


BUILD_ENV = None
CLIENT    = None


def select_build_environment(env_name):
    log.info("Using build environment '%s' on platform: '%s'" % (env_name, platform))

    if platform not in ['linux', 'darwin']:
        raise OSError('OS not supported yet, please submit a patch :)')

    try:
        env = copy.copy(core.config['build_environments'][env_name])
    except KeyError:
        log.error('Unknown build environment: %s' % env_name)
        sys.exit(1)

    env['name'] = env_name
    env['build_dir'] = expanduser(env['build_dir'])
    env['bin_dir'] = expanduser(env['bin_dir'])
    env['witness_filename'] = env.get('witness_filename', get_bin_name(build_env=env_name))
    env['wallet_filename'] = env.get('wallet_filename', get_cli_bin_name(build_env=env_name))
    env['gui_bin_name'] = env.get('gui_bin_name', get_gui_bin_name(build_env=env_name))

    global BUILD_ENV
    BUILD_ENV = env
    return env


def select_client(client):
    log.info("Running '%s' client" % client)
    try:
        env = copy.copy(core.config['clients'][client])
        env['name'] = client
    except KeyError:
        log.error('Unknown client: %s' % client)
        sys.exit(1)

    select_build_environment(env['type'])

    env['home_dir'] = get_data_dir(client)

    global CLIENT
    CLIENT = env
    return env


def is_valid_environment(env):
    return (env in core.config['build_environments'] or
            env in core.config['clients'])


def clone():
    def is_git_dir(path):
        try:
            run('git rev-parse', run_dir=BUILD_ENV['build_dir'], verbose=False)
            return True
        except RuntimeError:
            return False
    if not exists(BUILD_ENV['build_dir']) or not is_git_dir(BUILD_ENV['build_dir']):
        run('git clone %s "%s"' % (BUILD_ENV['git_repo'], BUILD_ENV['build_dir']))


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
        cmake_opts += ['-DBOOST_ROOT="{}"'.format(expanduser(boost_root))]

    if debug:
        # do not compile really in debug, it's unusably slow otherwise
        cmake_opts += ['-DCMAKE_BUILD_TYPE=RelWithDebInfo']
    else:
        cmake_opts += ['-DCMAKE_BUILD_TYPE=Release']

    cmake_opts += core.config['build_environments'].get('cmake_args', []) + BUILD_ENV.get('cmake_args', [])

    run('{} cmake {} .'.format(' '.join(CONFIGURE_OPTS),
                               ' '.join(cmake_opts)), shell=True)



def configure_gui():
    run('%s cmake -DINCLUDE_QT_WALLET=ON .' % ' '.join(CONFIGURE_OPTS))


def build(threads=None):
    make_list = ['make'] + core.config['build_environments'].get('make_args', []) + BUILD_ENV.get('make_args', [])
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
        print('Installing %s to %s' % (basename(dst), BUILD_ENV['bin_dir']))
        if islink(src):
            result = join(dirname(src), os.readlink(src))
            print('Following symlink %s -> %s' % (src, result))
            src = result
        dst = join(BUILD_ENV['bin_dir'], basename(dst))
        shutil.copy(src, dst)
        return dst

    def install_and_symlink(binary_type, bin_name):
        """binary_type should be either 'witness' or 'wallet'
        bin_name is the base name template that will be used to name the resulting file."""
        if binary_type == 'witness':
            bin_index = 0
        elif binary_type == 'wallet':
            bin_index = 1
        else:
            raise ValueError('binary_type needs to be either "witness" or "wallet"')
        client = join(BUILD_ENV['build_dir'], 'programs', get_all_bin_names(build_env=BUILD_ENV['name'])[bin_index])
        bin_filename = decorated_filename(bin_name)
        c = install(client, bin_filename)
        last_installed = join(BUILD_ENV['bin_dir'], basename(bin_name))
        with suppress(Exception):
            os.unlink(last_installed)
        os.symlink(c, last_installed)

    if not exists(BUILD_ENV['bin_dir']):
        os.makedirs(BUILD_ENV['bin_dir'])

    install_and_symlink('witness', BUILD_ENV['witness_filename'])
    install_and_symlink('wallet', BUILD_ENV['wallet_filename'])


def main(flavor='bts'):
    # parse commandline args
    DESC_COMMANDS = """following commands are available:
  - version                : show version of the tools
  - clean_homedir          : clean home directory. WARNING: this will delete your wallet!
  - save_blockchain_dir    : save a snapshot of the current state of the blockchain
  - restore_blockchain_dir : restore a snapshot of the current state of the blockchain
  - clean                  : clean build directory
  - build                  : update and build {bin} client
  - build_gui              : update and build {bin} gui client
  - run                    : run latest compiled {bin} client, or the one with the given hash or tag
  - run_cli                : run latest compiled {bin} cli wallet
  - run_gui                : run latest compiled {bin} gui client
  - list                   : list installed {bin} client binaries
  - monitor                : run the monitoring web app
  - deploy                 : deploy built binaries to a remote server
  - deploy_node            : full deploy of a seed or witness node on given ip address. Needs ssh root access
"""

    COMMAND_PLUGINS = {name: core.get_plugin('bts_tools.commands', name)
                       for name in core.list_valid_plugins('bts_tools.commands')}
    DESC_PLUGINS = '\n'.join('  - {:22} : {}'.format(name, plugin.short_description())
                             for name, plugin in COMMAND_PLUGINS.items())

    DESC_EXAMPLES = """
    
Examples:
  $ {bin} build                 # build the latest {bin} client by default
  $ {bin} build v0.4.27         # build specific version
  $ {bin} build ppy-dev v0.1.8  # build a specific client/version
  $ {bin} run                   # run the latest compiled client by default
  $ {bin} run seed-test         # clients are defined in the config.yaml file

  $ {bin} build_gui   # FIXME: broken...
  $ {bin} run_gui     # FIXME: broken...

    """

    DESC = (DESC_COMMANDS + DESC_PLUGINS + DESC_EXAMPLES).format(bin=flavor)

    EPILOG="""You should also look into ~/.bts_tools/config.yaml to tune it to your liking."""
    parser = argparse.ArgumentParser(description=DESC, epilog=EPILOG,
                                     formatter_class=RawTextHelpFormatter)
    parser.add_argument('command', choices=['version', 'clean_homedir', 'clean', 'build', 'build_gui',
                                            'run', 'run_cli', 'run_gui', 'list', 'monitor',
                                            'deploy', 'deploy_node'] + list(COMMAND_PLUGINS.keys()),
                        help='the command to run')
    parser.add_argument('environment', nargs='?',
                        help='the build/run environment (bts, steem, ...)')
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

    # FIXME: this needs to be implemented as plugins
    if args.command in {'build', 'build_gui'}:
        select_build_environment(args.environment)

        clone()
        os.chdir(BUILD_ENV['build_dir'])
        run('git fetch --all')

        tag = args.args[0] if args.args else None
        nthreads = None
        # if we specified -jXX, then it's not a tag, it's a thread count for compiling
        if tag and tag.startswith('-j'):
            nthreads = int(tag[2:])
            tag = None

        if tag:
            run('git checkout %s' % tag)
        else:
            r = run('git checkout %s' % BUILD_ENV['git_branch'])
            if r.status == 0:
                run('git pull')
        run('git submodule update --init --recursive')
        clean_config()

        start = pendulum.utcnow()

        if args.command == 'build':
            configure(debug=BUILD_ENV.get('debug', False))
            build(nthreads)
            install_last_built_bin()
        elif args.command == 'build_gui':
            configure_gui()
            build_gui()

        elapsed_seconds = (pendulum.utcnow() - start).in_seconds()
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
            bin_name = BUILD_ENV['witness_filename']
        elif args.command == 'run_cli':
            bin_name = BUILD_ENV['wallet_filename']

        # FIXME: only use tag if it actually corresponds to one
        if False: #tag:
            # if git rev specified, runs specific version
            print('Running specific instance of the %s client: %s' % (flavor, tag))
            bin_name = run('ls %s' % join(BUILD_ENV['bin_dir'],
                                          '%s_*%s*' % (bin_name, tag[:8])),
                           capture_io=True, verbose=False).stdout.strip()
            run_args += args.args[1:]
        else:
            # run last built version
            bin_name = join(BUILD_ENV['bin_dir'], bin_name)
            run_args += args.args

        if args.command == 'run':
            data_dir = client.get('data_dir')
            if data_dir:
                run_args = ['--data-dir', expanduser(data_dir)] + run_args

            shared_file_size = client.get('shared_file_size')
            if shared_file_size:
                run_args = ['--shared-file-size', shared_file_size] + run_args

            genesis_file = client.get('genesis_file')
            if genesis_file:
                run_args += ['--genesis-json', expanduser(genesis_file)]

            witness_port = client.get('witness_port')
            if witness_port:
                run_args += ['--rpc-endpoint=127.0.0.1:{}'.format(witness_port)]

            p2p_port = client.get('p2p_port')
            if p2p_port:
                run_args += ['--p2p-endpoint', '0.0.0.0:{}'.format(p2p_port)]

            seed_nodes = client.get('seed_nodes', [])
            for node in seed_nodes:
                run_args += ['--seed-node', node]

            checkpoints = client.get('checkpoints')
            if checkpoints:
                pass  # FIXME: implement me

            track_accounts = client.get('track_accounts', [])
            if track_accounts:
                run_args += ['--partial-operations', 'true']
                for account in track_accounts:
                    run_args += ['--track-account', '"{}"'.format(account)]

            plugins = []
            apis = []
            public_apis = []

            roles = client.get('roles', [])
            for role in roles:
                if role['role'] == 'witness':
                    plugins.append('witness')

                    if core.affiliation(client['type']) == 'steem':
                        private_key = role.get('signing_key')
                        if private_key:
                            run_args += ['--witness', '"{}"'.format(role['name']),
                                         '--private-key', '{}'.format(private_key)]

                    else:
                        witness_id = role.get('witness_id')
                        private_key = role.get('signing_key')
                        if witness_id and private_key:
                            witness_id = '"{}"'.format(witness_id)
                            public_key = format(PrivateKey(private_key).pubkey, client['type'])
                            private_key_pair = '["{}", "{}"]'.format(public_key, private_key)
                            # temporary workaround for https://github.com/bitshares/bitshares-core/issues/399
                            if client['type'] in ['bts', 'bts-testnet']:
                                log.error('BTS and BTS testnet versions don\'t support the --private-key option, not using it. '
                                          'Please edit the {}/config.ini file instead with the following values:'
                                          .format(client['data_dir']))
                                log.error('witness-id = {}'.format(witness_id))
                                log.error('private-key = {}'.format(private_key_pair))
                            else:
                                run_args += ['--witness-id', witness_id,
                                             '--private-key', private_key_pair]

                elif role['role'] == 'seed':
                    apis += ['network_node_api']

                elif role['role'] == 'feed_publisher':
                    apis += ['network_broadcast_api']

                elif role['role'] == 'api':
                    if core.affiliation(client['type']) == 'steem':
                        plugins += ['account_history', 'follow', 'market_history', 'private_message', 'tags']
                        public_apis += ['database_api', 'login_api', 'market_history_api', 'tag_api', 'follow_api']

            def make_unique(l):
                result = []
                for x in l:
                    if x not in result:
                        result.append(x)
                return result

            # enabling plugins
            if core.affiliation(client['type']) == 'steem':
                plugins = plugins or ['witness']  # always have at least the witness plugin
                plugins = make_unique(client.get('plugins', plugins))
                log.info('Running with plugins: {}'.format(plugins))

                for plugin in plugins:
                    run_args += ['--enable-plugin', plugin]

            # enabling api access
            if core.affiliation(client['type']) == 'steem':
                # always required for working with bts_tools, ensure they are always
                # in this order at the beginning (so database_api=0, login_api=1, etc.)
                # 'network_broadcast_api' required by the wallet
                apis = ['database_api', 'login_api', 'network_node_api', 'network_broadcast_api'] + apis
                apis = make_unique(client.get('apis', apis))
                public_apis = make_unique(client.get('public_apis', public_apis))

                log.info('Running with apis: {}'.format(apis))
                log.info('Running with public apis: {}'.format(public_apis))

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
                run_args += ['--server-rpc-endpoint=ws://{}:{}'.format(witness_host, witness_port)]

            run_args += ['--server-rpc-user={}'.format(client['witness_user'])]
            run_args += ['--server-rpc-password={}'.format(client['witness_password'])]

            wallet_port = client.get('wallet_port')
            if wallet_port:
                run_args += ['--rpc-http-endpoint=127.0.0.1:{}'.format(wallet_port)]

            chain_id = client.get('chain_id')
            if chain_id:
                run_args += ['--chain-id', chain_id]

            run_args += client.get('run_cli_args', [])

        if client.get('debug', False):
            if platform == 'linux':
                # FIXME: pidfile will write pid of gdb, not of the process being run inside gdb...
                cmd = ['gdb', '-ex', 'run', '--args', bin_name] + run_args
            else:
                log.warning('Running with debug=true is not implemented on your platform (%s)' % platform)
                cmd = [bin_name] + run_args
        else:
            cmd = [bin_name] + run_args

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
            run('open %s' % join(BUILD_ENV['build_dir'], 'programs/qt_wallet/bin/%s.app' % BUILD_ENV['gui_bin_name']))
        elif platform == 'linux':
            run(join(BUILD_ENV['build_dir'], 'programs/qt_wallet/bin/%s' % BUILD_ENV['gui_bin_name']))

    elif args.command == 'clean':
        select_build_environment(args.environment)
        print('\nCleaning build directory...')
        run('rm -fr "%s"' % BUILD_ENV['build_dir'], verbose=True)

    elif args.command == 'clean_homedir':
        select_client(args.environment)
        print('\nCleaning home directory...')
        if not CLIENT['home_dir']:
            print('ERROR: The home/data dir has not been specified in the build environment...')
            print('       Please check your config.yaml file')
            sys.exit(1)
        cmd = 'rm -fr "%s"' % CLIENT['home_dir']
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
        run('ls -ltr "%s"' % BUILD_ENV['bin_dir'])

    elif args.command == 'monitor':
        print('\nLaunching monitoring web app...')
        run('python3 -m bts_tools.wsgi')

    elif args.command == 'deploy':
        if not args.args:
            log.error('You need to specify a remote host to deploy to')
            sys.exit(1)

        from .deploy import deploy  # can only import now due to potential circular import

        for remote_host in args.args:
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

    elif args.command in COMMAND_PLUGINS:
        cmd = COMMAND_PLUGINS[args.command]
        cmd.run_command(*args.args)


def main_bts():
    return main(flavor='bts')


def main_muse():
    return main(flavor='muse')


def main_steem():
    return main(flavor='steem')


def main_ppy():
    return main(flavor='ppy')
