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

from setuptools import setup, find_packages
import os, os.path
import subprocess

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
HISTORY = open(os.path.join(here, 'HISTORY.rst')).read()

VERSION = '0.4.5'


install_requires = ['Flask', 'requests', 'psutil', 'arrow', 'pyyaml', 'dogpile.cache',
                    'beautifulsoup4', 'maxminddb-geolite2', 'autobahn', 'ruamel.yaml',
                    'doit', 'retrying', 'ecdsa', 'cachetools', 'wrapt',
                    'geoip2' # for ip addr -> lat, lon  (need account on maxmind)
                    ]

setup_requires = []

entry_points = {
    'console_scripts': [
        'bts = bts_tools.cmdline:main_bts',
        'bts1 = bts_tools.cmdline:main_bts1',
        'bts2 = bts_tools.cmdline:main_bts2',
        'muse = bts_tools.cmdline:main_muse',
        'steem = bts_tools.cmdline:main_steem',
        'dvs = bts_tools.cmdline:main_dvs',
        'pts = bts_tools.cmdline:main_pts',
        'pls = bts_tools.cmdline:main_pls'
    ],
}


args = dict(name='bts_tools',
            version=VERSION,
            description='BitShares delegate tools',
            long_description=README + '\n\n\n' + HISTORY,
            # Get strings from
            # http://pypi.python.org/pypi?%3Aaction=list_classifiers
            classifiers=['Development Status :: 4 - Beta',
                         'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
                         'Operating System :: OS Independent',
                         'Programming Language :: Python :: 3',
                         'Programming Language :: Python :: 3.4',
                         ],
            keywords='BitShares delegate tools',
            author='Nicolas Wack',
            author_email='wackou@gmail.com',
            url='https://github.com/wackou/bts_tools',
            packages=find_packages(),
            include_package_data=True,
            install_requires=install_requires,
            setup_requires=setup_requires,
            entry_points=entry_points,
            )

# if we are creating a source tarball, include the version in a text file
version_file = os.path.join(here, 'bts_tools', 'version.txt')
create_version_file = not os.path.exists(version_file)

if create_version_file:
    with open(version_file, 'w') as f:
        try:
            p = subprocess.Popen('git describe --tags', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            f.write(str(stdout, encoding='utf-8'))
        except:
            f.write(VERSION)

setup(**args)

if create_version_file:
    try:
        os.remove(version_file)
    except OSError:
        pass
