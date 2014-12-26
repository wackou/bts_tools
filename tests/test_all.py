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

from bts_tools.monitor import StableStateMonitor

def test_stable_state_monitor():
    s = StableStateMonitor(3)

    # check initial conditions
    s.push('online')
    assert s.stable_state() == None
    assert s.just_changed() == False
    s.push('online')
    s.push('online')
    assert s.stable_state() == 'online'
    assert s.just_changed() == False

    # simulate transient state
    s.push('offline')
    assert s.stable_state() == None
    assert s.just_changed() == False
    s.push('online')
    s.push('online')
    s.push('online')
    assert s.stable_state() == 'online'
    assert s.just_changed() == False

    # actual change of state
    s.push('online')
    s.push('online')
    s.push('offline')
    s.push('offline')
    s.push('offline')
    assert s.stable_state() == 'offline'
    assert s.just_changed() == True
    s.push('offline')
    assert s.just_changed() == False
