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

from os.path import join, exists
from . import core
import smtplib
import random
import requests
import logging

log = logging.getLogger(__name__)

def send_email(to, subject, body, bcc=None, replyto=None):
    """Return True if the email could be sent, raise an exception
    otherwise."""
    c = core.config['notification']['email']

    fromaddr = replyto or c['identity']
    #toaddrs = [ to, fromaddr ]
    toaddrs = [ to ]

    # create the email string with correct headers
    message = ("From: %s\r\n" % fromaddr +
               "To: %s\r\n" % to +
               ("BCC: %s\r\n" % bcc if bcc else '') +
               "Subject: %s\r\n" % subject +
               "\r\n" +
               body)

    # Send the message via the configured SMTP server
    s = smtplib.SMTP_SSL(c['smtp_server'])
    s.login(c['smtp_user'], c['smtp_password'])
    s.sendmail(fromaddr, toaddrs, message)
    s.quit()

    return True


def send_notification_email(msg, alert=False):
    log.debug('Sending notification by email: %s' % msg)
    c = core.config['notification']['email']
    send_email(c['recipient'], 'BTS notification', msg)
    log.info('Sent email notification: %s' % msg)


def send_notification_boxcar(msg, alert=False):
    log.debug('Sending notification trough Boxcar: %s' % msg)
    tokens = core.config['notification']['boxcar']['tokens']
    for token in tokens:
        requests.post('https://new.boxcar.io/api/notifications',
                      data={'user_credentials': token,
                            'notification[sound]': 'score' if alert else 'no-sound',
                            'notification[title]': msg,
                            'notification[source_name]': 'BTS Tools'})
    log.info('Sent Boxcar notification: %s' % msg)



def send_notification(nodes, node_msg, alert=False):
    for ntype, notify in [('email', send_notification_email),
                          ('boxcar', send_notification_boxcar)]:
        notify_nodes = [node for node in nodes if ntype in node.notification]
        if notify_nodes:
            node_names = ', '.join(n.name for n in notify_nodes)
            msg = '%s - %s: %s' % (notify_nodes[0].bts_type(), node_names, node_msg)
            try:
                notify(msg, alert)
            except Exception as e:
                log.warning('Failed sending %s notification to %s: %s' % (ntype, node_names, node_msg))
                log.exception(e)
