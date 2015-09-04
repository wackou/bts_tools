#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import re


DOIT_CONFIG = {
    'default_tasks': ['show_cmds'],
    'backend': 'json',
    'dep_file': '.doit.json',
}


def task_show_cmds():
    """Show the list of available doit commands"""
    def noargs():
        print('doit has been run without arguments. Please specify which command to run.\n')
    return {'actions': [noargs, 'doit list'],
            'verbosity': 2}


def task_clean_pyc():
    """Clean all the .pyc files."""
    return {'actions': ['find . -iname "*.pyc" -delete']}


def open_file(filename):
    """Open the given file using the OS's native programs"""
    if sys.platform.startswith('linux'):
        return 'xdg-open "%s"' % filename
    elif sys.platform == 'darwin':
        return 'open "%s"' % filename
    else:
        raise OSError('Platform not supported: %s' % sys.platform)


def task_doc():
    """Build the Sphinx documentation and open it in a web browser"""
    return {'actions': ['cd docs; make html',
                        open_file('docs/_build/html/index.html')]}


def task_pypi_doc():
    """Build the main page that will be uploaded to PyPI and open it in a web browser"""
    return {'actions': ['python setup.py --long-description | rst2html.py > /tmp/bts_tools_pypi_doc.html',
                        open_file('/tmp/bts_tools_pypi_doc.html')]}


# Release management functions

def set_version(pos):
    """Set the version in the appropriate places (docs, setup.py, ...)"""
    if len(pos) != 1:
        print('You need to specify a single version number...', file=sys.stderr)
        sys.exit(1)

    version = pos[0]
    print('setting version %s' % version)

    def replace_version(version_filename, old, new):
        vfile = open(version_filename).read()
        vfile = re.sub(old, new, vfile)
        open(version_filename, 'w').write(vfile)

    replace_version('setup.py',
                    r"VERSION = '\S*'",
                    r"VERSION = '%s'" % version)

    replace_version('docs/conf.py',
                    r"release = '\S*'",
                    r"release = '%s'" % version)


def task_set_version():
    """Set the version in the appropriate places (docs, setup.py, ...)"""
    return {'actions': [set_version],
            'pos_arg': 'pos',
            'verbosity': 2}


def task_upload_pypi():
    """Build and upload the package on PyPI"""
    #git stash && rm -fr dist/ && python setup.py sdist upload && git stash apply && python setup.py develop
    return {'actions': ['python setup.py register sdist upload'],
            'verbosity': 2}
