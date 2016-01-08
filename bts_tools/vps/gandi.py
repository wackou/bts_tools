#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
# Copyright (c) 2015 Nicolas Wack <wackou@gmail.com>
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

from xmlrpc.client import ServerProxy
import time
import logging

log = logging.getLogger(__name__)


class GandiAPI(object):
    datacenters = {'paris': 1,
                   'baltimore': 2}

    def __init__(self, api_key, endpoint='https://rpc.gandi.net/xmlrpc/'):
        self.endpoint = endpoint
        self.api = ServerProxy(endpoint)
        self.api_key = api_key

    def call(self, method, *args):
        a = self.api
        for m in method.split('.'):
            a = getattr(a, m)
        return a(self.api_key, *args)

    def update_dns(self, domain, host, ip):
        # 1- find zone_id
        try:
            zone_id = self.call('domain.info', domain)['zone_id']
            zone_info = self.call('domain.zone.info', zone_id)
        except Exception as e:
            log.warning('Cannot get access to the {} domain'.format(domain))
            log.exception(e)
            return

        # 2- create new version
        log.info('Creating new version for zone {}'.format(zone_info['name']))
        version = self.call('domain.zone.version.new', zone_id)

        # 3- delete old record for host, if any
        log.info('Updating entry for {}.{}'.format(host, domain))
        try:
            self.call('domain.zone.record.delete', zone_id, version,
                      {'type': ['A'], 'name': [host]})
        except:
            pass

        # 4- add new record
        self.call('domain.zone.record.add', zone_id, version,
                  {'type': 'A', 'name': host, 'value': ip})

        # 5- set active version
        log.info('Activating new version')
        self.call('domain.zone.version.set', zone_id, version)

        log.info('Update of dns entry for {}.{} successfully finished!'.format(host, domain))

    def create_server(self, name, location, src_disk_id, ssh_keys, cores=1, memory=1024, disk_size=20480):
        log.info('Creating Gandi instance {} in {}...'.format(name, location))
        ssh_key_id = {key['name']: key['id'] for key in self.call('hosting.ssh.list')}

        dc_id = self.datacenters[location.lower()]

        disk_spec = {'datacenter_id': dc_id,
                     'name': name,
                     'size': disk_size}

        vm_spec = {'datacenter_id':dc_id,
                   'hostname': name,
                   'memory': memory,
                   'cores': cores,
                   'keys': [ssh_key_id[k] for k in ssh_keys],
                   }

        op = self.call('hosting.vm.create_from', vm_spec, disk_spec, src_disk_id)

        log.info('Waiting for server to be created...')
        while self.call('operation.info', op[2]['id'])['step'] != 'DONE':
            time.sleep(10)

        vm_id = self.call('operation.info', op[2]['id'])['params']['vm_id']
        ip_addr = [ip['ip'] for ip in self.call('hosting.vm.info', vm_id)['ifaces'][0]['ips'] if ip['version'] == 4][0]

        log.info('Gandi instance successfully created on {}!!'.format(ip_addr))
        return ip_addr
