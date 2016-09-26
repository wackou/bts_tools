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
from .core import run, get_all_bin_names, hash_salt_password
from .cmdline import select_build_environment
from . import core, cmdline
from .vps import VultrAPI, GandiAPI
import copy
import os
import re
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
        log.info('================ Installing graphene on given host: {} ================'.format(cfg['host']))
        return cfg['host']


    VPS_PROVIDERS = {'gandi': GandiAPI,
                     'vultr': VultrAPI}

    vps_provider = cfg.get('vps', {}).get('provider', '').lower()

    if vps_provider in VPS_PROVIDERS:
        log.info('================ Creating new instance on {} ================'.format(vps_provider))
        v = cfg['vps'][vps_provider]
        provider = VPS_PROVIDERS[vps_provider](v['api_key'])
        params = dict(v)
        params.pop('api_key')
        params['os'] = cfg['os']
        ip_addr = provider.create_server(**params)
        cfg['host'] = ip_addr
        return cfg['host']

    raise ValueError('No host and no valid vps provider given (host = {}  --  vps provider = {}'
                     .format(cfg.get('host'), vps_provider))


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
    config_yaml.update(copy.deepcopy(cfg['config_yaml']))
    for client_name, client in config_yaml['clients'].items():
        client.pop('deploy', None)
    with open(join(build_dir, 'config.yaml'), 'w') as config_yaml_file:
        config_yaml_file.write(yaml.dump(config_yaml, indent=4, Dumper=yaml.RoundTripDumper))

    # 0.3- generate api_access.json
    cfg['witness_api_access_user'] = cfg['witness_api_access']['user']
    pw_hash, pw_salt = hash_salt_password(cfg['witness_api_access']['password'])
    cfg['witness_api_access_hash'] = pw_hash
    cfg['witness_api_access_salt'] = pw_salt

    render_template('api_access.json')
    render_template('api_access.steem.json')

    # 0.4- get authorized_keys if any
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
    log.info('================ Copying install scripts to remote host ================')
    copy('{}/*'.format(build_dir), '/tmp/')

    # 2- run the installation script remotely
    log.info('================ Installing remote host ================')
    run_remote('cd /tmp; bash install_new_graphene_node.sh')

    # 2.0- copy config.yaml file to ~/.bts_tools/
    copy(join(build_dir, 'config.yaml'), '~/.bts_tools/config.yaml', user=cfg['unix_user'])

    # 2.0- copy api_access.json
    copy(join(build_dir, 'api_access.json'), '~/', user=cfg['unix_user'])

    # 2.1- install supervisord conf
    log.info('* Installing supervisord config')
    run_remote('apt-get install -yfV supervisor')
    run_remote('systemctl enable supervisor')   # not enabled by default, at least on ubuntu 16.04 (bug?)
    render_template('supervisord.conf')
    copy(join(build_dir, 'supervisord.conf'), '/etc/supervisor/conf.d/bts_tools.conf')

    # 2.2- install nginx
    log.info('* Installing nginx...')

    run_remote('apt-get install -yfV nginx >> /tmp/setupVPS.log 2>&1')
    run_remote('rm -fr /etc/nginx-original; cp -R /etc/nginx /etc/nginx-original')
    nginx = join(build_dir, 'etc', 'nginx')
    run('mkdir -p {}'.format(join(nginx, 'sites-available')))
    render_template('nginx_sites_available', join(nginx, 'sites-available', 'default'))
    copy(join(nginx, 'sites-available', 'default'), '/etc/nginx/sites-available/default')
    run_remote('cd /etc/nginx/sites-enabled; ln -fs ../sites-available/default')
    # get remoter nginx.conf
    # add:   limit_req_zone $binary_remote_addr zone=ws:10m rate=1r/s;
    # write it back
    run_remote('chown -R root:root /etc/nginx')

    # copy certs if provided
    run_remote('cd /etc/nginx; mkdir -p certs')
    cfg_nginx = cfg.get('nginx', {})
    ssl_key, ssl_cert = cfg_nginx.get('ssl_key'), cfg_nginx.get('ssl_cert')
    if ssl_key:
        copy(ssl_key, '/etc/nginx/certs')
        run_remote('chmod 640 /etc/nginx/certs/{}'.format(os.path.basename(ssl_key)))
    if ssl_cert:
        copy(ssl_cert, '/etc/nginx/certs')

    run_remote('service nginx restart')

    # 2.2- install uwsgi
    log.info('* Installing uwsgi...')

    run_remote('apt-get install -yfV uwsgi uwsgi-plugin-python3 >> /tmp/setupVPS.log 2>&1')
    run_remote('rm -fr /etc/uwsgi-original; cp -R /etc/uwsgi /etc/uwsgi-original')
    uwsgi = join(build_dir, 'etc', 'uwsgi')
    run('mkdir -p {}'.format(join(uwsgi, 'apps-available')))
    render_template('uwsgi_apps_available', join(uwsgi, 'apps-available', 'bts_tools.ini'))
    copy(join(uwsgi, 'apps-available', 'bts_tools.ini'), '/etc/uwsgi/apps-available/bts_tools.ini')
    run_remote('cd /etc/uwsgi/apps-enabled; ln -fs ../apps-available/bts_tools.ini')
    run_remote('chown -R root:root /etc/uwsgi')
    run_remote('service uwsgi restart')

    # 3- copy prebuilt binaries
    if cfg.get('compile_on_new_host', False):
        log.info('================ Not deploying any binaries, they have been compiled locally ================')
    else:
        log.info('================ Deploying prebuilt binaries ================')
        # deploy for all clients required
        clients_to_deploy = {c['type'] for c in cfg['config_yaml']['clients'].values()}
        for build_env in clients_to_deploy:
            log.info('-- deploying {} client'.format(build_env))
            deploy(build_env, '{}@{}'.format(cfg['unix_user'], host))

    # 4- copy blockchain snapshots in their respective data dirs
    for client_name, client in cfg['config_yaml']['clients'].items():
        deploy_config = client.get('deploy', {})
        local_data_dir = deploy_config.get('blockchain_snapshot')
        if local_data_dir:
            log.info('Deploying {} chain snapshot from {}'.format(client_name, local_data_dir))
            try:
                # create remote data folder if it doesn't exist yet
                remote_data_dir = client['data_dir']
                run_remote_cmd(host, cfg['unix_user'], 'mkdir -p {}/blockchain'.format(remote_data_dir))
                copy('{}/blockchain/'.format(local_data_dir),
                     '{}/blockchain/'.format(remote_data_dir),
                     user=cfg['unix_user'], compress=False)
            except Exception as e:
                log.warning('Could not deploy {} blockchain dir because:'.format(client_name))
                log.exception(e)

    # make sure log file survives a reboot
    run_remote('cp /tmp/setupVPS.log /root/')


def deploy_seed_node(cfg):
    log.info('Deploying seed node...')
    deploy_base_node(cfg)


def is_ip(host):
    return re.fullmatch('[0-9]{1,3}(\.[0-9]{1,3}){3}', host) is not None

def load_config(config_file):
    log.info('Reading config from file: %s' % config_file)

    with open(config_file, 'r') as f:
        cfg = yaml.load(f)

    # auto adjustements of settings in the config
    cfg['pause'] = False  # do not pause during installation

    if cfg['os'] in ['debian', 'debian8', 'jessie']:
        cfg['is_debian'] = True
        cfg['is_ubuntu'] = False
        cfg['python_version'] = '3.4'
    elif cfg['os'] in ['ubuntu', 'ubuntu 16.04']:
        cfg['is_debian'] = False
        cfg['is_ubuntu'] = True
        cfg['python_version'] = '3.5'
    else:
        raise ValueError('unknown OS: {}'.format(cfg['os']))

    nginx = cfg.setdefault('nginx', {})
    nginx.setdefault('server_name', '{}.{}'.format(cfg['hostname'], cfg['domain']))
    if nginx.get('ssl_key'):
        nginx['ssl_key_basename'] = os.path.basename(nginx['ssl_key'])
    if nginx.get('ssl_cert'):
        nginx['ssl_cert_basename'] = os.path.basename(nginx['ssl_cert'])

    git = cfg.setdefault('git', {})
    git.setdefault('name', 'John Doe')
    git.setdefault('email', 'johndoe@example.com')

    return cfg


def deploy_node(build_env, config_file, host):
    select_build_environment(build_env)
    cfg = load_config(config_file)

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

    build_dir = '/tmp/bts_deploy_{}'.format(cfg['host'])

    # 2- prepare the bundle of files to be copied on the remote host
    prepare_installation_bundle(cfg, build_dir)

    # 3- perform the remote install
    log.info('To view the log of the current installation, run the following command in another terminal:')
    print()
    print('ssh root@{} "tail -f /tmp/setupVPS.log"'.format(cfg['host']))
    print()
    deploy_base_node(cfg, build_dir, build_env)


    # 4- reboot remote host
    if cfg.get('reboot', True):
        log.info('Installation completed successfully, starting fresh node')
        log.info('Please wait a minute or two to let it start fully')
        log.warning('The script will now hang, sorry... Please stop it using ctrl-c')
        run_remote_cmd(cfg['host'], 'root', 'reboot &')  # FIXME: we hang here on reboot
        # see: http://unix.stackexchange.com/questions/58271/closing-connection-after-executing-reboot-using-ssh-command
        # maybe use nohup: https://en.wikipedia.org/wiki/Nohup
