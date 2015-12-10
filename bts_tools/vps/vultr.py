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

from ..core import run
import requests
import time
import logging

log = logging.getLogger(__name__)


class VultrAPI(object):
    datacenters = {'atlanta': 6,
                   'miami': 39,
                   'amsterdam': 7,
                   'london': 8,
                   'tokyo': 25,
                   'los angeles': 5,
                   'new jersey': 1,
                   'frankfurt': 9,
                   'seattle': 4,
                   'sydney': 19,
                   'chicago': 2,
                   'dallas': 3,
                   'silicon valley': 12,
                   'paris': 24}

    def __init__(self, api_key, endpoint='https://api.vultr.com/v1'):
        if endpoint.endswith('/'):
            endpoint = endpoint[:-1]
        self.endpoint = endpoint
        self.api_key = api_key

    def call(self, method, **kwargs):
        if kwargs:
            r = requests.post('{}/{}'.format(self.endpoint, method), params={'api_key': self.api_key}, data=kwargs)
        else:
            r = requests.get('{}/{}'.format(self.endpoint, method), params={'api_key': self.api_key})
        return r.json()

    def create_server(self, location, vps_plan_id, os_id, label, ssh_key_ids):
        log.info('Creating Vultr instance {} in {}...'.format(label, location))
        ssh_keys_list = self.call('sshkey/list').values()
        ssh_keys = {key['name']: key['SSHKEYID'] for key in ssh_keys_list}
        r = self.call('server/create',
                      DCID=self.datacenters[location.lower()],
                      VPSPLANID=vps_plan_id,
                      OSID=os_id,
                      label=label,
                      SSHKEYID=','.join(ssh_keys[k] for k in ssh_key_ids))
        sub_id = r['SUBID']

        # wait until server is properly created
        time.sleep(3) # make sure it's at least being created
        r = self.call('server/list')[sub_id]
        while not (r['server_state'] == 'ok' and r['status'] == 'active' and r['power_status'] == 'running'):
            #print('waiting for server to be created...')
            time.sleep(5)
            r = self.call('server/list')[sub_id]

        ip_addr = r['main_ip']
        # should wait an additional (reasonable) time, eg: 1-2 minutes
        # from vultr API doc: "the API does not provide any way to determine if the initial installation has completed or not."
        log.info('Waiting for installation on {} to finish...'.format(ip_addr))
        time.sleep(180)
        log.info('Vultr instance successfully created on {}!!'.format(ip_addr))
        # make sure we can successfully connect to it via ssh
        run('ssh -o "StrictHostKeyChecking no" root@{} ls'.format(ip_addr))
        return ip_addr
