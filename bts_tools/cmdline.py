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
from jinja2 import Environment, PackageLoader
from ruamel import yaml
from .core import platform, run, get_data_dir, get_bin_name, get_gui_bin_name, get_all_bin_names, is_graphene_based, join_shell_cmd
from . import core, init
from .rpcutils import rpc_call, BTSProxy
from .vps.vultr import VultrAPI
import argparse
import os
import sys
import shutil
import base64
import hashlib
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


def select_run_environment(env_name):
    log.info("Running '%s' client" % env_name)
    try:
        env = core.config['run_environments'][env_name]
        env['name'] = env_name
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
        run('{} cmake -DCMAKE_BUILD_TYPE=Debug {} .'.format(' '.join(CONFIGURE_OPTS),
                                                            ' '.join(cmake_opts)))
    else:
        run('{} cmake -DCMAKE_BUILD_TYPE=Release {} .'.format(' '.join(CONFIGURE_OPTS),
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
            r = run('git describe --tags %s' % commit, capture_io=True, verbose=False)
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

    for bname in get_all_bin_names(BUILD_ENV['name']):
        install_and_symlink(bname)

def deploy(build_env, remote_host):
    select_build_environment(build_env)

    log.info('Deploying built binaries to {}'.format(remote_host))
    remote_bin_dir = core.config['build_environments'][build_env]['bin_dir']

    # strip binaries before sending, saves up to 10x space
    for bin_name in get_all_bin_names(BUILD_ENV['name']):
        bin_name = os.path.basename(bin_name)
        latest = os.path.basename(os.path.realpath(join(BTS_BIN_DIR, bin_name)))
        run('strip "{}/{}"'.format(BTS_BIN_DIR, latest))

    # sync all
    run('rsync -avzP "{}/" {}:"{}/"'.format(BTS_BIN_DIR, remote_host, remote_bin_dir))

    # also symlink properly latest built binaries)
    for bin_name in get_all_bin_names(BUILD_ENV['name']):
        bin_name = os.path.basename(bin_name)
        latest = os.path.basename(os.path.realpath(join(BTS_BIN_DIR, bin_name)))
        run('ssh {} "ln -fs {}/{} {}/{}"'.format(remote_host,
                                                 remote_bin_dir, latest,
                                                 remote_bin_dir, bin_name))



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
    parser.add_argument('-r', '--norpc', action='store_true',
                        help='run binary with RPC server deactivated')
    parser.add_argument('environment', nargs='?',
                        help='the build/run environment (bts, pts, ...)')
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
        run_env = select_run_environment(args.environment)
        run_args = core.config.get('run_args', []) + run_env.get('run_args', [])
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
            data_dir = run_env.get('data_dir')
            if data_dir:
                run_args = ['--data-dir', expanduser(data_dir)] + run_args

            genesis_file = run_env.get('genesis_file')
            if genesis_file:
                run_args += ['--genesis-json', expanduser(genesis_file)]

            witness_port = run_env.get('witness_port')
            if witness_port:
                run_args += ['--rpc-endpoint', '0.0.0.0:{}'.format(witness_port)]

            p2p_port = run_env.get('p2p_port')
            if p2p_port:
                run_args += ['--p2p-endpoint', '0.0.0.0:{}'.format(p2p_port)]

            seed_nodes = run_env.get('seed_nodes', [])
            for node in seed_nodes:
                run_args += ['--seed-node', node]

        elif args.command == 'run_cli':
            witness_port = run_env.get('witness_port')
            if witness_port:
                run_args += ['--server-rpc-endpoint', 'ws://127.0.0.1:{}'.format(witness_port)]

            cli_port = run_env.get('cli_port')
            if cli_port:
                run_args += ['--rpc-http-endpoint', '0.0.0.0:{}'.format(cli_port)]

            chain_id = run_env.get('chain_id')
            if chain_id:
                run_args += ['--chain-id', chain_id]

        if not args.norpc and not is_graphene_based(run_env):
            run_args = ['--server'] + run_args

        if run_env.get('debug', False):
            if platform == 'linux':
                cmd = ' '.join(['gdb', '-ex', 'run', '--args', bin_name] + run_args)
            else:
                log.warning('Running with debug=true is not implemented on your platform (%s)' % platform)
                cmd = [bin_name] + run_args

        else:
            cmd = [bin_name] + run_args

        if is_graphene_based(run_env):
            # for graphene clients, always cd to data dir first (if defined), this ensures the wallet file
            # and everything else doesn't get scattered all over the place
            data_dir = get_data_dir(run_env['name'])
            if data_dir:
                # ensure it exists to be able to cd into it
                with suppress(FileExistsError):
                    Path(data_dir).mkdir(parents=True)
                cmd = 'cd "{}"; {}'.format(data_dir, join_shell_cmd(cmd))

        run(cmd)

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
        run('ls -ltr "%s"' % BTS_BIN_DIR)

    elif args.command == 'monitor':
        print('\nLaunching monitoring web app...')
        run('python3 -m bts_tools.wsgi')

    elif args.command == 'deploy':
        if not args.args:
            log.error('You need to specify a remote host to deploy to')
            sys.exit(1)

        for remote_host in args.args:
            deploy(args.environment, remote_host)

    elif args.command == 'deploy_node':
        select_build_environment(args.environment)
        config_file = args.args[0] if args.args else None
        print()
        if not config_file:
            log.error('You need to specify a deployment config file as argument')
            log.info('It should be a YAML file with the following format')
            config_example = """
host: 192.168.0.1  # ip or name of host to deploy to, needs ssh access
pause: true  # pause between installation steps
is_debian: true
install_compile_dependencies: false

unix_hostname: seed01
unix_user: &user myuser
unix_password: changeme!
git_name: John Doe
git_email: johndoe@example.com
nginx_server_name: seed01.bitsharesnodes.com
uwsgi_user: *user
uwsgi_group: *user
"""
            print(config_example)
            #default_config = join(dirname(__file__), 'deploy_config.yaml')
            #log.info('You can find an example config at: %s' % default_config)
            sys.exit(1)

        log.info('Reading config from file: %s' % config_file)
        with open(config_file, 'r') as f:
            cfg = yaml.load(f)

        cfg['pause'] = False  # do not pause during installation

        # 0.0- create vps instance
        if cfg.get('host'):
            # do not create an instance, use the one on the given ip address
            log.info('Not creating new instance, using given host: {}'.format(cfg['host']))
            pass

        elif cfg['vps'].get('provider', '').lower() == 'vultr':
            v = cfg['vps']['vultr']
            vultr = VultrAPI(v['api_key'])
            params = dict(v)
            params.pop('api_key')
            params['label'] = cfg['unix_hostname']
            ip_addr = vultr.create_server(**params)
            cfg['host'] = ip_addr

        else:
            log.warning('No host and no valid vps provider given. Exiting...')
            return

        # 0- prepare the bundle of files to be copied on the remote host
        build_dir = '/tmp/bts_deploy'
        run('rm -fr {d}; mkdir {d}'.format(d=build_dir))
        env = Environment(loader=PackageLoader('bts_tools', 'templates/deploy'))

        def render_template(template_name, output_name=None):
            template = env.get_template(template_name)
            with open(join(build_dir, output_name or template_name), 'w') as output_file:
                output_file.write(template.render(**cfg))

        # 0.1- generate the install script
        render_template('install_new_graphene_node.sh')
        render_template('install_user.sh')

        # 0.2- generate config.yaml file
        config_yaml = yaml.load(env.get_template('config.yaml').render(), Loader=yaml.RoundTripLoader)
        config_yaml.update(cfg['config_yaml'])
        with open(join(build_dir, 'config.yaml'), 'w') as config_yaml_file:
            config_yaml_file.write(yaml.dump(config_yaml, indent=4, Dumper=yaml.RoundTripDumper))

        # 0.3- generate api_access.json and config.ini
        cfg['witness_api_access_user'] = cfg['witness_api_access']['user']
        pw_bytes = cfg['witness_api_access']['password'].encode('utf-8')
        salt_bytes = os.urandom(8)
        salt_b64 = base64.b64encode(salt_bytes)
        pw_hash = hashlib.sha256(pw_bytes + salt_bytes).digest()
        pw_hash_b64 = base64.b64encode(pw_hash)

        cfg['witness_api_access_hash'] = pw_hash_b64.decode('utf-8')
        cfg['witness_api_access_salt'] = salt_b64.decode('utf-8')
        render_template('api_access.json')

        render_template('config.ini')

        # 0.4- nginx
        nginx = join(build_dir, 'etc', 'nginx')
        run('mkdir -p {} {}'.format(join(nginx, 'sites-available'),
                                    join(nginx, 'sites-enabled')))
        render_template('nginx_sites_available', join(nginx, 'sites-available', 'default'))
        run('cd {}; ln -s ../sites-available/default'.format(join(nginx, 'sites-enabled')))
        run('cd {}; tar cvzf {} etc/nginx'.format(build_dir, join(build_dir, 'etcNginx.tgz')))

        def run_remote(cmd):
            run('ssh root@{} "{}"'.format(host, cmd))

        def copy(filename, dest_dir):
            run('scp "{}" root@"{}:{}"/'.format(filename, dest_dir))


        # 0.5- uwsgi
        uwsgi = join(build_dir, 'etc', 'uwsgi')
        run('mkdir -p {} {}'.format(join(uwsgi, 'apps-available'),
                                    join(uwsgi, 'apps-enabled')))
        render_template('uwsgi_apps_available', join(uwsgi, 'apps-available', 'bts_tools.ini'))
        run('cd {}; ln -s ../apps-available/bts_tools.ini'.format(join(uwsgi, 'apps-enabled')))
        run('cd {}; tar cvzf {} etc/uwsgi'.format(build_dir, join(build_dir, 'etcUwsgi.tgz')))

        # 0.6- get authorized_keys if any
        if cfg.get('ssh_keys'):
            with open(join(build_dir, 'authorized_keys'), 'w') as key_file:
                for key in cfg['ssh_keys']:
                    key_file.write('{}\n'.format(key))

        run('rm -fr {}'.format(join(build_dir, 'etc')))

        host = cfg['host']
        # 1- ssh to host and scp or rsync the installation scripts and tarballs
        log.info('Copying install scripts to remote host')
        run('ssh root@{} "apt-get install -yfV rsync"'.format(host))
        run('rsync -avzP {}/* root@{}:/tmp/'.format(build_dir, host))

        # 2- run the installation script remotely
        log.info('Installing remote host')
        run('ssh root@{} "cd /tmp; bash install_new_graphene_node.sh"'.format(host))

        # 3- copy prebuilt binaries
        log.info('Deploying prebuilt binaries')
        deploy(args.environment, '{}@{}'.format(cfg['unix_user'], host))

        # 4- reboot remote host
        log.info('Installation completed successfully, starting fresh node')
        #run('ssh root@{} reboot'.format(host))

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

        client = BTSProxy(type='delegate', name=delegate, client=args.environment)

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


def main_bts2():
    return main(flavor='bts2')


def main_muse():
    return main(flavor='muse')


def main_dvs():
    return main(flavor='dvs')


def main_pts():
    return main(flavor='pts')


def main_pls():
    return main(flavor='pls')


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

