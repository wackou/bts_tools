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

from collections import deque
from logging.handlers import TimedRotatingFileHandler
from os.path import expanduser
import logging
import sys
import os

GREEN_FONT = "\x1B[0;32m"
YELLOW_FONT = "\x1B[0;33m"
BLUE_FONT = "\x1B[0;34m"
RED_FONT = "\x1B[0;31m"
RESET_FONT = "\x1B[0m"

log_records = deque(maxlen=1000)

def setupLogging(colored=True, with_time=False, with_thread=False, filename=None, with_lineno=False):  # pragma: no cover
    """Set up a nice colored logger as the main application logger."""

    class SimpleFormatter(logging.Formatter):
        def __init__(self, with_time, with_thread):
            self.fmt = (('[%(asctime)s] ' if with_time else '') +
                        '%(levelname)-8s ' +
                        '[%(name)s:%(funcName)s' +
                        (':%(lineno)s' if with_lineno else '') + ']' +
                        ('[%(threadName)s]' if with_thread else '') +
                        ' -- %(message)s')
            logging.Formatter.__init__(self, self.fmt)

    class ColoredFormatter(logging.Formatter):
        def __init__(self, with_time, with_thread):
            self.fmt = (('%(asctime)s ' if with_time else '') +
                        '-CC-%(levelname)-8s ' +
                        BLUE_FONT + '[%(name)s:%(funcName)s' +
                        (':%(lineno)s' if with_lineno else '') + ']' +
                        RESET_FONT + ('[%(threadName)s]' if with_thread else '') +
                        ' -- %(message)s')

            logging.Formatter.__init__(self, self.fmt)

        def format(self, record):
            modpath = record.name.split('.')
            record.mname = modpath[0]
            record.mmodule = '.'.join(modpath[1:])
            result = logging.Formatter.format(self, record)
            if record.levelno == logging.DEBUG:
                color = BLUE_FONT
            elif record.levelno == logging.INFO:
                color = GREEN_FONT
            elif record.levelno == logging.WARNING:
                color = YELLOW_FONT
            else:
                color = RED_FONT

            result = result.replace('-CC-', color)
            return result

    if filename is not None:
        # make sure we can write to our log file
        logdir = os.path.dirname(filename)
        if not os.path.exists(logdir):
            os.makedirs(logdir)
        ch = logging.FileHandler(filename, mode='w')
        ch.setFormatter(SimpleFormatter(with_time, with_thread))
    else:
        ch = logging.StreamHandler()
        if colored and sys.platform != 'win32':
            ch.setFormatter(ColoredFormatter(with_time, with_thread))
        else:
            ch.setFormatter(SimpleFormatter(with_time, with_thread))

    logging.getLogger().addHandler(ch)

    class LogsCopy(logging.Handler):
        def emit(self, record):
            log_records.append(record)

    logging.getLogger().addHandler(LogsCopy())

    file_log = TimedRotatingFileHandler(expanduser('~/.bts_tools/bts_tools.log'), when='D', backupCount=10, utc=True)
    file_log.setFormatter(SimpleFormatter(with_time, with_thread))
    logging.getLogger().addHandler(file_log)
