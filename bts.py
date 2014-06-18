#!/usr/bin/env python
# -*- coding: utf-8 -*-

from os.path import join, dirname, exists, islink
from subprocess import Popen, PIPE
from collections import namedtuple
import argparse
import os
import sys
import shutil

IOStream = namedtuple('IOStream', 'status, stdout, stderr')


# load config
config_file = join(dirname(__file__), 'config.py')
exec(open(config_file).read())


# parse commandline args
parser = argparse.ArgumentParser()
parser.add_argument('command', help='the command to run',
                    choices=['build', 'run', 'clean'])
args = parser.parse_args()


def _run(cmd, io=False):
    if io:
        p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
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
configure = lambda: run('cmake .')
build = lambda: run('make -j1')


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
    configure()
    build()

    install_last_built_bin()

elif args.command == 'run':
    # run latest version
    # if git rev specified, runs specific version
    run('%s %s' % (join(Config.BITSHARES_BIN_DIR, 'bitshares_client'),
                      '--maximum-number-of-connections=128'))

elif args.command == 'clean':
    run('rm -fr "%s"' % Config.BITSHARES_BUILD_DIR)
