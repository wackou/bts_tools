#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bitshares_delegate_tools - Tools to easily manage the bitshares client
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
from .rpcutils import rpc_call
import argparse
import os
import sys
import shutil
import json
import logging

log = logging.getLogger(__name__)

BTS_GIT_REPO   = None
BTS_GIT_BRANCH = None
BTS_BUILD_DIR  = None
BTS_HOME_DIR   = None
BTS_BIN_DIR    = None

BUILD_ENV = None
RUN_ENV   = None


def select_build_environment(env=None):
    env = env or 'btsx'
    log.info("Using build environment '%s' on platform: '%s'" % (env, platform))

    if platform not in ['linux', 'darwin']:
        raise OSError('OS not supported yet, please submit a patch :)')

    try:
        env = core.config['build_environments'][env]
    except KeyError:
        log.error('Unknown build environment: %s' % env)
        sys.exit(1)

    global BTS_GIT_REPO, BTS_GIT_BRANCH, BTS_BUILD_DIR, BTS_BIN_DIR, BUILD_ENV
    BTS_GIT_REPO   = env['git_repo']
    BTS_GIT_BRANCH = env['git_branch']
    BTS_BUILD_DIR  = expanduser(env['build_dir'])
    BTS_BIN_DIR    = expanduser(env['bin_dir'])

    BUILD_ENV = env
    return env


def select_run_environment(env_name=None):
    env_name = env_name or 'default'
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
    make_list = ['make'] + BUILD_ENV.get('make_args', [])
    run(make_list, verbose=True)


def build_gui():
    # FIXME: need to make sure that we run once: npm install -g lineman
    run('rm -fr programs/qt_wallet/htdocs')
    run('cd programs/web_wallet; npm install')
    run('make buildweb')
    run('make BitSharesX')


def install_last_built_bin():
    # install into bin dir
    date = run('git show -s --format=%ci HEAD', io=True).stdout.split()[0]
    branch = run('git rev-parse --abbrev-ref HEAD', io=True).stdout.strip()
    commit = run('git log -1', io=True).stdout.splitlines()[0].split()[1]

    r = run('git describe --tags %s' % commit, io=True)
    if r.status == 0:
        # we are on a tag, use it for naming binary
        tag = r.stdout.strip()
        if tag.startswith('v'):
            tag = tag[1:]
        bin_filename = 'bts_client_%s_v%s' % (date, tag)
    else:
        bin_filename = 'bts_client_%s_%s_%s' % (date, branch, commit[:8])

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

    client = join(BTS_BUILD_DIR, 'programs', 'client', 'bitshares_client')

    c = install(client, bin_filename)

    last_installed = join(BTS_BIN_DIR, 'bts_client')
    try:
        os.unlink(last_installed)
    except:
        pass
    os.symlink(c, last_installed)


def main():
    # parse commandline args
    DESC="""following commands are available:
  - clean_homedir    : clean home directory. WARNING: this will delete your wallet!
  - clean            : clean build directory
  - build            : update and build bts client
  - build_gui        : update and build bts gui client
  - run              : run latest compiled bts client, or the one with the given hash or tag
  - run_gui          : run latest compiled bts gui client
  - list             : list installed bitshares client binaries

Example:
  $ bts build   # build the latest btsx client by default
  $ bts run

  $ bts build dns v0.0.4  # build a specific version
  $ bts run seed-dns      # run environments are defined in the config.yaml file

  $ bts build_gui
  $ bts run_gui
    """
    EPILOG="""You should also look into ~/.bts_tools/config.yaml to tune it to your liking."""
    parser = argparse.ArgumentParser(description=DESC, epilog=EPILOG,
                                     formatter_class=RawTextHelpFormatter)
    parser.add_argument('command', choices=['clean_homedir', 'clean', 'build', 'build_gui', 'run', 'run_gui', 'list'],
                        help='the command to run')
    parser.add_argument('-r', '--norpc', action='store_true',
                        help='run binary with RPC server deactivated')
    parser.add_argument('environment', nargs='?',
                        help='the build/run environment (btsx, dns, ...)')
    parser.add_argument('hash', nargs='?',
                        help='the hash or tag of the desired commit')
    args = parser.parse_args()

    init()

    if args.command in {'build', 'build_gui'}:
        select_build_environment(args.environment)

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
            print('Running specific instance of the bts client: %s' % args.hash)
            bin_name = run('ls %s' % join(BTS_BIN_DIR,
                                          'bts_client_*%s*' % args.hash[:8]),
                           io=True).stdout.strip()
        else:
            # run last built version
            bin_name = join(BTS_BIN_DIR, 'bts_client')

        run_args = run_env.get('run_args', [])

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
        run('open %s' % join(BTS_BUILD_DIR, 'programs/qt_wallet/bin/BitSharesX.app'))

    elif args.command == 'clean':
        select_build_environment(args.environment)
        run('rm -fr "%s"' % BTS_BUILD_DIR)

    elif args.command == 'clean_homedir':
        select_run_environment(args.environment)
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
        run('ls -ltr "%s"' % BTS_BIN_DIR)


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

    init(loglevels={'bitshares_delegate_tools': 'WARNING'})

    try:
        return rpc_call('localhost', int(args.rpc_port), args.rpc_user,
                        args.rpc_password, args.method, *args.args)
    except Exception as e:
        log.exception(e)
        result = { 'error': str(e), 'type': '%s.%s' % (e.__class__.__module__,
                                                       e.__class__.__name__) }

    print(json.dumps(result))

