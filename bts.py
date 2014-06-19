#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os.path import join, dirname, exists, islink
from subprocess import Popen, PIPE
from collections import namedtuple
from argparse import RawTextHelpFormatter
import argparse
import os
import sys
import shutil

IOStream = namedtuple('IOStream', 'status, stdout, stderr')


# load config
config_file = join(dirname(__file__), 'config.py')
exec(open(config_file).read())


# on mac osx, readline needs to be installed by brew and
# "brew link --force readline" to take precedence over the outdated readline

# parse commandline args
DESC="""following commands are available:
 - clean      : clean build directory
 - build      : update and build bts client
 - run [hash] : run latest compiled bts client, or the one with the given hash
 - list_bins  : list installed bitshares client binaries
"""
parser = argparse.ArgumentParser(description=DESC,
                                 formatter_class=RawTextHelpFormatter)
parser.add_argument('command', help='the command to run',
                    choices=['build', 'run', 'clean', 'list'])
parser.add_argument('hash', help='the hash of the desired commit', nargs='?')
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
        return IOStream(os.system(cmd), None, None)

def run(cmd, io=False):
    r = _run(cmd, io)
    if r.status != 0:
        raise RuntimeError('Failed running: %s' % cmd)
    return r


def clone():
    if not exists(Config.BITSHARES_BUILD_DIR):
        run('git clone https://github.com/BitShares/bitshares_toolkit.git "%s"' % Config.BITSHARES_BUILD_DIR)
        os.chdir(Config.BITSHARES_BUILD_DIR)
        run('git submodule init')



update = lambda: run('git pull && git submodule update')
clean_config = lambda: run('rm -f CMakeCache.txt')

if sys.platform == 'darwin':
    # assumes openssl installed from brew
    path = '/usr/local/opt/openssl/lib/pkgconfig'
    configure = lambda: run('PKG_CONFIG_PATH=%s:$PKG_CONFIG_PATH cmake .' % path)
else:
    configure = lambda: run('cmake .')

build = lambda: run('make')


def install_last_built_bin():
    # install into bin dir
    date = run('git show -s --format=%ci HEAD', io=True).stdout.split()[0]
    branch = run('git rev-parse --abbrev-ref HEAD', io=True).stdout.strip()
    commit = run('git log -1', io=True).stdout.splitlines()[0].split()[1]

    bin_filename = 'bitshares_client_%s_%s_%s' % (date, branch, commit[:6])

    def install(src, dst):
        print('Installing %s' % dst)
        if islink(src):
            result = join(dirname(src), os.readlink(src))
            print('Following symlink %s -> %s' % (src, result))
            src = result
        dst = join(Config.BITSHARES_BIN_DIR, dst)
        shutil.copy(src, dst)
        return dst

    if not exists(Config.BITSHARES_BIN_DIR):
        os.makedirs(Config.BITSHARES_BIN_DIR)

    client = join(Config.BITSHARES_BUILD_DIR, 'programs', 'client', 'bitshares_client')

    c = install(client, bin_filename)

    last_installed = join(Config.BITSHARES_BIN_DIR, 'bitshares_client')
    try:
        os.unlink(last_installed)
    except:
        pass
    os.symlink(c, last_installed)


if args.command == 'build':
    clone()

    os.chdir(Config.BITSHARES_BUILD_DIR)
    update()
    clean_config()
    configure()
    build()

    install_last_built_bin()

elif args.command == 'run':
    if args.hash:
        # if git rev specified, runs specific version
        print('Running specific instance of the bts client: %s' % args.hash)
        bin_name = run('ls %s' % join(Config.BITSHARES_BIN_DIR,
                                      'bitshares_client_*%s*' % args.hash),
                       io=True).stdout.strip()
    else:
        # run latest version
        bin_name = join(Config.BITSHARES_BIN_DIR, 'bitshares_client')

    if not exists(Config.BITSHARES_HOME_DIR):
        # run without --server the first time as we don't have a config.json yet
        run('"%s" %s' % (bin_name,
                         '--maximum-number-of-connections=128'))
    else:
        run('"%s" %s %s' % (bin_name,
                            '--maximum-number-of-connections=128',
                            '--server'))

elif args.command == 'clean':
    run('rm -fr "%s"' % Config.BITSHARES_BUILD_DIR)

elif args.command == 'list':
    run('ls -l "%s"' % Config.BITSHARES_BIN_DIR)