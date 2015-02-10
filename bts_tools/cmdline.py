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
from .core import platform, run, get_data_dir
from . import core, init
from .rpcutils import rpc_call, BTSProxy
import argparse
import os
import sys
import shutil
import json
import yaml
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


def select_build_environment(env):
    log.info("Using build environment '%s' on platform: '%s'" % (env, platform))

    if platform not in ['linux', 'darwin']:
        raise OSError('OS not supported yet, please submit a patch :)')

    try:
        env = core.config['build_environments'][env]
    except KeyError:
        log.error('Unknown build environment: %s' % env)
        sys.exit(1)

    global BTS_GIT_REPO, BTS_GIT_BRANCH, BTS_BUILD_DIR, BTS_BIN_DIR, BUILD_ENV, BTS_BIN_NAME, BTS_GUI_BIN_NAME
    BTS_GIT_REPO     = env['git_repo']
    BTS_GIT_BRANCH   = env['git_branch']
    BTS_BUILD_DIR    = expanduser(env['build_dir'])
    BTS_BIN_DIR      = expanduser(env['bin_dir'])
    BTS_BIN_NAME     = env['bin_name']
    BTS_GUI_BIN_NAME = env.get('gui_bin_name')

    BUILD_ENV = env
    return env


def select_run_environment(env_name):
    log.info("Running '%s' client" % env_name)
    try:
        env = core.config['run_environments'][env_name]
    except KeyError:
        log.error('Unknown run environment: %s' % env_name)
        sys.exit(1)

    select_build_environment(env['type'])

    global BTS_HOME_DIR, RUN_ENV
    BTS_HOME_DIR = get_data_dir(env_name)
    RUN_ENV = env

    return env


def is_valid_environment(env):
    return (env in core.config['build_environments'] or
            env in core.config['run_environments'])


def clone():
    if not exists(BTS_BUILD_DIR):
        run('git clone %s "%s"' % (BTS_GIT_REPO, BTS_BUILD_DIR))
        os.chdir(BTS_BUILD_DIR)
        run('git submodule init')


def update():
    run('git checkout %s && git pull && git submodule update' % BTS_GIT_BRANCH)


def clean_config():
    run('rm -f CMakeCache.txt')


CONFIGURE_OPTS = []
if platform == 'darwin':
    # assumes openssl and qt5 installed from brew
    CONFIGURE_OPTS = ['PATH=%s:$PATH' % '/usr/local/opt/qt5/bin',
                      'PKG_CONFIG_PATH=%s:$PKG_CONFIG_PATH' % '/usr/local/opt/openssl/lib/pkgconfig']

def configure():
    run('%s cmake .' % ' '.join(CONFIGURE_OPTS))


def configure_gui():
    run('%s cmake -DINCLUDE_QT_WALLET=ON .' % ' '.join(CONFIGURE_OPTS))


def build():
    make_list = ['make'] + core.config.get('make_args', []) + BUILD_ENV.get('make_args', [])
    run(make_list, verbose=True)


def build_gui():
    # FIXME: need to make sure that we run once: npm install -g lineman
    run('rm -fr programs/qt_wallet/htdocs')
    run('cd programs/web_wallet; npm install')
    run('make buildweb') # TODO: is 'make forcebuildweb' needed?
    run('make')


def install_last_built_bin():
    # install into bin dir
    date = run('git show -s --format=%ci HEAD', io=True).stdout.split()[0]
    branch = run('git rev-parse --abbrev-ref HEAD', io=True).stdout.strip()
    commit = run('git log -1', io=True).stdout.splitlines()[0].split()[1]

    r = run('git describe --tags %s' % commit, io=True)
    if r.status == 0:
        # we are on a tag, use it for naming binary
        tag = r.stdout.strip().replace('/', '_')
        bin_filename = '%s_%s_%s' % (BTS_BIN_NAME, date, tag)
    else:
        bin_filename = '%s_%s_%s_%s' % (BTS_BIN_NAME, date, branch, commit[:8])

    def install(src, dst):
        print('Installing %s' % dst)
        if islink(src):
            result = join(dirname(src), os.readlink(src))
            print('Following symlink %s -> %s' % (src, result))
            src = result
        dst = join(BTS_BIN_DIR, dst)
        shutil.copy(src, dst)
        return dst

    if not exists(BTS_BIN_DIR):
        os.makedirs(BTS_BIN_DIR)

    client = join(BTS_BUILD_DIR, 'programs', 'client', BTS_BIN_NAME)

    c = install(client, bin_filename)

    last_installed = join(BTS_BIN_DIR, BTS_BIN_NAME)
    try:
        os.unlink(last_installed)
    except:
        pass
    os.symlink(c, last_installed)


def main(flavor='bts'):
    # parse commandline args
    DESC="""following commands are available:
  - clean_homedir    : clean home directory. WARNING: this will delete your wallet!
  - clean            : clean build directory
  - build            : update and build %(bin)s client
  - build_gui        : update and build %(bin)s gui client
  - run              : run latest compiled %(bin)s client, or the one with the given hash or tag
  - run_gui          : run latest compiled %(bin)s gui client
  - list             : list installed %(bin)s client binaries
  - monitor          : run the monitoring web app
  - publish_slate    : publish the slate as described in the given file

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
    parser.add_argument('command', choices=['clean_homedir', 'clean', 'build', 'build_gui',
                                            'run', 'run_gui', 'list', 'monitor', 'publish_slate'],
                        help='the command to run')
    parser.add_argument('-r', '--norpc', action='store_true',
                        help='run binary with RPC server deactivated')
    parser.add_argument('environment', nargs='?',
                        help='the build/run environment (bts, pts, ...)')
    parser.add_argument('hash', nargs='?',
                        help='the hash or tag of the desired commit')
    args = parser.parse_args()

    init()

    if args.environment is None:
        args.environment = flavor
    elif args.environment == 'dev':
        args.environment = '%s-dev' % flavor

    # if given env is not valid, we want to use it as second argument, using
    # the default environment as working env
    if not is_valid_environment(args.environment):
        args.hash = args.environment
        args.environment = flavor

    if args.command in {'build', 'build_gui'}:
        select_build_environment(args.environment)

        # if we are on bitshares (devshares), tags are now prepended with bts/ (dvs/),
        # check if user forgot to specify it
        if args.environment in {'bts', 'dvs'} and args.hash:
            tags = run('cd %s; git tag -l' % BTS_BUILD_DIR, io=True).stdout.strip().split('\n')
            if args.environment == 'dvs' and 'dvs/' + args.hash in tags:
                args.hash = 'dvs/' + args.hash
            if args.environment == 'bts' and 'bts/' + args.hash in tags:
                args.hash = 'bts/' + args.hash

        # TODO: time compilation, display it

        clone()

        os.chdir(BTS_BUILD_DIR)
        update()
        if args.hash:
            run('git checkout %s && git submodule update' % args.hash)
        clean_config()
        if args.command == 'build':
            configure()
            build()
            install_last_built_bin()
        elif args.command == 'build_gui':
            configure_gui()
            build_gui()

    elif args.command == 'run':
        run_env = select_run_environment(args.environment)

        if args.hash:
            # if git rev specified, runs specific version
            print('Running specific instance of the %s client: %s' % (flavor, args.hash))
            bin_name = run('ls %s' % join(BTS_BIN_DIR,
                                          '%s_*%s*' % (BTS_BIN_NAME, args.hash[:8])),
                           io=True).stdout.strip()
        else:
            # run last built version
            bin_name = join(BTS_BIN_DIR, BTS_BIN_NAME)

        run_args = core.config.get('run_args', []) + run_env.get('run_args', [])

        data_dir = run_env.get('data_dir')
        if data_dir:
            run_args = ['--data-dir', expanduser(data_dir)] + run_args

        if not args.norpc:
            run_args = ['--server'] + run_args

        if run_env.get('debug', False):
            if platform == 'linux':
                cmd = ' '.join(['gdb', '-ex', 'run', '--args', bin_name] + run_args)
            else:
                log.warning('Running with debug=true is not implemented on your platform (%s)' % platform)
                cmd = [bin_name] + run_args

        else:
            cmd = [bin_name] + run_args

        run(cmd, verbose=True)

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
        select_run_environment(args.environment)
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
        run('ls -ltr "%s"/*_client*' % BTS_BIN_DIR)

    elif args.command == 'monitor':
        print('\nLaunching monitoring web app...')
        run('python -m bts_tools.wsgi')

    elif args.command == 'publish_slate':
        slate_file = args.hash # TODO: args.hash would probably benefit from being renamed
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

        client = BTSProxy(type='delegate', name=delegate, client=args.environment)

        if not client.get_info()['wallet_unlocked']:
            log.error('Cannot publish slate: wallet locked...')
            log.error('Please unlock your wallet first and try again')
            sys.exit(1)

        log.info('Clearing all previously approved delegates')
        for d in client.wallet_list_accounts():
            log.debug('Unapproving delegate: %s' % d['name'])
            client.wallet_account_set_approval(d['name'], 0)

        for d in slate:
            log.info('Approving delegate: %s' % d)
            try:
                client.wallet_account_set_approval(d, 1)
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


def main_dvs():
    return main(flavor='dvs')


def main_pts():
    return main(flavor='pts')


def main_rpc_call():
    # parse commandline args
    DESC="""Run the given command using JSON-RPC."""
    EPILOG="""You should look into config.yaml to configure the rpc user and password."""

    parser = argparse.ArgumentParser(description=DESC, epilog=EPILOG,
                                     formatter_class=RawTextHelpFormatter)
    parser.add_argument('rpc_port',
                        help='the rpc port')
    parser.add_argument('rpc_user',
                        help='the rpc user')
    parser.add_argument('rpc_password',
                        help='the rpc password')
    parser.add_argument('method',
                        help='the method to call')
    parser.add_argument('args',
                        help='the args to pass to the rpc method call', nargs='*')
    args = parser.parse_args()

    init(loglevels={'bts_tools': 'WARNING'})

    try:
        result = rpc_call('localhost', int(args.rpc_port), args.rpc_user,
                          args.rpc_password, args.method, *args.args)
    except Exception as e:
        log.exception(e)
        result = { 'error': str(e), 'type': '%s.%s' % (e.__class__.__module__,
                                                       e.__class__.__name__) }

    print(json.dumps(result))

