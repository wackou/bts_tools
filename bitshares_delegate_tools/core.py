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

from os.path import join, dirname, expanduser, exists
from collections import namedtuple
from subprocess import Popen, PIPE
import sys
import os
import shutil
import json
import logging

log = logging.getLogger(__name__)

platform = sys.platform
if platform.startswith('linux'):
    platform = 'linux'

BTS_TOOLS_HOMEDIR = '~/.bts_tools'
BTS_TOOLS_HOMEDIR = expanduser(BTS_TOOLS_HOMEDIR)
BTS_TOOLS_CONFIG_FILE = join(BTS_TOOLS_HOMEDIR, 'config.json')

log.info('Using home dir for BTS tools: %s' % BTS_TOOLS_HOMEDIR)

def load_config():
    if not exists(BTS_TOOLS_CONFIG_FILE):
        try:
            os.makedirs(BTS_TOOLS_HOMEDIR)
        except OSError:
            pass
        shutil.copyfile(join(dirname(__file__), 'config.json'),
                        BTS_TOOLS_CONFIG_FILE)

    try:
        config_contents = open(BTS_TOOLS_CONFIG_FILE).read()
    except:
        log.error('Could not read config file: %s' % BTS_TOOLS_CONFIG_FILE)
        raise

    try:
        config = json.loads(config_contents)
    except:
        log.error('-'*100)
        log.error('Config file contents is not a valid JSON object:')
        log.error(config_contents)
        log.error('-'*100)
        raise

    return config

config = load_config()
env = config['env'][config['env']['active']]

if platform not in env:
    raise OSError('OS not supported yet, please submit a patch :)')

# expand '~' in path names to the user's home dir
for attr, path in env[platform].items():
    env[platform][attr] = expanduser(path)

# setup logging levels from config file
for name, level in config.get('logging', {}).items():
    logging.getLogger(name).setLevel(getattr(logging, level))


IOStream = namedtuple('IOStream', 'status, stdout, stderr')
StatsFrame = namedtuple('StatsFrame', 'cpu, mem, connections, timestamp')


def _run(cmd, io=False):
    if isinstance(cmd, list):
        cmd = cmd[0] + ' "' + '" "'.join(cmd[1:]) + '"'
    log.debug('SHELL: running command: %s' % cmd)
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


class UnauthorizedError(Exception):
    pass


class RPCError(Exception):
    pass


#### util functions we want to be able to access easily, such as in templates


_DELEGATE_NAME = config['delegate']

try:
    import uwsgi
    _DELEGATE_NAME = str(uwsgi.opt['delegate-name'])
    log.info('Using delegate name "%s" from uwsgi config file' % _DELEGATE_NAME)

except:
    log.info('Using delegate name "%s" from config.json file' % _DELEGATE_NAME)

def delegate_name():
    # TODO: should parse my accounts to know the actual delegate name
    return _DELEGATE_NAME

