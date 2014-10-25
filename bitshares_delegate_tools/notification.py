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

from os.path import join, exists
from . import core
import smtplib
import random
import requests
import apnsclient
import logging

log = logging.getLogger(__name__)

def send_email(to, subject, body, bcc=None, replyto=None):
    """Return True if the email could be sent, raise an exception
    otherwise."""
    c = core.config['monitoring']['email']

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
    c = core.config['monitoring']['email']
    send_email(c['recipient'], 'BTS notification', msg)
    log.info('Sent email notification: %s' % msg)


def send_notification_boxcar(msg, alert=False):
    log.debug('Sending notification trough Boxcar: %s' % msg)
    tokens = core.config['monitoring']['boxcar']['tokens']
    for token in tokens:
        requests.post('https://new.boxcar.io/api/notifications',
                      data={'user_credentials': token,
                            'notification[sound]': 'score' if alert else 'no-sound',
                            'notification[title]': msg,
                            'notification[source_name]': 'BTS Tools'})
    log.info('Sent Boxcar notification: %s' % msg)


def send_notification_apns(msg, alert=False):
    """Sends an APNS notification. 'alert' means something wrong is happening,
    otherwise it's just a normal info message."""
    log.debug('Sending notification via APNS: %s' % msg)

    if not core.config['monitoring']['apns']['tokens']:
        log.warning('Cannot send notification: no device tokens configured')
        return

    certfile = join(core.BTS_TOOLS_HOMEDIR, core.config['monitoring']['apns']['cert'])
    if not exists(certfile):
        log.error('Missing certificate file for APNs service: %s' % certfile)
        return

    conn = apnsclient.Session().new_connection('push_sandbox', cert_file=certfile)
    tokens = core.config['monitoring']['apns']['tokens']
    if alert:
        message = apnsclient.Message(tokens,
                                     alert=msg,
                                     sound='base_under_attack_%s.caf' % random.choice(['terran', 'zerg', 'protoss']),
                                     badge=1)
    else:
        message = apnsclient.Message(tokens,
                                     alert=msg,
                                     badge=1)

    # Send the message.
    srv = apnsclient.APNs(conn)
    try:
        res = srv.send(message)
    except:
        log.error('Can\'t connect to APNs, looks like network is down')
    else:
        # Check failures. Check codes in APNs reference docs.
        for token, reason in res.failed.items():
            code, errmsg = reason
            # according to APNs protocol the token reported here
            # is garbage (invalid or empty), stop using and remove it.
            log.error('Device failed: {0}, reason: {1}'.format(token, errmsg))

        # Check failures not related to devices.
        for code, errmsg in res.errors:
            log.error('Error: {}'.format(errmsg))

        # Check if there are tokens that can be retried
        if res.needs_retry():
            # repeat with retry_message or reschedule your task
            log.error('Needs retry...')
            retry_message = res.retry()
            log.error('Did retry: %s' % retry_message)

    log.info('Sent APNS notification: %s' % msg)


def send_notification(nodes, node_msg, alert=False):
    """msg is sent to each node separately"""
    for node in nodes:
        msg = '%s: %s' % (node.name, node_msg)
        if 'email' in node.monitoring:
            try:
                send_notification_email(msg, alert)
            except Exception as e:
                log.warning('Failed sending notification to %s: %s' % (node.name, node_msg))
                log.exception(e)
        if 'apns' in node.monitoring:
            try:
                send_notification_apns(msg, alert)
            except Exception as e:
                log.warning('Failed sending notification to %s: %s' % (node.name, node_msg))
                log.exception(e)
        if 'boxcar' in node.monitoring:
            try:
                send_notification_boxcar(msg, alert)
            except Exception as e:
                log.warning('Failed sending notification to %s: %s' % (node.name, node_msg))
                log.exception(e)
