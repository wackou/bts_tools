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

from . import core
import geoip2
import geoip2.webservice
import socket
import fcntl
import struct
import sys
import functools
import logging

log = logging.getLogger(__name__)


def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])


def get_ip():
    if sys.platform == 'darwin':
        return socket.gethostbyname(socket.gethostname())
    else:
        for iface in [b'eth0', b'en1']:
            #with suppress(Exception):
            try:
                return get_ip_address(iface)
            except Exception as e:
                log.warning('iface : %s' % iface)
                log.exception(e)
    raise OSError('Could not get IP address')


def get_ip_nofail():
    try:
        return get_ip()
    except Exception:
        return 'N/A'


@functools.lru_cache()
def resolve_dns(host):
    if ':' in host:
        ip, port = host.split(':')
        return '%s:%s' % (resolve_dns(ip), port)
    return socket.gethostbyname(host)



geoip_cache = {}  # cache queries to geoip service


import copy

def get_geoip_info(ip_addr):
    try:
        core.config['geoip2']  # check that we have a geoip2 section in config.yaml
        client = geoip2.webservice.Client(core.config['geoip2']['user'],
                                          core.config['geoip2']['password'])
    except KeyError as e:
        raise ValueError('No geoip2 user and password defined in config.yaml') from e


    try:
        pt = geoip_cache[ip_addr]
        log.debug('using geoip2 cached value for {}: {}'.format(ip_addr, pt))

    except KeyError:
        log.debug('getting geoip2 info for for {}'.format(ip_addr))
        response = client.city(ip_addr)

        pt = {'country': response.country.name,
              'country_iso': response.country.iso_code,
              'lat': response.location.latitude,
              'lon': response.location.longitude
              }

        log.debug('  {} -- {} ({}, {})'.format(ip_addr, pt['country'], pt['lat'], pt['lon']))

    geoip_cache[ip_addr] = pt
    return copy.copy(pt)
