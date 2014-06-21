#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bitshares_delegate_tools - Some tools to ease the management of the
#                            bitshares client
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
from subprocess import Popen, PIPE
from collections import namedtuple
from argparse import RawTextHelpFormatter
import argparse
import os
import sys
import shutil
import json

IOStream = namedtuple('IOStream', 'status, stdout, stderr')


# load config
config = json.load(open(join(dirname(__file__), 'config.json')))
if sys.platform not in config:
    raise OSError('OS not supported yet, please submit a patch :)')

# expand '~' in path names to the user's home dir
for attr, path in config[sys.platform].items():
    config[sys.platform][attr] = expanduser(path)


BITSHARES_BUILD_DIR = config[sys.platform]['BITSHARES_BUILD_DIR']
BITSHARES_HOME_DIR = config[sys.platform]['BITSHARES_HOME_DIR']
BITSHARES_BIN_DIR = config[sys.platform]['BITSHARES_BIN_DIR']

# on mac osx, readline needs to be installed by brew and
# "brew link --force readline" to take precedence over the
# outdated version of the system

# parse commandline args
DESC="""following commands are available:
 - clean_homedir : clean home directory. WARNING: this will delete your wallet!
 - clean         : clean build directory
 - build [hash]  : update and build bts client
 - run [hash]    : run latest compiled bts client, or the one with the given hash
 - list_bins     : list installed bitshares client binaries
"""
EPILOG="""You should also look into config.json to tune it to your liking."""
parser = argparse.ArgumentParser(description=DESC, epilog=EPILOG,
                                 formatter_class=RawTextHelpFormatter)
parser.add_argument('command', choices=['clean_homedir', 'clean', 'build', 'run', 'list'],
                    help='the command to run')
parser.add_argument('-r', '--rpc', action='store_true',
                    help='run binary with RPC server activated')
parser.add_argument('hash',
                    help='the hash of the desired commit', nargs='?')
args = parser.parse_args()


def _run(cmd, io=False):
    print('-'*80)
    print('running command: %s\n' % cmd)
    if io:
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

def run(cmd, io=False):
    r = _run(cmd, io)
    if r.status != 0:
        raise RuntimeError('Failed running: %s' % cmd)
    return r


def clone():
    if not exists(BITSHARES_BUILD_DIR):
        run('git clone https://github.com/BitShares/bitshares_toolkit.git "%s"' % BITSHARES_BUILD_DIR)
        os.chdir(BITSHARES_BUILD_DIR)
        run('git submodule init')


update = lambda: run('git checkout master && git pull && git submodule update')
clean_config = lambda: run('rm -f CMakeCache.txt')

if sys.platform == 'darwin':
    # assumes openssl installed from brew
    path = '/usr/local/opt/openssl/lib/pkgconfig'
    configure = lambda: run('PKG_CONFIG_PATH=%s:$PKG_CONFIG_PATH cmake .' % path)
else:
    configure = lambda: run('cmake .')

build = lambda: run(['make']+config.get('make_args', []))


def install_last_built_bin():
    # install into bin dir
    date = run('git show -s --format=%ci HEAD', io=True).stdout.split()[0]
    branch = run('git rev-parse --abbrev-ref HEAD', io=True).stdout.strip()
    commit = run('git log -1', io=True).stdout.splitlines()[0].split()[1]

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


if args.command == 'build':
    clone()

    os.chdir(BITSHARES_BUILD_DIR)
    update()
    if args.hash:
        run('git checkout %s && git submodule update' % args.hash)
    clean_config()
    configure()
    build()

    install_last_built_bin()

elif args.command == 'run':
    if args.hash:
        # if git rev specified, runs specific version
        print('Running specific instance of the bts client: %s' % args.hash)
        bin_name = run('ls %s' % join(BITSHARES_BIN_DIR,
                                      'bitshares_client_*%s*' % args.hash[:8]),
                       io=True).stdout.strip()
    else:
        # run latest version
        bin_name = join(BITSHARES_BIN_DIR, 'bitshares_client')

    run_args = config.get('run_args', [])
    if args.rpc:
        run_args.append('--server')

    run([bin_name] + run_args)

elif args.command == 'clean':
    run('rm -fr "%s"' % BITSHARES_BUILD_DIR)

elif args.command == 'clean_homedir':
    run('rm -fr "%s"' % BITSHARES_HOME_DIR)

elif args.command == 'list':
    run('ls -ltr "%s"' % BITSHARES_BIN_DIR)
