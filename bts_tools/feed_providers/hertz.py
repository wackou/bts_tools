#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# bts_tools - Tools to easily manage the bitshares client
# Copyright (c) 2017 Nicolas Wack <wackou@gmail.com>
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

from . import FeedPrice, check_online_status, check_market, FeedSet
import math
import pendulum
import logging

log = logging.getLogger(__name__)

NAME = 'Hertz'

AVAILABLE_MARKETS = [('HERTZ', 'USD')]


def get_hertz_feed(reference_timestamp, current_timestamp, period_days, phase_days, amplitude):
    """Given the reference timestamp, the current timestamp, the period (in days), the phase (in days), the reference asset value (ie 1.00) and the amplitude (> 0 && < 1), output the current hertz value.
    You can use this for an alternative HERTZ asset!
    """
    hz_reference_timestamp = reference_timestamp  # Retrieving the Bitshares2.0 genesis block timestamp
    hz_period = pendulum.SECONDS_PER_DAY * period_days
    hz_phase = pendulum.SECONDS_PER_DAY * phase_days
    hz_waveform = math.sin(((((current_timestamp - (hz_reference_timestamp + hz_phase))/hz_period) % 1) * hz_period) * ((2*math.pi)/hz_period)) # Only change for an alternative HERTZ ABA.
    hertz_value = 1 + (amplitude * hz_waveform)
    # hertz_value = reference_asset_value + ((amplitude * reference_asset_value) * hz_waveform)
    log.debug('Value of the HERTZ asset in USD: {} USD'.format(hertz_value))
    return hertz_value



@check_online_status
@check_market
def get(asset, base):
    log.debug('checking feeds for %s/%s at %s' % (asset, base, NAME))
    hertz_reference_time = "2015-10-13T14:12:24+00:00"  # Bitshares 2.0 genesis block timestamp
    hertz_reference_timestamp = pendulum.parse(hertz_reference_time).timestamp()
    hertz_current_timestamp = pendulum.now().timestamp()  # Current timestamp for reference within the hertz script
    hertz_amplitude = 0.14  # 14% fluctuation (1% per day)
    hertz_period_days = 28  # 28 days
    hertz_phase_days = 0.908056  # Time offset from genesis till the first wednesday, to set wednesday as the primary Hz day.
    #hertz_reference_asset_price = usd_price

    hertz = get_hertz_feed(hertz_reference_timestamp, hertz_current_timestamp,
                           hertz_period_days, hertz_phase_days,
                           hertz_amplitude)

    return FeedPrice(hertz, asset, base)
