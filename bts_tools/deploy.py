#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
# Copyright (c) 2016 Nicolas Wack <wackou@gmail.com>
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

from os.path import join
from functools import partial
from jinja2 import Environment, PackageLoader
from ruamel import yaml
from .core import run, get_all_bin_names
from .cmdline import select_build_environment
from . import core, cmdline
from .vps import VultrAPI, GandiAPI
import os
import re
import base64
import hashlib
import logging

log = logging.getLogger(__name__)


def deploy(build_env, remote_host):
    env = select_build_environment(build_env)

    log.info('Deploying built binaries to {}'.format(remote_host))
    remote_bin_dir = core.config['build_environments'][build_env]['bin_dir']

    # strip binaries before sending, saves up to 10x space
    for bin_name in get_all_bin_names(env['name']):
        bin_name = os.path.basename(bin_name)
        latest = os.path.basename(os.path.realpath(join(cmdline.BTS_BIN_DIR, bin_name)))
        run('strip "{}/{}"'.format(cmdline.BTS_BIN_DIR, latest))

    # sync all
    run('rsync -avzP "{}/" {}:"{}/"'.format(cmdline.BTS_BIN_DIR, remote_host, remote_bin_dir))

    # also symlink properly latest built binaries)
    for bin_name in get_all_bin_names(env['name']):
        bin_name = os.path.basename(bin_name)
        latest = os.path.basename(os.path.realpath(join(cmdline.BTS_BIN_DIR, bin_name)))
        run('ssh {} "ln -fs {}/{} {}/{}"'.format(remote_host,
                                                 remote_bin_dir, latest,
                                                 remote_bin_dir, bin_name))

def create_vps_instance(cfg):
    if cfg.get('host'):
        # do not create an instance, use the one on the given ip address
        log.info('Not creating new instance, using given host: {}'.format(cfg['host']))
        return

    elif cfg['vps'].get('provider', '').lower() == 'vultr':
        v = cfg['vps']['vultr']
        vultr = VultrAPI(v['api_key'])
        params = dict(v)
        params.pop('api_key')
        ip_addr = vultr.create_server(**params)
        cfg['host'] = ip_addr

    elif cfg['vps'].get('provider', '').lower() == 'gandi':
        v = cfg['vps']['gandi']
        gandi = GandiAPI(v['api_key'])
        params = dict(v)
        params.pop('api_key')
        ip_addr = gandi.create_server(**params)
        cfg['host'] = ip_addr

    else:
        raise ValueError('No host and no valid vps provider given')


def render_template_file(cfg, build_dir, env, template_name, output_name=None):
    template = env.get_template(template_name)
    with open(join(build_dir, output_name or template_name), 'w') as output_file:
        output_file.write(template.render(**cfg))


def prepare_installation_bundle(cfg, build_dir):
    run('rm -fr {d}; mkdir {d}'.format(d=build_dir))
    env = Environment(loader=PackageLoader('bts_tools', 'templates/deploy'))

    render_template = partial(render_template_file, cfg, build_dir, env)

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


def run_remote_cmd(host, user, cmd):
    run('ssh -o "ControlMaster=no" {}@{} "{}"'.format(user, host, cmd))


def deploy_base_node(cfg, build_dir, build_env):
    env = Environment(loader=PackageLoader('bts_tools', 'templates/deploy'))
    host = cfg['host']

    render_template = partial(render_template_file, cfg, build_dir, env)
    run_remote = partial(run_remote_cmd, host, 'root')

    def copy(filename, dest_dir, user='root', compress=True):
        run('rsync -av{}P {} {}@{}:"{}"'.format('z' if compress else '', filename, user, host, dest_dir))

    # make sure we can successfully connect to it via ssh without confirmation
    run('ssh -o "StrictHostKeyChecking no" root@{} ls'.format(host))

    run_remote('apt-get install -yfV rsync')

    # TODO: all the following steps should actually be self-contained execution units available as plugins.
    #       this would allow to create ad-hoc scripts very quickly with very little text editing required.

    # 1- ssh to host and scp or rsync the installation scripts and tarballs
    log.info('Copying install scripts to remote host')
    copy('{}/*'.format(build_dir), '/tmp/')

    # 2- run the installation script remotely
    log.info('Installing remote host')
    run_remote('cd /tmp; bash install_new_graphene_node.sh')

    # 2.1- install supervisord conf
    log.info('Installing supervisord config')
    run_remote('apt-get install -yfV supervisor')
    render_template('supervisord.conf')
    copy(join(build_dir, 'supervisord.conf'), '/etc/supervisor/conf.d/bts_tools.conf')

    # 3- copy prebuilt binaries
    if cfg.get('compile_on_new_host', False):
        log.info('Not deploying any binaries, they have been compiled locally')
    else:
        log.info('Deploying prebuilt binaries')
        # deploy for all clients required
        clients_to_deploy = {c['type'] for c in cfg['config_yaml']['clients'].values()}
        for build_env in clients_to_deploy:
            log.info('-- deploying {} client'.format(build_env))
            deploy(build_env, '{}@{}'.format(cfg['unix_user'], host))

    # 4- copy snapshot of the blockchain, if available
    snapshot = cfg.get('blockchain_snapshot')
    if snapshot:
        for client_name, client in cfg['config_yaml']['clients'].items():
            try:
                local_data_dir = snapshot[client_name]
                remote_data_dir = client['data_dir']
                run_remote_cmd(host, cfg['unix_user'], 'mkdir -p {}/blockchain'.format(remote_data_dir))
                copy('{}/blockchain/'.format(local_data_dir),
                     '{}/blockchain/'.format(remote_data_dir),
                     user=cfg['unix_user'], compress=False)
            except Exception as e:
                log.warning('Could not deploy {} blockchain dir because:'.format(client_name))
                log.exception(e)


def deploy_seed_node(cfg):
    log.info('Deploying seed node...')
    deploy_base_node(cfg)


def is_ip(host):
    return re.fullmatch('[0-9]{1,3}(\.[0-9]{1,3}){3}', host) is not None

def deploy_node(build_env, config_file, host):
    select_build_environment(build_env)

    log.info('Reading config from file: %s' % config_file)
    with open(config_file, 'r') as f:
        cfg = yaml.load(f)

    cfg['pause'] = False  # do not pause during installation
    cfg['is_debian'] = True
    cfg['nginx_server_name'] = '{}.{}'.format(cfg['hostname'], cfg['domain'])

    # 1- create vps instance if needed
    try:
        if is_ip(host):
            cfg['host'] = host
        else:
            cfg['vps']['provider'] = host

        create_vps_instance(cfg)
    except ValueError as e:
        log.exception(e)
        log.warning('No host and no valid vps provider given. Exiting...')
        return

    build_dir = '/tmp/bts_deploy'

    # 2- prepare the bundle of files to be copied on the remote host
    prepare_installation_bundle(cfg, build_dir)

    # 4- perform the remote install
    log.info('To view the log of the current installation, run the following command in another terminal:')
    print()
    print('ssh root@{} "tail -f /tmp/setupVPS.log"'.format(cfg['host']))
    print()
    deploy_base_node(cfg, build_dir, build_env)


    # 4- reboot remote host
    log.info('Installation completed successfully, starting fresh node')
    log.info('Please wait a minute or two to let it start fully')
    log.warning('The script will now hang, sorry... Please stop it using ctrl-c')
    run_remote_cmd(cfg['host'], 'root', 'reboot &')  # FIXME: we hang here on reboot
    # see: http://unix.stackexchange.com/questions/58271/closing-connection-after-executing-reboot-using-ssh-command
    # maybe use nohup: https://en.wikipedia.org/wiki/Nohup
