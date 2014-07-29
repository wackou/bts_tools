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
from bitshares_delegate_tools.core import config, env, platform, rpc, run
import random
import apnsclient
import argparse
import os
import sys
import shutil
import json
import logging

log = logging.getLogger(__name__)

BITSHARES_GIT_REPO  = env['git_repo']
BITSHARES_BUILD_DIR = env[platform]['BITSHARES_BUILD_DIR']
BITSHARES_HOME_DIR  = env[platform]['BITSHARES_HOME_DIR']
BITSHARES_BIN_DIR   = env[platform]['BITSHARES_BIN_DIR']

# TODO: move this comment somewhere appropriate
# on mac osx, readline needs to be installed by brew and
# "brew link --force readline" to take precedence over the
# outdated version of the system


def clone():
    if not exists(BITSHARES_BUILD_DIR):
        run('git clone %s "%s"' % (BITSHARES_GIT_REPO, BITSHARES_BUILD_DIR))
        os.chdir(BITSHARES_BUILD_DIR)
        run('git submodule init')


update = lambda: run('git checkout master && git pull && git submodule update')
clean_config = lambda: run('rm -f CMakeCache.txt')

if platform == 'darwin':
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



def main():
    # parse commandline args
    DESC="""following commands are available:
     - clean_homedir : clean home directory. WARNING: this will delete your wallet!
     - clean         : clean build directory
     - build [hash]  : update and build bts client
     - run [hash]    : run latest compiled bts client, or the one with the given hash
     - list          : list installed bitshares client binaries
    """
    EPILOG="""You should also look into config.json to tune it to your liking."""
    parser = argparse.ArgumentParser(description=DESC, epilog=EPILOG,
                                     formatter_class=RawTextHelpFormatter)
    parser.add_argument('command', choices=['clean_homedir', 'clean', 'build', 'run', 'list'],
                        help='the command to run')
    parser.add_argument('-r', '--norpc', action='store_true',
                        help='run binary with RPC server deactivated')
    parser.add_argument('hash',
                        help='the hash of the desired commit', nargs='?')
    args = parser.parse_args()


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
    EPILOG="""You should look into config.json to configure the rpc user and password."""
    parser = argparse.ArgumentParser(description=DESC, epilog=EPILOG,
                                     formatter_class=RawTextHelpFormatter)
    parser.add_argument('method',
                        help='the command to run')
    parser.add_argument('args',
                        help='the hash of the desired commit', nargs='*')
    args = parser.parse_args()

    logging.getLogger('bitshares_delegate_tools').setLevel(logging.WARNING)

    try:
        result = getattr(rpc, args.method)(*args.args)
    except Exception as e:
        result = { 'error': str(e), 'type': '%s.%s' % (e.__class__.__module__,
                                                       e.__class__.__name__) }

    print(json.dumps(result))


def send_notification(msg):
    print('Sending message...')

    certfile = join(dirname(__file__), config['monitoring']['apns']['cert'])
    if not exists(certfile):
        log.error('Missing certificate file for APNs service: %s' % certfile)
    conn = apnsclient.Session().new_connection('push_sandbox', cert_file=certfile)
    message = apnsclient.Message(config['monitoring']['apns']['tokens'],
                                 alert=msg,
                                 sound='base_under_attack_%s.caf' % random.choice(['terran', 'zerg', 'protoss']),
                                 badge=1)

    # Send the message.
    srv = apnsclient.APNs(conn)
    try:
        res = srv.send(message)
    except:
        log.error('Can\'t connect to APNs, looks like network is down')
    else:
        # Check failures. Check codes in APNs reference docs.
        for token, reason in res.failed.items():
            code, errmsg = reason
            # according to APNs protocol the token reported here
            # is garbage (invalid or empty), stop using and remove it.
            log.error('Device failed: {0}, reason: {1}'.format(token, errmsg))

        # Check failures not related to devices.
        for code, errmsg in res.errors:
            log.error('Error: {}'.format(errmsg))

        # Check if there are tokens that can be retried
        if res.needs_retry():
            # repeat with retry_message or reschedule your task
            log.error('Needs retry...')
            retry_message = res.retry()
            log.error('Did retry: %s' % retry_message)

    log.info('Done sending notification: %s' % msg)


def main_bts_notify():
    # parse commandline args
    DESC="""Send the given message using push notifications."""
    parser = argparse.ArgumentParser(description=DESC,
                                     formatter_class=RawTextHelpFormatter)
    parser.add_argument('msg',
                        help='the message to send')
    args = parser.parse_args()

    send_notification(args.msg)
