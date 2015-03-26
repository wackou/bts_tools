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

from datetime import datetime, timedelta
from os.path import join
from .. import core
import dateutil
import logging

log = logging.getLogger(__name__)

BTS_ASSET_IDX = 0       # assert node.blockchain_get_asset(BTS_ASSET_IDX)['symbol'] == 'BTS'
BTS_PRECISION = 100000  # node.blockchain_get_asset(BTS_ASSET_IDX)['precision']


# Used for payroll distribution
def parse_date(date):
    return datetime.datetime.strptime(date, "%Y%m%dT%H%M")


# TODO: move this directly into the BTSProxy class
def get_account_balance(node, account, asset_idx=BTS_ASSET_IDX):
    log.debug('get_account_balance %s' % account)
    # Returns the current balance of the given asset for the given account name
    balances = node.wallet_account_balance(account)  # rpc returns: [['account.name', [[asset_idx, balance]]]]
    if not balances:
        return 0
    for idx, balance in balances[0][1]:
        if idx == asset_idx:
            log.debug('balance: %s' % balance / BTS_PRECISION)
            return balance / BTS_PRECISION  # FIXME: need to divide by asset precision
    return 0


def monitor(node, ctx, cfg):
    if 'payroll' not in node.monitoring or node.type != 'delegate':
        return

    if not ctx.info['wallet_unlocked']:
        log.warning('Cannot perform payroll distribution when wallet is closed or locked')
        return

    log.info('monitoring payroll')
    payday_file = join(core.BTS_TOOLS_HOMEDIR, cfg['payday_file'])
    pay_interval = int(cfg['pay_interval'])

    try:
        with open(payday_file, 'r') as f :
            last_payday = f.read()

        last_payday = last_payday[:10]             # Strip all but first 10 characters
        log.debug('Last payday %s' % last_payday)

        # Calculate when the next payday will occur
        last_payday_date = dateutil.parser.parse(last_payday)

    except OSError:
        last_payday_date = datetime.now() - timedelta(days=2*pay_interval)

    next_payday = last_payday_date + timedelta(days=pay_interval)
    log.debug('Next payday %s' % str(next_payday)[:10])

    now = datetime.now()
    if now <= next_payday:
        # not yet payday!
        return

    try:
        # Get the pay balance available to distribute
        account_info = node.wallet_get_account(node.name)
        pay_balance = account_info['delegate_info']['pay_balance'] / BTS_PRECISION
        log.debug('Balance available to withdraw: %s' % pay_balance)

        # If the delegate account balance is below the minimum resupply it.
        # We need to maintain this to pay feed publishing fees for example.
        # Delegate account balance is different from delegate pay balance.
        minimum_balance = cfg['minimum_balance']
        balance = get_account_balance(node, node.name)
        log.debug('Current balance in delegate account: %s' % balance)
        if balance < minimum_balance:
            resupply = minimum_balance - balance
            if pay_balance > resupply:
                node.wallet_delegate_withdraw_pay(node.name, node.name, resupply)
                pay_balance -= resupply
            else:
                log.warning('Insufficient pay to resupply delegate account. Shortfall: %s' % resupply)

        # Distribute all of the pay_balance based on config.yaml file settings
        if pay_balance > len(cfg['accounts']) : # Leave enough for fees! (1 BTS per distribution account)
            # Get the BTS price per share in USD from the market feed price
            try:
                market = node.blockchain_market_status("USD", "BTS")
                feed_price = float(market.get('current_feed_price'))
                log.info('Current BTS share price in USD is %s' % feed_price)
            except:
                log.warning('Failed to get market status for USD / BTS')
                feed_price = 1 # The value of the payout will be in BTS not USD

            # Distribute the account balance to the accounts listed at the proportions specified
            for a_idx, account in enumerate(cfg['accounts']):
                pay_rate = cfg['pay_rate'][a_idx]
                pay = pay_balance * (pay_rate * 0.01)    # The proportioned amount to pay

                try:
                    node.wallet_delegate_withdraw_pay(node.name, account, pay)   # It's Payday!
                    if feed_price == 1:
                        usd_value = '?'
                    else:
                        usd_value = pay * feed_price
                    log.info('Paid %s BTS (%s USD) to %s' % (pay, usd_value, account))  # Value paid

                    history = node.wallet_account_transaction_history(node.name)  # Get transaction info
                    (xTrxId, timestamp) = (history[0].get('trx_id'), history[0].get('timestamp'))

                    # Log the payroll transaction info TODO: Verify this captures the payment just made
                    transactions_file = join(core.BTS_TOOLS_HOMEDIR, cfg['transactions_file'])
                    with open(transactions_file, 'a') as f:
                        f.write("%s, %s, %s, %s, %s\n" % (timestamp, pay, usd_value, account, xTrxId))

                    # Update the payday file to record when this payout occurred
                    timezone_offset = int(cfg['timezone_offset'])
                    with open(payday_file, 'w') as f:
                        f.write(str((datetime.now() + timedelta(hours=timezone_offset))))

                except Exception as e :
                    log.error('An exception occurred in the payroll distribution:')
                    log.exception(e)
        else :
            log.debug('Balance is below the minimum (%s) for payout' % balance)

    except Exception as e:
        log.error('An exception occurred getting delegate account info:')
        log.exception(e)
