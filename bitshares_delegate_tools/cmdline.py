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

from os.path import join, dirname, exists, islink
from argparse import RawTextHelpFormatter
from .core import config, env, platform, run
from .rpcutils import rpc_call
import argparse
import os
import sys
import shutil
import json
import logging

log = logging.getLogger(__name__)

BITSHARES_GIT_REPO   = env['git_repo']
BITSHARES_GIT_BRANCH = env['git_branch']
BITSHARES_BUILD_DIR  = env[platform]['BITSHARES_BUILD_DIR']
BITSHARES_HOME_DIR   = env[platform]['BITSHARES_HOME_DIR']
BITSHARES_BIN_DIR    = env[platform]['BITSHARES_BIN_DIR']


def clone():
    if not exists(BITSHARES_BUILD_DIR):
        run('git clone %s "%s"' % (BITSHARES_GIT_REPO, BITSHARES_BUILD_DIR))
        os.chdir(BITSHARES_BUILD_DIR)
        run('git submodule init')


def update():
    run('git checkout %s && git pull && git submodule update' % BITSHARES_GIT_BRANCH)


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
    run(['make']+config.get('make_args', []))


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
        bin_filename = 'bitshares_client_%s_v%s' % (date, tag)
    else:
        bin_filename = 'bitshares_client_%s_%s_%s' % (date, branch, commit[:8])

    def install(src, dst):
        print('Installing %s' % dst)
        if islink(src):
            result = join(dirname(src), os.readlink(src))
            print('Following symlink %s -> %s' % (src, result))
            src = result
        dst = join(BITSHARES_BIN_DIR, dst)
        shutil.copy(src, dst)
        return dst

    if not exists(BITSHARES_BIN_DIR):
        os.makedirs(BITSHARES_BIN_DIR)

    client = join(BITSHARES_BUILD_DIR, 'programs', 'client', 'bitshares_client')

    c = install(client, bin_filename)

    last_installed = join(BITSHARES_BIN_DIR, 'bitshares_client')
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
  - build [hash]     : update and build bts client
  - build_gui [hash] : update and build bts gui client
  - run [hash]       : run latest compiled bts client, or the one with the given hash or tag
  - run_gui          : run latest compiled bts gui client
  - list             : list installed bitshares client binaries

Example:
  $ bts build 0.4.7
  $ bts run

  $ bts build_gui 0.4.14
  $ bts run_gui
    """
    EPILOG="""You should also look into ~/.bts_tools/config.yaml to tune it to your liking."""
    parser = argparse.ArgumentParser(description=DESC, epilog=EPILOG,
                                     formatter_class=RawTextHelpFormatter)
    parser.add_argument('command', choices=['clean_homedir', 'clean', 'build', 'build_gui', 'run', 'run_gui', 'list'],
                        help='the command to run')
    parser.add_argument('-r', '--norpc', action='store_true',
                        help='run binary with RPC server deactivated')
    parser.add_argument('hash',
                        help='the hash of the desired commit', nargs='?')
    args = parser.parse_args()


    if args.command in {'build', 'build_gui'}:
        clone()

        os.chdir(BITSHARES_BUILD_DIR)
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
        if args.hash:
            # if git rev specified, runs specific version
            print('Running specific instance of the bts client: %s' % args.hash)
            bin_name = run('ls %s' % join(BITSHARES_BIN_DIR,
                                          'bitshares_client_*%s*' % args.hash[:8]),
                           io=True).stdout.strip()
        else:
            # run last built version
            bin_name = join(BITSHARES_BIN_DIR, 'bitshares_client')

        run_args = config.get('run_args', [])
        if not args.norpc:
            run_args = ['--server'] + run_args

        # on linux, run with "gdb -ex run ./bts_client"
        if platform == 'linux':
            run(' '.join(['gdb', '-ex', 'run', '--args', bin_name] + run_args))
        else:
            run([bin_name] + run_args)

    elif args.command == 'run_gui':
        run('open %s' % join(BITSHARES_BUILD_DIR, 'programs/qt_wallet/bin/BitSharesX.app'))

    elif args.command == 'clean':
        run('rm -fr "%s"' % BITSHARES_BUILD_DIR)

    elif args.command == 'clean_homedir':
        cmd = 'rm -fr "%s"' % BITSHARES_HOME_DIR
        if config['env']['active'] == 'production':
            print('WARNING: you are about to delete your wallet on the real BTSX chain.')
            print('         you may lose some real money if you do this!...')
            print('If you really want to do it, you\'ll have to manually run the command:')
            print(cmd)
            sys.exit(1)
        run(cmd)

    elif args.command == 'list':
        run('ls -ltr "%s"' % BITSHARES_BIN_DIR)


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

    logging.getLogger('bitshares_delegate_tools').setLevel(logging.WARNING)

    try:
        return rpc_call('localhost', args.rpc_port, args.rpc_user,
                        args.rpc_password, args.method, *args.args)
    except Exception as e:
        result = { 'error': str(e), 'type': '%s.%s' % (e.__class__.__module__,
                                                       e.__class__.__name__) }

    print(json.dumps(result))

