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
from .. import core, feeds, rpcutils
import pendulum
import re
import json
import logging

log = logging.getLogger(__name__)

NAME = 'Bit20'

AVAILABLE_MARKETS = [('BTWTY', 'USD')]

def is_valid_bit20_publication(trx):
    """
    check that the transaction is a valid one, ie:
      - it contains a single operation
      - it is a transfer from 'bittwenty' (1.2.111226) to 'bittwenty.feed' (1.2.126782)

    note: this does not check the contents of the transaction, it only
          authenticates it
    """
    try:
        # we only want a single operation
        if len(trx['op']['op']) != 2:  # (trx_id, content)
            return False

        # authenticates sender and receiver
        trx_metadata = trx['op']['op'][1]
        authorized_accounts = ['1.2.111226',  # bittwenty
                               '1.2.126782']  # bittwenty.feed

        if trx_metadata['from'] not in authorized_accounts:
            log.debug('invalid sender for bit20 publication: {}'.format(json.dumps(trx, indent=4)))
            return False
        if trx_metadata['to'] not in authorized_accounts:
            log.debug('invalid receiver for bit20 publication: {}'.format(json.dumps(trx, indent=4)))
            return False

        return True

    except KeyError:
        # trying to access a non-existent field -> probably looking at something we don't want
        log.warning('invalid transaction for bit20 publication: {}'.format(json.dumps(trx, indent=4)))
        return False


def get_bit20_feed_usd(node):
    # read composition of the index

    # need to import the following key to be able to decrypt memos
    #   import_key "announce" 5KJJNfiSyzsbHoVb81WkHHjaX2vZVQ1Fqq5wE5ro8HWXe6qNFyQ
    if node.type().split('-')[0] != 'bts':
        return
    if not node.is_online():
        log.warning('Wallet is offline, will not be able to read bit20 composition')
        return
    if not node.is_synced():
        log.warning('Client is not synced yet, will not try to read bit20 composition')
        return
    if node.is_locked():
        log.warning('Wallet is locked, will not be able to read bit20 composition')
        return

    bit20 = None  # contains the composition of the feed

    bit20feed = node.get_account_history('bittwenty.feed', 15)

    if not bit20feed:
        BIT20_ANNOUNCE_KEY = '5KJJNfiSyzsbHoVb81WkHHjaX2vZVQ1Fqq5wE5ro8HWXe6qNFyQ'
        announce_key_exists = any(priv == BIT20_ANNOUNCE_KEY for pub, priv in node.dump_private_keys())
        if not announce_key_exists:
            # import the 'announce' key to be able to read the memo publications
            log.info('Importing the "announce" key in the wallet')
            node.import_key('announce', BIT20_ANNOUNCE_KEY)
            # try again
            bit20feed = node.get_account_history('bittwenty.feed', 15)

    # find bit20 composition
    for f in bit20feed:
        if not is_valid_bit20_publication(f):
            log.warning('Hijacking attempt of the bit20 feed? trx: {}'.format(json.dumps(f, indent=4)))
            continue

        if f['memo'].startswith('COMPOSITION'):
            last_updated = re.search('\((.*)\)', f['memo'])
            if last_updated:
                last_updated = pendulum.from_format(last_updated.group(1), '%Y/%m/%d')

            bit20 = json.loads(f['memo'].split(')', maxsplit=1)[1])
            log.debug('Found bit20 composition, last update = {}'.format(last_updated))
            break

    else:
        log.warning('Did not find any bit20 composition in the last {} messages '
                    'to account bittwenty.feed'.format(len(bit20feed)))
        log.warning('Make sure in the following order that:')
        log.warning('  - your wallet is unlocked')
        log.warning('  - your client is synced')
        log.warning('  - if you use the "track-accounts" option, make sure to include 1.2.111226 and 1.2.126782 accounts')
        log.warning('  - the "account_history" plugin is active and that your client is compiled to support it')
        log.warning('  - you have imported the private key needed for reading bittwenty.feed memos: '
                    'import_key "announce" 5KJJNfiSyzsbHoVb81WkHHjaX2vZVQ1Fqq5wE5ro8HWXe6qNFyQ')
        return

    # look for custom market parameters
    for f in bit20feed:
        if not is_valid_bit20_publication(f):
            log.warning('Hijacking attempt of the bit20 feed? trx: {}'.format(json.dumps(f, indent=4)))
            continue

        if f['memo'].startswith('MARKET'):
            # only take the most recent into account
            market_params = json.loads(f['memo'][len('MARKET :: '):])
            log.debug('Got market params for bit20: {}'.format(market_params))
            # FIXME: this affects the global config object
            params = feeds.cfg['bts']['asset_params']
            params['BTWTY'] = {'maintenance_collateral_ratio': market_params['MCR'],
                               'maximum_short_squeeze_ratio': market_params['MSSR'],
                               'core_exchange_factor': params.get('BTWTY', {}).get('core_exchange_factor',
                                                                                   params['default']['core_exchange_factor'])}
            break
    else:
        log.debug('Did not find any custom market parameters in the last {} messages '
                  'to account bittwenty.feed'.format(len(bit20feed)))
        log.debug('Make sure that your wallet is unlocked and you have imported '
                  'the private key needed for reading bittwenty.feed memos: ')
        log.debug('import_key "announce" 5KJJNfiSyzsbHoVb81WkHHjaX2vZVQ1Fqq5wE5ro8HWXe6qNFyQ')

    if len(bit20['data']) < 3:
        log.warning('Not enough assets in bit20 data: {}'.format(bit20['data']))
        return

    bit20_value_cmc = 0
    cmc_missing_assets = []
    bit20_value_cc = 0
    coincap_missing_assets = []
    providers = core.get_plugin_dict('bts_tools.feed_providers')

    try:
        cmc_assets = providers.CoinMarketCap.get_all()
        for bit20asset, qty in bit20['data']:
            try:
                price = cmc_assets.price(bit20asset, 'USD')
                log.debug('CoinMarketcap {} {} at ${} = ${}'.format(qty, bit20asset, price, qty * price))
                bit20_value_cmc += qty * price
            except ValueError as e:
                log.debug('Unknown asset on CMC: {}'.format(bit20asset))
                #log.exception(e)
                cmc_missing_assets.append(bit20asset)

    except Exception as e:
        log.warning('Could not get bit20 assets feed from CoinMarketCap: {}'.format(e))
        cmc_missing_assets = [asset for asset, qty in bit20['data']]

    try:
        coincap_assets = providers.CoinCap.get_all()
        for bit20asset, qty in bit20['data']:
            try:
                price = coincap_assets.price(bit20asset, 'USD')
                #log.debug('CoinCap {} {} at ${} = ${}'.format(qty, bit20asset, price, qty * price))
                bit20_value_cc += qty * price

            except ValueError as e:
                log.debug('Unknown asset on CoinCap: {}'.format(bit20asset))
                #log.exception(e)
                coincap_missing_assets.append(bit20asset)

    except Exception as e:
        log.warning('Could not get bit20 assets feed from CoinCap: {}'.format(e))
        coincap_missing_assets = [asset for asset, qty in bit20['data']]


    bit20_feeds = FeedSet()
    cmc_feed = FeedPrice(bit20_value_cmc, 'BTWTY', 'USD', provider=providers.CoinMarketCap.NAME)
    cc_feed = FeedPrice(bit20_value_cc, 'BTWTY', 'USD', provider=providers.CoinCap.NAME)

    # TODO: simple logic, could do something better here
    # take the feed for the providers that provide a price for all the assets inside the index
    # if none of them can (ie: they all have at least one asset that is not listed), then we
    # take the weighted mean anyway, and hope for the best...
    if not cmc_missing_assets:
        bit20_feeds.append(cmc_feed)
    if not coincap_missing_assets:
        bit20_feeds.append(cc_feed)
    if not bit20_feeds:
        log.warning('No provider could provider feed for all assets:')
        log.warning('- CoinMarketCap missing: {}'.format(cmc_missing_assets))
        log.warning('- CoinCap missing: {}'.format(coincap_missing_assets))
        raise core.NoFeedData('Could not get any BTWTY feed')

    bit20_value = bit20_feeds.price(stddev_tolerance=0.02)
    log.debug('Total value of bit20 asset: ${}'.format(bit20_value))

    return bit20_value


REQUIRES_NODE = True

@check_online_status
@check_market
def get(asset, base, node):
    log.debug('checking feeds for %s/%s at %s' % (asset, base, NAME))

    return FeedPrice(get_bit20_feed_usd(node), asset, base)
